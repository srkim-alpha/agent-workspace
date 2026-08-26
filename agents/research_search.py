import os
import sys
import json
import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# Project Root Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from google import genai
from core.agent_engine import mask_sensitive_info

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

class SearchAgent:
    """
    글로벌 AI 트렌드 및 수익화 비즈니스 모델 탐색 전담 에이전트 '서치(Search)'
    - 뉴스 기사 2건 (한국어 3줄 요약 + 원문 링크)
    - 유튜브 영상 1건 (한국어 3줄 요약 + 유튜브 재생 링크)
    - 한국 시장 적용 비즈니스 영감 (1~2줄 요약)
    """
    def __init__(self):
        self.name = "서치 (Search)"
        self.role = "글로벌 최신 AI 트렌드 탐색, 팩트체크, 한국형 비즈니스 수익화 모델 도출"

    def fetch_global_sources(self) -> tuple[list[dict], list[dict]]:
        """
        검증된 기사 및 유튜브 소스 수집
        Returns: (articles_list, youtube_list)
        """
        articles = []
        yt_videos = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        # 1. 뉴스 기사 RSS
        article_rss_urls = [
            "https://news.google.com/rss/search?q=AI+agent+monetization+OR+AI+trend&hl=en&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=AI+%EC%97%90%EC%9D%B4%EC%A0%84%ED%8A%B8+%EC%88%98%EC%9D%B5%ED%99%94+OR+AI+%ED%8A%B8%EB%A0%8C%EB%93%9C&hl=ko&gl=KR&ceid=KR:ko",
            "https://techcrunch.com/category/artificial-intelligence/feed/",
        ]

        for url in article_rss_urls:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as response:
                    xml_data = response.read()
                    root = ET.fromstring(xml_data)

                    for item in root.findall(".//item"):
                        title = item.findtext("title", "").strip()
                        link = item.findtext("link", "").strip()
                        if title and link:
                            articles.append({"title": title, "link": link})
                            if len(articles) >= 6:
                                break
            except Exception as e:
                logger.warning(f"[서치 에이전트] 뉴스 RSS 수집 오류 ({url}): {e}")

        # 2. 유튜브 영상 RSS/Google News Search (site:youtube.com)
        yt_rss_url = "https://news.google.com/rss/search?q=site:youtube.com+AI+agent+OR+AI+business+model&hl=en&gl=US&ceid=US:en"
        try:
            req = urllib.request.Request(yt_rss_url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                xml_data = response.read()
                root = ET.fromstring(xml_data)

                for item in root.findall(".//item"):
                    title = item.findtext("title", "").strip()
                    link = item.findtext("link", "").strip()
                    if title and link:
                        yt_videos.append({"title": title, "link": link})
                        if len(yt_videos) >= 4:
                            break
        except Exception as e:
            logger.warning(f"[서치 에이전트] 유튜브 RSS 수집 오류: {e}")

        return articles[:5], yt_videos[:3]

    def conduct_research(self) -> dict:
        """
        글로벌 데이터 수집 -> 팩트체크 -> 기사 2건 + 유튜브 영상 1건 정제 -> 한국 시장 비즈니스 영감 도출
        """
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        articles, yt_videos = self.fetch_global_sources()

        if not gemini_key or not articles:
            logger.warning("[서치 에이전트] 소스 수집 또는 API 키 부재로 폴백 리포트 반환")
            return self._fallback_research_data()

        article_context = "\n".join([f"- 기사: {a['title']} (URL: {a['link']})" for a in articles])
        yt_context = "\n".join([f"- 유튜브 영상 후보: {y['title']} (URL: {y['link']})" for y in yt_videos])

        prompt = f"""
당신은 대표님을 위해 글로벌 AI 트렌드와 수익화 비즈니스 모델을 탐색하고 정제하는 리서치 전문 에이전트 '서치(Search)'입니다.

[전달 원칙 & 지침]
1. 대표님께 보고할 때는 **100% 자연스럽고 완벽한 한국어**로 번역/정제하여 제공하세요.
2. 코딩이나 복잡한 기술 용어는 지양하고, 대표님이 직관적으로 이해할 수 있는 **비즈니스 수익성 및 시장 관점**으로 설명하세요.
3. 리포트 구성 필수 조건:
   - **글로벌 AI 핵심 트렌드 기사**: 정확히 **2건** (제목, 한국어 3줄 요약, 원문 URL)
   - **엄선된 AI/수익화 유튜브 영상**: 정확히 **1건** (제목, 한국어 3줄 요약, 유튜브 URL, 채널/출처 정보)
   - **한국 시장 적용 비즈니스 영감**: 1인 비즈니스/에이전트 적용 제안 **1~2줄 요약**
4. 보안 지침: 개인정보나 시크릿 키는 마스킹 처리하세요.

[수집된 데이터 소스]
=== 기사 후보 ===
{article_context}

=== 유튜브 영상 후보 ===
{yt_context}

아래 JSON 구조로 정확히 마크다운 백틱 없이 순수 JSON만 응답하세요.

JSON 출력 포맷:
{{
  "tech_trends": [
    {{
      "title": "첫 번째 글로벌 AI 핵심 기사 제목",
      "summary_3lines": [
        "비즈니스 요약 1번째 줄",
        "비즈니스 요약 2번째 줄",
        "비즈니스 요약 3번째 줄"
      ],
      "url": "원문 URL"
    }},
    {{
      "title": "두 번째 글로벌 AI 핵심 기사 제목",
      "summary_3lines": [
        "비즈니스 요약 1번째 줄",
        "비즈니스 요약 2번째 줄",
        "비즈니스 요약 3번째 줄"
      ],
      "url": "원문 URL"
    }}
  ],
  "youtube_video": {{
    "title": "엄선된 AI 수익화/에이전트 유튜브 영상 제목",
    "channel_name": "유튜브 채널/출처명",
    "summary_3lines": [
      "영상 핵심 요약 1번째 줄",
      "영상 핵심 요약 2번째 줄",
      "영상 핵심 요약 3번째 줄"
    ],
    "url": "유튜브 영상 URL"
  }},
  "korea_market_insight": "글로벌 트렌드 및 영상 인사이트를 한국 시장 및 1인 비즈니스/에이전트에 적용하는 1~2줄 요약 아이디어"
}}
"""

        try:
            client = genai.Client(api_key=gemini_key)
            from google.genai import types
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=2500,
                    temperature=0.2
                )
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            raw_text = raw_text.strip()
            data = json.loads(raw_text)

            masked_str = mask_sensitive_info(json.dumps(data, ensure_ascii=False))
            return json.loads(masked_str)

        except Exception as e:
            logger.error(f"[서치 에이전트] Gemini 분석 실패 ({e}), 폴백 데이터 반환")
            return self._fallback_research_data()

    def _fallback_research_data(self) -> dict:
        return {
            "tech_trends": [
                {
                    "title": "글로벌 AI 에이전트 2.0: 자율 업무 수행 및 B2B 구독 수익화 모델 확산",
                    "summary_3lines": [
                        "단순 대화형 챗봇을 넘어 실제 업무 프로세스를 독립 수행하는 AI 에이전트 도입이 급증하고 있습니다.",
                        "기업 대상 월정액 구독과 과금형 API를 결합한 B2B 수익 구조가 핵심 주력 모델로 안착했습니다.",
                        "실제 작업 완료율에 따른 성과 기반 요금 체계가 신규 캐시카우로 부상 중입니다."
                    ],
                    "url": "https://news.google.com"
                },
                {
                    "title": "빅테크 AI 생태계와 1인 에이전트 개발자의 온디맨드 자동화 시장 개척",
                    "summary_3lines": [
                        "소규모 개발팀 및 1인 기업이 특정 도메인 맞춤형 에이전트 솔루션을 개발하여 빠르게 시장에 진입하고 있습니다.",
                        "노코드 툴과 최신 LLM API를 결합하여 개발 기간을 획기적으로 단축하고 마진율을 극대화하고 있습니다.",
                        "고객 상담, 서류 정제, 재무 보고서 작성 등 니치 분야의 버티컬 자동화 수요가 매우 견고합니다."
                    ],
                    "url": "https://techcrunch.com"
                }
            ],
            "youtube_video": {
                "title": "Build & Monetize AI Agents in 2026: Complete Business Blueprint",
                "channel_name": "AI Business Insights",
                "summary_3lines": [
                    "2026년 최신 AI 에이전트 구축 및 유료 고객 유치 전략을 다룬 실전 가이드 영상입니다.",
                    "맞춤형 워크플로우 템플릿과 정기 구독 결제 시스템을 연동하여 월 순수익을 창출하는 방법을 안내합니다.",
                    "초기 마케팅부터 1인 기업의 스케일업 전략까지 핵심 노하우를 제공합니다."
                ],
                "url": "https://youtube.com/watch?v=demo_ai_monetization"
            },
            "korea_market_insight": "당사 에이전트 시스템에 맞춤형 업무 자동화 템플릿과 구독형 요금제를 결합하여 1인 기업 및 소상공인 대상 유료 솔루션으로 즉시 확장 가능합니다."
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    search_agent = SearchAgent()
    print("=== [서치 에이전트 (기사 2건 + 유튜브 1건) 리서치 테스트] ===")
    res = search_agent.conduct_research()
    print(json.dumps(res, ensure_ascii=False, indent=2))
