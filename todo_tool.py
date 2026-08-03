"""ToDo管理(SQLite)。LLMからツールとして呼ばれる。

外部サービスに依存せず、期限つきタスクを確実に保持する。
リマインド(Phase4)もこのDBを見る。
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
DB_PATH = os.getenv("TODO_DB", "tasks.db")


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS todos (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            title   TEXT NOT NULL,
            due     TEXT,
            done    INTEGER NOT NULL DEFAULT 0,
            created TEXT NOT NULL
        )"""
    )
    return con


def _fmt_due(due: str) -> str:
    if not due:
        return "期限なし"
    try:
        d = datetime.fromisoformat(due).replace(tzinfo=JST)
        left = (d - datetime.now(JST)).days
        mark = "【期限切れ】" if left < 0 else ("【今日】" if left == 0 else f"(あと{left}日)")
        return f"{d.strftime('%m/%d %H:%M')} {mark}"
    except Exception:
        return due


def todo(action: str, title: str = "", task_id: int = 0, due: str = "") -> str:
    """ToDoを管理する。
    action='add'  … タスクを追加(title必須、dueは'2026-08-10T18:00'形式で任意)
    action='list' … 未完了のタスクを一覧(期限が近い順)
    action='done' … タスクを完了にする(task_id必須。IDはlistで確認)
    """
    action = (action or "").strip().lower()
    con = _conn()
    try:
        if action == "add":
            if not title:
                return "タスクの内容(title)が必要です。"
            now = datetime.now(JST).isoformat(timespec="minutes")
            cur = con.execute(
                "INSERT INTO todos (title, due, created) VALUES (?,?,?)",
                (title, due or None, now),
            )
            con.commit()
            return f"タスクを追加しました(ID {cur.lastrowid}): {title} / {_fmt_due(due)}"

        if action == "list":
            rows = con.execute(
                "SELECT id, title, due FROM todos WHERE done=0 "
                "ORDER BY (due IS NULL), due ASC"
            ).fetchall()
            if not rows:
                return "未完了のタスクはありません。"
            return "\n".join(f"- [{r[0]}] {r[1]} / {_fmt_due(r[2] or '')}" for r in rows)

        if action == "done":
            if not task_id:
                return "完了にするタスクのID(task_id)が必要です。listで確認してください。"
            cur = con.execute("UPDATE todos SET done=1 WHERE id=? AND done=0", (task_id,))
            con.commit()
            if cur.rowcount == 0:
                return f"ID {task_id} の未完了タスクが見つかりません。"
            return f"タスク {task_id} を完了にしました。"

        return "actionは 'add' / 'list' / 'done' のいずれかを指定してください。"
    except Exception as e:
        return f"タスク操作に失敗しました: {e}"
    finally:
        con.close()


def due_soon(hours: int = 24):
    """期限が迫った未完了タスクを返す(リマインド用。LLMツールではない)。"""
    limit = (datetime.now(JST) + timedelta(hours=hours)).isoformat(timespec="minutes")
    con = _conn()
    try:
        return con.execute(
            "SELECT id, title, due FROM todos WHERE done=0 AND due IS NOT NULL "
            "AND due <= ? ORDER BY due ASC",
            (limit,),
        ).fetchall()
    finally:
        con.close()


def list_open():
    """未完了タスクを構造化して返す(ダッシュボード表示用)。"""
    con = _conn()
    try:
        rows = con.execute(
            "SELECT id, title, due FROM todos WHERE done=0 "
            "ORDER BY (due IS NULL), due ASC"
        ).fetchall()
        return [
            {"id": r[0], "title": r[1], "due": r[2] or "", "due_text": _fmt_due(r[2] or "")}
            for r in rows
        ]
    finally:
        con.close()
