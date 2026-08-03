"""ntfy へのプッシュ通知。"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

NTFY_URL = os.getenv("NTFY_URL", "http://localhost:8082")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")


def notify(message: str, title: str = "秘書", tags: str = "calendar", priority: str = "default") -> bool:
    if not NTFY_TOPIC:
        print("[notify] NTFY_TOPIC が未設定です")
        return False
    try:
        r = requests.post(
            f"{NTFY_URL}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Tags": tags,
                "Priority": priority,
                "Markdown": "yes",
            },
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[notify] 送信失敗: {e}")
        return False
