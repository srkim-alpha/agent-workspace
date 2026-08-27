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
        # Create dummy deployment directories
        self.test_docs_dir = BASE_DIR / "docs" / "applications" / "test_dummy_app"
        self.test_root_dir = BASE_DIR / "applications" / "test_dummy_app"
        self.test_docs_dir.mkdir(parents=True, exist_ok=True)
        self.test_root_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.test_docs_dir / "index.html", "w", encoding="utf-8") as f:
            f.write("<h1>Test</h1>")

        # Create dummy PDF in data/outputs
        self.outputs_dir = BASE_DIR / "data" / "outputs"
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_path = self.outputs_dir / "test_dummy_app_김승률_지원서.pdf"
        with open(self.pdf_path, "w", encoding="utf-8") as f:
            f.write("PDF Ground Truth Content")

    def test_delete_application_general_cleanup(self):
        """Tests that delete_application cleans test/temp folders and preserves local PDF."""
        result = self.generator.delete_application("테스트")
        self.assertTrue(result["success"])
        self.assertFalse(self.test_docs_dir.exists())
        self.assertFalse(self.test_root_dir.exists())
        # Verify non-destructive principle: local PDF must still exist
        self.assertTrue(self.pdf_path.exists())
        print(f"[Pass] Delete application test folder removed, local PDF preserved: {result}")

    def tearDown(self):
        shutil.rmtree(self.test_docs_dir, ignore_errors=True)
        shutil.rmtree(self.test_root_dir, ignore_errors=True)
        if self.pdf_path.exists():
            os.remove(self.pdf_path)

if __name__ == "__main__":
    unittest.main()
