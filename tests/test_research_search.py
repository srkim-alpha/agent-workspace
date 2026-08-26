import os
import sys
import json
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from agents.research_search import SearchAgent
from core.briefing_manager import prepare_daily_briefing_cache, get_morning_briefing, CACHE_FILE

class TestResearchSearch(unittest.TestCase):

    def test_search_agent_research(self):
        agent = SearchAgent()
        res = agent.conduct_research()
        print("\n[Test] SearchAgent research output:")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        self.assertIn("tech_trends", res)
        self.assertIn("monetization_cases", res)
        self.assertIn("korea_market_insight", res)

    def test_pre_caching_and_briefing(self):
        cache_res = prepare_daily_briefing_cache()
        self.assertTrue(os.path.exists(CACHE_FILE))

        report = get_morning_briefing(force_refresh=False)
        print("\n[Test] Cached Briefing Output:\n" + report)
        self.assertIn("모닝 인텔리전스 리포트", report)
        self.assertIn("'서치' 에이전트 선정 글로벌 AI 핵심 트렌드", report)

if __name__ == "__main__":
    unittest.main()
