"""Gmail操作(複数アカウント対応)。LLMからツールとして呼ばれる。

安全方針: 送信はしない。返信は「下書き」を作るところまでで、送信は人間が行う。
"""
import base64
from email.mime.text import MIMEText

import google_auth


def _decode_body(payload) -> str:
    """本文(text/plain)を取り出す。無ければHTMLを雑に落として返す。"""
    def walk(part):
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "ignore")
        for sub in part.get("parts", []) or []:
            got = walk(sub)
            if got:
                return got
        return ""

    text = walk(payload)
    if text:
        return text
    if payload.get("body", {}).get("data"):
        raw = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "ignore")
        import re
        return re.sub(r"<[^>]+>", " ", raw)
    return ""


def _headers(msg) -> dict:
    return {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}


def gmail_list(query: str = "is:unread", account: str = "", max_results: int = 10) -> str:
    """メールを検索して一覧する。queryはGmailの検索式(既定は未読)。
    account は使うアカウントのラベル(省略時はメイン)。
    例: query='is:unread', query='from:example.com newer_than:7d'
    """
    try:
        svc = google_auth.gmail_service(account)
        res = svc.users().messages().list(
            userId="me", q=query, maxResults=max(1, min(max_results, 20))
        ).execute()
        ids = [m["id"] for m in res.get("messages", [])]
    except Exception as e:
        return f"メールの取得に失敗しました: {e}"

    if not ids:
        return f"該当するメールはありません(検索: {query})。"

    lines = []
    for mid in ids:
        try:
            msg = svc.users().messages().get(
                userId="me", id=mid,
                format="metadata", metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            h = _headers(msg)
            lines.append(
                f"- [{mid}] {h.get('date','?')[:22]} | {h.get('from','?')}\n"
                f"  件名: {h.get('subject','(件名なし)')}\n"
                f"  概要: {msg.get('snippet','')[:120]}"
            )
        except Exception as e:
            lines.append(f"- [{mid}] 取得失敗: {e}")
    return "\n".join(lines)


def gmail_read(message_id: str, account: str = "") -> str:
    """メールIDを指定して本文を読む。gmail_list で得たIDを使う。"""
    try:
        svc = google_auth.gmail_service(account)
        msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    except Exception as e:
        return f"メールの読み取りに失敗しました: {e}"

    h = _headers(msg)
    body = _decode_body(msg.get("payload", {}))[:4000]
    return (
        f"From: {h.get('from','?')}\nTo: {h.get('to','?')}\n"
        f"Date: {h.get('date','?')}\n件名: {h.get('subject','(件名なし)')}\n\n{body}"
    )


def gmail_draft(to: str, subject: str, body: str, account: str = "") -> str:
    """返信やメールの下書きを作成する(送信はしない)。作成後は本人がGmailで確認して送る。"""
    try:
        svc = google_auth.gmail_service(account)
        mime = MIMEText(body, "plain", "utf-8")
        mime["to"] = to
        mime["subject"] = subject
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        draft = svc.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}
        ).execute()
    except Exception as e:
        return f"下書きの作成に失敗しました: {e}"

    return (
        f"下書きを作成しました(送信はしていません)。\n"
        f"宛先: {to}\n件名: {subject}\n"
        f"Gmailの下書きフォルダで確認して送信してください。ID: {draft.get('id')}"
    )
