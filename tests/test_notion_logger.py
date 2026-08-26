import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.notion_logger import create_2track_notion_archive, restore_recent_context
from core.agent_engine import AgentEngine

class TestNotionLogger(unittest.TestCase):

    def test_2track_archive_creation(self):
        res = create_2track_notion_archive(
            chapter_title="단위 테스트 챕터",
            pain_points="• 에러 테스트 1",
            solution_ideas="• 해결 아이디어 1",
            applied_prompts="• 적용 프롬프트 1",
            monetization_insights="• 수익화 아이디어 1",
            raw_logs="[Test Raw Log Data]"
        )
        self.assertIsNotNone(res)
        self.assertIn("summary_file", res)
        self.assertTrue(os.path.exists(res["summary_file"]))

    def test_context_restoration(self):
        ctx = restore_recent_context()
        print("\n[Test] Restored Context:\n" + ctx)
        self.assertIn("🧠", ctx)
        self.assertIn("Chapter", ctx)

    def test_agent_engine_day_end_routine(self):
        engine = AgentEngine()
        success, report = engine.perform_day_end_cleanup()
        print("\n[Test] Day-End Routine Report:\n" + report)
        self.assertTrue(success)
        self.assertIn("🧹 [마감 및 자산화 완료]", report)

if __name__ == "__main__":
    unittest.main()
