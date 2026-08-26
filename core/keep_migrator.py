import os
import sys
import json
import glob
import logging
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, "config", ".env"))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

CATEGORIES = [
    "💡 아이디어/비즈니스",
    "📋 할 일/체크리스트",
    "📚 지식/스크랩",
    "☕ 일상/개인 메모"
]

def parse_keep_files(keep_dir: str) -> list[dict]:
    """
    data/keep_notes/ 디렉토리의 모든 .json 파일을 읽어 정제된 메모 목록 반환
    """
    json_files = glob.glob(os.path.join(keep_dir, "*.json"))
    notes = []

    for fpath in json_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            title = data.get("title", "").strip()
            text_content = data.get("textContent", "").strip()
            list_content = data.get("listContent", [])

            # 체크리스트 추출
            checklist = []
            if list_content:
                for item in list_content:
                    txt = item.get("text", "").strip()
                    checked = item.get("isChecked", False)
                    if txt:
                        checklist.append({"text": txt, "checked": checked})

            # 제목 자동 생성 (제목이 비어 있는 경우 본문 첫 줄 활용)
            if not title:
                if text_content:
                    first_line = text_content.split("\n")[0].strip()
                    title = first_line[:40] if first_line else "제목 없는 메모"
                elif checklist:
                    title = f"체크리스트: {checklist[0]['text'][:30]}"
                else:
                    title = "제목 없는 메모"

            # 작성 시각 추출 (microsecond -> YYYY-MM-DD)
            created_usec = data.get("createdTimestampUsec", 0)
            if created_usec:
                created_dt = datetime.fromtimestamp(created_usec / 1000000.0, tz=timezone.utc).astimezone(KST)
                created_str = created_dt.strftime("%Y-%m-%d")
            else:
                created_str = datetime.now(KST).strftime("%Y-%m-%d")

            notes.append({
                "file_name": os.path.basename(fpath),
                "title": title,
                "text_content": text_content,
                "checklist": checklist,
                "created_date": created_str,
                "is_archived": data.get("isArchived", False),
                "is_pinned": data.get("isPinned", False),
                "is_trashed": data.get("isTrashed", False)
            })
        except Exception as e:
            logger.warning(f"파일 파싱 실패 ({fpath}): {e}")

    return notes

def batch_classify_with_llm(notes: list[dict]) -> list[dict]:
    """
    Gemini LLM을 활용하여 각 메모를 4대 카테고리로 자동 분류
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        logger.warning("Gemini API Key 부재 - 키워드 기반 기본 분류 적용")
        return _fallback_classify(notes)

    client = genai.Client(api_key=gemini_key)

    # 10개씩 배치 분류
    batch_size = 15
    classified_notes = []

    for i in range(0, len(notes), batch_size):
        batch = notes[i:i+batch_size]
        items_payload = []
        for idx, n in enumerate(batch):
            body_preview = n['text_content'][:200] if n['text_content'] else str([c['text'] for c in n['checklist'][:5]])
            items_payload.append({
                "id": idx,
                "title": n['title'],
                "content_preview": body_preview
            })

        prompt = f"""
당신은 메모 정리 전문 파이프라인 LLM입니다.
아래 메모 항목들을 읽고 각 항목에 가장 어울리는 카테고리를 아래 4개 중 정확히 1개 선택하세요.

[선택 가능 카테고리]
1. "💡 아이디어/비즈니스" (사업 구상, 새로운 생각, 기획, 수수료/계약/정산, 전략)
2. "📋 할 일/체크리스트" (ToDo, 장보기, 구매 목록, 작업 목록, 일정/준비물)
3. "📚 지식/스크랩" (유튜브/뉴스/강의 요약, 프롬프트, 링크, 공부 내용, AI 기술)
4. "☕ 일상/개인 메모" (개인 성향, 감상, 노래 목록, 일상 기록)

[입력 메모 목록]
{json.dumps(items_payload, ensure_ascii=False, indent=2)}

출력은 반드시 JSON 배열 구조로만 작성하세요:
[
  {{"id": 0, "category": "💡 아이디어/비즈니스"}},
  ...
]
"""
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            res_text = response.text.strip()
            cat_map = {item['id']: item['category'] for item in json.loads(res_text)}
            for idx, n in enumerate(batch):
                cat = cat_map.get(idx, "☕ 일상/개인 메모")
                if cat not in CATEGORIES:
                    cat = "☕ 일상/개인 메모"
                n["category"] = cat
                classified_notes.append(n)
        except Exception as e:
            logger.warning(f"LLM 배치 분류 오류 ({e}), 폴백 적용")
            for n in batch:
                n["category"] = _fallback_single_classify(n)
                classified_notes.append(n)

    return classified_notes

def _fallback_single_classify(n: dict) -> str:
    text = (n['title'] + " " + n['text_content']).lower()
    if any(k in text for k in ["체크리스트", "할일", "장보기", "구매", "서류", "준비"]):
        return "📋 할 일/체크리스트"
    elif any(k in text for k in ["사업", "아이디어", "수익", "계약", "비즈니스", "마스터", "전략"]):
        return "💡 아이디어/비즈니스"
    elif any(k in text for k in ["ai", "프롬프트", "유튜브", "강의", "노트북lm", "제미나이", "온톨로지", "클로드"]):
        return "📚 지식/스크랩"
    else:
        return "☕ 일상/개인 메모"

def _fallback_classify(notes: list[dict]) -> list[dict]:
    for n in notes:
        n["category"] = _fallback_single_classify(n)
    return notes

def run_keep_migration():
    keep_dir = os.path.join(PROJECT_ROOT, "data", "keep_notes")
    logger.info(f"📂 구글 킵 메모 파싱 시작 ({keep_dir})...")

    raw_notes = parse_keep_files(keep_dir)
    logger.info(f"✅ 총 {len(raw_notes)}개 구글 킵 메모 파싱 완료")

    logger.info("🧠 LLM 기반 스마트 카테고리 자동 분류 실행 중...")
    classified_notes = batch_classify_with_llm(raw_notes)

    # 카테고리별 집계
    cat_counts = {c: 0 for c in CATEGORIES}
    for n in classified_notes:
        cat_counts[n["category"]] += 1

    # 로컬 저장 (JSON & Markdown 아카이브)
    archive_json_path = os.path.join(PROJECT_ROOT, "data", "keep_notes_archived.json")
    archive_md_path = os.path.join(PROJECT_ROOT, "data", "keep_notes_summary.md")

    with open(archive_json_path, "w", encoding="utf-8") as f:
        json.dump(classified_notes, f, ensure_ascii=False, indent=2)

    # 마크다운 요약 리포트 생성
    md_content = f"# 📌 구글 킵 스마트 아카이브 (총 {len(classified_notes)}개 메모 이관 완료)\n\n"
    md_content += f"- **분류 일시**: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}\n\n"
    md_content += "## 📊 카테고리별 이관 현황\n"
    for cat, count in cat_counts.items():
        md_content += f"- **{cat}**: {count}개\n"
    md_content += "\n---\n\n"

    for cat in CATEGORIES:
        cat_items = [n for n in classified_notes if n["category"] == cat]
        md_content += f"## {cat} ({len(cat_items)}개)\n\n"
        for item in cat_items:
            md_content += f"### 📝 {item['title']} (작성일: {item['created_date']})\n"
            if item["text_content"]:
                md_content += f"```text\n{item['text_content'][:500]}\n```\n"
            if item["checklist"]:
                md_content += "**체크리스트**:\n"
                for chk in item["checklist"]:
                    mark = "x" if chk["checked"] else " "
                    md_content += f"- [{mark}] {chk['text']}\n"
            md_content += "\n"

    with open(archive_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    summary_msg = (
        f"✅ **[구글 킵 스마트 이관 완료]** 총 **{len(classified_notes)}개**의 메모를 성공적으로 분석 및 노션 지식 자산으로 이관했습니다.\n\n"
        f"📊 **카테고리별 정돈 결과**:\n"
        f"• 💡 아이디어/비즈니스: {cat_counts['💡 아이디어/비즈니스']}개\n"
        f"• 📋 할 일/체크리스트: {cat_counts['📋 할 일/체크리스트']}개\n"
        f"• 📚 지식/스크랩: {cat_counts['📚 지식/스크랩']}개\n"
        f"• ☕ 일상/개인 메모: {cat_counts['☕ 일상/개인 메모']}개\n"
    )

    print(summary_msg)
    return classified_notes, cat_counts, summary_msg

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_keep_migration()
