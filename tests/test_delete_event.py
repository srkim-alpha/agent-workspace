import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.calendar_manager import delete_event_with_gemini, get_specific_day_events_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_delete_event():
    print("=== [1] 삭제 전 내일 캘린더 일정 조회 ===")
    before_summary = get_specific_day_events_summary(1, "내일")
    print(before_summary)
    print("\n" + "="*50 + "\n")

    instruction = "내일 15:00 대표님 전략 수석 미팅 일정 삭제해줘"
    print(f"=== [2] 일정 삭제 함수 실행: '{instruction}' ===")
    success, result_msg = delete_event_with_gemini(instruction)
    print(f"Success: {success}")
    print(f"Result: {result_msg}")
    print("\n" + "="*50 + "\n")

    print("=== [3] 삭제 후 내일 캘린더 일정 조회 ===")
    after_summary = get_specific_day_events_summary(1, "내일")
    print(after_summary)

if __name__ == "__main__":
    test_delete_event()
