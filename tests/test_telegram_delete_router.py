import unittest
import sys
import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from skills.job_application_generator import JobApplicationGenerator

class TestTelegramDeleteRouterPrecision(unittest.TestCase):

    def setUp(self):
        self.generator = JobApplicationGenerator()
        
        self.geo_docs = BASE_DIR / "docs" / "applications" / "geo_young"
        self.geo_root = BASE_DIR / "applications" / "geo_young"
        self.gray_docs = BASE_DIR / "docs" / "applications" / "graybox"
        self.gray_root = BASE_DIR / "applications" / "graybox"
        
        for d in [self.geo_docs, self.geo_root, self.gray_docs, self.gray_root]:
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "index.html", "w", encoding="utf-8") as f:
                f.write("<h1>Test</h1>")

        self.outputs_dir = BASE_DIR / "data" / "outputs"
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_path = self.outputs_dir / "geo_young_김승률_지원서.pdf"
        with open(self.pdf_path, "w", encoding="utf-8") as f:
            f.write("PDF Ground Truth Content")

    def test_precision_target_delete(self):
        """Tests that '그래이박스 지워' extracts target_keyword '그래이박스' and deletes only graybox."""
        result = self.generator.delete_application("그래이박스 지워")
        self.assertTrue(result["success"])
        self.assertFalse(result["is_all"])
        self.assertEqual(result["target_keyword"], "그래이박스")
        self.assertFalse(self.gray_docs.exists())
        self.assertTrue(self.geo_docs.exists())  # geo_young preserved!
        self.assertTrue(self.pdf_path.exists())   # PDF preserved
        print(f"[Pass] Precision target delete verified: {result}")

    def test_precision_all_delete(self):
        """Tests that '/정리' or '다 지워' triggers all delete mode."""
        result = self.generator.delete_application("다 지워")
        self.assertTrue(result["success"])
        self.assertTrue(result["is_all"])
        self.assertFalse(self.geo_docs.exists())
        self.assertFalse(self.gray_docs.exists())
        self.assertTrue(self.pdf_path.exists())   # PDF preserved
        print(f"[Pass] Precision all delete verified: {result}")

    def tearDown(self):
        for d in [self.geo_docs, self.geo_root, self.gray_docs, self.gray_root]:
            shutil.rmtree(d, ignore_errors=True)
        if self.pdf_path.exists():
            os.remove(self.pdf_path)

if __name__ == "__main__":
    unittest.main()
