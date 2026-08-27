import unittest
import sys
import os
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.telegram_secretary import scrape_job_posting_url, command_dashboard, command_cleanup, command_apply

class TestTelegramRouter(unittest.TestCase):

    def test_scrape_job_posting_url_parsing(self):
        """Tests company name extraction logic in scrape_job_posting_url."""
        url = "https://example.com/job/123"
        company_name, full_text = scrape_job_posting_url(url)
        self.assertTrue(isinstance(company_name, str))
        self.assertTrue(isinstance(full_text, str))
        print(f"[Pass] URL Scraping helper returned company: {company_name}")

    def test_command_handlers_exist(self):
        """Verifies that command handlers are callable functions."""
        self.assertTrue(callable(command_apply))
        self.assertTrue(callable(command_cleanup))
        self.assertTrue(callable(command_dashboard))
        print("[Pass] Telegram command handlers (/지원, /정리, /대시보드) verified.")

if __name__ == "__main__":
    unittest.main()
