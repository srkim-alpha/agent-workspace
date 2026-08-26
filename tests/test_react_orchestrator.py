import os
import sys
import asyncio
import logging

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from core.agent_engine import AgentEngine, tool_calendar, tool_web_browse, tool_shopping_search, tool_notion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_react_orchestrator")

async def test_tools_direct():
    logger.info("=== [1. Direct Tool Unit Tests] ===")
    
    # Calendar Tool
    cal_res = tool_calendar(action="query", query="tomorrow")
    logger.info(f"tool_calendar result:\n{cal_res[:100]}...")
    assert "내일" in cal_res or "일정" in cal_res or "없습니다" in cal_res

    # Web Browse Tool
    web_res = tool_web_browse(url="https://news.google.com")
    logger.info(f"tool_web_browse result: {web_res}")
    assert web_res.get("success") is True

    # Notion Tool
    notion_res = tool_notion(action="memo", title="ReAct 테스트 메모", content="ReAct 자율 오케스트레이터 검증 완수")
    logger.info(f"tool_notion result: {notion_res}")
    assert "성공" in notion_res or "완료" in notion_res

async def test_react_orchestrator_multi_instruction():
    logger.info("=== [2. ReAct Multi-Instruction Orchestration Test] ===")
    engine = AgentEngine()
    
    user_instruction = "내일 일정 확인하고, 구글 뉴스 메인 헤드라인 캡처해서 노션에 메모해 줘"
    logger.info(f"Test Instruction: '{user_instruction}'")
    
    success, report, artifacts = await engine.process_instruction(user_instruction)
    
    logger.info(f"Process Result: success={success}")
    logger.info(f"Report Text:\n{report}")
    logger.info(f"Artifacts Generated: {artifacts}")
    
    assert success is True
    assert len(report) > 0
    logger.info("SUCCESS: ReAct Orchestrator integration test passed!")

if __name__ == "__main__":
    asyncio.run(test_tools_direct())
    asyncio.run(test_react_orchestrator_multi_instruction())
