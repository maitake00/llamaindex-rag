"""音声合成(VOICEVOX)。秘書の回答を日本語で読み上げる。"""
import os
import re

import requests

BASE = os.getenv("VOICEVOX_URL", "http://localhost:50021")
SPEAKER = int(os.getenv("VOICEVOX_SPEAKER", "3"))  # 3 = ずんだもん(ノーマル)
TIMEOUT = 60
MAX_CHARS = 600


def _clean(text: str) -> str:
    """読み上げに不要な記法(コードブロック・記号)を落とす。"""
    text = re.sub(r"```.*?```", "、コードは省略します。", text, flags=re.S)
    text = re.sub(r"https?://\S+", "リンク", text)
    text = re.sub(r"[*_`#>\-\[\]|]", "", text)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text[:MAX_CHARS]


def synth(text: str, speaker: int = 0) -> bytes:
    """テキストを読み上げ音声(wav)にする。"""
    spk = speaker or SPEAKER
    body = _clean(text)
    if not body:
        raise ValueError("読み上げる内容がありません")

    q = requests.post(
        f"{BASE}/audio_query", params={"text": body, "speaker": spk}, timeout=TIMEOUT
    )
    q.raise_for_status()

    r = requests.post(
        f"{BASE}/synthesis", params={"speaker": spk},
        json=q.json(), headers={"Content-Type": "application/json"}, timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.content


def speakers():
    """使える話者の一覧(id と名前)。"""
    r = requests.get(f"{BASE}/speakers", timeout=20)
    r.raise_for_status()
    out = []
    for s in r.json():
        for st in s.get("styles", []):
            out.append({"id": st["id"], "name": f"{s['name']}({st['name']})"})
    return out
