import os
import re
import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_PATTERNS = [
    r"바로가기", r"본문", r"메뉴", r"네비게이션", r"주요서비스",
    r"검색어.*자동완성", r"로그인", r"도움말", r"열기", r"닫기",
    r"더보기", r"네이버", r"리뷰", r"블로그", r"뉴스", r"쇼핑몰",
    r"접근성", r"건너뛰기", r"스킵", r"skip"
]

def search_naver_shopping(keyword: str = "기계식 키보드", headless: bool = True) -> dict:
    """
    Naver Shopping & Web 검색 자동화 시나리오:
    1. headless 모드로 접속 및 검색어 타입 (120ms human delay)
    2. 3초 대기 후 data/temp_screenshots/capture_{timestamp}.png 캡처
    3. 상위 3개 실 상품명/가격 정보 추출 (접근성/스킵 텍스트 완전 배제)
    """
    temp_dir = os.path.join(PROJECT_ROOT, "data", "temp_screenshots")
    os.makedirs(temp_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:17]
    screenshot_path = os.path.join(temp_dir, f"capture_{timestamp}.png")
    abs_screenshot_path = os.path.abspath(screenshot_path)
    
    result = {
        "success": False,
        "keyword": keyword,
        "screenshot_path": abs_screenshot_path,
        "top_products": [],
        "page_title": "",
        "error": None
    }
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                slow_mo=100,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                viewport={"width": 1400, "height": 950},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                locale="ko-KR"
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("🌐 [NaverShopping] 네이버(https://www.naver.com) 접속 중...")
            page.goto("https://www.naver.com", wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(1000)
            
            print(f"⌨️ [NaverShopping] 검색창에 '{keyword}' 사람처럼 타이핑 입력 중...")
            search_input = page.locator("input#query, input[name='query']").first
            search_input.wait_for(state="visible", timeout=10000)
            search_input.click()
            search_input.type(keyword, delay=120)
            page.wait_for_timeout(300)
            search_input.press("Enter")
            
            print("⏳ [NaverShopping] 검색 결과 로딩 후 3초 대기 중...")
            page.wait_for_timeout(3000)
            
            result["page_title"] = page.title()
            
            print(f"📸 [NaverShopping] 전체 화면 스크린샷 저장 중 ({abs_screenshot_path})...")
            page.screenshot(path=abs_screenshot_path, full_page=True)
            
            print(f"🔍 [NaverShopping] '{keyword}' 관련 상위 3개 정보 추출 중...")
            
            products = []
            
            # Find candidate elements on Naver Search / Shopping results
            links = page.locator("a").all()
            for a in links:
                try:
                    title_text = a.text_content().strip()
                    title_text = " ".join(title_text.split())
                    
                    # Filter out short or non-relevant accessibility / skip navigation titles
                    if len(title_text) >= 5:
                        # Exclude skip navigation and UI buttons
                        if any(re.search(pat, title_text, re.IGNORECASE) for pat in SKIP_PATTERNS):
                            continue
                            
                        if title_text not in [p['title'] for p in products]:
                            parent_elem = a.locator("xpath=../..")
                            container_text = parent_elem.text_content() if parent_elem.count() > 0 else ""
                            prices = re.findall(r'[\d,]{3,9}\s*원', container_text)
                            
                            price_val = prices[0] if prices else "가격 정보 확인"
                            products.append({
                                "title": title_text,
                                "price": price_val
                            })
                            if len(products) >= 5:
                                break
                except Exception:
                    continue
            
            result["top_products"] = products[:3]
            result["success"] = True
            browser.close()
            
    except Exception as e:
        print(f"❌ [NaverShopping] 오류 발생: {e}")
        result["error"] = str(e)
        
    return result


if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding="utf-8")
    print("🚀 네이버 쇼핑/웹 검색 스크린샷 딜리버리 테스트 시작...")
    res = search_naver_shopping(keyword="RTX 5080", headless=True)
    print("\n📋 [실행 결과 요약]")
    print(f"- 성공 여부: {res['success']}")
    print(f"- 스크린샷 절대경로: {res['screenshot_path']}")
    print("- 추출된 상위 항목:")
    for idx, item in enumerate(res['top_products'], 1):
        print(f"  {idx}. {item['title']} | {item['price']}")
