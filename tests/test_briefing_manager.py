import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.briefing_manager import fetch_verified_ai_news, generate_morning_intelligence_report

class TestBriefingManager(unittest.TestCase):

    def test_fetch_verified_ai_news(self):
        items = fetch_verified_ai_news()
        print(f"\n[Test] Fetched {len(items)} news items:")
        for item in items:
            print(f"- {item['title']} ({item['link']})")
            self.assertIn("http", item["link"])
        self.assertGreater(len(items), 0, "News items should not be empty")

    def test_generate_morning_intelligence_report(self):
        report = generate_morning_intelligence_report()
        print(f"\n[Test] Generated Report:\n{report}")
        self.assertIn("모닝 인텔리전스 리포트", report)
        self.assertIn("오늘", report)
        self.assertTrue("구글 캘린더 일정" in report or "일정" in report)

if __name__ == "__main__":
    unittest.main()
