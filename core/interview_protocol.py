import re
import json
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

COMPLEXITY_KEYWORDS = ["구축", "이식", "연동", "개발", "배포", "리팩토링", "자동화", "엔진", "파이프라인"]

class InterviewProtocol:
    """Pre-Interview (Ask User Question) Protocol Guardrail for complex multi-step tasks."""

    def __init__(self, min_steps_threshold: int = 3):
        self.min_steps_threshold = min_steps_threshold

    def estimate_steps(self, task_prompt: str) -> int:
        """Estimates task steps based on bullet points, numbered lists, or action verbs."""
        # Check explicit numbered items like "1.", "2.", "3.", etc.
        numbered = re.findall(r"^\s*\d+[\.\)]\s+", task_prompt, re.MULTILINE)
        if len(numbered) > 0:
            return len(numbered)

        # Check action verbs / keywords
        action_count = sum(1 for kw in COMPLEXITY_KEYWORDS if kw in task_prompt)
        return max(1, action_count)

    def should_trigger_interview(self, task_prompt: str, estimated_steps: Optional[int] = None) -> bool:
        """Determines if pre-interview clarification is required (3+ steps or complex task)."""
        steps = estimated_steps if estimated_steps is not None else self.estimate_steps(task_prompt)
        return steps >= self.min_steps_threshold

    def generate_interview_questions(self, task_prompt: str) -> str:
        """Generates structured 3-question Ask User Question (AUQ) pre-interview message."""
        steps = self.estimate_steps(task_prompt)
        msg = (
            f"📋 **[알파 사전 인터뷰 프로토콜 - Ask User Question]**\n\n"
            f"대표님, 요청하신 과업 is multi-step complex task (추정 단계: {steps}단계).\n"
            f"실행 전 요구사항을 명확히 확립하기 위해 다음 3가지 질문을 드립니다:\n\n"
            f"1️⃣ **[목표 범위 (Goal Scope)]**\n"
            f"   • 이번 과업에서 반드시 완성해야 할 최우선 핵심 범위는 무엇입니까?\n\n"
            f"2️⃣ **[우선순위 (Priority)]**\n"
            f"   • [개발 속도 / 완성도·안정성 / 0-의존성 경량성] 중 최우선 고려 요소는 무엇입니까?\n\n"
            f"3️⃣ **[선호 산출물 포맷 (Preferred Output Format)]**\n"
            f"   • 결과물 형태로 [코드 파일만 / 요약 보고서 / 단위 테스트 실행 로그] 중 어느 것을 선호하십니까?\n\n"
            f"=====================================\n"
            f"💡 답변을 간략히 주시면 요구사항에 맞춰 완벽히 집행하겠습니다."
        )
        return msg

    def parse_interview_responses(self, response_text: str) -> Dict[str, str]:
        """Parses user response into structured requirement attributes."""
        parsed = {
            "scope": "전체 기능 및 핵심 범위",
            "priority": "완성도 및 0-의존성 안정성",
            "output_format": "코드 파일 및 단위 테스트 로그"
        }
        lines = [line.strip() for line in response_text.split("\n") if line.strip()]
        for line in lines:
            if "1" in line or "범위" in line or "목표" in line:
                parsed["scope"] = line.split(":", 1)[-1].strip() if ":" in line else line
            elif "2" in line or "우선" in line or "속도" in line or "안정성" in line:
                parsed["priority"] = line.split(":", 1)[-1].strip() if ":" in line else line
            elif "3" in line or "포맷" in line or "산출물" in line or "보고서" in line or "코드" in line:
                parsed["output_format"] = line.split(":", 1)[-1].strip() if ":" in line else line

        return parsed

    def format_clarified_spec(self, task_prompt: str, responses: Dict[str, str]) -> str:
        """Formats the final clarified task specification for session binding."""
        spec = (
            f"🎯 **[사전 인터뷰 확정 요구사항 명세 (Clarified Spec)]**\n\n"
            f"• **요청 과업**: {task_prompt.strip()[:100]}...\n"
            f"• **[목표 범위]**: {responses.get('scope')}\n"
            f"• **[우선순위]**: {responses.get('priority')}\n"
            f"• **[선호 포맷]**: {responses.get('output_format')}\n\n"
            f"가드레일 확정 완료. 과업 실행을 개시합니다."
        )
        return spec
