import os
import sys
import json
import logging
import asyncio
import re
import functools
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone, timedelta

# Project Root Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from google import genai
from core.calendar_manager import (
    get_today_events_summary,
    get_specific_day_events_summary,
    get_week_events_summary,
    parse_and_create_event_with_gemini,
    delete_event_with_gemini,
    update_event_with_gemini,
)
from core.resilience_manager import (
    safe_gemini_call,
    execute_tool_with_resilience,
    sanitize_user_facing_error,
)

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

FAST_MODEL = "gemini-3.6-flash"
DEEP_MODEL = "gemini-3.6-flash"

LATEST_ARTIFACTS = []

def mask_sensitive_info(text: str) -> str:
    """
    정규식 기반 민감 정보(API Key, 주민등록번호, 카드번호 등) 자동 마스킹
    """
    if not text:
        return text

    # 1. API Keys (Gemini, Telegram Bot Token, OpenAI, etc.)
    text = re.sub(r'(?:AIzaSy[A-Za-z0-9_-]{30,}|AQ\.[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}|[0-9]{8,10}:AA[A-Za-z0-9_-]{30,})', '****[SECRET_MASKED]****', text)

    # 2. 주민등록번호 (YYMMDD-[1-4]XXXXXX)
    text = re.sub(r'\b\d{6}-[1-4]\d{6}\b', '******-*******', text)

    # 3. 신용카드 번호 (16자리)
    text = re.sub(r'\b(?:\d{4}[-\s]?){3}\d{4}\b', '****-****-****-****', text)

    return text

def _run_capture_page_process(url: str, keyword: str):
    from tools.browser_controller import capture_page
    return capture_page(url=url, keyword=keyword, headless=True)

def _run_shopping_search_process(keyword: str):
    from tools.shopping_search import search_naver_shopping
    return search_naver_shopping(keyword=keyword, headless=True)

# ==========================================
# Standardized Tool Registry for ReAct Orchestrator
# ==========================================

def tool_calendar(action: str, query: str = "today", event_text: str = "") -> str:
    """
    구글 캘린더 일정을 조회, 생성, 수정, 삭제합니다.
    Args:
        action: 'query' (조회), 'create' (등록), 'update' (수정), 'delete' (삭제) 중 하나
        query: 조회 시 'today' (오늘), 'tomorrow' (내일), 'week' (이번주), '모레' 등
        event_text: 등록/수정/삭제 대상 일정 설명 텍스트
    """
    try:
        if action == "query":
            if query in ["tomorrow", "내일"]:
                return get_specific_day_events_summary(1, "내일")
            elif query in ["week", "이번주"]:
                return get_week_events_summary()
            elif query in ["모레"]:
                return get_specific_day_events_summary(2, "모레")
            else:
                return get_today_events_summary()
        elif action == "create":
            success, msg = parse_and_create_event_with_gemini(event_text or query)
            return msg
        elif action == "update":
            success, msg = update_event_with_gemini(event_text or query)
            return msg
        elif action == "delete":
            success, msg = delete_event_with_gemini(event_text or query)
            return msg
        return "캘린더 작업 실패: 알 수 없는 action"
    except Exception as e:
        return f"캘린더 연동 오류: {e}"

def tool_web_browse(url: str = "https://news.google.com", keyword: str = "") -> dict:
    """
    일반 웹페이지 또는 구글 뉴스 등에 접속하여 페이지 타이틀과 화면 스크린샷 캡처본을 반환합니다.
    주의: 단순 영상 추천, 콘텐츠 추천, 트렌드 알려줘 등의 요청 시에는 이 도구를 사용하지 마세요. (Playwright 실행 차단)
    Args:
        url: 접속할 웹 사이트 URL 또는 사이트명 (예: 'https://news.google.com', '구글 뉴스', '네이버 메인')
        keyword: 검색창에 검색할 키워드 (선택 사항)
    """
    try:
        check_str = f"{url} {keyword}".lower()
        rec_keywords = ["추천", "영상", "유튜브", "볼만한", "찾아줘", "알려줘", "추천해줘"]
        if any(kw in check_str for kw in rec_keywords):
            logger.warning(f"🚫 [tool_web_browse Blocked] Recommendation query detected ('{check_str}'). Playwright launch aborted.")
            return {
                "success": True,
                "blocked": True,
                "title": "단순 추천 대화형 전환 완료",
                "url": url,
                "result": "단순 추천 요청으로 무거운 웹 브라우저(Playwright) 실행이 차단되고 1초 대화형 추천 모드로 자동 전환되었습니다."
            }

        alias_map = {
            "구글 뉴스": "https://news.google.com",
            "구글뉴스": "https://news.google.com",
            "google news": "https://news.google.com",
            "네이버 뉴스": "https://news.naver.com",
            "네이버뉴스": "https://news.naver.com",
            "네이버 메인": "https://www.naver.com",
            "네이버": "https://www.naver.com",
            "구글 메인": "https://www.google.com",
            "구글": "https://www.google.com"
        }
        target_url = alias_map.get(url, url)
        if not target_url.startswith("http://") and not target_url.startswith("https://"):
            target_url = f"https://www.google.com/search?q={target_url}"
            
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_capture_page_process, target_url, keyword)
            res = future.result(timeout=15)
            
        if isinstance(res, dict) and res.get("screenshot_path") and os.path.exists(res.get("screenshot_path")):
            LATEST_ARTIFACTS.append(res["screenshot_path"])
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}

def tool_shopping_search(keyword: str) -> dict:
    """
    네이버 쇼핑에서 상품 가격 및 상위 상품 정보를 수집하고 화면을 캡처합니다.
    Args:
        keyword: 쇼핑 검색 키워드 (예: 'RTX 5080', '기계식 키보드')
    """
    try:
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_shopping_search_process, keyword)
            res = future.result(timeout=45)
            
        if isinstance(res, dict) and res.get("screenshot_path") and os.path.exists(res.get("screenshot_path")):
            LATEST_ARTIFACTS.append(res["screenshot_path"])
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}

def tool_research(topic: str = "AI trend") -> str:
    """
    글로벌 AI 트렌드 및 수익화 비즈니스 모델을 심층 탐색하거나 아침 모닝 인텔리전스 리포트를 생성합니다.
    Args:
        topic: 리서치 주제 키워드
    """
    try:
        from agents.research_search import SearchAgent
        agent = SearchAgent()
        data = agent.conduct_research()
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"리서치 오류: {e}"

def tool_notion(
    action: str = "briefing",
    title: str = "알파 일일 브리핑",
    content: str = "",
    summary: str = "",
    calendar_text: str = "",
    web_capture_info: dict = None
) -> str:
    """
    대표님의 지시사항, 캡처 내용, 일정 정보 등을 노션 DB 또는 2-Track 지식 아카이브에 프리미엄 UI 메모/브리핑으로 저장합니다.
    Args:
        action: 'briefing' (일일 브리핑/메모 프리미엄 UI 적재) 또는 'archive' (일일 마감 자산화)
        title: 노션 페이지 제목
        content: 메모/브리핑 본문 텍스트 또는 raw 로그
        summary: 핵심 1~2줄 요약 (Callout 블록용)
        calendar_text: 구글 캘린더 조회 내용 (주요 일정 현황 블록용)
        web_capture_info: 웹 캡처 결과 정보 dict {'url': ..., 'screenshot_path': ...}
    """
    try:
        from core.notion_logger import create_2track_notion_archive, create_daily_briefing_page
        if action == "archive":
            entry = create_2track_notion_archive(chapter_title=title, raw_logs=content)
            url_info = f" (URL: {entry.get('notion_url')})" if entry.get('notion_url') else ""
            return f"✅ 노션 2-Track 지식 자산화 완료: {entry.get('date')} - {entry.get('chapter')}{url_info}"
        else:
            entry = create_daily_briefing_page(
                title=title,
                summary=summary or (content[:150] if content else "일일 브리핑 수집 완수"),
                calendar_text=calendar_text,
                web_capture_info=web_capture_info,
                raw_log=content
            )
            url_info = f" (URL: {entry.get('notion_url')})" if entry.get('notion_url') else ""
            return f"✅ 노션 프리미엄 UI 브리핑 저장 성공: {title}{url_info}"
    except Exception as e:
        return f"노션 저장 오류: {e}"

def tool_universal_search(query: str = "유튜브 추천 영상") -> str:
    """
    YouTube 영상 추천, 최신 트렌드, 날씨, 일반 상식 등 개별 전용 도구가 없는 모든 검색 및 조회를 단일 탐색으로 1~2초 내에 즉각 처리합니다.
    Args:
        query: 검색/추천 요청 주제 키워드 (예: '쉬면서 볼만한 유튜브 영상 추천', '오늘 서울 날씨', 'AI 최신 트렌드')
    """
    try:
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        query_encoded = urllib.parse.quote(query)
        yt_search_url = f"https://www.youtube.com/results?search_query={query_encoded}"
        google_search_url = f"https://www.google.com/search?q={query_encoded}"

        snippets = []
        rss_url = f"https://news.google.com/rss/search?q={query_encoded}&hl=ko&gl=KR&ceid=KR:ko"
        try:
            req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                root = ET.fromstring(resp.read())
                for item in root.findall(".//item")[:3]:
                    t = item.findtext("title", "").strip()
                    l = item.findtext("link", "").strip()
                    if t and l:
                        snippets.append(f"- [{t}]({l})")
        except Exception:
            pass

        if gemini_key:
            client = genai.Client(api_key=gemini_key)
            from google.genai import types
            prompt = (
                f"당신은 정보 탐색 및 수집 전문 서치 어시스턴트입니다.\n"
                f"사용자의 질의: '{query}'\n"
                f"수집된 실시간 RSS 소스:\n" + ("\n".join(snippets) if snippets else "없음") + "\n\n"
                f"다음 요구사항에 맞춰 품격 있고 정중하게 답변을 작성하세요:\n"
                f"1. 유튜브/영상 관련 질의인 경우 대표적인 추천 콘텐츠 3가지와 아래 유튜브 검색 직접 링크를 반드시 포함하세요:\n"
                f"   ▶ 유튜브 검색 바로가기: {yt_search_url}\n"
                f"2. 일반 트렌드/날씨/정보 질의인 경우 핵심 요약 3줄과 관련 구글 검색 링크({google_search_url})를 포함하세요.\n"
                f"3. 가독성 높은 마크다운 형식으로 작성하세요."
            )
            response = client.models.generate_content(
                model=FAST_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=1000
                )
            )
            if response and response.text:
                return response.text.strip()

        return (
            f"🔍 **[Universal Search 탐색 결과]**\n"
            f"• **검색 주제**: `{query}`\n"
            f"• **유튜브 검색 바로가기**: {yt_search_url}\n"
            f"• **구글 검색 바로가기**: {google_search_url}\n\n"
            f"위 링크를 통해 실시간 영상 및 최신 소식을 즉시 확인하실 수 있습니다."
        )
    except Exception as e:
        return f"범용 검색 처리 중 오류: {e}"

TOOL_MAP = {
    "tool_calendar": tool_calendar,
    "tool_universal_search": tool_universal_search,
    "tool_web_browse": tool_web_browse,
    "tool_shopping_search": tool_shopping_search,
    "tool_research": tool_research,
    "tool_notion": tool_notion
}


class AgentEngine:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.logs_dir = os.path.join(PROJECT_ROOT, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)

    # ==========================================
    # Dynamic Model Tiering: Complexity Classifier
    # ==========================================
    async def classify_complexity(self, user_text: str) -> tuple[str, str]:
        """
        Gemini Flash 기반 동적 작업 복잡도 분류기
        Returns: (complexity: "LOW" | "HIGH", reasoning: str)
        """
        if not self.gemini_key:
            return "LOW", "No API Key"

        prompt = f"""
당신은 AI 에이전트 라우팅을 위한 작업 복잡도 분류기입니다.
사용자의 지시사항을 분석하여 단일/경량 작업(LOW)인지 복합/다단계/고추론 작업(HIGH)인지 분류하세요.

[분류 기준]
1. LOW (단순 작업):
   - 단일 캘린더 일정 조회/등록/수정/삭제 (예: "내일 일정 알려줘")
   - 단일 웹페이지 접속 및 캡처 (예: "구글 뉴스 캡처해줘")
   - 단일 쇼핑 최저가 검색 (예: "RTX 5080 가격 확인해줘")
   - 단순 인사 및 1단계 질의응답 (예: "안녕", "오늘 날씨 어때?")

2. HIGH (복합 작업):
   - 2개 이상의 서로 다른 도구를 연속 실행(Chaining)해야 하는 지시 (예: "내일 일정 확인하고, 구글 뉴스 메인 캡처해서 노션에 메모해 줘")
   - 심층 비즈니스/기술 리서치 및 장문 종합 분석 요구
   - 다단계 논리적 추론 및 종합 전략 기획

사용자 지시사항: "{user_text}"

순수 JSON 포맷으로 응답하세요:
{{
  "complexity": "LOW" 또는 "HIGH",
  "reasoning": "판단 이유 1줄 요약"
}}
"""
        try:
            client = genai.Client(api_key=self.gemini_key)
            from google.genai import types
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=FAST_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            data = json.loads(response.text.strip())
            comp = data.get("complexity", "LOW").upper()
            reason = data.get("reasoning", "")
            logger.info(f"[Complexity Classifier] Result: {comp} | Reason: {reason}")
            return ("HIGH" if comp == "HIGH" else "LOW"), reason
        except Exception as e:
            logger.warning(f"[Complexity Classifier] Fallback to LOW due to error: {e}")
            return "LOW", str(e)

    # ==========================================
    # Track 1: Local Daily Context Logging
    # ==========================================
    def _get_daily_log_path() -> str:
        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        return os.path.join(PROJECT_ROOT, "logs", f"daily_context_{today_str}.md")

    def append_daily_context(self, user_text: str, intent: str, result_summary: str):
        try:
            log_path = AgentEngine._get_daily_log_path()
            time_str = datetime.now(KST).strftime("%H:%M:%S")
            masked_user = mask_sensitive_info(user_text)
            masked_result = mask_sensitive_info(result_summary)
            log_entry = (
                f"### [{time_str}] [{intent}]\n"
                f"- **지시**: {masked_user}\n"
                f"- **결과**: {masked_result}\n\n"
            )
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Local daily context logging failed: {e}")

    def load_today_context(self) -> str:
        try:
            log_path = AgentEngine._get_daily_log_path()
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    return f.read()[-1500:]
        except Exception as e:
            logger.error(f"Loading daily context failed: {e}")
        return ""

    # ==========================================
    # Track 2: Notion DB Logging (Fallback-safe)
    # ==========================================
    def log_to_notion_task_db(self, action_title: str, status: str, details: str):
        try:
            masked_title = mask_sensitive_info(action_title)
            masked_details = mask_sensitive_info(details)
            logger.info(f"[Track 2 Notion Log] {masked_title} | Status: {status} | Details: {masked_details}")
        except Exception as e:
            logger.warning(f"Notion logging skipped: {e}")

    # ==========================================
    # Day-End Routine & Workspace Cleanup
    # ==========================================
    def perform_day_end_cleanup(self) -> tuple[bool, str, list[str]]:
        cleaned_count = 0
        try:
            from core.notion_logger import create_2track_notion_archive
            create_2track_notion_archive(
                raw_logs=self.load_today_context()
            )

            import shutil
            target_exts = [".ogg", ".wav", ".mp3", ".m4a"]

            for root, dirs, files in os.walk(PROJECT_ROOT):
                for d in list(dirs):
                    if d in ["__pycache__", ".pytest_cache"]:
                        dir_path = os.path.join(root, d)
                        try:
                            shutil.rmtree(dir_path)
                            dirs.remove(d)
                            cleaned_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to remove dir {dir_path}: {e}")

                for file in files:
                    if file.startswith("temp_") and any(file.endswith(ext) for ext in target_exts):
                        file_path = os.path.join(root, file)
                        try:
                            os.remove(file_path)
                            cleaned_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to remove file {file_path}: {e}")

            tmp_dir = os.path.join(PROJECT_ROOT, "tmp")
            if os.path.exists(tmp_dir):
                for file in os.listdir(tmp_dir):
                    if file.startswith("temp_") or file.endswith(".ogg") or file.endswith(".wav"):
                        file_path = os.path.join(tmp_dir, file)
                        try:
                            os.remove(file_path)
                            cleaned_count += 1
                        except Exception:
                            pass

            report = "🧹 [마감 및 자산화 완료] 오늘의 개발 아카이브 동기화 및 워크스페이스 정리를 완료했습니다. 오늘 하루도 고생 많으셨습니다, 대표님!"
            self.append_daily_context("오늘 작업 끝", "DAY_END", report)
            return True, report, []

        except Exception as e:
            logger.error(f"Day-End Cleanup error: {e}")
            return False, f"⚠️ 마감 처리 중 오류가 발생했습니다: {e}", []

    # ==========================================
    # ReAct Execution Loop (Dynamic Model Tiering + 60s Circuit Breaker)
    # ==========================================
    async def process_instruction(self, user_text: str, pre_classified_complexity: tuple[str, str] = None) -> tuple[bool, str, list[str]]:
        """
        Dynamic Model Tiering ReAct Engine
        Returns: (success: bool, final_report: str, artifacts: list[str])
        """
        if any(kw in user_text.lower() for kw in ["오늘 작업 끝", "퇴근", "업무 마감해줘", "작업 마감"]):
            return self.perform_day_end_cleanup()

        # 1. Complexity Classification & Model Selection
        if pre_classified_complexity:
            complexity, reasoning = pre_classified_complexity
        else:
            complexity, reasoning = await self.classify_complexity(user_text)

        # 도구 실행 키워드가 전혀 없는 단순 대화/호출인 경우 (예: "알파야?", "안녕", "고생했어") Fast Bypass 처리
        tool_keywords = [
            "일정", "미팅", "회의", "약속", "스케줄", "등록", "삭제", "수정", "변경",
            "캡처", "캡쳐", "검색", "최저가", "가격", "노션", "아카이브", "리서치", "뉴스", "브리핑",
            "유튜브", "영상", "추천", "날씨", "트렌드", "상식", "음식점", "맛집", "식당", "영화"
        ]
        text_lower = user_text.lower().strip()
        has_tool_keyword = any(kw in text_lower for kw in tool_keywords)

        if complexity == "LOW" and not has_tool_keyword:
            logger.info(f"[Fast Bypass Triggered] Simple conversation detected: '{user_text}'")
            try:
                client = genai.Client(api_key=self.gemini_key)
                from google.genai import types
                now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S (%A, KST)")
                prompt = (
                    f"당신은 대표님을 1:1로 전담 보좌하는 최정예 AI 수석비서 '알파'입니다.\n"
                    f"현재 시각: {now_str}\n"
                    f"대표님의 말씀: \"{user_text}\"\n\n"
                    f"대표님께 품격 있고 정중하게 수석비서로서 짧고 명쾌한 회신을 작성하세요."
                )

                @safe_gemini_call(max_retries=3, initial_delay=2.0)
                async def _fast_bypass_call():
                    return await asyncio.to_thread(
                        client.models.generate_content,
                        model=FAST_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.2,
                            max_output_tokens=300
                        )
                    )

                response = await _fast_bypass_call()
                if isinstance(response, str) and response.startswith("⚠️"):
                    reply = response
                else:
                    reply = response.text.strip() if response and response.text else "네 대표님, 수석비서 알파 대기 중입니다. 지시사항을 말씀해 주십시오!"
                
                self.append_daily_context(user_text, "FAST_CHAT", reply)
                self.log_to_notion_task_db(user_text, "SUCCESS", reply)
                return True, reply, []
            except Exception as e:
                logger.warning(f"Fast Bypass error ({e}), falling back to ReAct loop")

        # Fast Recommendation Trigger (웹 브라우징 차단 및 1~2초 이내 대화형 추천 반환)
        rec_triggers = ["영상 추천", "유튜브 추천", "볼만한 영상", "추천해줘", "영상 찾아줘", "볼만한거"]
        is_simple_rec = any(trig in text_lower for trig in rec_triggers) and not any(kw in text_lower for kw in ["캡처", "캡쳐", "스크린샷", "최저가", "구매", "캘린더"])

        if is_simple_rec:
            logger.info(f"[Fast Recommendation Triggered] Fast 1-2s conversational recommendation for: '{user_text}'")
            try:
                client = genai.Client(api_key=self.gemini_key)
                from google.genai import types
                now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S (%A, KST)")
                prompt = (
                    f"당신은 대표님을 1:1로 전담 보좌하는 최정예 AI 수석비서 '알파'입니다.\n"
                    f"현재 시각: {now_str}\n"
                    f"대표님의 지시: \"{user_text}\"\n\n"
                    f"[지침]\n"
                    f"웹 스크래핑이나 무거운 브라우저 접속 없이 Gemini 모델 자체 지식을 활용해 1~2초 내에 품격 있고 유쾌하게 영상/콘텐츠 추천 답변을 작성하세요.\n"
                    f"반드시 다음과 같은 대화형 템플릿 형태로 작성하세요:\n"
                    f"\"대표님, 오늘 밤 편안한 휴식을 위해 볼만한 영상 3가지를 추천해 드립니다:\n"
                    f"1️⃣ 힐링/자연 ASMR 영상\n"
                    f"2️⃣ 가벼운 테크 트렌드 리포트\n"
                    f"3️⃣ 몰입감 있는 과학 다큐멘터리\"\n"
                    f"원하시는 주제를 말씀해 주시면 바로 찾아드리겠다는 멘트를 포함하세요."
                )

                @safe_gemini_call(max_retries=3, initial_delay=2.0)
                async def _fast_rec_call():
                    return await asyncio.to_thread(
                        client.models.generate_content,
                        model=FAST_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.3,
                            max_output_tokens=600
                        )
                    )

                response = await _fast_rec_call()
                if isinstance(response, str) and response.startswith("⚠️"):
                    reply = response
                else:
                    reply = response.text.strip() if response and hasattr(response, 'text') and response.text else (
                        "대표님, 오늘 밤 편안한 휴식을 위해 볼만한 영상 3가지를 추천해 드립니다:\n"
                        "1️⃣ 힐링/자연 ASMR 영상\n"
                        "2️⃣ 가벼운 테크 트렌드 리포트\n"
                        "3️⃣ 몰입감 있는 과학 다큐멘터리"
                    )
                self.append_daily_context(user_text, "FAST_RECOMMENDATION", reply)
                self.log_to_notion_task_db(user_text, "SUCCESS", reply)
                return True, reply, []
            except Exception as e:
                logger.warning(f"Fast Recommendation error ({e}), falling back to ReAct loop")

        target_model = DEEP_MODEL if complexity == "HIGH" else FAST_MODEL
        tier_tag = "🧠 [Deep Track - Gemini Pro]" if complexity == "HIGH" else "⚡ [Fast Track - Gemini Flash]"
        logger.info(f"Model Tiering Selected: {tier_tag} ({target_model}) | Reason: {reasoning}")

        try:
            return await asyncio.wait_for(
                self._react_loop(user_text, target_model=target_model, complexity=complexity),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            err_msg = "⏱️ **[타임아웃 발생]** 60초 초과로 작업을 안전하게 정지했습니다. (원인: API response latency / 재시도 방안: 명령어를 단순화하여 다시 지시해 주세요)"
            logger.error("AgentEngine: 60s execution timeout triggered.")
            self.append_daily_context(user_text, "TIMEOUT", "60s Circuit Breaker Triggered")
            self.log_to_notion_task_db(user_text, "TIMEOUT", "60s Circuit Breaker Triggered")
            return False, err_msg, []
        except Exception as e:
            err_msg = f"⚠️ **[작업 실행 실패]**\n원인: {e}\n대표님 권장 조치: 구글 계정 및 네트워크 상태 재확인을 권장합니다."
            logger.error(f"AgentEngine execution exception: {e}")
            self.append_daily_context(user_text, "ERROR", f"실패: {e}")
            return False, err_msg, []

    async def _react_loop(self, user_text: str, target_model: str = FAST_MODEL, complexity: str = "LOW") -> tuple[bool, str, list[str]]:
        """
        Dynamic Tiering ReAct 자율 오케스트레이션 루프
        """
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_key:
            return False, "⚠️ GEMINI_API_KEY 환경변수가 설정되지 않았습니다.", []

        now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S (%A, KST)")
        tier_label = "Deep Track (Gemini 2.5 Pro)" if complexity == "HIGH" else "Fast Track (Gemini 2.5 Flash)"
        
        system_instruction = f"""
당신은 대표님의 수석비서 AI '알파'입니다. (구동 엔진: {tier_label})
현재 시각: {now_str}

[당신의 역할]
대표님의 지시사항을 분석하여 제공된 도구들(tool_calendar, tool_universal_search, tool_web_browse, tool_shopping_search, tool_research, tool_notion)을 적절한 순서로 **자율 실행(Chaining)** 하세요.

[Playwright 웹 브라우저(tool_web_browse) 실행 절대 금지 규칙]
- "추천해줘", "알려줘", "영상 찾아줘", "유튜브 추천해줘" 등 단순 정보/영상 추천 요청 시 **절대로 tool_web_browse(Playwright 브라우저)를 호출하지 마세요.**
- 무거운 웹 탐색 대신 Gemini 모델 자체 지식을 활용하여 1~2초 내에 품격 있는 대화형 추천으로 회신하세요.
- 대화형 추천 응답 예시:
  "대표님, 오늘 밤 편안한 휴식을 위해 볼만한 영상 3가지를 추천해 드립니다:
  1️⃣ 힐링/자연 ASMR 영상
  2️⃣ 가벼운 테크 트렌드 리포트
  3️⃣ 몰입감 있는 과학 다큐멘터리"

[스마트 역질문 (Clarification) 및 인터랙티브 추천 모드]
- 대표님의 지시가 "볼만한 영상 찾아줘", "음식점 추천해줘", "뭐 먹을까", "영화 추천해줘" 등 세부 조건(위치, 장르, 기분, 상황 등)이 지정되지 않은 넓은 의미의 추천 요청인 경우:
  1. 무리하게 바로 웹 탐색/스크래핑 도구(tool_web_browse 등)를 실행하지 마세요.
  2. 대표님의 현재 상태/피로도/선호도를 확인할 수 있는 3~4가지 카테고리(선택지 1️⃣, 2️⃣, 3️⃣, 4️⃣)를 위트 있게 역제안하는 스마트 역질문을 먼저 수행하세요.
  3. 대표님이 "1번", "2" 등 편하게 한 글자로 답신하실 수 있도록 번호 선택지(1️⃣, 2️⃣, 3️⃣, 4️⃣)를 명확히 제시하세요.
- 단, "강남역 일식 초밥 맛집 추천해줘"나 "유튜브 재테크 영상 추천해줘"처럼 구체적인 키워드/조건이 포함된 경우 역질문 없이 즉시 도구를 호출하여 수집 결과를 보고하세요.

[도구 사용 가이드]
1. 유튜브 추천, 최신 트렌드, 날씨, 일반 상식 등 전용 도구가 없는 조율/검색 요청은 tool_universal_search를 활용하세요.
2. 필요하다면 도구들을 순차적으로 호출하여 완결된 결과를 수집하세요.
3. 모든 도구 실행 결과를 종합하여 대표님께 명확하고 품격 있는 최종 요약 보고서(한국어)로 작성해 주세요.
4. 이미지 캡처 결과가 발생했다면 보고서에서도 스크린샷 딜리버리 완료 사실을 명시하세요.
"""

        client = genai.Client(api_key=gemini_key)
        from google.genai import types

        LATEST_ARTIFACTS.clear()
        tools_list = [tool_calendar, tool_universal_search, tool_web_browse, tool_shopping_search, tool_research, tool_notion]
        
        messages = [
            types.Content(role="user", parts=[types.Part.from_text(text=user_text)])
        ]
        
        for iteration in range(5):
            logger.info(f"ReAct Loop Iteration #{iteration + 1} (Model={target_model})")
            
            async def _call_gemini_api(model_name: str):
                return await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=tools_list,
                        temperature=0.1,
                        max_output_tokens=2500
                    )
                )

            wrapped_call = safe_gemini_call(max_retries=3, initial_delay=3.0)(_call_gemini_api)
            response = await wrapped_call(target_model)

            if isinstance(response, str) and response.startswith("⚠️"):
                return False, response, LATEST_ARTIFACTS.copy()

            if response.candidates and response.candidates[0].content:
                messages.append(response.candidates[0].content)

            if response.function_calls:
                function_responses = []
                for call in response.function_calls:
                    fn_name = call.name
                    fn_args = dict(call.args) if call.args else {}
                    logger.info(f"⚙️ ReAct Tool Call ({target_model}): {fn_name}({fn_args})")
                    
                    fn = TOOL_MAP.get(fn_name)
                    if fn:
                        res_str = await execute_tool_with_resilience(fn, fn_args, timeout_seconds=15.0)
                    else:
                        res_str = f"Error: Unknown tool '{fn_name}'"

                    function_responses.append(
                        types.Part.from_function_response(
                            name=fn_name,
                            response={"result": res_str}
                        )
                    )

                messages.append(types.Content(role="user", parts=function_responses))
            else:
                final_text = response.text if response.text else "네 대표님, 지시사항 완수하였습니다."
                self.append_daily_context(user_text, f"REACT_{complexity}", final_text)
                self.log_to_notion_task_db(user_text, "SUCCESS", final_text)
                return True, final_text, LATEST_ARTIFACTS.copy()

        final_text = "네 대표님, 지시하신 도구 연속 실행을 완료하였습니다."
        return True, final_text, LATEST_ARTIFACTS.copy()
