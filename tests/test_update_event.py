import os
import sys
import logging
from dotenv import load_dotenv

# Path setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(dotenv_path="config/.env")

from core.calendar_manager import (
    get_specific_day_events_summary,
    update_event_with_gemini
)

logging.basicConfig(level=logging.INFO)

def main():
    print("=== [1] 수정 전 내일(2026-08-25) 캘린더 일정 조회 ===")
    before = get_specific_day_events_summary(1, "내일")
    print(before)
    print("=" * 50)

    print("\n=== [2] 일정 수정 함수 실행: '내일 오후 4시에 등록된 일정 민성 수영 강자를 민성수영강좌로 바꿔줘' ===")
    success, result_msg = update_event_with_gemini("내일 오후 4시에 등록된 일정 민성 수영 강자를 민성수영강좌로 바꿔줘")
    print(f"Success: {success}")
    print(f"Result: {result_msg}")
    print("=" * 50)

    print("\n=== [3] 수정 후 내일(2026-08-25) 캘린더 일정 조회 ===")
    after = get_specific_day_events_summary(1, "내일")
    print(after)

if __name__ == "__main__":
    main()
