import sqlite3
import time
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

class Ledger:
    def __init__(self, db_path: str = None):
        if not db_path:
            # Default to ~/.llm-sdk/ledger.db
            home = Path.home()
            folder = home / ".llm-sdk"
            folder.mkdir(parents=True, exist_ok=True)
            db_path = str(folder / "ledger.db")
            
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0) # 10s busy timeout
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            # Enable WAL mode for concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cost REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'success',
                    metadata TEXT
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON transactions(timestamp);")

    def record_transaction(self, 
                           tx_id: str, 
                           provider: str, 
                           model: str, 
                           cost: float, 
                           input_tokens: int = 0, 
                           output_tokens: int = 0, 
                           status: str = 'success'):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO transactions 
                (id, timestamp, provider, model, input_tokens, output_tokens, cost, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (tx_id, time.time(), provider, model, input_tokens, output_tokens, cost, status))

    def get_daily_spend(self) -> float:
        """Calculate total successful spend for current UTC day."""
        # Get start of day in UTC
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT SUM(cost) FROM transactions 
                WHERE timestamp >= ? AND status = 'success'
            """, (start_of_day,))
            result = cursor.fetchone()[0]
            return result if result else 0.0
