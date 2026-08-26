import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tools.browser_controller import capture_page
from tools.shopping_search import search_naver_shopping
from core.telegram_secretary import classify_intent_with_gemini, _fallback_keyword_intent

def test_capture_page():
    print("\n🧪 [TEST] capture_page 스크린샷 딜리버리 테스트...")
    res = capture_page(url="https://news.google.com", headless=True)
    assert res["success"] is True
    assert res["screenshot_path"] is not None
    assert os.path.exists(res["screenshot_path"])
    print(f"✅ capture_page 성공: {res['screenshot_path']}")

def test_search_naver_shopping():
    print("\n🧪 [TEST] search_naver_shopping 상품 검색 & 캡처 테스트...")
    res = search_naver_shopping(keyword="기계식 키보드", headless=True)
    assert res["success"] is True
    assert res["screenshot_path"] is not None
    assert os.path.exists(res["screenshot_path"])
    print(f"✅ search_naver_shopping 성공: {res['screenshot_path']}")

def test_web_search_intent_classification():
    print("\n🧪 [TEST] WEB_SEARCH 정밀 의도 및 액션/타깃 분류 테스트...")
    
    # Case 1: 구글 뉴스 메인 접속 및 헤드라인 캡처
    text1 = "구글 뉴스 메인 화면 캡처해서 헤드라인 알려줘"
    intent_res1 = classify_intent_with_gemini(text1)
    print(f"분류 결과 1 (구글 뉴스): {intent_res1}")
    assert intent_res1.get("intent") == "WEB_SEARCH"
    assert intent_res1.get("action") == "browse"
    
    # Case 2: 쇼핑 최저가 검색
    text2 = "네이버에서 RTX 5080 최저가 검색해줘"
    intent_res2 = classify_intent_with_gemini(text2)
    print(f"분류 결과 2 (RTX 5080 최저가): {intent_res2}")
    assert intent_res2.get("intent") == "WEB_SEARCH"
    assert intent_res2.get("action") == "shopping"

    # Case 3: 일반 검색
    text3 = "인천 날씨 검색해줘"
    intent_res3 = classify_intent_with_gemini(text3)
    print(f"분류 결과 3 (인천 날씨): {intent_res3}")
    assert intent_res3.get("intent") == "WEB_SEARCH"

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding="utf-8")
    print("🚀 Remote Browser Dispatcher 통합 테스트 시작...")
    test_web_search_intent_classification()
    print("\n🎉 모든 테스트 통과 완료!")
