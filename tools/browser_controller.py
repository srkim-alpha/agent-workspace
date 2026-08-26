import os
import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def capture_page(
    url: str = "https://www.naver.com",
    output_path: str = None,
    keyword: str = None,
    headless: bool = True,
    full_page: bool = True
) -> dict:
    """
    Playwright 브라우저 조종 & 고화질 스크린샷 딜리버리 인터페이스.
    
    Args:
        url (str): 접속할 Target URL (기본: Naver)
        output_path (str, optional): 스크린샷 저장 경로. 지정되지 않을 경우 data/temp_screenshots/capture_{timestamp}.png 사용.
        keyword (str, optional): 검색어 입력 시 인간 모사 타이핑(120ms) 및 엔터 실행.
        headless (bool): 백그라운드 구동 여부 (기본값 True)
        full_page (bool): 전체 화면 캡처 여부 (기본값 True)
        
    Returns:
        dict: {
            "success": bool,
            "title": str,
            "url": str,
            "screenshot_path": str (절대 경로),
            "error": str or None
        }
    """
    # 1. 저장 디렉토리 및 파일명 설정
    temp_dir = os.path.join(PROJECT_ROOT, "data", "temp_screenshots")
    os.makedirs(temp_dir, exist_ok=True)
    
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:17]
        output_path = os.path.join(temp_dir, f"capture_{timestamp}.png")
        
    abs_screenshot_path = os.path.abspath(output_path)
    
    result = {
        "success": False,
        "title": "",
        "url": url,
        "screenshot_path": abs_screenshot_path,
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
            
            print(f"🌐 [BrowserController] Connecting to: {url} (headless={headless})")
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(1000)
            
            # 검색어 키워드가 지정된 경우 (검색창 자동 타이핑)
            if keyword:
                print(f"⌨️ [BrowserController] Searching keyword: '{keyword}' (human delay 120ms)")
                search_input = page.locator("input#query, input[name='query'], input[type='search'], input[type='text']").first
                if search_input.count() > 0:
                    search_input.wait_for(state="visible", timeout=5000)
                    search_input.click()
                    search_input.type(keyword, delay=120)
                    page.wait_for_timeout(300)
                    search_input.press("Enter")
                    page.wait_for_timeout(2500)
                    
            title = page.title()
            result["title"] = title
            result["url"] = page.url
            print(f"📄 [BrowserController] Page Title: '{title}' | Current URL: {page.url}")
            
            # 고화질 스크린샷 캡처
            page.screenshot(path=abs_screenshot_path, full_page=full_page)
            print(f"📸 [BrowserController] Screenshot saved to absolute path: {abs_screenshot_path}")
            
            browser.close()
            result["success"] = True
            
    except Exception as e:
        print(f"❌ [BrowserController] Error during capture_page: {e}")
        result["error"] = str(e)
        
    return result

def run_browser_test(target_url: str = "https://www.naver.com", headless: bool = True) -> dict:
    return capture_page(url=target_url, headless=headless)

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding="utf-8")
    print("🚀 [BrowserController] capture_page 스크린샷 딜리버리 테스트 시작...")
    res = capture_page(url="https://www.naver.com", keyword="RTX 5080", headless=True)
    print("📋 테스트 결과:")
    print(res)
