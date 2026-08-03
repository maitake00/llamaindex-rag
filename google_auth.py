"""Google API の認証(カレンダー / Gmail 共通、複数アカウント対応)。

アカウントごとに token_<ラベル>.json を持つ。
  python auth_setup.py main    → token_main.json
  python auth_setup.py work    → token_work.json

credentials.json(OAuthクライアント)は全アカウントで共用できる。
"""
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# カレンダーは読み書き、メールは読み取りと下書き作成まで。
# 安全のため「送信」スコープは要求しない(送信は自分の手で行う)。
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")

# 使うアカウントのラベル一覧(先頭がメイン)。.env で "main,work" のように指定。
ACCOUNTS = [a.strip() for a in os.getenv("GOOGLE_ACCOUNTS", "main").split(",") if a.strip()]
MAIN_ACCOUNT = ACCOUNTS[0]


def token_file(account: str) -> str:
    return f"token_{account}.json"


def get_credentials(account: str = "", interactive: bool = False) -> Credentials:
    account = account or MAIN_ACCOUNT
    path = token_file(account)

    creds = None
    if os.path.exists(path):
        creds = Credentials.from_authorized_user_file(path, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(path, "w") as f:
            f.write(creds.to_json())
        return creds

    if not interactive:
        raise RuntimeError(
            f"アカウント '{account}' の認証が未設定です。"
            f"`python auth_setup.py {account}` を一度実行してください。"
        )

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=8765, open_browser=False)
    with open(path, "w") as f:
        f.write(creds.to_json())
    return creds


def calendar_service(account: str = ""):
    return build("calendar", "v3", credentials=get_credentials(account), cache_discovery=False)


def gmail_service(account: str = ""):
    return build("gmail", "v1", credentials=get_credentials(account), cache_discovery=False)
