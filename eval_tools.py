"""ツール選択の精度を測る。

秘書に質問を投げ、期待したツールが呼ばれたかを判定する。
機能追加の前後で実行すれば、劣化しているかが数字で分かる。

  python eval_tools.py
"""
import json
import os
import re
import subprocess
import time

from dotenv import load_dotenv

load_dotenv()
API = "http://localhost:8000/v1/chat/completions"
KEY = os.getenv("API_KEY", "")

# (質問, 期待するツール。None は「道具を使わないのが正解」)
CASES = [
    ("監視は何で行っている？", "search_documents"),
    ("確率統計の模擬問題の制限時間は？", "search_documents"),
    ("今週の予定を教えて", "calendar_list"),
    ("明日の15時に打ち合わせを入れて", "calendar_add"),
    ("未読メールを教えて", "gmail_list"),
    ("レポート提出を金曜18時期限でタスクに追加して", "todo"),
    ("今やることは何がある？", "todo"),
    ("Ollamaの最新バージョンを調べて", "search_web"),
    ("コンテナの状態を教えて", "homelab"),
    ("ディスクの空き容量は？", "homelab"),
    ("最近のアプリの使い方の傾向は？", "life_stats"),
    ("https://example.com を資料に追加して", "ingest_url"),
    ("こんにちは", None),
    ("ありがとう、助かりました", None),
]


def _called_tools(since: str):
    """journalctl から [agent] の行を読み、呼ばれたツール名を返す。"""
    out = subprocess.run(
        ["journalctl", "-u", "rag-api", "--since", since, "--no-pager"],
        capture_output=True, text=True,
    ).stdout
    return re.findall(r"\[agent\] (\w+)\(", out)


def ask(q: str) -> str:
    r = subprocess.run(
        ["curl", "-s", API, "-H", f"Authorization: Bearer {KEY}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"model": "secretary",
                           "messages": [{"role": "user", "content": q}]})],
        capture_output=True, text=True, timeout=300,
    ).stdout
    try:
        return json.loads(r)["choices"][0]["message"]["content"]
    except Exception:
        return "(応答の取得に失敗)"


def main():
    ok = 0
    print(f"{'結果':<4} {'質問':<34} {'期待':<18} 実際")
    print("-" * 90)
    for q, expected in CASES:
        mark = time.strftime("%Y-%m-%d %H:%M:%S")
        time.sleep(1)
        ask(q)
        time.sleep(1)
        called = _called_tools(mark)

        if expected is None:
            good = len(called) == 0
        else:
            good = expected in called

        ok += good
        print(f"{'○' if good else '×':<4} {q[:32]:<34} "
              f"{str(expected):<18} {','.join(called) or '(なし)'}")

    print("-" * 90)
    print(f"正解 {ok}/{len(CASES)}  ({ok / len(CASES) * 100:.0f}%)")


if __name__ == "__main__":
    main()
