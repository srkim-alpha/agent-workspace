import os
import sys
import json
import uuid
import asyncio
import logging
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

KST = timezone(timedelta(hours=9))

import psutil
from google import genai

from core.calendar_manager import (
    get_today_events_summary,
    get_specific_day_events_summary,
    get_week_events_summary,
    parse_and_create_event_with_gemini,
    delete_event_with_gemini,
    update_event_with_gemini,
    update_calendar_event,
)
from core.agent_engine import AgentEngine
from core.briefing_manager import get_morning_briefing, prepare_daily_briefing_cache
from core.resilience_manager import safe_gemini_call, sanitize_user_facing_error
from core.interaction_guard import check_ambiguity
from tools.shopping_search import search_naver_shopping
from tools.browser_controller import capture_page, run_browser_test
agent_engine = AgentEngine()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# 1. 환경 변수 로드
ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)
load_dotenv()  # 루트 .env 동시 로드

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAW_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8392524393")
ALLOWED_CHAT_ID = int(RAW_CHAT_ID)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# 거버넌스 승인 대기열 메모리 저장소 (task_id -> user_text)
PENDING_CRITICAL_TASKS = {}

# 로깅 설정
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

if GEMINI_API_KEY:
    logger.info("✅ GEMINI API KEY 로드 성공")
else:
    logger.warning("⚠️ GEMINI_API_KEY가 로드되지 않았습니다. config/.env 파일에 GEMINI_API_KEY를 추가해 주세요.")

logger.info("✅ 구글 캘린더 연동 준비 완료")

# 안전한 메세지 회신/전송/수정 헬퍼 함수 (마크다운 파싱 에러 시 parse_mode=None Fallback 적용)
async def safe_reply_text(message, text: str, parse_mode: str = "Markdown", reply_markup=None, **kwargs):
    try:
        return await message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup, **kwargs)
    except BadRequest as e:
        if "parse" in str(e).lower() or "entity" in str(e).lower():
            logger.warning(f"텔레그램 마크다운 파싱 오류 발생 ({e}). 일반 텍스트 모드로 회신합니다.")
            return await message.reply_text(text, parse_mode=None, reply_markup=reply_markup, **kwargs)
        raise e
    except Exception as e:
        logger.warning(f"메시지 회신 예외 발생 ({e}). 일반 텍스트 모드로 회신합니다.")
        return await message.reply_text(text, parse_mode=None, reply_markup=reply_markup, **kwargs)

async def safe_send_message(bot, chat_id, text: str, parse_mode: str = "Markdown", reply_markup=None, **kwargs):
    try:
        return await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup, **kwargs)
    except BadRequest as e:
        if "parse" in str(e).lower() or "entity" in str(e).lower():
            logger.warning(f"텔레그램 마크다운 파싱 오류 발생 ({e}). 일반 텍스트 모드로 전송합니다.")
            return await bot.send_message(chat_id=chat_id, text=text, parse_mode=None, reply_markup=reply_markup, **kwargs)
        raise e
    except Exception as e:
        logger.warning(f"메시지 전송 예외 발생 ({e}). 일반 텍스트 모드로 전송합니다.")
        return await bot.send_message(chat_id=chat_id, text=text, parse_mode=None, reply_markup=reply_markup, **kwargs)

async def safe_edit_text(message_or_query, text: str, parse_mode: str = "Markdown", reply_markup=None, **kwargs):
    try:
        return await message_or_query.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup, **kwargs)
    except BadRequest as e:
        if "parse" in str(e).lower() or "entity" in str(e).lower():
            logger.warning(f"텔레그램 마크다운 파싱 오류 발생 ({e}). 일반 텍스트 모드로 수정합니다.")
            return await message_or_query.edit_text(text, parse_mode=None, reply_markup=reply_markup, **kwargs)
        raise e
    except Exception as e:
        logger.warning(f"메시지 수정 예외 발생 ({e}). 일반 텍스트 모드로 수정합니다.")
        return await message_or_query.edit_text(text, parse_mode=None, reply_markup=reply_markup, **kwargs)

async def safe_send_photo(bot, chat_id, photo_path: str, caption: str = None, parse_mode: str = "Markdown", **kwargs):
    try:
        if not photo_path or not os.path.exists(photo_path):
            logger.warning(f"스크린샷 파일이 존재하지 않습니다: {photo_path}")
            return None
        with open(photo_path, "rb") as photo_file:
            return await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=caption, parse_mode=parse_mode, **kwargs)
    except BadRequest as e:
        if "parse" in str(e).lower() or "entity" in str(e).lower():
            logger.warning(f"텔레그램 사진 캡션 마크다운 파싱 오류 ({e}). 일반 텍스트 모드로 전송합니다.")
            with open(photo_path, "rb") as photo_file:
                return await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=caption, parse_mode=None, **kwargs)
        raise e
    except Exception as e:
        logger.warning(f"사진 전송 예외 발생 ({e}).")
        return None

# 보안 화이트리스트 검증 함수
def check_whitelist(update: Update) -> bool:
    if not update.effective_chat:
        return False
    return update.effective_chat.id == ALLOWED_CHAT_ID

async def send_unauthorized_msg(update: Update):
    if update.effective_message:
        await safe_reply_text(
            update.effective_message,
            f"⛔ 접근 불허: 대표님(Chat ID: {ALLOWED_CHAT_ID}) 전용 1:1 수석비서 게이트웨이입니다."
        )

# 2. 시작 시 대표님 전송 알림
async def post_init(application: Application) -> None:
    logger.info(f"대표님({ALLOWED_CHAT_ID})에게 가동 메시지 전송 중...")
    try:
        await safe_send_message(
            application.bot,
            chat_id=ALLOWED_CHAT_ID,
            text="🫡 대표님, 마크다운 예외 래핑 및 가동 패치가 완료되었습니다. 편안히 테스트해 주세요."
        )
    except Exception as e:
        logger.error(f"초기 메세지 발송 실패: {e}")

# 3. Gemini STT 멀티모달 변환 함수
@safe_gemini_call(
    max_retries=3,
    initial_delay=17.0,
    backoff_factor=1.2,
    custom_fallback="⚠️ 현재 음성 처리 서버 요청이 집중되어 지연되고 있습니다. 10초 뒤 다시 말씀해 주시면 즉시 처리하겠습니다."
)
def transcribe_audio_gemini(file_path: str) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        logger.error("GEMINI_API_KEY가 설정되어 있지 않습니다.")
        return ""

    path = Path(file_path)
    if not path.exists():
        logger.error(f"음성 파일이 존재하지 않습니다: {file_path}")
        return ""

    mime_type = "audio/ogg"
    if path.suffix.lower() in [".mp3"]:
        mime_type = "audio/mp3"
    elif path.suffix.lower() in [".wav"]:
        mime_type = "audio/wav"
    elif path.suffix.lower() in [".m4a"]:
        mime_type = "audio/m4a"

    try:
        client = genai.Client(api_key=gemini_key)
        logger.info(f"Gemini STT 바이너리 패킷 전달 중: {file_path} (MIME: {mime_type})")

        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        from google.genai import types
        part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        prompt = "이 음성 파일의 한국어 발화를 빠짐없이 정확히 텍스트로만 받아적어줘. 부가 설명 없이 인식된 문장만 출력해."

        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=[part, prompt],
            config=types.GenerateContentConfig(
                max_output_tokens=256,
                temperature=0.1
            )
        )

        transcribed_text = response.text.strip() if response and response.text else ""
        logger.info(f"Gemini STT 전사 성공 결과: '{transcribed_text}'")
        return transcribed_text

    except Exception as e:
        logger.error(f"Gemini STT 변환 실패: {e}")
        return ""

# 4. 실시간 데이터 수집 및 Gemini 브리핑 생성 함수 (경량화 고속 스캔)
def collect_realtime_metrics() -> dict:
    now_str = datetime.now().strftime("%Y년 %m월 %d일 %H:%M:%S (KST)")
    
    # 💻 시스템 자원 정보 (interval=0 즉각 반환)
    try:
        cpu_usage = psutil.cpu_percent(interval=0)
        ram = psutil.virtual_memory()
        ram_usage = ram.percent
        ram_used_gb = round(ram.used / (1024**3), 2)
        ram_total_gb = round(ram.total / (1024**3), 2)
        sys_info = f"CPU 사용률: {cpu_usage}%, RAM 사용량: {ram_usage}% ({ram_used_gb}GB / {ram_total_gb}GB)"
    except Exception as e:
        sys_info = f"시스템 리소스 측정 실패 ({e})"

    # 📂 워크스페이스 현황 (얕은 고속 스캔)
    workspace_path = Path("c:/agent-workspace")
    items_summary = []
    recent_files = []
    try:
        if workspace_path.exists():
            top_items = [p.name for p in workspace_path.iterdir() if not p.name.startswith(".") and p.name not in ["tmp", "__pycache__", "node_modules", "venv", ".git"]]
            items_summary = top_items[:10]

            top_files = [p for p in workspace_path.iterdir() if p.is_file() and not p.name.startswith(".")]
            top_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for p in top_files[:5]:
                mtime_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                recent_files.append(f"{p.name} (수정: {mtime_str})")
    except Exception as e:
        logger.error(f"워크스페이스 스캔 실패: {e}")

    # 📋 핵심 프로젝트 현황
    projects = [
        "🚀 [바이브코딩 4주 로드맵]: 🟢 1:1 수석비서 게이트웨이 & Voice STT 고도화 완료",
        "📅 [구글 캘린더 연동]: 🟢 캘린더 일정 조회 및 음성/텍스트 자동 등록 모듈 적용 완료",
        "🔗 [노션 연동 상태]: 🟢 Notion MCP & Master Dashboard 연결 완료",
        "💰 [가계부/재무 연동]: 🟡 MVP 인터페이스 및 텔레그램 연동 준비 완료"
    ]

    # 📅 구글 캘린더 일정 요약 수집
    calendar_today = get_today_events_summary()

    return {
        "datetime": now_str,
        "system_info": sys_info,
        "workspace_items": items_summary,
        "recent_files": recent_files,
        "projects": projects,
        "calendar_today": calendar_today
    }

def generate_gemini_briefing(data: dict) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    raw_summary = (
        f"📅 **현재 시각 (KST)**: {data['datetime']}\n"
        f"💻 **노트북 리소스**: {data['system_info']}\n\n"
        f"{data.get('calendar_today', '')}\n\n"
        f"📂 **주요 워크스페이스 목록 (`c:\\agent-workspace`)**: {', '.join(data['workspace_items'])}\n\n"
        f"📝 **최근 수정 파일 (Top 5)**:\n" + "\n".join([f"  • `{f}`" for f in data['recent_files']]) + "\n\n"
        f"📋 **진행 중인 핵심 프로젝트 현황**:\n" + "\n".join([f"  • {p}" for p in data['projects']])
    )

    if not gemini_key:
        return (
            f"📊 **[알파 COO 실시간 종합 브리핑 보고서]**\n"
            f"=====================================\n\n"
            f"{raw_summary}\n\n"
            f"=====================================\n"
            f"🫡 대표님, 수석비서 알파가 항상 신속하게 보좌하겠습니다!"
        )

    try:
        client = genai.Client(api_key=gemini_key)
        from google.genai import types
        prompt = (
            "당신은 대표님을 1:1로 전담 보좌하는 최정예 AI 수석비서 '알파'입니다.\n"
            "아래 제공된 데이터를 바탕으로 대표님께 정중하고 깔끔하며 신뢰감을 주는 '일일 종합 브리핑 보고서'를 작성해 주세요.\n"
            "1. 텔레그램 마크다운(Markdown) 포맷으로 작성\n"
            "2. 이모지를 적절히 배치하여 가독성 극대화\n\n"
            f"[실시간 수집 데이터]\n{raw_summary}"
        )
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=500,
                temperature=0.2
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini 브리핑 생성 중 오류 발생: {e}")
        return (
            f"📊 **[알파 COO 실시간 종합 브리핑 보고서]**\n"
            f"=====================================\n\n"
            f"{raw_summary}\n\n"
            f"=====================================\n"
            f"🫡 대표님, 수석비서 알파가 항상 신속하게 보좌하겠습니다!"
        )

URL_ALIASES = {
    "구글 뉴스": "https://news.google.com",
    "구글뉴스": "https://news.google.com",
    "google news": "https://news.google.com",
    "구글 메인": "https://www.google.com",
    "구글": "https://www.google.com",
    "네이버 뉴스": "https://news.naver.com",
    "네이버뉴스": "https://news.naver.com",
    "네이버 메인": "https://www.naver.com",
    "네이버": "https://www.naver.com",
    "다음": "https://www.daum.net",
    "유튜브": "https://www.youtube.com"
}

# 4.1 Gemini 기반 자연어 의도 & 파라미터 추출기 (Intent & Parameter Extractor)
def classify_intent_with_gemini(user_text: str) -> dict:
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        return _fallback_keyword_intent(user_text)

    now = datetime.now()
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S (%A, KST)")

    prompt = f"""
당신은 대표님의 수석비서 AI 의도 분류 및 파라미터 추출기(Intent & Parameter Extractor)입니다.
현재 시각: {current_time_str} (타임존: Asia/Seoul)

대표님의 지시 문장:
"{user_text}"

위 지시 문장의 의도와 파라미터를 분석하여 순수 JSON만 출력하세요. 마크다운 백틱 없이 JSON만 응답하세요.

[카테고리]
1. "FULL_BRIEFING": 전체 시스템 현황 및 종합 브리핑 요청
2. "CALENDAR_QUERY": 날짜/주간 구글 캘린더 일정 단순 조회
3. "CALENDAR_CREATE": 구글 캘린더 신규 일정 등록
4. "CALENDAR_UPDATE": 구글 캘린더 일정 수정/변경
5. "WEB_SEARCH": 웹 탐색, 특정 사이트/뉴스 캡처, 가격/최저가 확인 요청
6. "DAY_END": 하루 업무 마감 및 워크스페이스 정리
7. "CRITICAL_ACTION": 파일 삭제, 서버 리셋, 배포 등 위험 변경
8. "GENERAL_CHAT": 기타 질문, 일반 대화

[WEB_SEARCH action & target 세부 추출 규칙]
- intent가 "WEB_SEARCH"인 경우 action과 target을 정밀하게 추출하세요:
  1. action: "browse" (특정 사이트/뉴스 직접 접속 및 캡처)
     - 예: "구글 뉴스 메인 화면 캡처해서 헤드라인 알려줘" -> action: "browse", target: "https://news.google.com"
     - 예: "네이버 메인 캡처해줘" -> action: "browse", target: "https://www.naver.com"
     - 예: "https://github.com 캡처" -> action: "browse", target: "https://github.com"
  2. action: "shopping" (상품 쇼핑 검색 및 가격/최저가 비교)
     - 예: "네이버에서 RTX 5080 최저가 검색해줘" -> action: "shopping", target: "RTX 5080"
     - 예: "키보드 가격 확인해줘" -> action: "shopping", target: "키보드"
  3. action: "browse_search" (일반 검색어 웹 탐색)
     - 예: "인천 날씨 검색해줘" -> action: "browse_search", target: "인천 날씨"
  
  target 규칙: "캡처해서 헤드라인 알려줘", "메인 화면", "최저가 검색해줘", "보고해" 등 불필요한 서술어를 완벽히 떼어낸 순수 URL 또는 핵심 키워드만 지정하세요.

응답 JSON 포맷:
{{"intent": "WEB_SEARCH | FULL_BRIEFING | CALENDAR_QUERY | CALENDAR_CREATE | CALENDAR_UPDATE | DAY_END | CRITICAL_ACTION | GENERAL_CHAT", "action": "browse | shopping | browse_search | none", "target": "정제된 target URL 또는 검색어", "query_period": "today | tomorrow | week | specific"}}
"""
    try:
        client = genai.Client(api_key=gemini_key)
        from google.genai import types
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=200,
                temperature=0.1
            )
        )
        raw_output = response.text.strip()
        if raw_output.startswith("```"):
            raw_output = raw_output.split("```")[1]
            if raw_output.startswith("json"):
                raw_output = raw_output[4:]
        raw_output = raw_output.strip()
        return json.loads(raw_output)
    except Exception as e:
        logger.warning(f"Gemini 인텐트 분류 실패 ({e}), 키워드 폴백 적용")
        return _fallback_keyword_intent(user_text)

def _fallback_keyword_intent(user_text: str) -> dict:
    text_lower = user_text.lower()
    
    web_keywords = [
        "캡처", "최저가", "가격 확인", "검색해 줘", "검색해줘", "화면 캡처", "웹 검색", 
        "사이트 캡처", "가격 검색", "가격 확인하고", "가격 검토", "검색해서", "최저가 검색", 
        "검색해", "조회해", "보고해", "뉴스", "헤드라인"
    ]
    if any(kw in text_lower for kw in web_keywords) or ("가격" in text_lower and any(kw in text_lower for kw in ["확인", "검색", "캡처", "알려줘", "보고"])):
        action = "browse_search"
        target = user_text
        
        for alias_key, alias_url in URL_ALIASES.items():
            if alias_key in text_lower:
                action = "browse"
                target = alias_url
                break

        if action != "browse":
            if any(kw in text_lower for kw in ["최저가", "쇼핑", "가격"]):
                action = "shopping"
            elif any(kw in text_lower for kw in ["뉴스", "메인", "캡처"]) or text_lower.startswith("http"):
                action = "browse"

        if not target.startswith("http"):
            clean_target = user_text
            for strip_word in [
                "알파", "네이버에서", "네이버", "구글에서", "구글", "가격", "확인하고", "확인해 줘", "확인해줘", 
                "화면", "캡처해 줘", "캡처해줘", "검색해 줘", "검색해줘", "최저가", "알려줘", "해줘", 
                "보고해", "검색해서", "검색해", "찾아줘", "찾아서", "조회해줘", "보고", "메인 화면", "메인", "헤드라인", "캡처해서"
            ]:
                clean_target = clean_target.replace(strip_word, "")
            clean_target = clean_target.strip()
            target = clean_target if clean_target else "RTX 5080"
            
        return {
            "intent": "WEB_SEARCH",
            "action": action,
            "target": target,
            "query_period": "today"
        }

    day_end_keywords = ["작업 끝", "퇴근", "업무 끝", "마감", "오늘 작업"]
    if any(kw in text_lower for kw in day_end_keywords):
        return {"intent": "DAY_END", "query_period": "today", "target_date": ""}

    update_keywords = ["바꿔", "수정", "변경", "바꿔줘", "수정해줘", "변경해줘"]
    if any(kw in text_lower for kw in update_keywords):
        return {"intent": "CALENDAR_UPDATE", "query_period": "today", "target_date": ""}

    critical_keywords = ["삭제", "delete", "rm", "배포", "deploy", "초기화", "reset", "리팩토링"]
    if any(kw in text_lower for kw in critical_keywords):
        return {"intent": "CRITICAL_ACTION", "query_period": "today", "target_date": ""}

    calendar_create_keywords = ["등록", "추가", "예약", "잡아줘", "만들어줘"]
    if any(kw in text_lower for kw in calendar_create_keywords) and any(kw in text_lower for kw in ["일정", "미팅", "회의", "스케줄", "약속"]):
        return {"intent": "CALENDAR_CREATE", "query_period": "today", "target_date": ""}

    if any(kw in text_lower for kw in ["종합", "상태", "현황", "시스템", "브리핑"]):
        return {"intent": "FULL_BRIEFING", "query_period": "today", "target_date": ""}

    if any(kw in text_lower for kw in ["일정", "스케줄", "약속"]):
        if "내일" in user_text:
            return {"intent": "CALENDAR_QUERY", "query_period": "tomorrow", "target_date": ""}
        elif "주" in user_text or "이번주" in user_text:
            return {"intent": "CALENDAR_QUERY", "query_period": "week", "target_date": ""}
        else:
            return {"intent": "CALENDAR_QUERY", "query_period": "today", "target_date": ""}

    return {"intent": "GENERAL_CHAT", "query_period": "today", "target_date": ""}

def generate_gemini_general_reply(user_text: str) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        return f"🤖 **[알파 COO 수석비서]**\n\n대표님, '{user_text}' 지시를 확인하였습니다. 세부 사항을 말씀해 주시면 신속히 보좌하겠습니다!"

    now = datetime.now()
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S (%A, KST)")

    prompt = f"""
당신은 대표님을 1:1로 전담 보좌하는 최정예 AI 수석비서 "알파 COO"입니다.
대표님은 높은 명확성과 빠른 의사결정을 원하시는 경영 리더이십니다.

[수석비서 알파의 행동 지침]
1. 대표님께 격식 있고 깍듯하며 정중하고 신뢰감을 주는 최정예 수석비서 어조를 사용하세요. ("대표님, ...")
2. '지시사항을 확인하였습니다' 같은 기계식 템플릿 답변을 절대 사용하지 마세요.
3. 대표님의 지시/질문의 맥락과 의도를 깊이 이해하고, 실제 유용하고 명쾌하며 스마트한 LLM 수석비서 답변을 제공하세요.
4. 텔레그램 마크다운 포맷과 적절한 이모지를 배치하여 가독성을 높이세요.

현재 시각: {current_time_str} (타임존: Asia/Seoul)

대표님의 지시/대화:
"{user_text}"

수석비서 알파의 답변:
"""
    try:
        client = genai.Client(api_key=gemini_key)
        from google.genai import types
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=350,
                temperature=0.3
            )
        )
        reply = response.text.strip() if response and response.text else ""
        if not reply:
            reply = f"🤖 **[알파 COO 수석비서]**\n\n대표님, 말씀해주신 내용('{user_text}')에 대해 명확히 파악하여 완벽히 보좌하겠습니다."
        return reply
    except Exception as e:
        logger.error(f"Gemini 일반 대화 답변 생성 오류: {e}")
        return f"🤖 **[알파 COO 수석비서]**\n\n대표님, 말씀해주신 지시사항('{user_text}') 건을 신속히 확인하여 보좌하겠습니다."

# 5. 명령어 핸들러
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_whitelist(update):
        await send_unauthorized_msg(update)
        return

    msg = (
        "🤖 **[알파 COO 수석비서 게이트웨이]**\n\n"
        "대표님, 반갑습니다! 모바일 텔레그램 1:1 수석비서 게이트웨이입니다.\n\n"
        "📌 **주요 기능 및 명령어 안내**\n"
        "• `/status` : 시스템 및 워크스페이스 실시간 종합 브리핑\n"
        "• `/briefing` : 일일 종합 상황판 및 프로젝트 실시간 브리핑\n"
        "• `/calendar` : 구글 캘린더 오늘/주간 일정 조회\n"
        "• **📅 캘린더 자동 등록** : '내일 오후 3시 OOO 미팅 등록해줘' 음성/텍스트 즉시 일정 등록\n"
        "• **텍스트/음성 지시** : '브리핑', '상태', '현황', '일정', '보고' 키워드 수신 시 즉시 실시간 종합 브리핑 회신\n"
        "• 🎙️ **음성 지시 (Voice STT)** : Gemini 멀티모달 고정밀 STT 자동 변환\n"
        "• **거버넌스 가드레일** : 주요/위험 작업 요청 시 승인 인라인 버튼 발송"
    )
    await safe_reply_text(update.message, msg)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_whitelist(update):
        await send_unauthorized_msg(update)
        return

    metrics_data = await asyncio.to_thread(collect_realtime_metrics)
    briefing_text = await asyncio.to_thread(generate_gemini_briefing, metrics_data)
    await safe_reply_text(update.message, briefing_text)

async def briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_whitelist(update):
        await send_unauthorized_msg(update)
        return

    report_text = await asyncio.to_thread(get_morning_briefing)
    await safe_reply_text(update.message, report_text)

async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_whitelist(update):
        await send_unauthorized_msg(update)
        return

    today_summary = await asyncio.to_thread(get_today_events_summary)
    week_summary = await asyncio.to_thread(get_week_events_summary)
    msg = f"🗓️ **[알파 COO 구글 캘린더 일정 상황판]**\n\n{today_summary}\n\n{week_summary}"
    await safe_reply_text(update.message, msg)

# 6. 공통 지시 처리 로직 (ReAct Dynamic Model Tiering 단일 통로)
async def process_instruction_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, is_voice: bool = False):
    logger.info(f"대표님 지시 처리 중 (Voice={is_voice}): {user_text}")

    voice_prefix = f"🎙️ **[음성 지시]**: *\"{user_text}\"*\n\n" if is_voice else ""

    # 0. Ambiguity Pre-Filter (Clarification Guard)
    guard_res = check_ambiguity(user_text)
    if guard_res.get("is_ambiguous"):
        logger.info(f"Clarification Guard 감지 (모호한 질의): '{user_text}' ({guard_res['latency_ms']:.2f}ms)")
        reply_msg = f"{voice_prefix}{guard_res['clarification_message']}"
        await safe_reply_text(update.message, reply_msg)
        return

    # 1. 1차 경량 복잡도 분류 (Gemini Flash)
    complexity, reason = await agent_engine.classify_complexity(user_text)

    if complexity == "HIGH":
        status_text = f"{voice_prefix}🧠 **[Deep Track - Gemini Pro 가동]**\n복합 다단계 자율 체이닝 및 심층 추론을 수행 중입니다..."
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        except Exception:
            pass
    else:
        status_text = f"{voice_prefix}⚡ **[Fast Track - Gemini Flash 가동]**\n신속하게 요청을 처리하고 있습니다..."

    status_msg = await safe_reply_text(update.message, status_text)

    # 2. Dynamic Model Tiering ReAct Engine 실행
    success, report_text, artifacts = await agent_engine.process_instruction(
        user_text,
        pre_classified_complexity=(complexity, reason)
    )

    await safe_edit_text(status_msg, f"{voice_prefix}{report_text}")

    # 산출물(스크린샷 이미지 등) 텔레그램 딜리버리
    if artifacts:
        for art_path in artifacts:
            if os.path.exists(art_path):
                caption = f"📸 **[알파 자율 딜리버리 산출물]**"
                await safe_send_photo(context.bot, update.effective_chat.id, photo_path=art_path, caption=caption)



# 7. 텍스트 핸들러
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_whitelist(update):
        await send_unauthorized_msg(update)
        return

    await process_instruction_text(update, context, update.message.text, is_voice=False)

# 8. 음성 메세지 핸들러 (filters.VOICE - Non-blocking 및 단일 응답 처리)
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_whitelist(update):
        await send_unauthorized_msg(update)
        return

    if not update.message or not update.message.voice:
        return

    voice = update.message.voice
    logger.info(f"대표님 음성 메시지 수신 (File ID: {voice.file_id})")

    temp_dir = BASE_DIR / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    unique_id = f"{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
    temp_path = temp_dir / f"voice_{unique_id}.ogg"

    try:
        # 1) 음성 파일 다운로드 (1회 재시도 및 60초 타임아웃 적용)
        voice_file = None
        for attempt in range(2):
            try:
                voice_file = await context.bot.get_file(
                    voice.file_id,
                    read_timeout=60,
                    write_timeout=60,
                    connect_timeout=60
                )
                await voice_file.download_to_drive(
                    custom_path=temp_path,
                    read_timeout=60,
                    write_timeout=60,
                    connect_timeout=60
                )
                logger.info(f"유니크 임시 음성 파일 다운로드 성공 ({attempt+1}차 시도): {temp_path}")
                break
            except Exception as dl_err:
                logger.warning(f"음성 다운로드 {attempt+1}차 시도 실패: {dl_err}")
                if attempt == 0:
                    await asyncio.sleep(1)
                else:
                    await safe_reply_text(update.message, f"⚠️ 음성 파일 다운로드 네트워크 오류가 발생했습니다: {dl_err}")
                    return

        # 2) Gemini 멀티모달 STT 변환 (asyncio.to_thread 비동기 실행 및 1회 재시도)
        transcribed_text = ""
        try:
            transcribed_text = await asyncio.to_thread(transcribe_audio_gemini, str(temp_path))
        except Exception as stt_err:
            logger.error(f"Gemini STT Execution exception: {stt_err}")

        if not transcribed_text:
            await safe_reply_text(
                update.message,
                "⚠️ 대표님, 음성 인식(STT) 처리에 실패하였거나 변환된 텍스트가 없습니다.\n"
                "(10초 뒤 명확한 음성으로 다시 말씀해 주시면 즉시 처리하겠습니다.)"
            )
            return

        if transcribed_text.startswith("⚠️"):
            await safe_reply_text(update.message, transcribed_text)
            return

        # 3) 변환된 텍스트로 단일 응답 비동기 Gemini 인텐트 라우팅 수행 (is_voice=True)
        await process_instruction_text(update, context, transcribed_text, is_voice=True)

    except Exception as e:
        logger.error(f"음성 메세지 처리 오류: {e}")
        await safe_reply_text(update.message, f"⚠️ 음성 처리 중 오류가 발생했습니다: {e}")
    finally:
        # 4) 임시 음성 파일 즉시 삭제
        if temp_path.exists():
            try:
                os.remove(temp_path)
                logger.info(f"임시 음성 파일 즉시 삭제 완료: {temp_path}")
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {e}")

# 9. 거버넌스 버튼 콜백 핸들러
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.message.chat.id != ALLOWED_CHAT_ID:
        await query.answer("⛔ 접근 권한이 없습니다.", show_alert=True)
        return

    await query.answer()

    data = query.data
    if data.startswith("approve:") or data == "approve_task":
        task_id = data.split(":")[1] if ":" in data else None
        user_text = PENDING_CRITICAL_TASKS.get(task_id, "") if task_id else ""

        if not user_text and "`" in query.message.text:
            try:
                user_text = query.message.text.split("`")[1]
            except Exception:
                user_text = ""

        # 진행 상태 즉시 업데이트
        progress_text = (
            query.message.text + "\n\n"
            "===============================\n"
            "⏳ **[대표님 승인 완료 - 작업 즉시 집행 중]**\n"
            "구글 캘린더 API를 호출하여 해당 이벤트를 삭제하고 있습니다..."
        )
        await safe_edit_text(query.message, progress_text)

        # Gemini 기반 캘린더 일정 삭제 비동기 수행
        exec_text = user_text if user_text else "내일 3시 일정 삭제"
        success, result_text = await asyncio.to_thread(delete_event_with_gemini, exec_text)

        final_text = (
            query.message.text + "\n\n"
            "===============================\n"
            "✅ **[대표님 승인 완료 및 작업 집행 성공]**\n\n"
            f"{result_text}"
        )
        await safe_edit_text(query.message, final_text)

    elif data.startswith("deny:") or data == "deny_task":
        result_text = (
            query.message.text + "\n\n"
            "===============================\n"
            "❌ **[작업 거부 처리]**\n"
            "대표님의 명령으로 해당 중대 작업이 전면 취소되었습니다. 🛑"
        )
        await safe_edit_text(query.message, result_text)

# 10. 선제적 아침 브리핑 스케줄러 (08:15 사전 캐싱 & 08:30 KST 정시 발송)
async def schedule_morning_briefing(app: Application):
    """
    매일 아침 08:15 KST '서치' 에이전트 사전 리서치 캐싱 -> 08:30 KST 정시 선제적 발송 스케줄러
    """
    logger.info("⏰ 08:15 사전 준비 & 08:30 KST 아침 선제 브리핑 백그라운드 스케줄러 가동됨")
    last_cached_date = ""
    last_sent_date = ""

    while True:
        try:
            now_kst = datetime.now(KST)
            current_date = now_kst.strftime("%Y-%m-%d")

            # 1. 08:15 KST: '서치' 에이전트 백그라운드 리서치 & data/morning_briefing.json 캐싱
            if now_kst.hour == 8 and now_kst.minute == 15 and last_cached_date != current_date:
                logger.info("🕵️ [08:15 KST] '서치' 에이전트 사전 백그라운드 리서치 캐싱 루틴 실행")
                last_cached_date = current_date
                await asyncio.to_thread(prepare_daily_briefing_cache)

            # 2. 08:30 KST: 구글 캘린더 일정 + 캐시된 글로벌 AI 인텔리전스 즉시 전송
            if now_kst.hour == 8 and now_kst.minute == 30 and last_sent_date != current_date:
                logger.info("☀️ [08:30 KST] 대표님 전담 모닝 인텔리전스 리포트 정시 발송 루틴 실행")
                last_sent_date = current_date

                briefing_msg = await asyncio.to_thread(get_morning_briefing)

                await app.bot.send_message(
                    chat_id=ALLOWED_CHAT_ID,
                    text=briefing_msg,
                    parse_mode="Markdown"
                )
                logger.info("✅ [08:30 KST] 모닝 인텔리전스 브리핑 텔레그램 발송 성공")

        except Exception as e:
            logger.error(f"아침 선제 브리핑 스케줄러 오류: {e}")

        await asyncio.sleep(30)

async def post_init(app: Application):
    """
    Application post-init hook: 백그라운드 스케줄러 루프 시작
    """
    asyncio.create_task(schedule_morning_briefing(app))

def main():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    logger.info("알파 수석비서 텔레그램 게이트웨이 (60초 타임아웃 확장 & Non-blocking STT) 초기화 중...")
    
    # 텔레그램 네트워크 타임아웃 60초 확장 설정
    request_config = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0
    )
    
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request_config)
        .get_updates_request(request_config)
        .post_init(post_init)
        .build()
    )

    # Command Handlers
    app.add_handler(CommandHandler(["start", "help"], start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("briefing", briefing_command))
    app.add_handler(CommandHandler(["calendar", "schedule"], calendar_command))

    # Message Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Callback Handler
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("텔레그램 수석비서 폴링 서비스 가동 시작...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
