import os
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
TOKEN_PATH = CONFIG_DIR / "token.json"
SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print("===================================================", flush=True)
    print("🔑 [알파 COO 구글 캘린더 OAuth 1회성 인증 도우미]", flush=True)
    print("===================================================", flush=True)

    if not CREDENTIALS_PATH.exists():
        print(f"\n❌ [오류] OAuth 클라이언트 키 파일이 필요합니다: {CREDENTIALS_PATH}", flush=True)
        return

    print("\n✅ credentials.json 파일 확인 완료!", flush=True)
    print("🚀 구글 캘린더 OAuth 인증 서버를 가동합니다...", flush=True)

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        auth_url, _ = flow.authorization_url(prompt='consent')
        print("\n---------------------------------------------------", flush=True)
        print("🔗 아래 구글 OAuth 인증 URL을 클릭하여 구글 로그인을 완료하세요:", flush=True)
        print(auth_url, flush=True)
        print("---------------------------------------------------\n", flush=True)

        creds = flow.run_local_server(port=0, open_browser=True)
        with open(TOKEN_PATH, 'w', encoding='utf-8') as token_file:
            token_file.write(creds.to_json())
        print("\n===================================================", flush=True)
        print("🎉 [인증 완료] token.json이 성공적으로 생성 및 저장되었습니다!", flush=True)
        print("이제 알파 수석비서가 대표님의 구글 캘린더와 24시간 실시간 연동됩니다. 🚀", flush=True)
        print("===================================================", flush=True)
    except Exception as e:
        print(f"\n❌ OAuth 인증 중 오류 발생: {e}", flush=True)

if __name__ == "__main__":
    main()
