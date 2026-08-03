"""Google認証の初回セットアップ。アカウントごとに一度ずつ実行する。

  python auth_setup.py main
  python auth_setup.py work
"""
import sys

import google_auth

if __name__ == "__main__":
    account = sys.argv[1] if len(sys.argv) > 1 else google_auth.MAIN_ACCOUNT
    print(f"アカウント '{account}' を認証します。")
    print("下に表示されるURLをブラウザで開き、目的のGoogleアカウントを選んで許可してください。\n")

    google_auth.get_credentials(account=account, interactive=True)
    print(f"\n認証成功: {google_auth.token_file(account)} を作成しました。")

    try:
        profile = google_auth.gmail_service(account).users().getProfile(userId="me").execute()
        print(f"メールアドレス: {profile.get('emailAddress')}")
    except Exception as e:
        print(f"確認に失敗: {e}")
