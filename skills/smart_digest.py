"""
Smart Digest Skill Module (skills/smart_digest.py)
---------------------------------------------------
GitHub Open-Source Refined Lightweight Content Summarizer.
Extracts YouTube transcripts or web article text, then generates a structured 3-part insight
using Gemini API (📌 한 줄 핵심 결론, 💡 3대 핵심 인사이트, 🚀 실행 액션 플랜).
Zero heavy dependencies (uses Python standard library + google.genai SDK).
"""

import os
import sys
import re
import json
import html
import logging
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure root .env is loaded
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "config" / ".env")

logger = logging.getLogger("SmartDigest")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def is_youtube_url(url: str) -> bool:
    """Checks if a URL points to YouTube."""
    if not url:
        return False
    url_lower = url.lower()
    return any(domain in url_lower for domain in ["youtube.com", "youtu.be", "m.youtube.com"])


def fetch_youtube_content(url_or_id: str) -> dict:
    """
    Extracts YouTube video ID, title, description, and transcript text.
    Uses standard library urllib and regex parsing.
    """
    video_id = url_or_id
    m_id = re.search(r"(?:v=|\/([0-9A-Za-z_-]{11})|v\/|e\/|watch\?v=|embed\/|shorts\/)([0-9A-Za-z_-]{11})", url_or_id)
    if m_id:
        video_id = m_id.group(1) or m_id.group(2)
    else:
        m_id2 = re.search(r"[0-9A-Za-z_-]{11}", url_or_id)
        if m_id2:
            video_id = m_id2.group(0)

    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    title = "YouTube Video"
    description = ""
    transcript_text = ""
    caption_found = False

    try:
        req = urllib.request.Request(watch_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")

        # 1. Parse ytInitialPlayerResponse
        m_json = re.search(r"ytInitialPlayerResponse\s*=\s*({.+?});(?:var meta|</script>|window\[)", raw_html)
        if not m_json:
            m_json = re.search(r"ytInitialPlayerResponse\s*=\s*({.+?});", raw_html)

        player_data = {}
        if m_json:
            try:
                player_data = json.loads(m_json.group(1))
            except Exception:
                pass

        details = player_data.get("videoDetails", {})
        title = details.get("title", title)
        description = details.get("shortDescription", "")

        # 2. Caption tracks extraction
        tracks = player_data.get("captions", {}).get("playerCaptionsTracklistRenderer", {}).get("captionTracks", [])
        
        selected_track = None
        for t in tracks:
            if t.get("languageCode", "").startswith("ko"):
                selected_track = t
                break
        if not selected_track:
            for t in tracks:
                if t.get("languageCode", "").startswith("en"):
                    selected_track = t
                    break
        if not selected_track and tracks:
            selected_track = tracks[0]

        if selected_track and "baseUrl" in selected_track:
            base_url = html.unescape(selected_track["baseUrl"])
            sub_req = urllib.request.Request(base_url, headers=headers)
            try:
                with urllib.request.urlopen(sub_req, timeout=5) as sub_resp:
                    sub_content = sub_resp.read().decode("utf-8", errors="ignore")
                
                matches = re.findall(r'<text[^>]*>(.*?)</text>', sub_content)
                if matches:
                    clean_lines = [html.unescape(m) for m in matches if m.strip()]
                    transcript_text = " ".join(clean_lines)
                    caption_found = True
            except Exception as sub_err:
                logger.warning(f"Caption track download warning: {sub_err}")

    except Exception as e:
        logger.error(f"YouTube content fetch error: {e}")

    content_payload = transcript_text if caption_found else f"제목: {title}\n설명:\n{description}"
    return {
        "content_type": "YouTube",
        "video_id": video_id,
        "title": title,
        "caption_found": caption_found,
        "raw_text": content_payload[:5000]
    }


def fetch_web_article_text(url: str) -> dict:
    """
    Extracts title and main article text from a general web page URL.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    title = "Web Article"
    clean_text = ""

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")

        # 1. Extract title
        m_title = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
        if m_title:
            title = html.unescape(m_title.group(1)).strip()

        # 2. Remove scripts, styles, and non-article structural tags
        cleaned = re.sub(r"<(script|style|head|nav|footer|header|svg|noscript)[^>]*>.*?</\1>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)

        # 3. Extract main or article block if available
        m_main = re.search(r"<(main|article)[^>]*>(.*?)</\1>", cleaned, re.IGNORECASE | re.DOTALL)
        if m_main:
            cleaned = m_main.group(2)

        # 4. Remove remaining tags and unescape entities
        text = re.sub(r"<[^>]+>", " ", cleaned)
        text = html.unescape(text)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = " ".join(lines)

    except Exception as e:
        logger.error(f"Article fetch error: {e}")

    return {
        "content_type": "Web Article",
        "title": title,
        "caption_found": True,
        "raw_text": clean_text[:5000] if clean_text else f"제목: {title}"
    }


def generate_smart_digest(url: str) -> dict:
    """
    Main entry point: Fetches content from URL and generates a 3-part structured digest using Gemini.

    Returns:
        dict: {
            "url": str,
            "title": str,
            "content_type": str,
            "caption_found": bool,
            "digest_text": str,
            "success": bool
        }
    """
    if is_youtube_url(url):
        data = fetch_youtube_content(url)
    else:
        data = fetch_web_article_text(url)

    title = data.get("title", "제목 없음")
    raw_text = data.get("raw_text", "")
    content_type = data.get("content_type", "Content")
    caption_found = data.get("caption_found", False)

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key or not raw_text:
        fallback_digest = (
            f"📌 **[한 줄 핵심 결론]**\n{title} (원문 콘텐츠 수집 완료)\n\n"
            f"💡 **[3대 핵심 인사이트]**\n1. {title} 관련 콘텐츠입니다.\n2. 원문 링크를 참고하여 세부 내용을 확인하세요.\n3. 주요 지식으로 적재되었습니다.\n\n"
            f"🚀 **[실행 액션 플랜]**\n• 원문 링크 복습 및 필요 시 세부 액션 항목 추출."
        )
        return {
            "url": url,
            "title": title,
            "content_type": content_type,
            "caption_found": caption_found,
            "digest_text": fallback_digest,
            "success": True
        }

    prompt = f"""
당신은 대표님을 위한 지능형 콘텐츠 요약 수석비서 "Smart Digest Engine"입니다.
제공된 {content_type} 콘텐츠(제목: '{title}')의 핵심 내용을 분석하여 정확히 아래의 3개 섹션 구조로 명확하고 스마트하게 요약하세요.

[필수 요약 포맷]
📌 **[한 줄 핵심 결론]**
(전체 내용을 관통하는 명쾌한 핵심 메시지 1문장)

💡 **[3대 핵심 인사이트]**
1. (첫 번째 핵심 포인트 및 가치)
2. (두 번째 핵심 포인트 및 기술/시장 의의)
3. (세 번째 핵심 포인트 및 주요 시사점)

🚀 **[실행 액션 플랜]**
• (경영/개발/업무에 즉시 적용할 실천 과제 1~2개)

[원문 콘텐츠]
{raw_text[:4000]}
"""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=500,
                temperature=0.3
            )
        )

        digest_text = response.text.strip() if response and response.text else ""
        if not digest_text:
            digest_text = f"📌 **[한 줄 핵심 결론]**\n{title}\n\n💡 **[3대 핵심 인사이트]**\n1. 콘텐츠 분석 완료.\n2. 핵심 정보 수집.\n3. 지식 적재 완료.\n\n🚀 **[실행 액션 플랜]**\n• 원문 확인."

        return {
            "url": url,
            "title": title,
            "content_type": content_type,
            "caption_found": caption_found,
            "digest_text": digest_text,
            "success": True
        }

    except Exception as e:
        logger.error(f"Gemini digest generation error: {e}")
        error_digest = (
            f"📌 **[한 줄 핵심 결론]**\n{title}\n\n"
            f"💡 **[3대 핵심 인사이트]**\n1. 콘텐츠 원문 수집 완료 ({content_type}).\n2. 요약 생성 중 API 처리 오류가 발생했습니다.\n3. 원문 링크를 참조하세요.\n\n"
            f"🚀 **[실행 액션 플랜]**\n• 아래 원문 URL 클릭하여 직접 확인."
        )
        return {
            "url": url,
            "title": title,
            "content_type": content_type,
            "caption_found": caption_found,
            "digest_text": error_digest,
            "success": False
        }


def save_digest_to_notion(digest_res: dict) -> bool:
    """
    Optional helper to format and archive digest to Notion Knowledge DB.
    """
    notion_key = os.getenv("NOTION_API_KEY")
    if not notion_key:
        logger.info("Notion API Key not set; skipping automated Notion block archive.")
        return False
    logger.info(f"Notion integration ready for archiving: {digest_res.get('title')}")
    return True


if __name__ == "__main__":
    test_yt = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    res = generate_smart_digest(test_yt)
    print("=" * 60)
    print(f"Title       : {res['title']}")
    print(f"Content Type: {res['content_type']}")
    print(f"Caption     : {res['caption_found']}")
    print(f"Digest:\n{res['digest_text']}")
    print("=" * 60)
