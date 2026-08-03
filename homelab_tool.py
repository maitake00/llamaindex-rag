"""ホームラボ(Docker/ホスト)の状態確認と操作。LLMからツールとして呼ばれる。

安全方針:
  許可する操作は restart / start / stop のみ。
  削除系(rm, down, prune, volume)は復旧できないため、ツールとして提供しない。
"""
import os
import shutil
import subprocess

DOCKER = shutil.which("docker") or "/usr/bin/docker"
ALLOWED = {"restart", "start", "stop"}
TIMEOUT = 30


def _run(args, timeout=TIMEOUT):
    r = subprocess.run(
        args, capture_output=True, text=True, timeout=timeout
    )  # shell=False なので注入の心配なし
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return r.stdout.strip()


def _containers() -> str:
    out = _run([DOCKER, "ps", "-a", "--format",
                "{{.Names}}\t{{.State}}\t{{.Status}}"])
    if not out:
        return "コンテナがありません。"
    lines = []
    for row in out.split("\n"):
        parts = row.split("\t")
        if len(parts) < 3:
            continue
        name, state, status = parts[0], parts[1], parts[2]
        mark = "正常" if state == "running" else f"【{state}】"
        lines.append(f"- {name}: {mark} ({status})")
    return "\n".join(lines)


def _resources() -> str:
    lines = []

    # ディスク
    try:
        t, u, f = shutil.disk_usage("/")
        lines.append(f"ディスク: {u//2**30}GB使用 / {t//2**30}GB中 (空き {f//2**30}GB)")
    except Exception:
        pass

    # メモリ
    try:
        info = {}
        for l in open("/proc/meminfo"):
            k, _, v = l.partition(":")
            info[k] = int(v.split()[0])
        total = info["MemTotal"] // 1024
        avail = info["MemAvailable"] // 1024
        lines.append(f"メモリ: {total - avail}MB使用 / {total}MB中 (空き {avail}MB)")
    except Exception:
        pass

    # CPU負荷
    try:
        l1, l5, l15 = os.getloadavg()
        lines.append(f"CPU負荷: {l1:.2f} (5分 {l5:.2f} / 15分 {l15:.2f})")
    except Exception:
        pass

    # GPU
    try:
        g = _run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                  "--format=csv,noheader,nounits"], timeout=10)
        for row in g.split("\n"):
            name, used, tot, util = [x.strip() for x in row.split(",")]
            lines.append(f"GPU {name}: VRAM {used}/{tot}MB, 使用率 {util}%")
    except Exception:
        lines.append("GPU: 情報を取得できません")

    # コンテナ別リソース(上位5件)
    try:
        st = _run([DOCKER, "stats", "--no-stream", "--format",
                   "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"], timeout=25)
        rows = [r.split("\t") for r in st.split("\n") if r]
        rows = [r for r in rows if len(r) >= 3][:5]
        if rows:
            lines.append("コンテナ別: " + " / ".join(f"{r[0]} CPU{r[1]} MEM{r[2]}" for r in rows))
    except Exception:
        pass

    return "\n".join(lines) or "情報を取得できませんでした。"


def homelab(action: str, container: str = "", lines: int = 50) -> str:
    """自分のサーバー(ホームラボ)の状態確認と操作を行う。

    action='status'    … 全コンテナの稼働状況を一覧
    action='resources' … ディスク/メモリ/CPU/GPUの使用状況
    action='logs'      … container のログ末尾を見る(linesで行数指定)
    action='restart'   … container を再起動する
    action='start'     … container を起動する
    action='stop'      … container を停止する
    """
    action = (action or "").strip().lower()

    try:
        if action == "status":
            return _containers()
        if action in ("resources", "resource", "system"):
            return _resources()

        if action in ("logs", "log"):
            if not container:
                return "コンテナ名(container)を指定してください。"
            out = _run([DOCKER, "logs", "--tail", str(max(1, min(lines, 200))), container])
            return out[-3000:] or "(ログは空です)"

        if action in ALLOWED:
            if not container:
                return "コンテナ名(container)を指定してください。"
            _run([DOCKER, action, container], timeout=90)
            state = _run([DOCKER, "ps", "-a", "--filter", f"name=^{container}$",
                          "--format", "{{.Status}}"])
            return f"{container} を {action} しました。現在: {state or '不明'}"

        return ("action は status / resources / logs / restart / start / stop の"
                "いずれかを指定してください。削除や down は安全のため実行できません。")

    except subprocess.TimeoutExpired:
        return f"操作がタイムアウトしました({action} {container})。"
    except Exception as e:
        return f"操作に失敗しました: {e}"
