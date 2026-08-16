"""端末から送られる行動データの蓄積と集計。すべて自分のサーバー内で完結する。"""
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
DB_PATH = os.getenv("TELEMETRY_DB", "telemetry.db")


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL, kind TEXT NOT NULL,
        name TEXT, value REAL, extra TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ts ON events(ts)")
    return con


def record(kind: str, items: list) -> int:
    """items: [{"ts":..., "name":..., "value":..., "extra":{...}}, ...]"""
    con = _conn()
    try:
        rows = [(i.get("ts") or datetime.now(JST).isoformat(timespec="minutes"),
                 kind, i.get("name", ""), float(i.get("value") or 0),
                 json.dumps(i.get("extra") or {}, ensure_ascii=False))
                for i in items]
        con.executemany(
            "INSERT INTO events (ts, kind, name, value, extra) VALUES (?,?,?,?,?)", rows)
        con.commit()
        return len(rows)
    finally:
        con.close()


def summary(days: int = 7) -> str:
    """秘書が参照する集計。時間帯ごとの傾向を出す。"""
    since = (datetime.now(JST) - timedelta(days=days)).isoformat()
    con = _conn()
    try:
        out = [f"直近{days}日間の記録"]

        rows = con.execute(
            "SELECT name, SUM(value)/60.0 FROM events WHERE kind='app_usage' AND ts>=? "
            "GROUP BY name ORDER BY 2 DESC LIMIT 8", (since,)).fetchall()
        if rows:
            out.append("よく使うアプリ(時間): " +
                       ", ".join(f"{n} {v:.1f}h" for n, v in rows))

        rows = con.execute(
            "SELECT substr(ts,12,2) AS h, SUM(value)/60.0 FROM events "
            "WHERE kind='app_usage' AND ts>=? GROUP BY h ORDER BY 2 DESC LIMIT 5",
            (since,)).fetchall()
        if rows:
            out.append("利用が多い時間帯: " +
                       ", ".join(f"{h}時台 {v:.1f}h" for h, v in rows))

        for kind, label, unit in [("steps", "歩数", "歩"), ("sleep", "睡眠", "時間"),
                                  ("heart_rate", "心拍", "bpm")]:
            r = con.execute(
                "SELECT AVG(value), COUNT(*) FROM events WHERE kind=? AND ts>=?",
                (kind, since)).fetchone()
            if r and r[1]:
                out.append(f"{label}の平均: {r[0]:.1f}{unit} ({r[1]}件)")

        r = con.execute(
            "SELECT COUNT(*) FROM events WHERE kind='notification' AND ts>=?",
            (since,)).fetchone()
        if r and r[0]:
            out.append(f"通知の件数: {r[0]}件")

        return "\n".join(out) if len(out) > 1 else "まだ十分なデータがありません。"
    finally:
        con.close()


def life_stats(days: int = 7) -> str:
    """自分の生活・行動の記録(アプリ利用、歩数、睡眠、通知量など)を確認する。"""
    return summary(days)
