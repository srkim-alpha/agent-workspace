import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta

# Project Root Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.calendar_manager import get_today_events_summary
from agents.research_search import SearchAgent

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

CACHE_DIR = os.path.join(PROJECT_ROOT, "data")
CACHE_FILE = os.path.join(CACHE_DIR, "morning_briefing.json")

def prepare_daily_briefing_cache() -> dict:
    """
    [08:15 KST 백그라운드 사전 준비 루틴]
    '서치(Search)' 에이전트가 기사 2건 + 유튜브 1건 필수 수집하여 data/morning_briefing.json에 캐싱함.
    """
    logger.info("🕵️ [08:15 KST] '서치(Search)' 에이전트 사전 글로벌 AI 트렌드(기사 2건 + 유튜브 1건) 리서치 시작...")
    os.makedirs(CACHE_DIR, exist_ok=True)

    now_kst = datetime.now(KST)
    current_date = now_kst.strftime("%Y-%m-%d")

    search_agent = SearchAgent()
    research_data = search_agent.conduct_research()

    cache_payload = {
        "date": current_date,
        "timestamp": now_kst.isoformat(),
        "research": research_data
    }

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_payload, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ [08:15 KST] '서치' 리서치 완료 및 캐시 저장 성공 ({CACHE_FILE})")
    except Exception as e:
        logger.error(f"캐시 파일 쓰기 실패: {e}")

    return research_data

def get_morning_briefing(force_refresh: bool = False) -> str:
    """
    [08:30 KST 정시 선제 발송 및 온디맨드 회신]
    구글 캘린더 일정 + '서치' 에이전트의 [기사 2건 + 유튜브 1건] 캐시 리포트를 조립하여 회신.
    """
    now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y-%m-%d(%a)")
    current_date = now_kst.strftime("%Y-%m-%d")

    # 1. 구글 캘린더 일정 수집
    try:
        schedule_text = get_today_events_summary()
    except Exception as e:
        logger.error(f"캘린더 일정 수집 실패: {e}")
        schedule_text = "일정 조회 실패 (네트워크 상태 확인 필요)"

    # 2. '서치' 에이전트 리서치 데이터 읽기
    research_data = None
    if not force_refresh and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_payload = json.load(f)
                if cache_payload.get("date") == current_date:
                    logger.info("⚡ [08:30 / 온디맨드] 캐시된 모닝 인텔리전스 사용 (즉시 응답)")
                    research_data = cache_payload.get("research")
        except Exception as e:
            logger.warning(f"캐시 읽기 중 오류 발생 ({e}), 라이브 생성 전환")

    if not research_data:
        logger.info("🔄 캐시 미존재 또는 force_refresh 요망 -> '서치' 에이전트 라이브 수행")
        research_data = prepare_daily_briefing_cache()

    # 3. 리포트 조립 (기사 2건 + 유튜브 1건 + 비즈니스 영감 1~2줄)
    tech_trends = research_data.get("tech_trends", [])[:2]
    yt_video = research_data.get("youtube_video", {})
    korea_insight = research_data.get("korea_market_insight", "")

    # 기사 2건 렌더링
    trends_md = ""
    for idx, item in enumerate(tech_trends, 1):
        summary_lines = "\n   • ".join(item.get("summary_3lines", []))
        url = item.get("url", "#")
        trends_md += f"{idx}. **{item.get('title')}**\n   • {summary_lines}\n   🔗 [원문 기사 보기]({url})\n\n"

    # 유튜브 영상 1건 렌더링
    yt_title = yt_video.get("title", "AI 에이전트 수익화 핵심 영상")
    yt_channel = yt_video.get("channel_name", "추천 채널")
    yt_summary = "\n   • ".join(yt_video.get("summary_3lines", []))
    yt_url = yt_video.get("url", "https://youtube.com")

    yt_md = (
        f"📺 **{yt_title}** *(출처: {yt_channel})*\n"
        f"   • {yt_summary}\n"
        f"   🔗 [유튜브 영상 재생하기]({yt_url})"
    )

    report = (
        f"☀️ **[알파 AI 수석비서 모닝 인텔리전스 리포트]**\n"
        f"=====================================\n\n"
        f"📅 **[1] 오늘({date_str}) 구글 캘린더 일정**\n\n"
        f"{schedule_text}\n\n"
        f"🚀 **[2] '서치' 에이전트 선정 글로벌 AI 핵심 트렌드 (기사 2건)**\n\n"
        f"{trends_md.strip()}\n\n"
        f"🎬 **[3] 엄선된 AI/수익화 유튜브 추천 영상 (필수 1건)**\n\n"
        f"{yt_md}\n\n"
        f"💡 **[4] [한국 시장 적용 영감] (1인 비즈니스/에이전트 제안)**\n"
        f"• {korea_insight}\n\n"
        f"=====================================\n"
        f"🫡 대표님, 오늘 하루도 성공적인 비즈니스를 기원합니다!"
    )

    return report

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== [기사 2건 + 유튜브 1건 필수 모닝 브리핑 테스트] ===")
    rep = get_morning_briefing(force_refresh=True)
    print(rep)
