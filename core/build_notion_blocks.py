import os
import sys
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
archive_json_path = os.path.join(PROJECT_ROOT, "data", "keep_notes_archived.json")

with open(archive_json_path, "r", encoding="utf-8") as f:
    notes = json.load(f)

CATEGORY_PAGES = {
    "💡 아이디어/비즈니스": "3c62a254-6920-8185-bc32-cb4adbd53ba5",
    "📋 할 일/체크리스트": "3c62a254-6920-818f-ac4a-d606ae40297e",
    "📚 지식/스크랩": "3c62a254-6920-81f9-8821-fa6c2bf8e140",
    "☕ 일상/개인 메모": "3c62a254-6920-8146-be2e-f4f38c2aba63"
}

def create_note_blocks(note: dict) -> dict:
    title = note.get("title", "제목 없는 메모")
    date_str = note.get("created_date", "")
    text_content = note.get("text_content", "").strip()
    checklist = note.get("checklist", [])

    children = []

    # 1. 본문 텍스트가 있을 경우 (2000자 단위 분할)
    if text_content:
        chunks = [text_content[i:i+1900] for i in range(0, len(text_content), 1900)]
        for chunk in chunks[:10]: # 최대 10개 단락
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            })

    # 2. 체크리스트가 있을 경우 (to_do 블록)
    if checklist:
        for chk in checklist[:20]: # 최대 20개
            children.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"type": "text", "text": {"content": chk["text"][:1900]}}],
                    "checked": chk["checked"]
                }
            })

    # 3. 토글 블록 생성
    toggle_header = f"📝 {title} (작성일: {date_str})"
    if len(toggle_header) > 100:
        toggle_header = toggle_header[:97] + "..."

    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": toggle_header},
                    "annotations": {"bold": True}
                }
            ],
            "children": children
        }
    }

def main():
    output_dir = os.path.join(PROJECT_ROOT, "tmp", "notion_blocks")
    os.makedirs(output_dir, exist_ok=True)

    grouped = {}
    for cat in CATEGORY_PAGES.keys():
        grouped[cat] = []

    for n in notes:
        cat = n.get("category", "☕ 일상/개인 메모")
        if cat in grouped:
            grouped[cat].append(create_note_blocks(n))

    for cat, blocks in grouped.items():
        fname = cat.replace("/", "_").replace(" ", "_") + ".json"
        out_path = os.path.join(output_dir, fname)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(blocks, f, ensure_ascii=False, indent=2)
        print(f"✅ [{cat}] {len(blocks)}개 블록 저장완료: {out_path}")

if __name__ == "__main__":
    main()
