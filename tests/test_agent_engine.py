import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, "config", ".env"))
logging.basicConfig(level=logging.INFO)

from core.agent_engine import AgentEngine

async def main():
    engine = AgentEngine()
    print("=== [1] Fast Bypass Simple Chat Test ===")
    success, fast_reply, _ = await engine.process_instruction("알파야?")
    print(f"Fast Chat Success: {success} | Reply: {fast_reply}")
    assert success is True
    print("✓ Fast Bypass Simple Chat Test Passed!")
    print("=" * 50)
    await asyncio.sleep(3)

    print("\n=== [2] Agent Engine Execution Test (ReAct Loop + 2-Track Logging) ===")
    success, result, _ = await engine.process_instruction("내일 일정 확인해줘")
    print(f"Success: {success}")
    print(f"Result:\n{result}")
    print("=" * 50)
    await asyncio.sleep(3)

    print("\n=== [2-1] Universal Search Tool Test (YouTube Recommendation) ===")
    success, yt_result, _ = await engine.process_instruction("강남역 일식 초밥 맛집 추천해줘")
    print(f"Universal Search Success: {success}")
    print(f"Result:\n{yt_result}")
    assert success is True
    print("✓ Universal Search Tool Test Passed!")
    print("=" * 50)
    await asyncio.sleep(3)

    print("\n=== [2-2] Intelligent Clarification Mode Test ===")
    success, clar_result, _ = await engine.process_instruction("볼만한 영상 찾아줘")
    print(f"Clarification Success: {success}")
    print(f"Result:\n{clar_result}")
    assert success is True
    assert "1️⃣" in clar_result or "1." in clar_result
    print("✓ Intelligent Clarification Mode Test Passed!")
    print("=" * 50)
    await asyncio.sleep(3)

    print("\n=== [3] Track 1 Local Daily Context Log Verification ===")
    context = engine.load_today_context()
    print(f"Today's Daily Context Snippet:\n{context}")
    assert len(context) > 0
    print("✓ Track 1 Local Daily Context Logging Verified!")

    print("\n=== [4] Day-End Routine & Workspace Cleanup Test ===")
    # Create a dummy temp file to test cleanup
    dummy_temp = os.path.join(PROJECT_ROOT, "temp_test_audio.ogg")
    with open(dummy_temp, "w") as f:
        f.write("dummy audio content")

    success, day_end_report, _ = await engine.process_instruction("오늘 작업 끝")
    print(f"Day-End Success: {success}")
    print(f"Report:\n{day_end_report}")
    assert success is True
    assert not os.path.exists(dummy_temp)
    print("✓ Day-End Routine Cleanup Verified!")

    print("\n=== [5] Security & Sensitive Data Masking Test ===")
    from core.agent_engine import mask_sensitive_info
    sample_text = "API Key: AQ.Ab8RN6L3fjFB2k47LHFE4GGDiUtv_mv9anOMD37-D696_wKgDg, 주민번호: 900101-1234567"
    masked = mask_sensitive_info(sample_text)
    print(f"Original: {sample_text}")
    print(f"Masked:   {masked}")
    assert "AQ.Ab8RN6L3fjFB2k47LHFE4GGDiUtv_mv9anOMD37-D696_wKgDg" not in masked
    assert "900101-1234567" not in masked
    assert "[SECRET_MASKED]" in masked
    assert "******-*******" in masked
    print("✓ Security Sensitive Data Masking Verified!")

if __name__ == "__main__":
    asyncio.run(main())
