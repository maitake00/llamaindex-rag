"""Googleカレンダー操作。LLMからツールとして呼ばれる。"""
from datetime import datetime, timedelta, timezone

import google_auth

JST = timezone(timedelta(hours=9))
CAL_ID = "primary"


def _fmt(dt_str: str) -> str:
    if not dt_str:
        return "?"
    if len(dt_str) == 10:
        return f"{dt_str}(終日)"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(JST)
        return dt.strftime("%m/%d %H:%M")
    except Exception:
        return dt_str


def calendar_list(days: int = 7) -> str:
    """今日から指定日数ぶんの予定を一覧する。「明日の予定は?」なら days=2。"""
    try:
        svc = google_auth.calendar_service()
        now = datetime.now(JST)
        end = now + timedelta(days=max(1, days))
        res = svc.events().list(
            calendarId=CAL_ID,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=30,
        ).execute()
    except Exception as e:
        return f"カレンダーの取得に失敗しました: {e}"

    items = res.get("items", [])
    if not items:
        return f"今後{days}日間に予定はありません。"

    lines = []
    for ev in items:
        start = ev.get("start", {})
        s = _fmt(start.get("dateTime") or start.get("date", ""))
        title = ev.get("summary", "(件名なし)")
        loc = ev.get("location")
        lines.append(f"- {s} {title}" + (f" @{loc}" if loc else ""))
    return "\n".join(lines)


def calendar_add(title: str, start: str, end: str = "", location: str = "") -> str:
    """予定を追加する。start/end は '2026-08-05T14:00' 形式(日本時間)。endは省略時1時間後。"""
    try:
        s = datetime.fromisoformat(start).replace(tzinfo=JST)
        e = datetime.fromisoformat(end).replace(tzinfo=JST) if end else s + timedelta(hours=1)
    except Exception:
        return "日時の形式が不正です。'2026-08-05T14:00' の形式で指定してください。"

    body = {
        "summary": title,
        "start": {"dateTime": s.isoformat(), "timeZone": "Asia/Tokyo"},
        "end": {"dateTime": e.isoformat(), "timeZone": "Asia/Tokyo"},
    }
    if location:
        body["location"] = location

    try:
        ev = google_auth.calendar_service().events().insert(
            calendarId=CAL_ID, body=body
        ).execute()
    except Exception as e:
        return f"予定の追加に失敗しました: {e}"

    return f"予定を追加しました: {_fmt(s.isoformat())} {title}\n{ev.get('htmlLink', '')}"


def list_events(days: int = 7):
    """予定を構造化して返す(ダッシュボード表示用)。"""
    try:
        svc = google_auth.calendar_service()
        now = datetime.now(JST)
        res = svc.events().list(
            calendarId=CAL_ID,
            timeMin=now.isoformat(),
            timeMax=(now + timedelta(days=max(1, days))).isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=30,
        ).execute()
    except Exception:
        return []

    out = []
    for ev in res.get("items", []):
        start = ev.get("start", {})
        raw = start.get("dateTime") or start.get("date", "")
        out.append({
            "title": ev.get("summary", "(件名なし)"),
            "start": raw,
            "start_text": _fmt(raw),
            "location": ev.get("location", ""),
            "url": ev.get("htmlLink", ""),
        })
    return out
