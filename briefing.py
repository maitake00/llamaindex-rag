"""朝のブリーフィングをスマホへ通知する(cronから実行)。

  今日の予定 / 期限が近いタスク / 未読メール件数

LLMは使わず事実だけを組み立てる(通知は確実性が最優先のため)。
"""
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

JST = timezone(timedelta(hours=9))


def _calendar_part() -> str:
    try:
        import calendar_tool
        body = calendar_tool.calendar_list(days=1)
    except Exception as e:
        return f"**予定**\n取得失敗: {e}"
    return f"**今日の予定**\n{body}"


def _todo_part() -> str:
    try:
        import todo_tool
        rows = todo_tool.due_soon(hours=48)
        if not rows:
            return "**期限間近のタスク**\nありません"
        lines = [f"- {t} ({todo_tool._fmt_due(d or '')})" for _, t, d in rows]
        return "**期限間近のタスク**\n" + "\n".join(lines)
    except Exception as e:
        return f"**タスク**\n取得失敗: {e}"


def _mail_part() -> str:
    try:
        import google_auth
        parts = []
        for acc in google_auth.ACCOUNTS:
            try:
                svc = google_auth.gmail_service(acc)
                res = svc.users().messages().list(
                    userId="me", q="is:unread", maxResults=50
                ).execute()
                n = len(res.get("messages", []))
                parts.append(f"{acc}: {n}件")
            except Exception as e:
                parts.append(f"{acc}: 取得失敗({type(e).__name__})")
        return "**未読メール**\n" + " / ".join(parts)
    except Exception as e:
        return f"**メール**\n取得失敗: {e}"


def main():
    now = datetime.now(JST)
    body = "\n\n".join([_calendar_part(), _todo_part(), _mail_part()])
    from notify import notify
    ok = notify(body, title=f"おはようございます({now.strftime('%m/%d %a')})", tags="sunrise")
    print("通知しました" if ok else "通知に失敗しました")
    print(body)


if __name__ == "__main__":
    main()
