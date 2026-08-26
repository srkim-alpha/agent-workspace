import os
import sys
import time
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from skills.smart_digest import generate_smart_digest, is_youtube_url


class TestSmartDigest(unittest.TestCase):

    def test_youtube_url_detection(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_youtube_url("https://youtu.be/jNQXAC9IVRw"))
        self.assertFalse(is_youtube_url("https://en.wikipedia.org/wiki/Artificial_intelligence"))

    def test_youtube_digest_generation(self):
        """
        Standalone Unit Test for YouTube Video URL.
        Verifies title retrieval, transcript/metadata extraction, and 3-part structured insight generation.
        """
        youtube_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

        start_time = time.perf_counter()
        res = generate_smart_digest(youtube_url)
        elapsed_sec = time.perf_counter() - start_time

        print("\n" + "=" * 60)
        print("🧪 [Unit Test: YouTube Smart Digest Test]")
        print(f"URL          : {res['url']}")
        print(f"Title        : {res['title']}")
        print(f"Content Type : {res['content_type']}")
        print(f"Caption Found: {res['caption_found']}")
        print(f"Elapsed Time : {elapsed_sec:.2f} seconds")
        print("-" * 60)
        print(f"Generated Digest:\n{res['digest_text']}")
        print("=" * 60)

        self.assertTrue(res["success"])
        self.assertEqual(res["content_type"], "YouTube")
        self.assertIsNotNone(res["title"])
        self.assertIn("한 줄 핵심 결론", res["digest_text"])
        self.assertIn("3대 핵심 인사이트", res["digest_text"])
        self.assertIn("실행 액션 플랜", res["digest_text"])


if __name__ == "__main__":
    unittest.main()
