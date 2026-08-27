import unittest
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from skills.job_application_generator import JobApplicationGenerator

class TestJobApplicationGenerator(unittest.TestCase):

    def setUp(self):
        self.generator = JobApplicationGenerator()
        self.test_company = "종합물류_그래이박스"
        self.test_job = "종합물류기업 SCM 및 4000평 냉장냉동 물류센터 총괄 관리자 채용 (WMS 전산, 입출고 관리, 엑셀 쿼리, 현장관리)"

    def test_01_star_matching(self):
        """Tests if SCM/WMS job posting matches WMS STAR episode as #1."""
        matched = self.generator.match_star_episodes(self.test_job, top_k=3)
        self.assertGreaterEqual(len(matched), 1)
        self.assertEqual(matched[0]["id"], "wms_excel")
        print("[Pass] STAR episode keyword matching test succeeded.")

    def test_02_application_data_generation(self):
        """Tests structure and Ground Truth integrity of generated application data."""
        data = self.generator.generate_application_data(self.test_company, self.test_job)
        self.assertEqual(len(data["full_work_chronology"]), 12)  # 12 Ground Truth work entries
        self.assertLessEqual(len(data["work_chronology"]), 6)  # Filtered key career entries for job posting
        print("[Pass] Application data Ground Truth integrity test succeeded.")

    def test_03_full_pipeline_execution(self):
        """Tests full pipeline: PDF generation, PWA WebApp publishing, and 3-Track archiving."""
        result = self.generator.generate_job_application(self.test_company, self.test_job)
        self.assertTrue(result["pdf_success"])
        self.assertIsNotNone(result["pdf_path"])
        self.assertTrue(os.path.exists(result["pdf_path"]))
        self.assertGreater(os.path.getsize(result["pdf_path"]), 0)
        self.assertIn("https://srkim-alpha.github.io/agent-workspace/applications/", result["web_url"])
        self.assertTrue(os.path.exists(result["archive_path"]))
        self.assertTrue(result.get("telegram_success", False))
        print("[Pass] Full pipeline PDF, WebApp, Archiving, and Telegram notification test succeeded.")

if __name__ == "__main__":
    unittest.main()
