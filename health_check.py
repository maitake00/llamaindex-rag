"""秘書が依存しているサービスの稼働確認。ダッシュボード表示用。

各項目は短いタイムアウトで確認する(ダッシュボードの表示を待たせないため)。
"""
import os

import requests

import config


def _ollama():
    try:
        r = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=4)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
        have = lambda x: any(n.split(":")[0] == x.split(":")[0] for n in names)
        missing = [m for m in (config.LLM_MODEL, config.EMBED_MODEL) if not have(m)]
        if missing:
            return False, f"モデル未導入: {', '.join(missing)}"
        return True, f"{len(names)}モデル"
    except Exception as e:
        return False, type(e).__name__


def _reranker():
    try:
        r = requests.post(
            f"{config.XINFERENCE_BASE_URL}/rerank",
            json={"model": config.RERANK_MODEL, "query": "t", "documents": ["a", "b"]},
            timeout=6,
        )
        r.raise_for_status()
        if "results" in r.json():
            return True, config.RERANK_MODEL
        return False, "応答が不正"
    except Exception as e:
        return False, "未起動" if "404" in str(e) else type(e).__name__


def _chroma():
    try:
        import chromadb
        col = chromadb.PersistentClient(path=config.CHROMA_DIR).get_or_create_collection(
            config.COLLECTION
        )
        return True, f"{col.count()}チャンク"
    except Exception as e:
        return False, type(e).__name__


def _google():
    try:
        import google_auth
        ok, ng = [], []
        for acc in google_auth.ACCOUNTS:
            if os.path.exists(google_auth.token_file(acc)):
                ok.append(acc)
            else:
                ng.append(acc)
        if ng:
            return False, f"未認証: {', '.join(ng)}"
        return True, ", ".join(ok)
    except Exception as e:
        return False, type(e).__name__


def _tavily():
    if config.TAVILY_API_KEY:
        return True, "キー設定済み"
    return False, "キー未設定"


def _ntfy():
    url = os.getenv("NTFY_URL", "http://localhost:8082")
    try:
        r = requests.get(f"{url}/v1/health", timeout=4)
        r.raise_for_status()
        return bool(r.json().get("healthy")), "正常" if r.json().get("healthy") else "異常"
    except Exception as e:
        return False, type(e).__name__


CHECKS = [
    ("Ollama (生成/埋め込み)", _ollama),
    ("リランカー (Xinference)", _reranker),
    ("ベクトルDB (Chroma)", _chroma),
    ("Google (予定/メール)", _google),
    ("Web検索 (Tavily)", _tavily),
    ("通知 (ntfy)", _ntfy),
]


def status():
    out = []
    for name, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, type(e).__name__
        out.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    return out
