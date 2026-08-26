import os
import sys
import asyncio
import logging

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from core.agent_engine import AgentEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_dynamic_tiering")

async def test_classification():
    logger.info("=== [1. Complexity Classification Test] ===")
    engine = AgentEngine()

    # Low Complexity Test
    comp_low, reason_low = await engine.classify_complexity("내일 일정 알려줘")
    logger.info(f"Input 1: '내일 일정 알려줘' -> Result: {comp_low} ({reason_low})")
    assert comp_low == "LOW"

    # High Complexity Test
    comp_high, reason_high = await engine.classify_complexity("구글 뉴스 헤드라인 캡처하고 내일 일정 확인해서 노션에 메모해 줘")
    logger.info(f"Input 2: '구글 뉴스 헤드라인 캡처하고 내일 일정 확인해서 노션에 메모해 줘' -> Result: {comp_high} ({reason_high})")
    assert comp_high == "HIGH"

async def test_tiering_execution():
    logger.info("=== [2. Fast Track vs Deep Track Execution Test] ===")
    engine = AgentEngine()

    # Fast Track Execution
    logger.info("Testing Fast Track Execution...")
    success_low, report_low, art_low = await engine.process_instruction("내일 일정 알려줘")
    logger.info(f"Fast Track Result (Success={success_low}):\n{report_low}")
    assert success_low is True

    # Deep Track Execution
    logger.info("Testing Deep Track Execution...")
    success_high, report_high, art_high = await engine.process_instruction("구글 뉴스 메인 캡처하고 내일 일정 확인해서 노션에 메모해 줘")
    logger.info(f"Deep Track Result (Success={success_high}):\n{report_high}")
    assert success_high is True

if __name__ == "__main__":
    asyncio.run(test_classification())
    asyncio.run(test_tiering_execution())
