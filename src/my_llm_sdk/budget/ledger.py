import sqlite3
import time
import os
import json
import asyncio
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, asdict

@dataclass
class LedgerEvent:
    event_type: str  # precheck_hold | commit | cancel | adjust
    trace_id: str
    provider: str
    model: str
    usage: Dict[str, Any]  # tokens_in, tokens_out, images, etc.
    cost_est_usd: float = 0.0
    cost_actual_usd: float = 0.0
    status: str = 'ok'  # ok | error | cancelled
    timing: Dict[str, float] = None
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if self.timing is None:
            self.timing = {}

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
        
        # Async Queue for Worker
        self._queue: Optional[asyncio.Queue] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

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
            
            # --- Migration for V0.2.0 ---
            # Attempt to add new columns if they don't exist
            # SQLite doesn't support IF NOT EXISTS for columns, so we try/except
            new_columns = [
                ("event_type", "TEXT DEFAULT 'legacy'"),
                ("trace_id", "TEXT"),
                ("usage_json", "TEXT"),
                ("timing_json", "TEXT")
            ]
            
            for col_name, col_def in new_columns:
                try:
                    conn.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_def}")
                except sqlite3.OperationalError:
                    # Column likely already exists
                    pass
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON transactions(timestamp);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_id ON transactions(trace_id);")

            # --- V0.5.0 Reporting Schema (Read Model) ---
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_facts (
                    trace_id TEXT PRIMARY KEY,
                    ts_start INTEGER,
                    ts_end INTEGER,
                    provider TEXT,
                    model TEXT,
                    profile_id TEXT,
                    status TEXT,
                    cost_usd REAL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_ms REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_ts ON request_facts(ts_start);")

    # --- Sync Legacy API (Maintaining Backward Compatibility) ---
    def record_transaction(self, 
                           tx_id: str, 
                           provider: str, 
                           model: str, 
                           cost: float, 
                           input_tokens: int = 0, 
                           output_tokens: int = 0, 
                           status: str = 'success'):
        """Sync wrapper for legacy calls."""
        # We construct a LedgerEvent and write it synchronously
        ev = LedgerEvent(
            event_type='commit',
            trace_id=tx_id,
            provider=provider,
            model=model,
            usage={"tokens_in": input_tokens, "tokens_out": output_tokens},
            cost_actual_usd=cost,
            status=status
        )
        self.write_event_sync(ev)

    def write_event_sync(self, ev: LedgerEvent):
        """Direct synchronous write to DB."""
        with self._get_conn() as conn:
            self._insert_event(conn, ev)

    def _insert_event(self, conn, ev: LedgerEvent):
        """Internal helper to insert event."""
        # Map back to flat columns for now, store JSON in usage_json
        # id is trace_id for compat, or new uuid for events
        # Legacy schema expects unique ID. If trace_id is shared by multiple events (start/end),
        # we might strictly need unique PK. For V0.2, let's make ID random if not legacy.
        
        pk = str(uuid.uuid4())
        # If legacy call had specific tx_id, we might use it, but keeping it simple:
        # If event_type is commit, maybe reuse trace_id if intended?
        # Let's just use UUID for the row PK.
        
        tokens_in = ev.usage.get("tokens_in", 0)
        tokens_out = ev.usage.get("tokens_out", 0)
        
        conn.execute("""
            INSERT INTO transactions 
            (id, timestamp, provider, model, input_tokens, output_tokens, cost, status, 
             event_type, trace_id, usage_json, timing_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pk, 
            ev.timestamp, 
            ev.provider, 
            ev.model, 
            tokens_in, 
            tokens_out, 
            ev.cost_actual_usd or ev.cost_est_usd, 
            ev.status,
            ev.event_type,
            ev.trace_id,
            json.dumps(ev.usage),
            json.dumps(ev.timing)
        ))
        
        # Incremental Sync to facts
        self._sync_fact(conn, ev.trace_id)

    def get_daily_spend(self) -> float:
        """Sync daily spend calc."""
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT SUM(cost) FROM transactions 
                WHERE timestamp >= ? AND status != 'error'
            """, (start_of_day,))
            result = cursor.fetchone()[0]
            return result if result else 0.0

    # --- Async API (V0.2.0) ---
    
    async def _ensure_worker(self):
        """Lazy init of worker task."""
        if self._queue is None:
            self._queue = asyncio.Queue()
            self._running = True
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        """Background worker to flush events."""
        # Hold a dedicated connection for this loop?
        # Or better: use run_in_executor to avoid blocking the loop with sqlite commits.
        # Strict Async SQLite should use aiosqlite, but to keep deps low (Option #2),
        # we can batch and run_in_executor.
        
        pending_events = []
        
        while self._running:
            try:
                # Wait for next event
                ev = await self._queue.get()
                pending_events.append(ev)
                
                # Drain queue if more available
                while not self._queue.empty() and len(pending_events) < 100:
                    pending_events.append(self._queue.get_nowait())
                
                if pending_events:
                    # Execute Sync Write in Thread
                    await asyncio.to_thread(self._flush_batch, pending_events[:]) # Copy list
                    pending_events.clear()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ledger Worker Error: {e}")
                # Don't crash loop
                await asyncio.sleep(1)

    def _flush_batch(self, events):
        """Sync batch write."""
        try:
            with self._get_conn() as conn:
                conn.execute("BEGIN TRANSACTION;")
                for ev in events:
                    self._insert_event(conn, ev)
                conn.execute("COMMIT;")
        except Exception as e:
            print(f"Flush Batch Failed: {e}")

    async def awrite_event(self, ev: LedgerEvent, sync: bool = False):
        """
        Async write event. 
        If sync=True (Strict Mode), waits for persistence.
        If sync=False (Best Effort), enqueues and returns immediately.
        """
        await self._ensure_worker()
        
        if sync:
            # Sync mode: bypass queue logic for certainty, or use a Future?
            # For simplicity in V0.2, sync=True just does a direct thread write
            # This ensures pre-check hold is really in DB.
            await asyncio.to_thread(self.write_event_sync, ev)
        else:
            await self._queue.put(ev)

    async def aspend_today(self) -> float:
        """Async version of daily spend."""
        return await asyncio.to_thread(self.get_daily_spend)

    async def aclose(self):
        """Graceful shutdown."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    # --- Reporting / Fact Table Logic (V0.5.0) ---

    def rebuild_facts(self):
        """Rebuild request_facts from transactions (Full Sync)."""
        print("Rebuilding request_facts...")
        with self._get_conn() as conn:
            conn.execute("BEGIN TRANSACTION;")
            conn.execute("DELETE FROM request_facts;")
            
            # Find all unique trace_ids
            cursor = conn.execute("SELECT DISTINCT trace_id FROM transactions WHERE trace_id IS NOT NULL")
            trace_ids = [r[0] for r in cursor.fetchall()]
            
            for tid in trace_ids:
                self._sync_fact(conn, tid)
            
            conn.execute("COMMIT;")
        print(f"✅ Rebuilt facts for {len(trace_ids)} requests.")

    def _sync_fact(self, conn, trace_id: str):
        """
        Merge all events for a trace_id into a single fact row.
        Logic: 
        - Start timestamp = min(timestamp)
        - End timestamp = max(timestamp)
        - Final status: if any event is 'success' then 'success', else 'error'
        - Cost: sum of actual costs
        """
        if not trace_id: return
        
        events = conn.execute("""
            SELECT timestamp, provider, model, input_tokens, output_tokens, cost, status, timing_json
            FROM transactions WHERE trace_id = ?
            ORDER BY timestamp ASC
        """, (trace_id,)).fetchall()
        
        if not events: 
            return
        
        ts_start = int(events[0][0] * 1000)
        ts_end = int(events[-1][0] * 1000)
        provider = events[0][1]
        model = events[0][2]
        
        total_cost = sum(e[5] or 0.0 for e in events)
        total_in = sum(e[3] or 0 for e in events)
        total_out = sum(e[4] or 0 for e in events)
        
        # Status priority: if any success, it's success (from user perspective of the request)
        final_status = 'error'
        if any(e[6] == 'success' for e in events):
            final_status = 'success'
            
        # Timing (from last event or specific timing logs)
        total_ms = 0.0
        for e in events:
            if e[7]:
                try:
                    t = json.loads(e[7])
                    if 'total' in t: total_ms = t['total'] * 1000
                except: pass

        conn.execute("""
            INSERT OR REPLACE INTO request_facts 
            (trace_id, ts_start, ts_end, provider, model, status, cost_usd, input_tokens, output_tokens, total_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (trace_id, ts_start, ts_end, provider, model, final_status, total_cost, total_in, total_out, total_ms))
