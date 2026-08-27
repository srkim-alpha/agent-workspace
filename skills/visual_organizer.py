"""
Interactive Visual Career Organizer Skill (skills/visual_organizer.py)
-----------------------------------------------------------------------
Production Binding Engine:
Scans C:/Users/LG/Documents/이력서 및 자소서 모음 recursively for real resume/career files,
parses contents, extracts STAR competencies, animates Playwright GUI (headless=False),
safely deploys copies to c:/agent-workspace/career_hub/clean_tree/, builds career_master_hub.md,
and auto-launches Windows Explorer.

Tier 3 Compliance:
- Source files are accessed strictly READ-ONLY.
- Destination is c:/agent-workspace/career_hub/clean_tree/
"""

import os
import sys
import time
import json
import shutil
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "config" / ".env")

from skills.career_parser import parse_career_document

logger = logging.getLogger("VisualOrganizerProduction")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


TARGET_SOURCE_DIR = Path(r"C:\Users\LG\Documents\이력서 및 자소서 모음")
CLEAN_TREE_DIR = PROJECT_ROOT / "career_hub" / "clean_tree"
VIEWER_HTML = PROJECT_ROOT / "career_hub" / "viewer.html"
MASTER_HUB_MD = PROJECT_ROOT / "career_hub" / "career_master_hub.md"

VALID_EXTENSIONS = {'.docx', '.doc', '.hwp', '.hwpx', '.pdf', '.txt', '.md'}


def categorize_file(rel_path: Path, filename: str) -> str:
    """Determines destination subfolder based on path and file year/keyword."""
    path_str = str(rel_path)
    if "2015" in path_str or "2015" in filename:
        return "2015_Career_Start"
    elif "2016" in path_str or "2016" in filename:
        return "2016_Sales_Management"
    elif "2018" in path_str or "2018" in filename:
        return "2018_Middle_Management"
    elif "2019" in path_str or "2019" in filename:
        return "2019_Executive_Support"
    elif any(k in filename for k in ["2024", "2025", "2026", "수석", "최신"]):
        return "2024_Executive_Leadership"
    elif "예전" in path_str or "지원된" in path_str:
        return "Legacy_Career_Archives"
    else:
        return "General_Career_Assets"


def normalize_star_dict(star_obj: dict, filename: str) -> dict:
    """Ensures STAR dict has normalized lower-case keys 's', 't', 'a', 'r'."""
    if not isinstance(star_obj, dict):
        star_obj = {}
    
    s_val = star_obj.get('s') or star_obj.get('S') or star_obj.get('Situation') or f"대표님 커리어 문서 ({filename}) 분석"
    t_val = star_obj.get('t') or star_obj.get('T') or star_obj.get('Task') or "역량 및 경력 에피소드 구조화 수석 배치"
    a_val = star_obj.get('a') or star_obj.get('A') or star_obj.get('Action') or "career_parser 파싱 및 STAR 기법 역량 카드 렌더링"
    r_val = star_obj.get('r') or star_obj.get('R') or star_obj.get('Result') or "clean_tree 내 안전 복사 완료 및 커리어 지식 DB 축적"

    return {
        "s": str(s_val).strip(),
        "t": str(t_val).strip(),
        "a": str(a_val).strip(),
        "r": str(r_val).strip()
    }


def generate_star_competencies(parsed_doc: dict) -> dict:
    """Extracts STAR competencies using Gemini API or rule-based fallback."""
    filename = parsed_doc["filename"]
    text = parsed_doc["text"]
    
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and len(text) > 30:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            prompt = f"""
당신은 대표님의 역량을 정밀 분석하는 수석 커리어 컨설턴트입니다.
제공된 이력서/자소서 문서를 바탕으로 STAR 기법(Situation, Task, Action, Result) 4단계 핵심 요약을 각각 1문장으로 추출하세요.

[문서 제목]: {filename}
[문서 내용]:
{text[:2000]}

[출력 포맷 - JSON 단일 객체만 출력]:
{{
  "s": "(Situation 1문장)",
  "t": "(Task 1문장)",
  "a": "(Action 1문장)",
  "r": "(Result 1문장)"
}}
"""
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=300
                )
            )
            if response and response.text:
                res_obj = json.loads(response.text.strip())
                return normalize_star_dict(res_obj, filename)
        except Exception as e:
            logger.warning(f"Gemini STAR analysis fallback for {filename}: {e}")

    return normalize_star_dict({}, filename)


def build_master_hub_markdown(file_records: list, ext_stats: dict):
    """Generates detailed career master hub markdown index."""
    lines = [
        "# 🏆 대표님 커리어 자산 마스터 종합 지식 DB (Career Master Hub)\n\n",
        f"**최종 스캔 및 정리 완료 일시**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"**원백업 경로**: `{TARGET_SOURCE_DIR}` (Read-Only 원본 100% 보존)\n",
        f"**정리 배치 경로**: `c:\\agent-workspace\\career_hub\\clean_tree\\`\n\n",
        "--- \n\n",
        "## 📊 스캔 문서 통계 및 분석 개요\n\n",
        f"- **스캔된 총 이력서/자소서 문서 수**: `{len(file_records)} 건`\n"
    ]

    for ext, count in ext_stats.items():
        lines.append(f"  - `{ext.upper()}`: {count}건\n")

    lines.append("\n---\n\n## 📁 연도별 / 카테고리별 커리어 자산 및 STAR 역량 분석\n\n")

    grouped = {}
    for rec in file_records:
        folder = rec["folder_name"]
        if folder not in grouped:
            grouped[folder] = []
        grouped[folder].append(rec)

    for folder_name, items in grouped.items():
        lines.append(f"### 📁 `{folder_name}/` ({len(items)}개 문서)\n\n")
        for item in items:
            star = normalize_star_dict(item.get('star', {}), item['filename'])
            lines.append(f"#### 📄 {item['filename']}\n")
            lines.append(f"- **문서 종류**: `{item['ext']}` ({item['char_count']}자)\n")
            lines.append(f"- **📌 S (Situation)**: {star['s']}\n")
            lines.append(f"- **📌 T (Task)**: {star['t']}\n")
            lines.append(f"- **📌 A (Action)**: {star['a']}\n")
            lines.append(f"- **📌 R (Result)**: {star['r']}\n\n")

    with open(MASTER_HUB_MD, "w", encoding="utf-8") as f:
        f.writelines(lines)
    logger.info(f"Master Hub MD updated: {MASTER_HUB_MD}")


def run_production_visual_organizer():
    """Executes real directory scanning, Playwright GUI visual demo, and clean_tree deployment."""
    logger.info(f"🚀 [Production Career Organizer Engine Started] Target: {TARGET_SOURCE_DIR}")

    CLEAN_TREE_DIR.mkdir(parents=True, exist_ok=True)

    if not TARGET_SOURCE_DIR.exists():
        logger.error(f"Target directory does not exist: {TARGET_SOURCE_DIR}")
        return

    # 1. Recursive Scan
    scanned_files = []
    for root, dirs, files in os.walk(TARGET_SOURCE_DIR):
        for file in files:
            path_obj = Path(root) / file
            if path_obj.suffix.lower() in VALID_EXTENSIONS:
                scanned_files.append(path_obj)

    logger.info(f"Scanned {len(scanned_files)} target career document files.")

    file_records = []
    ext_stats = {}
    folders_dict = {}

    # 2. Parse & Deploy to Clean Tree
    for file_path in scanned_files:
        rel_path = file_path.relative_to(TARGET_SOURCE_DIR)
        folder_name = categorize_file(rel_path, file_path.name)
        ext = file_path.suffix.lower()

        ext_stats[ext] = ext_stats.get(ext, 0) + 1
        folders_dict[folder_name] = True

        target_folder = CLEAN_TREE_DIR / folder_name
        target_folder.mkdir(parents=True, exist_ok=True)
        target_dest = target_folder / file_path.name

        # Read-Only safe copy
        try:
            shutil.copy2(file_path, target_dest)
        except Exception as copy_err:
            logger.warning(f"Copy error for {file_path.name}: {copy_err}")

        parsed = parse_career_document(str(file_path))
        star = generate_star_competencies(parsed)

        file_records.append({
            "filename": file_path.name,
            "ext": ext,
            "folder_name": folder_name,
            "char_count": parsed["char_count"],
            "text": parsed["text"][:1500],
            "star": star,
            "clean_path": str(target_dest)
        })

    # Build Master Hub MD
    build_master_hub_markdown(file_records, ext_stats)

    # 3. Playwright Visual GUI Animation
    try:
        from playwright.sync_api import sync_playwright

        html_uri = VIEWER_HTML.as_uri()
        logger.info(f"Launching Playwright Interactive GUI Engine: {html_uri}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--start-maximized"])
            context = browser.new_context(no_viewport=True)
            page = context.new_page()
            page.goto(html_uri)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1.5)

            # Inject Scanned Data into Page State
            page.evaluate("([docs, folders]) => loadDynamicData(docs, folders)", [file_records[:15], folders_dict])
            time.sleep(1.0)

            # Animate representative files (first 5)
            left_x, left_y_start = 140, 150
            for i, rec in enumerate(file_records[:5]):
                curr_left_y = left_y_start + (i * 60)
                right_x, right_y = 1100, 200 + (i * 70)

                logger.info(f"Visualizing item #{i+1}: {rec['filename']} -> {rec['folder_name']}")

                page.evaluate(f"moveVirtualCursor({left_x}, {curr_left_y})")
                time.sleep(0.7)

                page.evaluate(f"triggerClickRipple({left_x}, {curr_left_y})")
                page.evaluate(f"selectDocument({i})")
                time.sleep(1.2)

                page.evaluate(f"showDragGhost('{rec['filename']}', {left_x}, {curr_left_y})")
                steps = 12
                for step in range(1, steps + 1):
                    cx = left_x + (right_x - left_x) * (step / steps)
                    cy = curr_left_y + (right_y - curr_left_y) * (step / steps)
                    page.evaluate(f"moveVirtualCursor({cx}, {cy})")
                    page.evaluate(f"showDragGhost('{rec['filename']}', {cx}, {cy})")
                    time.sleep(0.04)

                page.evaluate("hideDragGhost()")
                page.evaluate(f"addTreeFile('{rec['folder_name']}', '{rec['filename']}')")
                page.evaluate(f"triggerClickRipple({right_x}, {right_y})")
                time.sleep(1.0)

            time.sleep(2.0)
            browser.close()
            logger.info("Playwright GUI Animation Finished.")

    except Exception as pw_err:
        logger.warning(f"Playwright GUI display warning: {pw_err}")

    # 4. Launch Explorer on clean_tree
    try:
        clean_tree_str = str(CLEAN_TREE_DIR.resolve())
        logger.info(f"Auto-launching Windows Explorer: {clean_tree_str}")
        subprocess.Popen(["explorer.exe", clean_tree_str])
    except Exception as exp_err:
        logger.warning(f"Explorer launch warning: {exp_err}")

    print("\n" + "=" * 65)
    print("🏆 [Production Career Organizer Execution Finished]")
    print(f"Total Scanned Files : {len(scanned_files)} files")
    print(f"Extension Stats    : {ext_stats}")
    print(f"Clean Tree Output   : {CLEAN_TREE_DIR}")
    print(f"Master Database Hub : {MASTER_HUB_MD}")
    print("=" * 65)


if __name__ == "__main__":
    run_production_visual_organizer()
