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


class TestSmartDigestFallbackGuard(unittest.TestCase):

    def test_youtube_url_detection(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_youtube_url("https://youtu.be/jNQXAC9IVRw"))
        self.assertFalse(is_youtube_url("https://en.wikipedia.org/wiki/Artificial_intelligence"))

    def test_case_1_captioned_video(self):
        """
        Test Case 1: Captioned Knowledge/News Video
        URL: https://www.youtube.com/watch?v=aircAruvnKk (3Blue1Brown Neural Networks)
        Expected: Captions extracted, 3-part structured insight generated accurately.
        """
        youtube_url = "https://www.youtube.com/watch?v=0PT5c1z3LL8"

        start_time = time.perf_counter()
        res = generate_smart_digest(youtube_url)
        elapsed_sec = time.perf_counter() - start_time

        print("\n" + "=" * 60)
        print("🧪 [Test Case 1: Captioned Knowledge Video Test]")
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
        self.assertFalse(res.get("fallback_triggered", False))
        self.assertIn("한 줄 핵심 결론", res["digest_text"])
        self.assertIn("3대 핵심 인사이트", res["digest_text"])
        self.assertIn("실행 액션 플랜", res["digest_text"])

    def test_case_2_non_captioned_short_video_fallback_guard(self):
        """
        Test Case 2: Non-captioned Short Video (Me at the zoo)
        URL: https://www.youtube.com/watch?v=jNQXAC9IVRw
        Expected: Fallback guard triggered (fallback_triggered=True), returns clean notice message without hallucination.
        """
        youtube_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

        start_time = time.perf_counter()
        res = generate_smart_digest(youtube_url)
        elapsed_sec = time.perf_counter() - start_time

        print("\n" + "=" * 60)
        print("🧪 [Test Case 2: Fallback Guard Test (Non-captioned Short Video)]")
        print(f"URL          : {res['url']}")
        print(f"Title        : {res['title']}")
        print(f"Content Type : {res['content_type']}")
        print(f"Caption Found: {res['caption_found']}")
        print(f"Fallback     : {res.get('fallback_triggered', False)}")
        print(f"Elapsed Time : {elapsed_sec:.2f} seconds")
        print("-" * 60)
        print(f"Returned Message:\n{res['digest_text']}")
        print("=" * 60)

        self.assertTrue(res["success"])
        self.assertEqual(res["content_type"], "YouTube")
        self.assertFalse(res["caption_found"])
        self.assertTrue(res.get("fallback_triggered", False))
        self.assertIn("자막 및 상세 설명이 없어 요약이 불가능한 영상입니다", res["digest_text"])


if __name__ == "__main__":
    unittest.main()
