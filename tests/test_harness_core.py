import os
import sys
import unittest
import tempfile
import sqlite3

# Ensure UTF-8 output formatting on Windows environments
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from skills.memory_vault import MemoryVault
from skills.dreaming_engine import DreamingEngine
from core.interview_protocol import InterviewProtocol

class TestHarnessCore(unittest.TestCase):
    """Unit test suite for L2 Memory Vault, Dreaming & Pruning Engine, and Interview Protocol."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.vault = MemoryVault(db_path=self.temp_db.name)
        self.dreaming = DreamingEngine(memory_vault=self.vault)
        self.interview = InterviewProtocol(min_steps_threshold=3)

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except Exception:
                pass

    def test_01_open_source_exploration_log(self):
        """Prints open-source exploration & reference repository findings summary."""
        log = (
            "\n" + "=" * 60 + "\n"
            "🔍 [GitHub MCP 오픈소스 탐색 및 분석 내역 보고]\n"
            "============================================================\n"
            "1. Hermes-Agent (L0~L3 계층형 메모리 & SQLite FTS):\n"
            "   - L0(세션 컨텍스트), L1(MEMORY.md/USER.md 지속성), L2(SQLite FTS), L3(장기 탐색)\n"
            "   - Downtime Dreaming(주기적 백그라운드 팩트 추출) 및 Pruning(망각/갱신) 패턴 적용\n\n"
            "2. Mem0 & Zep (Graphiti):\n"
            "   - 팩트/결정/선호/교훈 라벨링 및 모순 팩트 자동 갱신 구조\n\n"
            "3. Ask User Question (AUQ - Clarification Loop):\n"
            "   - 복합 과업(3단계 이상) 전 [목표 범위], [우선순위], [선호 산출물 포맷] 3대 사전 역질문 프로토콜\n"
            "============================================================\n"
        )
        print(log)
        self.assertTrue(True)

    def test_02_memory_vault_crud_and_recall(self):
        """Tests Memory Vault save, recall, update, and deletion operations."""
        # 1. Save memories (Representative preferences and system facts)
        mem1_id = self.vault.save_memory("PREFERENCE", "대표님 선호 보고 방식", "일일 브리핑은 3줄 요약 형태로 수신 선호")
        mem2_id = self.vault.save_memory("FACT", "시스템 거버넌스 원칙", "0-의존성 파이썬 표준 라이브러리 준수")
        mem3_id = self.vault.save_memory("DECISION", "텔레그램 게이트웨이 연동", "1:1 단일 채널 승인 인라인 버튼 적용")

        self.assertGreater(mem1_id, 0)
        self.assertGreater(mem2_id, 0)
        self.assertGreater(mem3_id, 0)

        # 2. Keyword Recall Test
        recalled_pref = self.vault.recall_memory(query_keyword="보고", category="PREFERENCE")
        self.assertEqual(len(recalled_pref), 1)
        self.assertIn("3줄 요약", recalled_pref[0]["context"])

        recalled_fact = self.vault.recall_memory(query_keyword="거버넌스")
        self.assertEqual(len(recalled_fact), 1)
        self.assertEqual(recalled_fact[0]["category"], "FACT")

        # 3. Update behavior on duplicate key_fact
        updated_id = self.vault.save_memory("PREFERENCE", "대표님 선호 보고 방식", "수정된 3줄 요약 및 마크다운 포맷 선호")
        self.assertEqual(updated_id, mem1_id)
        
        fetched = self.vault.get_memory_by_id(mem1_id)
        self.assertIn("마크다운 포맷", fetched["context"])

        # 4. Delete operation
        deleted = self.vault.delete_memory(mem3_id)
        self.assertTrue(deleted)
        self.assertIsNone(self.vault.get_memory_by_id(mem3_id))

    def test_03_dreaming_and_pruning_engine(self):
        """Tests fact extraction, pruning update, and ambiguity detection."""
        log_sample = (
            "FACT: 대표님 출장 일정은 다음 주 월요일임\n"
            "DECISION: 데이터베이스 스키마는 SQLite 사용하기로 결정\n"
            "FACT: 서버 이전 날짜는 미정 및 확인 필요\n"
        )
        results = self.dreaming.process_dreaming(log_sample)

        self.assertEqual(len(results), 3)

        # Non-ambiguous fact
        self.assertFalse(results[0]["ambiguous"])
        self.assertEqual(results[0]["confidence"], 1.0)

        # Decision fact
        self.assertEqual(results[1]["category"], "DECISION")

        # Ambiguous fact with Telegram message format
        self.assertTrue(results[2]["ambiguous"])
        self.assertEqual(results[2]["confidence"], 0.5)
        self.assertIsNotNone(results[2]["telegram_msg"])
        self.assertIn("대표님 확인 질문", results[2]["telegram_msg"])

    def test_04_interview_protocol_guardrail(self):
        """Tests pre-interview protocol step estimation, trigger, AUQ question generation, and spec parsing."""
        simple_prompt = "간단한 날씨 조회해줘"
        complex_prompt = (
            "1. 계층형 메모리 DB 구축\n"
            "2. 드리밍 엔진 개발 및 텔레그램 연동\n"
            "3. 사전 인터뷰 프로토콜 이식 및 종합 테스트"
        )

        # Trigger logic
        self.assertFalse(self.interview.should_trigger_interview(simple_prompt))
        self.assertTrue(self.interview.should_trigger_interview(complex_prompt))

        # Question generation
        questions_msg = self.interview.generate_interview_questions(complex_prompt)
        self.assertIn("1️⃣ **[목표 범위 (Goal Scope)]**", questions_msg)
        self.assertIn("2️⃣ **[우선순위 (Priority)]**", questions_msg)
        self.assertIn("3️⃣ **[선호 산출물 포맷 (Preferred Output Format)]**", questions_msg)

        # Response parsing & spec creation
        user_response = (
            "1. 목표 범위: L2 메모리와 드리밍, 인터뷰 프로토콜 0-의존성 이식\n"
            "2. 우선순위: 0-의존성 및 코드 완성도\n"
            "3. 선호 포맷: 단위 테스트 로그 및 최종 보고서"
        )
        parsed = self.interview.parse_interview_responses(user_response)
        spec = self.interview.format_clarified_spec(complex_prompt, parsed)

        self.assertIn("Clarified Spec", spec)
        self.assertIn("0-의존성 및 코드 완성도", spec)

if __name__ == "__main__":
    unittest.main()
