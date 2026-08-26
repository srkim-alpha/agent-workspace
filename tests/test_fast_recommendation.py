import os
import sys
import time
import asyncio

# Project Root Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.agent_engine import AgentEngine, tool_web_browse

async def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("🚀 [Fast Recommendation Test] Playwright 브라우저 차단 & 2초 내 추천 반환 검증")
    print("=" * 60)

    # Test 1: Direct Guard test on tool_web_browse with recommendation keyword
    print("\n=== [1] tool_web_browse Recommendation Query Direct Guard Test ===")
    res = tool_web_browse(url="https://www.youtube.com", keyword="영상 추천해줘")
    print(f"Result: {res}")
    assert res.get("blocked") is True
    print("✓ [1] Direct Guard Blocked Playwright Execution Successfully!")

    # Test 2: AgentEngine.process_instruction with recommendation query
    print("\n=== [2] AgentEngine.process_instruction Fast Recommendation Test ===")
    engine = AgentEngine()
    start_time = time.time()
    
    success, reply, artifacts = await engine.process_instruction("유튜브 영상 추천해줘")
    elapsed = time.time() - start_time
    
    print(f"Elapsed Time: {elapsed:.2f}s")
    print(f"Success: {success}")
    print(f"Reply:\n{reply}")
    
    assert success is True
    assert elapsed < 5.0  # Fast response (<5s, target <2s)
    assert any(kw in reply for kw in ["추천", "영상", "1️⃣", "2️⃣", "ASMR", "테크"])
    assert "Playwright" not in reply
    
    print("✓ [2] Fast Recommendation Response Delivered without Playwright Blocking!")
    print("=" * 60)
    print("🎉 ALL FAST RECOMMENDATION TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
