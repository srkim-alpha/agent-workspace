"""
Interaction Guard Module (core/interaction_guard.py)
------------------------------------------------------
Pre-filters ambiguous or non-specific user queries (e.g., "영상 추천해줘", "자료 찾아줘")
before triggering heavy browser automation or complex routing pipelines.
Delivers structured clarification options in under 2 seconds.
"""

import sys
import time
import re

# Configure UTF-8 stdout encoding if available
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# Stopwords and generic verbs that do not constitute a specific topic by themselves
GENERIC_ACTION_WORDS = [
    "추천해줘", "추천해 줘", "추천해", "추천", "찾아줘", "찾아 줘", "찾아", "자료 찾아줘",
    "영상 추천해줘", "영상 추천해", "영상 찾아줘", "영상 보여줘", "알려줘", "볼만한 거",
    "유튜브 영상 추천해줘", "유튜브 영상 추천", "유튜브 추천", "검색해줘", "검색해 줘",
    "검색해", "조회해줘", "조회해 줘", "보여줘", "보여 줘", "해줘"
]

GENERIC_CATEGORY_WORDS = [
    "유튜브", "youtube", "영상", "동영상", "비디오", "자료", "검색", "정보", "내용"
]


def check_ambiguity(user_input: str) -> dict:
    """
    Analyzes whether the user query is ambiguous (lacking concrete topic/URL/keywords).

    Args:
        user_input (str): The raw input text from user or STT transcript.

    Returns:
        dict: {
            "is_ambiguous": bool,
            "reason": str,
            "category": str or None,
            "clarification_message": str or None,
            "latency_ms": float
        }
    """
    start_time = time.perf_counter()

    if not user_input or not user_input.strip():
        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "is_ambiguous": False,
            "reason": "Empty input",
            "category": None,
            "clarification_message": None,
            "latency_ms": latency_ms
        }

    text = user_input.strip()
    text_lower = text.lower()

    # 1. URL check: If input contains explicit URL or domain, it's not ambiguous
    url_pattern = r"(https?://|www\.|\.com|\.net|\.org|\.kr|\.co\.kr|\.io|\.dev)"
    if re.search(url_pattern, text_lower):
        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "is_ambiguous": False,
            "reason": "Explicit URL present",
            "category": None,
            "clarification_message": None,
            "latency_ms": latency_ms
        }

    # 2. Check if text expresses recommendation or generic search intent
    is_recommendation_intent = any(kw in text_lower for kw in ["추천", "볼만한", "어떤게 좋", "무슨", "볼만한거"])
    is_search_intent = any(kw in text_lower for kw in ["찾아줘", "검색해줘", "자료", "조회해줘"])

    if not (is_recommendation_intent or is_search_intent):
        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "is_ambiguous": False,
            "reason": "Not an exploration/recommendation query",
            "category": None,
            "clarification_message": None,
            "latency_ms": latency_ms
        }

    # 3. Extract core topic by stripping generic action & category words
    cleaned = text_lower
    for word in GENERIC_ACTION_WORDS + GENERIC_CATEGORY_WORDS:
        cleaned = cleaned.replace(word.lower(), "")

    cleaned_topic = cleaned.strip()

    # If the remaining topic is negligible or empty, it is ambiguous!
    # E.g. "유튜브 영상 추천해줘" -> cleaned_topic: "" -> AMBIGUOUS
    # E.g. "2026 AI 에이전트 트렌드 유튜브 검색해줘" -> cleaned_topic: "2026 ai 에이전트 트렌드" -> NOT AMBIGUOUS
    if len(cleaned_topic) <= 2:
        category = "video_recommendation" if ("영상" in text_lower or "유튜브" in text_lower or "youtube" in text_lower) else "general_data"
        
        clarification_msg = _build_clarification_message(category)
        latency_ms = (time.perf_counter() - start_time) * 1000

        return {
            "is_ambiguous": True,
            "reason": "Lack of specific search target or topic keyword",
            "category": category,
            "clarification_message": clarification_msg,
            "latency_ms": latency_ms
        }

    latency_ms = (time.perf_counter() - start_time) * 1000
    return {
        "is_ambiguous": False,
        "reason": f"Specific topic detected: '{cleaned_topic}'",
        "category": None,
        "clarification_message": None,
        "latency_ms": latency_ms
    }


def _build_clarification_message(category: str) -> str:
    """Generates structured options with option numbers."""
    if category == "video_recommendation":
        return (
            "💡 **대표님, 어떤 분야의 유튜브 영상을 찾으시나요?**\n"
            "원하시는 번호나 키워드를 말씀해 주시면 즉시 최적의 콘텐츠를 찾아드리겠습니다.\n\n"
            "1️⃣ 🤖 **최신 AI & 테크 트렌드** (예: 2026 AI 에이전트, LLM 활용법)\n"
            "2️⃣ 📈 **주식·재테크 & 글로벌 경제** (예: 증시 전망, 환율 분석)\n"
            "3️⃣ 🎧 **몰입·딥워크 교양 & ASMR** (예: Lofi 백그라운드 음악)\n"
            "4️⃣ 💡 **자기계발 & 업무 자동화 꿀팁** (예: 파이썬 자동화, 시간관리)"
        )
    else:
        return (
            "💡 **대표님, 어떤 주제의 자료를 검색해 드릴까요?**\n"
            "원하시는 번호나 상세 키워드를 입력해 주시면 신속히 수집하여 보고드리겠습니다.\n\n"
            "1️⃣ 📰 **최신 뉴스 & 글로벌 산업 동향**\n"
            "2️⃣ 💻 **개발 코드 & 기술 아키텍처 문서**\n"
            "3️⃣ 📊 **시장 조사 & 경제 동향 리포트**\n"
            "4️⃣ 🛒 **상품 정보 및 가격·최저가 비교**"
        )


if __name__ == "__main__":
    # Self-test
    res1 = check_ambiguity("유튜브 영상 추천해줘")
    print(f"[Test 1] Ambiguous check: {res1['is_ambiguous']} (Latency: {res1['latency_ms']:.2f}ms)")
    if res1["is_ambiguous"]:
        print(f"Clarification Msg:\n{res1['clarification_message']}\n")

    res2 = check_ambiguity("2026 AI 에이전트 트렌드 유튜브 검색해줘")
    print(f"[Test 2] Ambiguous check: {res2['is_ambiguous']} (Latency: {res2['latency_ms']:.2f}ms, Reason: {res2['reason']})")
