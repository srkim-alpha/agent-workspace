import os
import sys
import unittest
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, "config", ".env"))

from core.notion_logger import create_daily_briefing_page
from core.agent_engine import tool_notion


class TestNotionPremiumBriefing(unittest.TestCase):

    def test_create_daily_briefing_page_direct(self):
        res = create_daily_briefing_page(
            title="[테스트] 프리미엄 UI 브리핑 (2026-08-25)",
            summary="💡 대표님, 구글 뉴스 주요 헤드라인 캡처 및 내일 일정 2건 수집을 완수하였습니다.",
            calendar_text="• 10:00 AM - 11:00 AM: 주간 아키텍처 점검 회의\n• 14:00 PM - 15:30 PM: 글로벌 AI 트렌드 및 Notion 연동 세미나",
            web_capture_info={
                "url": "https://news.google.com",
                "screenshot_path": "data/temp_screenshots/google_news_20260825.png"
            },
            raw_log="[2026-08-25 21:35:00] ReAct Orchestrator executed tool_web_browse -> tool_calendar -> tool_notion successfully."
        )
        print("\n=== Direct create_daily_briefing_page Result ===")
        print("Title:", res.get("title"))
        print("Notion URL:", res.get("notion_url"))
        self.assertIsNotNone(res.get("notion_url"))

    def test_tool_notion_briefing(self):
        msg = tool_notion(
            action="briefing",
            title="[테스트] tool_notion 브리핑 연동 (2026-08-25)",
            summary="💡 ReAct 오케스트레이터를 통한 자동 노션 프리미엄 UI 적재 검증",
            calendar_text="• 09:00 AM - 팀 모닝 스탠드업\n• 16:00 PM - 사업화 전략 피드백",
            web_capture_info={
                "url": "https://news.naver.com",
                "screenshot_path": "data/temp_screenshots/naver_news_20260825.png"
            },
            content="Full execution log snapshot for tool_notion integration."
        )
        print("\n=== tool_notion Result ===")
        print(msg)
        self.assertIn("✅ 노션 프리미엄 UI 브리핑 저장 성공", msg)
        self.assertIn("URL:", msg)


if __name__ == "__main__":
    unittest.main()
