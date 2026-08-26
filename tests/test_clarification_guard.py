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

from core.interaction_guard import check_ambiguity


class TestClarificationGuard(unittest.TestCase):

    def test_case_1_ambiguous_video_recommendation(self):
        """
        Test Case 1: "유튜브 영상 추천해줘"
        Expected: is_ambiguous is True, returns structured choices, latency < 2.0 seconds.
        """
        user_input = "유튜브 영상 추천해줘"
        
        start = time.perf_counter()
        res = check_ambiguity(user_input)
        elapsed_sec = time.perf_counter() - start

        print("\n" + "=" * 60)
        print("🧪 [Test Case 1: Ambiguous Query Test]")
        print(f"Input   : '{user_input}'")
        print(f"Latency : {elapsed_sec * 1000:.3f} ms (SLA < 2000 ms)")
        print(f"Ambiguous: {res['is_ambiguous']}")
        print(f"Reason  : {res['reason']}")
        print(f"Options Message:\n{res['clarification_message']}")
        print("=" * 60)

        self.assertTrue(res["is_ambiguous"])
        self.assertLess(elapsed_sec, 2.0)
        self.assertIsNotNone(res["clarification_message"])
        self.assertIn("1️⃣", res["clarification_message"])
        self.assertIn("2️⃣", res["clarification_message"])
        self.assertIn("3️⃣", res["clarification_message"])
        self.assertIn("4️⃣", res["clarification_message"])

    def test_case_2_specific_search_query(self):
        """
        Test Case 2: "2026 AI 에이전트 트렌드 유튜브 검색해줘"
        Expected: is_ambiguous is False, specific topic detected, passes to search pipeline.
        """
        user_input = "2026 AI 에이전트 트렌드 유튜브 검색해줘"

        start = time.perf_counter()
        res = check_ambiguity(user_input)
        elapsed_sec = time.perf_counter() - start

        print("\n" + "=" * 60)
        print("🧪 [Test Case 2: Specific Search Query Test]")
        print(f"Input   : '{user_input}'")
        print(f"Latency : {elapsed_sec * 1000:.3f} ms (SLA < 2000 ms)")
        print(f"Ambiguous: {res['is_ambiguous']}")
        print(f"Reason  : {res['reason']}")
        print("=" * 60)

        self.assertFalse(res["is_ambiguous"])
        self.assertLess(elapsed_sec, 2.0)
        self.assertIsNone(res["clarification_message"])


if __name__ == "__main__":
    unittest.main()
