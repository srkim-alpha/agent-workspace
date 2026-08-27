import sqlite3
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "memory_vault.db")

VALID_CATEGORIES = {"FACT", "DECISION", "PREFERENCE", "LESSON"}

def get_current_iso_time() -> str:
    """Returns ISO8601 timestamp string with KST timezone offset or local system time."""
    tz_kst = timezone(timedelta(hours=9))
    return datetime.now(tz_kst).isoformat()

class MemoryVault:
    """L2 SQLite Long-Term Memory Vault for Agentic Assistant."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key_fact TEXT NOT NULL,
                    context TEXT,
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON memories(category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at)
            """)
            conn.commit()

    def save_memory(self, category: str, key_fact: str, context: str = "", confidence: float = 1.0) -> int:
        """Saves a new memory or updates existing identical/similar key_fact."""
        category_clean = category.strip().upper()
        if category_clean not in VALID_CATEGORIES:
            category_clean = "FACT"
        
        now = get_current_iso_time()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Check if identical key_fact and category exists
            cursor.execute("""
                SELECT id FROM memories WHERE category = ? AND key_fact = ?
            """, (category_clean, key_fact.strip()))
            row = cursor.fetchone()
            
            if row:
                memory_id = row['id']
                cursor.execute("""
                    UPDATE memories 
                    SET context = ?, confidence = ?, updated_at = ?
                    WHERE id = ?
                """, (context.strip(), confidence, now, memory_id))
                conn.commit()
                return memory_id
            else:
                cursor.execute("""
                    INSERT INTO memories (category, key_fact, context, confidence, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (category_clean, key_fact.strip(), context.strip(), confidence, now, now))
                conn.commit()
                return cursor.lastrowid

    def recall_memory(self, query_keyword: str = "", category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recalls memories matching a keyword and optional category filter."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = "SELECT id, category, key_fact, context, confidence, created_at, updated_at FROM memories WHERE 1=1"
            params = []
            
            if category:
                sql += " AND category = ?"
                params.append(category.strip().upper())
                
            if query_keyword and query_keyword.strip():
                sql += " AND (key_fact LIKE ? OR context LIKE ?)"
                kw = f"%{query_keyword.strip()}%"
                params.append(kw)
                params.append(kw)
                
            sql += " ORDER BY updated_at DESC"
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            return [dict(r) for r in rows]

    def get_memory_by_id(self, memory_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a single memory record by its ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, key_fact, context, confidence, created_at, updated_at FROM memories WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_memory(self, memory_id: int) -> bool:
        """Deletes a memory record by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_all_memories(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all memories ordered by creation date."""
        return self.recall_memory(query_keyword="", category=category)
