"""会話履歴の保存(SQLite)。個人利用前提でサーバ側に持ち、端末間で共有する。"""
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
DB_PATH = os.getenv("CHAT_DB", "chats.db")


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS convs (
            id      TEXT PRIMARY KEY,
            title   TEXT NOT NULL,
            updated TEXT NOT NULL,
            msgs    TEXT NOT NULL
        )"""
    )
    return con


def list_convs(limit: int = 100):
    con = _conn()
    try:
        rows = con.execute(
            "SELECT id, title, msgs FROM convs ORDER BY updated DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"id": r[0], "title": r[1], "msgs": json.loads(r[2])} for r in rows]
    finally:
        con.close()


def put(conv_id: str, title: str, msgs) -> None:
    con = _conn()
    try:
        con.execute(
            "INSERT INTO convs (id, title, updated, msgs) VALUES (?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET title=excluded.title, "
            "updated=excluded.updated, msgs=excluded.msgs",
            (conv_id, title, datetime.now(JST).isoformat(timespec="seconds"),
             json.dumps(msgs, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()


def delete(conv_id: str) -> None:
    con = _conn()
    try:
        con.execute("DELETE FROM convs WHERE id=?", (conv_id,))
        con.commit()
    finally:
        con.close()
