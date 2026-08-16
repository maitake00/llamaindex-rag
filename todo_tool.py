"""ToDo管理(Google Tasks)。スマホの標準アプリからも見える。

注意: Google Tasks の期限は「日付」までで、時刻は保持されない。
時刻まで管理したい予定は、あわせてカレンダーに登録する。
"""
from datetime import datetime, timedelta, timezone

import google_auth

JST = timezone(timedelta(hours=9))
LIST = "@default"


def _svc():
    return google_auth.tasks_service()


def _to_rfc(due: str) -> str:
    """'2026-08-10T18:00' → Google Tasks の due 形式(UTC・日付のみ有効)。"""
    d = datetime.fromisoformat(due).replace(tzinfo=JST)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT00:00:00.000Z")


def _fmt_due(due: str) -> str:
    if not due:
        return "期限なし"
    try:
        d = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(JST)
        left = (d.date() - datetime.now(JST).date()).days
        mark = "【期限切れ】" if left < 0 else ("【今日】" if left == 0 else f"(あと{left}日)")
        return f"{d.strftime('%m/%d')} {mark}"
    except Exception:
        return due


def _open_tasks():
    r = _svc().tasks().list(
        tasklist=LIST, showCompleted=False, maxResults=100
    ).execute()
    items = [t for t in r.get("items", []) if t.get("status") != "completed"]
    return sorted(items, key=lambda t: (not t.get("due"), t.get("due", "")))


def todo(action: str, title: str = "", task_id: str = "", due: str = "") -> str:
    """ToDoを管理する(Google Tasksと同期)。
    action='add'  … タスクを追加(title必須、dueは'2026-08-10T18:00'形式で任意)
    action='list' … 未完了のタスクを一覧(期限が近い順)
    action='done' … タスクを完了にする(task_id必須。IDはlistで確認)
    """
    action = (action or "").strip().lower()
    try:
        if action == "add":
            if not title:
                return "タスクの内容(title)が必要です。"
            body = {"title": title}
            if due:
                try:
                    body["due"] = _to_rfc(due)
                except Exception:
                    return "日時の形式が不正です。'2026-08-10T18:00' の形式で指定してください。"
            t = _svc().tasks().insert(tasklist=LIST, body=body).execute()
            msg = f"タスクを追加しました(ID {t['id']}): {title} / {_fmt_due(t.get('due',''))}"
            if due:
                try:
                    import calendar_tool
                    calendar_tool.calendar_add(f"[タスク] {title}", due)
                    msg += " / カレンダーにも追加しました"
                except Exception as e:
                    msg += f" (カレンダー登録は失敗: {e})"
            return msg

        if action == "list":
            items = _open_tasks()
            if not items:
                return "未完了のタスクはありません。"
            return "\n".join(
                f"- [{t['id']}] {t.get('title','(無題)')} / {_fmt_due(t.get('due',''))}"
                for t in items)

        if action == "done":
            if not task_id:
                return "完了にするタスクのID(task_id)が必要です。listで確認してください。"
            _svc().tasks().patch(
                tasklist=LIST, task=task_id, body={"status": "completed"}).execute()
            return f"タスク {task_id} を完了にしました。"

        return "actionは 'add' / 'list' / 'done' のいずれかを指定してください。"
    except Exception as e:
        return f"タスク操作に失敗しました: {e}"


def due_soon(hours: int = 24):
    """期限が迫った未完了タスク(リマインド用)。"""
    limit = (datetime.now(JST) + timedelta(hours=hours)).date()
    out = []
    try:
        for t in _open_tasks():
            d = t.get("due")
            if not d:
                continue
            day = datetime.fromisoformat(d.replace("Z", "+00:00")).astimezone(JST).date()
            if day <= limit:
                out.append((t["id"], t.get("title", "(無題)"), d))
    except Exception:
        pass
    return out


def list_open():
    """未完了タスクを構造化して返す(ダッシュボード表示用)。"""
    try:
        return [{"id": t["id"], "title": t.get("title", "(無題)"),
                 "due": t.get("due", ""), "due_text": _fmt_due(t.get("due", ""))}
                for t in _open_tasks()]
    except Exception:
        return []
