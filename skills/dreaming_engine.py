import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from skills.memory_vault import MemoryVault, get_current_iso_time

logger = logging.getLogger(__name__)

AMBIGUITY_KEYWORDS = ["미정", "확인 필요", "모호", "추후 결정", "TBD", "불확실", "변경 여지", "?"]

CATEGORY_PATTERNS = [
    (r"(?:DECISION|결정|방침|방향성)[:\-]\s*(.+)", "DECISION"),
    (r"(?:PREFERENCE|선호|취향|스타일)[:\-]\s*(.+)", "PREFERENCE"),
    (r"(?:LESSON|교훈|피드백|학습|개선점)[:\-]\s*(.+)", "LESSON"),
    (r"(?:FACT|팩트|사실|확정|정보)[:\-]\s*(.+)", "FACT"),
]

NATURAL_DECISION_REGEX = r"([가-힣a-zA-Z0-9\s]+(?:하기로 결정|방침으로 확정|결정함|방침임))"
NATURAL_PREFERENCE_REGEX = r"([가-힣a-zA-Z0-9\s]+(?:선호함|선호하심|좋아함|방식 선호|스타일 선호))"
NATURAL_LESSON_REGEX = r"([가-힣a-zA-Z0-9\s]+(?:주의 필요|개선해야 함|피드백 반영|학습됨|교훈))"

class DreamingEngine:
    """Dreaming (fact extraction) & Pruning (conflict update/ambiguity detection) Engine."""

    def __init__(self, memory_vault: Optional[MemoryVault] = None):
        self.vault = memory_vault or MemoryVault()

    def is_ambiguous(self, text: str) -> bool:
        """Checks if a fact or context statement contains ambiguous keywords."""
        return any(kw in text for kw in AMBIGUITY_KEYWORDS)

    def extract_facts_from_text(self, text_log: str) -> List[Dict[str, Any]]:
        """Parses session/work log text and extracts structured candidate memories."""
        extracted = []
        lines = [line.strip() for line in text_log.split("\n") if line.strip()]

        for line in lines:
            category_found = None
            key_fact = None

            # 1. Pattern matching (Explicit labels)
            for pattern, cat in CATEGORY_PATTERNS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    key_fact = match.group(1).strip()
                    category_found = cat
                    break

            # 2. Natural language pattern matching if no explicit label found
            if not category_found:
                if re.search(NATURAL_DECISION_REGEX, line):
                    category_found = "DECISION"
                    key_fact = line
                elif re.search(NATURAL_PREFERENCE_REGEX, line):
                    category_found = "PREFERENCE"
                    key_fact = line
                elif re.search(NATURAL_LESSON_REGEX, line):
                    category_found = "LESSON"
                    key_fact = line
                elif any(kw in line for kw in ["대표님", "대표", "방침", "원칙", "보안"]):
                    category_found = "FACT"
                    key_fact = line

            if category_found and key_fact:
                extracted.append({
                    "category": category_found,
                    "key_fact": key_fact,
                    "context": line,
                    "is_ambiguous": self.is_ambiguous(key_fact) or self.is_ambiguous(line)
                })

        return extracted

    def prune_and_save(self, category: str, key_fact: str, context: str = "") -> Dict[str, Any]:
        """
        Prunes conflicting or old memories and saves the updated memory record.
        Detects ambiguity and triggers Telegram clarification format if needed.
        """
        ambiguous = self.is_ambiguous(key_fact) or self.is_ambiguous(context)
        confidence = 0.5 if ambiguous else 1.0

        # Check existing memories for conflict or overlap in key terms
        # Extract main nouns/keywords from key_fact for recall search
        clean_words = [w for w in re.findall(r"[가-힣a-zA-Z0-9]+", key_fact) if len(w) >= 2]
        query_kw = clean_words[0] if clean_words else key_fact[:5]

        existing_memories = self.vault.recall_memory(query_keyword=query_kw, category=category)
        
        target_id = None
        action = "INSERTED"

        if existing_memories:
            # Check for close topic match to update (prune old)
            for mem in existing_memories:
                # If key topics match, we treat it as an update/prune operation
                overlap = set(clean_words).intersection(set(re.findall(r"[가-힣a-zA-Z0-9]+", mem["key_fact"])))
                if len(overlap) >= 1 or mem["key_fact"] == key_fact:
                    target_id = mem["id"]
                    action = "UPDATED"
                    break

        if target_id:
            # Update existing record (Pruning old fact with new)
            saved_id = self.vault.save_memory(category=category, key_fact=key_fact, context=context, confidence=confidence)
        else:
            saved_id = self.vault.save_memory(category=category, key_fact=key_fact, context=context, confidence=confidence)

        telegram_msg = None
        if ambiguous:
            telegram_msg = (
                f"❓ **[알파 기억 정제 - 대표님 확인 질문]**\n\n"
                f"수석비서가 대화 중 다음 항목의 모호성을 탐지하였습니다:\n"
                f"• 카테고리: `{category}`\n"
                f"• 추출 내용: *\"{key_fact}\"*\n\n"
                f"대표님, 해당 내용을 최종 확정 지침으로 업데이트할지 확인 부탁드립니다."
            )
            self._notify_telegram_if_available(telegram_msg)

        return {
            "saved_id": saved_id,
            "action": action,
            "category": category,
            "key_fact": key_fact,
            "ambiguous": ambiguous,
            "confidence": confidence,
            "telegram_msg": telegram_msg
        }

    def process_dreaming(self, text_log: str) -> List[Dict[str, Any]]:
        """Main Dreaming entry point: extracts and prunes memories from text log."""
        candidate_facts = self.extract_facts_from_text(text_log)
        results = []
        for fact in candidate_facts:
            res = self.prune_and_save(
                category=fact["category"],
                key_fact=fact["key_fact"],
                context=fact["context"]
            )
            results.append(res)
        return results

    def _notify_telegram_if_available(self, message_text: str):
        """Helper to send Telegram notification if token & chat_id are present."""
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "8392524393")
        if bot_token and chat_id:
            try:
                import urllib.request
                import urllib.parse
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                data = urllib.parse.urlencode({
                    "chat_id": chat_id,
                    "text": message_text,
                    "parse_mode": "Markdown"
                }).encode("utf-8")
                req = urllib.request.Request(url, data=data)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    pass
                logger.info("Telegram clarification question sent successfully.")
            except Exception as e:
                logger.warning(f"Telegram notification skipped/failed: {e}")
