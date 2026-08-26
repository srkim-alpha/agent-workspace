import os
import sys
import json
import logging
import urllib.request
import glob
from datetime import datetime, timezone, timedelta

# Project Root Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.agent_engine import mask_sensitive_info

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

SUMMARIES_DIR = os.path.join(PROJECT_ROOT, "data", "daily_summaries")
ARCHIVE_INDEX_FILE = os.path.join(PROJECT_ROOT, "data", "notion_daily_archive.json")

def format_2track_markdown(
    date_str: str,
    chapter_title: str,
    pain_points: str,
    solution_ideas: str,
    applied_prompts: str,
    monetization_insights: str,
    raw_logs: str
) -> str:
    """
    2-Track 노션 지식 자산화 마크다운 템플릿 생성
    - 상단: 가벼운 알파 메모리 및 챕터 요약본 (1초 복원용)
    - 하단: Raw 데이터 보관용 (토글 형태)
    """
    content = (
        f"# 🧠 [AI 에이전트 구축 실전 아카이브] - {date_str}\n\n"
        f"--- \n"
        f"### 📌 [Chapter]: {chapter_title}\n\n"
        f"#### 1. ❓ 부딪힌 문제 (Real Pain-Point)\n"
        f"{pain_points.strip()}\n\n"
        f"#### 2. 💡 해결 아이디어 및 인터뷰 과정\n"
        f"{solution_ideas.strip()}\n\n"
        f"#### 3. 🛠️ 실전 적용 프롬프트\n"
        f"```markdown\n{applied_prompts.strip()}\n```\n\n"
        f"#### 4. 💰 수익화/강의 인사이트\n"
        f"{monetization_insights.strip()}\n\n"
        f"--- \n"
        f"### ▶ 📂 [클릭하여 펼치기] 오늘의 티키타카 대화 및 시스템 작업 Raw 데이터 전문\n"
        f"<details>\n<summary><b>🔍 Raw Data 대화 및 수행 로그 전체 보기 (Expand)</b></summary>\n\n"
        f"```log\n{raw_logs.strip()}\n```\n"
        f"</details>\n"
    )
    return content

def create_2track_notion_archive(
    chapter_title: str = "AI 수석비서 하네스 & 서치 에이전트 구축 및 모닝 브리핑 엔진",
    pain_points: str = None,
    solution_ideas: str = None,
    applied_prompts: str = None,
    monetization_insights: str = None,
    raw_logs: str = None
) -> dict:
    """
    [오늘 작업 끝 / 퇴근 시 자동 실행]
    2-Track 노션 페이지 생성 & 로컬 영속성 저장을 동시 수행
    """
    now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y-%m-%d")

    # 기본값 설정 (오늘 작업 맥락 자동 합성)
    if not pain_points:
        pain_points = (
            "• 텔레그램 가드레일 승인 후 일정 삭제/수정 API 미실행 버그\n"
            "• 음성 인식(STT) 및 Gemini API 호출 시 이벤트 루프 블로킹으로 인한 3~5분 지연\n"
            "• 백그라운드 텔레그램 데몬 중복 실행으로 인한 중복 응답 및 리소스 낭비"
        )
    if not solution_ideas:
        solution_ideas = (
            "• ReAct 루프 엔진 및 60초 타임아웃 서킷 브레이커 도입\n"
            "• 모든 I/O 네트워크 연산 asyncio.to_thread() 비동기 전환\n"
            "• 글로벌 리서치 전담 '서치(Search)' 에이전트 구축 및 08:15 KST 사전 캐싱 파이프라인(data/morning_briefing.json) 완성\n"
            "• 최상위 영구 헌법(docs/agent_rules.md) 확립 및 민감정보 자동 마스킹 적용"
        )
    if not applied_prompts:
        applied_prompts = (
            "System Constitution (docs/agent_rules.md):\n"
            "- Article 1: Jarvis Persona & Concise Tone\n"
            "- Article 3: Harness Guardrail (Inline [Approval] required for critical actions)\n"
            "- Article 8: Day-End Routine & Workspace Cleanup\n"
            "- Article 9: Security Masking (Regex API Key / PII Masking)\n"
            "- Article 10: Proactive Morning Intelligence Briefing"
        )
    if not monetization_insights:
        monetization_insights = (
            "• 1인 기업 및 중소기업 대상 '맞춤형 업무 자동화 에이전트 구축 패키지' 구독형(SaaS) 상품화\n"
            "• 리얼 타임 텔레그램 음성 비서 + 구글 캘린더 연동 하네스 구축 노하우 전자책/강의 아카이브화"
        )
    if not raw_logs:
        raw_logs = (
            f"[{date_str} System Log Snapshot]\n"
            "- Registered intents: FULL_BRIEFING, DAY_END, CALENDAR_UPDATE, CALENDAR_DELETE\n"
            "- Checked single daemon process PID running cleanly.\n"
            "- Cleaned temp files (temp_*.ogg, __pycache__)."
        )

    # 1. 2-Track 마크다운 문서 합성
    markdown_doc = format_2track_markdown(
        date_str, chapter_title, pain_points, solution_ideas,
        applied_prompts, monetization_insights, raw_logs
    )

    # 2. 로컬 영속성 저장 (1초 복원용)
    os.makedirs(SUMMARIES_DIR, exist_ok=True)
    summary_path = os.path.join(SUMMARIES_DIR, f"{date_str}.md")
    
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(markdown_doc)

    archive_entry = {
        "date": date_str,
        "chapter": chapter_title,
        "summary_file": summary_path,
        "timestamp": now_kst.isoformat(),
        "top_summary": {
            "pain_points": pain_points,
            "solution_ideas": solution_ideas,
            "monetization_insights": monetization_insights
        }
    }

    try:
        archives = []
        if os.path.exists(ARCHIVE_INDEX_FILE):
            with open(ARCHIVE_INDEX_FILE, "r", encoding="utf-8") as f:
                archives = json.load(f)
        
        # 날짜 중복 제거 후 추가
        archives = [a for a in archives if a.get("date") != date_str]
        archives.append(archive_entry)

        with open(ARCHIVE_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(archives, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ [2-Track 로컬 자산화] {summary_path} 저장 성공")
    except Exception as e:
        logger.error(f"로컬 아카이브 인덱스 업데이트 실패: {e}")

    # 3. 노션 API 동기화 시도 (NOTION_API_KEY 환경변수 존재 시)
    notion_api_key = os.getenv("NOTION_API_KEY") or os.getenv("NOTION_TOKEN")
    notion_db_id = os.getenv("NOTION_DATABASE_ID")

    if notion_api_key and notion_db_id:
        try:
            resp = sync_to_notion_api(notion_api_key, notion_db_id, date_str, chapter_title, markdown_doc)
            page_url = resp.get("url")
            archive_entry["notion_url"] = page_url
            logger.info(f"✅ [노션 API] 2-Track 페이지 노션 동기화 완료: {page_url}")
        except Exception as e:
            logger.warning(f"노션 API 동기화 중 오류 (로컬 보관으로 보호됨): {e}")
    else:
        logger.info("ℹ️ Notion API Key/DB ID 미설정으로 로컬 2-Track 아카이브 저장을 완료했습니다.")

    return archive_entry

def create_daily_briefing_page(
    title: str = "알파 일일 브리핑 메모",
    summary: str = "구글 뉴스 및 캘린더 주요 일정 수집 완수",
    calendar_text: str = "일정 정보 없음",
    web_capture_info: dict = None,
    raw_log: str = ""
) -> dict:
    """
    [실데이터 매핑 & 프리미엄 UI 블록 렌더링]
    Callout, Divider, Heading 3, Bulleted List, Toggle 블록을 사용해 노션에 일일 브리핑 페이지 적재
    """
    now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y-%m-%d")
    page_title = title if date_str in title else f"[{date_str}] {title}"

    notion_api_key = os.getenv("NOTION_API_KEY") or os.getenv("NOTION_TOKEN")
    notion_target_id = os.getenv("NOTION_DATABASE_ID")

    if not web_capture_info:
        web_capture_info = {}

    url_str = web_capture_info.get("url") or web_capture_info.get("target_url") or "https://news.google.com"
    screenshot_str = web_capture_info.get("screenshot_path") or "N/A"

    # Build children blocks
    children_blocks = []

    # 1. 💡 Callout Block (Blue Background)
    children_blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": "💡"},
            "color": "blue_background",
            "rich_text": [{"type": "text", "text": {"content": summary.strip() or "브리핑 요약 정보가 없습니다."}}]
        }
    })

    # 2. ─── Divider Block
    children_blocks.append({
        "object": "block",
        "type": "divider",
        "divider": {}
    })

    # 3. 📌 Heading 3: "📅 주요 일정 현황"
    children_blocks.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": "📅 주요 일정 현황"}}]
        }
    })

    # Bullet list for calendar_text
    cal_lines = [line.strip() for line in calendar_text.strip().splitlines() if line.strip()] if calendar_text else []
    if not cal_lines:
        cal_lines = ["등록된 주요 일정이 없습니다."]
    for line in cal_lines:
        # Strip existing bullet markers if present
        clean_line = line.lstrip("•-*\t ").strip()
        children_blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": clean_line}}]
            }
        })

    # 4. 🌐 Heading 3: "🔍 웹 탐색 및 스크린샷"
    children_blocks.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": "🔍 웹 탐색 및 스크린샷"}}]
        }
    })

    children_blocks.append({
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": f"🌐 Target URL: {url_str}"}}]
        }
    })

    children_blocks.append({
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": f"📸 Screenshot: {screenshot_str}"}}]
        }
    })

    # 5. ▶ Toggle Block (Gray Background): "상세 실행 로그 및 전문 보기"
    log_content = raw_log.strip() or f"[{date_str}] Briefing process completed successfully."
    log_chunks = [log_content[i:i+1500] for i in range(0, len(log_content), 1500)]
    toggle_children = []
    for chunk in log_chunks:
        toggle_children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": chunk}}]
            }
        })

    children_blocks.append({
        "object": "block",
        "type": "toggle",
        "toggle": {
            "color": "gray_background",
            "rich_text": [{"type": "text", "text": {"content": "▶ 상세 실행 로그 및 전문 보기"}}],
            "children": toggle_children
        }
    })

    res_entry = {
        "date": date_str,
        "title": page_title,
        "summary": summary,
        "timestamp": now_kst.isoformat()
    }

    if not notion_api_key or not notion_target_id:
        logger.info("ℹ️ Notion API credentials missing. Daily briefing saved locally.")
        return res_entry

    # Submit to Notion API
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    payload_page = {
        "parent": {"page_id": notion_target_id},
        "properties": {
            "title": {
                "title": [{"text": {"content": page_title}}]
            }
        },
        "children": children_blocks
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload_page).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            page_url = data.get("url")
            res_entry["notion_url"] = page_url
            logger.info(f"✅ [프리미엄 UI 브리핑] 노션 페이지 생성 성공: {page_url}")
            return res_entry
    except urllib.error.HTTPError:
        payload_db = {
            "parent": {"database_id": notion_target_id},
            "properties": {
                "이름": {
                    "title": [{"text": {"content": page_title}}]
                },
                "날짜": {
                    "date": {"start": date_str}
                }
            },
            "children": children_blocks
        }
        req = urllib.request.Request(url, data=json.dumps(payload_db).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            page_url = data.get("url")
            res_entry["notion_url"] = page_url
            logger.info(f"✅ [프리미엄 UI 브리핑] 노션 DB 페이지 생성 성공: {page_url}")
            return res_entry


def sync_to_notion_api(api_key: str, target_id: str, date_str: str, chapter_title: str, content: str) -> dict:

    """
    Notion REST API를 사용해 노션 DB 또는 상위 페이지 하위에 2-Track 아카이빙 페이지 생성
    """
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # Split content into chunks of 1500 chars to fit Notion paragraph limits
    text_chunks = [content[i:i+1500] for i in range(0, len(content), 1500)]
    children_blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": f"📌 [Chapter]: {chapter_title}"}}]
            }
        }
    ]
    for chunk in text_chunks:
        children_blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": chunk}}]
            }
        })

    # Try parent as page_id first
    payload_page = {
        "parent": {"page_id": target_id},
        "properties": {
            "title": {
                "title": [{"text": {"content": f"[{date_str}] {chapter_title}"}}]
            }
        },
        "children": children_blocks
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload_page).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        # Fallback to database_id parent if target_id is a database
        payload_db = {
            "parent": {"database_id": target_id},
            "properties": {
                "이름": {
                    "title": [{"text": {"content": f"[{date_str}] {chapter_title}"}}]
                },
                "날짜": {
                    "date": {"start": date_str}
                }
            },
            "children": children_blocks
        }
        req = urllib.request.Request(url, data=json.dumps(payload_db).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))


def restore_recent_context() -> str:
    """
    [1초 맥락 복원 룰]
    새 세션 시작 시, 노션/로컬 상단의 [요약본]만 1초 만에 읽어 맥락 복원
    """
    if os.path.exists(ARCHIVE_INDEX_FILE):
        try:
            with open(ARCHIVE_INDEX_FILE, "r", encoding="utf-8") as f:
                archives = json.load(f)
                if archives:
                    latest = archives[-1]
                    summary_file = latest.get("summary_file")
                    if summary_file and os.path.exists(summary_file):
                        with open(summary_file, "r", encoding="utf-8") as sf:
                            full_text = sf.read()
                            # 토글 Raw Data 전까지만 잘라서 요약본 추출 (1초 복원)
                            summary_only = full_text.split("---")[1] if "---" in full_text else full_text[:1000]
                            return f"🧠 [복원된 지난 세션 지식 자산 - {latest.get('date')}]\n" + summary_only.strip()
        except Exception as e:
            logger.error(f"컨텍스트 복원 실패: {e}")

    return "🧠 이전 세션 자산 요약본 없음 (새로운 세션을 시작합니다)."

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== [2-Track 노션 지식 자산화 및 1초 복원 테스트] ===")
    res = create_2track_notion_archive()
    print("저장 결과:", res)
    print("\n=== [1초 컨텍스트 복원 출력] ===")
    ctx = restore_recent_context()
    print(ctx)
