import os
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(r"c:\agent-workspace\config\.env")
load_dotenv(r"c:\agent-workspace\.env")

bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID", "8392524393")

pdf_path = Path(r"c:\agent-workspace\data\outputs\종합물류_그래이박스_김승률_지원서.pdf")
web_url = "https://srkim-alpha.github.io/agent-workspace/applications/종합물류_그래이박스/"

text = f"""📄 [맞춤형 입사지원서 생성 완료]
• 지원 기업: 종합물류_그래이박스
• 모바일 웹앱 링크: {web_url}

※ 첨부된 서류 제출용 A4 PDF를 확인해 주십시오."""

msg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

res_msg = requests.post(msg_url, data={"chat_id": chat_id, "text": text})
print("Text msg response status:", res_msg.status_code, res_msg.json().get("ok"))

if pdf_path.exists():
    with open(pdf_path, "rb") as f:
        res_doc = requests.post(
            doc_url,
            data={"chat_id": chat_id, "caption": "📄 종합물류_그래이박스 서류제출용 A4 PDF"},
            files={"document": ("종합물류_그래이박스_김승률_지원서.pdf", f, "application/pdf")}
        )
        print("Document response status:", res_doc.status_code, res_doc.json().get("ok"))
else:
    print("PDF path does not exist:", pdf_path)
