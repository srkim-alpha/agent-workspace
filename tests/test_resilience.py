import os
import sys
import asyncio
import logging
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO)

from core.resilience_manager import (
    safe_gemini_call,
    tool_timeout_guard,
    execute_tool_with_resilience,
    sanitize_user_facing_error,
    FALLBACK_ERROR_MESSAGE,
)


async def main():
    print("=== [1] Safe Gemini Call Exponential Backoff & Error Sanitization Test ===")
    attempt_counter = 0

    @safe_gemini_call(max_retries=3, initial_delay=0.5, backoff_factor=1.5)
    async def mock_failing_gemini_api():
        nonlocal attempt_counter
        attempt_counter += 1
        print(f"  -> Executing mock API call (attempt {attempt_counter})...")
        raise Exception("429 RESOURCE_EXHAUSTED: You exceeded your current quota.")

    start_t = time.time()
    res = await mock_failing_gemini_api()
    elapsed = time.time() - start_t
    print(f"Result: {res}")
    print(f"Total Attempts: {attempt_counter} | Elapsed Time: {elapsed:.2f}s")

    assert attempt_counter == 3, "Should retry exactly 3 times"
    assert res == FALLBACK_ERROR_MESSAGE, "Should return polite Korean fallback message"
    assert "RESOURCE_EXHAUSTED" not in res, "Must not leak raw JSON error"
    print("✓ [1] Exponential Backoff & Error Sanitization Test Passed!")
    print("=" * 60)

    print("\n=== [2] Tool 15s Timeout Guard Test ===")

    async def mock_slow_tool(delay: float):
        print(f"  -> Mock tool sleeping for {delay}s...")
        await asyncio.sleep(delay)
        return "Slow Tool Completed"

    res_timeout = await execute_tool_with_resilience(mock_slow_tool, {"delay": 2.0}, timeout_seconds=1.0)
    print(f"Timeout Result:\n{res_timeout}")
    assert "1초 타임아웃" in res_timeout or "타임아웃" in res_timeout or "대화형 브리핑" in res_timeout
    print("✓ [2] Tool Timeout Guard Test Passed!")
    print("=" * 60)

    print("\n=== [3] Sensitive Data & Raw Error Sanitization Test ===")
    raw_error_with_key = "429 RESOURCE_EXHAUSTED: key=AIzaSyA1234567890_SECRET_KEY, limit=20"
    sanitized = sanitize_user_facing_error(raw_error_with_key)
    print(f"Raw Input:  {raw_error_with_key}")
    print(f"Sanitized:  {sanitized}")

    assert "AIzaSyA1234567890_SECRET_KEY" not in sanitized
    assert "429" not in sanitized
    assert "RESOURCE_EXHAUSTED" not in sanitized
    print("✓ [3] Sensitive Data & Raw Error Sanitization Test Passed!")
    print("=" * 60)

    print("\n=== [4] STT 429 Retry & Custom Fallback Notice Test ===")
    stt_attempts = 0

    @safe_gemini_call(
        max_retries=3,
        initial_delay=0.2,
        backoff_factor=1.1,
        custom_fallback="⚠️ 현재 음성 처리 서버 요청이 집중되어 지연되고 있습니다. 10초 뒤 다시 말씀해 주시면 즉시 처리하겠습니다."
    )
    async def mock_stt_failing():
        nonlocal stt_attempts
        stt_attempts += 1
        raise Exception("429 RESOURCE_EXHAUSTED: Please retry in 0.1s.")

    stt_res = await mock_stt_failing()
    print(f"STT Fallback Result:\n{stt_res}")
    assert stt_attempts == 3
    assert stt_res == "⚠️ 현재 음성 처리 서버 요청이 집중되어 지연되고 있습니다. 10초 뒤 다시 말씀해 주시면 즉시 처리하겠습니다."
    assert "RESOURCE_EXHAUSTED" not in stt_res
    print("✓ [4] STT 429 Retry & Custom Fallback Notice Test Passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
