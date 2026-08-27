import unittest
import sys
import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from skills.job_application_generator import JobApplicationGenerator

class TestTelegramDeleteRouter(unittest.TestCase):

    def setUp(self):
        self.generator = JobApplicationGenerator()
        
        # Create dummy deployment directories for two targets
        self.geo_docs = BASE_DIR / "docs" / "applications" / "geo_young"
        self.geo_root = BASE_DIR / "applications" / "geo_young"
        self.gray_docs = BASE_DIR / "docs" / "applications" / "graybox"
        self.gray_root = BASE_DIR / "applications" / "graybox"
        
        for d in [self.geo_docs, self.geo_root, self.gray_docs, self.gray_root]:
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "index.html", "w", encoding="utf-8") as f:
                f.write("<h1>Test</h1>")

        # Create dummy PDF in data/outputs
        self.outputs_dir = BASE_DIR / "data" / "outputs"
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_path = self.outputs_dir / "geo_young_김승률_지원서.pdf"
        with open(self.pdf_path, "w", encoding="utf-8") as f:
            f.write("PDF Ground Truth Content")

    def test_target_delete_application(self):
        """Tests target deletion (e.g. '지오영'). Only geo_young folder should be removed, graybox remains, PDF preserved."""
        result = self.generator.delete_application("지오영")
        self.assertTrue(result["success"])
        self.assertFalse(result["is_all"])
        self.assertFalse(self.geo_docs.exists())
        self.assertFalse(self.geo_root.exists())
        self.assertTrue(self.gray_docs.exists())  # graybox should still exist!
        self.assertTrue(self.pdf_path.exists())   # PDF preserved
        print(f"[Pass] Target delete verified: {result}")

    def test_all_delete_application(self):
        """Tests all deletion (e.g. '다 지워'). All deployment folders removed, PDF preserved."""
        result = self.generator.delete_application("다 지워")
        self.assertTrue(result["success"])
        self.assertTrue(result["is_all"])
        self.assertFalse(self.geo_docs.exists())
        self.assertFalse(self.gray_docs.exists())
        self.assertTrue(self.pdf_path.exists())   # PDF preserved
        print(f"[Pass] All delete verified: {result}")

    def tearDown(self):
        for d in [self.geo_docs, self.geo_root, self.gray_docs, self.gray_root]:
            shutil.rmtree(d, ignore_errors=True)
        if self.pdf_path.exists():
            os.remove(self.pdf_path)

if __name__ == "__main__":
    unittest.main()
