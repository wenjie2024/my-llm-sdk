import pytest
import sqlite3
import uuid
import os
import json
from datetime import datetime
from my_llm_sdk.budget.ledger import Ledger, LedgerEvent
from my_llm_sdk.budget.reporter import Reporter

@pytest.fixture
def temp_ledger(tmp_path):
    db_path = tmp_path / "ledger.db"
    ledger = Ledger(str(db_path))
    return ledger

def test_schema_created(temp_ledger):
    """Verify request_facts table exists."""
    with temp_ledger._get_conn() as conn:
        # Check table
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='request_facts';")
        assert cursor.fetchone() is not None
        
        # Check columns
        cursor = conn.execute("PRAGMA table_info(request_facts);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "trace_id" in columns
        assert "cost_usd" in columns
        assert "status" in columns
        assert "status" in columns
        # assert "ttft_ms" in columns # Not in schema

def test_event_sync_lifecycle(temp_ledger):
    """Test full lifecycle: Hold -> Commit -> Adjust."""
    
    trace_id = str(uuid.uuid4())
    
    # 1. Pre-check Hold
    ev_hold = LedgerEvent(
        event_type="precheck_hold",
        trace_id=trace_id,
        provider="google",
        model="gemini-flash",
        cost_est_usd=0.01,
        status="running",
        usage={},
        timestamp=datetime.now().timestamp()
    )
    temp_ledger.write_event_sync(ev_hold)
    
    # Verify in facts
    with temp_ledger._get_conn() as conn:
        row = conn.execute("SELECT status, cost_usd FROM request_facts WHERE trace_id=?", (trace_id,)).fetchone()
        assert row[0] == "running"
        assert row[1] == 0.01

    # 2. Commit (Success)
    ev_commit = LedgerEvent(
        event_type="commit",
        trace_id=trace_id,
        provider="google",
        model="gemini-flash",
        usage={"tokens_in": 100, "tokens_out": 50},
        cost_actual_usd=0.005,
        status="success",
        timestamp=datetime.now().timestamp(),
        timing={"total": 1.5, "ttft": 0.2}
    )
    temp_ledger.write_event_sync(ev_commit)
    
    # Verify update
    with temp_ledger._get_conn() as conn:
        row = conn.execute("""
            SELECT status, cost_usd, input_tokens, total_ms FROM request_facts WHERE trace_id=?
        """, (trace_id,)).fetchone()
        assert row[0] == "success"
        assert row[1] == 0.005
        assert row[2] == 100
        assert row[3] == 1500 # ms

    # 3. Adjust (Correction)
    ev_adjust = LedgerEvent(
        event_type="adjust",
        trace_id=trace_id,
        provider="google",
        model="gemini-flash",
        usage={"tokens_in": 102, "tokens_out": 50},
        cost_actual_usd=0.0051,
        status="success",
        timestamp=datetime.now().timestamp()
    )
    temp_ledger.write_event_sync(ev_adjust)
    
    # Verify final state
    with temp_ledger._get_conn() as conn:
        row = conn.execute("SELECT cost_usd, input_tokens FROM request_facts WHERE trace_id=?", (trace_id,)).fetchone()
        assert row[0] == 0.0051
        assert row[1] == 102

def test_reporter_aggregations(temp_ledger):
    """Test Reporter class aggregations."""
    reporter = Reporter(temp_ledger)
    
    # Seed data
    # Day 1: 2 reqs, $0.10 total
    # Day 2: 1 req, $0.05 total
    
    with temp_ledger._get_conn() as conn:
        # We manipulate timestamps relative to 'now' logic of Reporter
        # Reporter uses SQLite 'now', which is UTC.
        # We insert using raw SQL to force timestamps.
        
        now = datetime.now().timestamp() * 1000
        day_ms = 86400 * 1000
        
        # Today
        conn.execute("""
            INSERT INTO request_facts (trace_id, ts_start, provider, model, status, cost_usd, input_tokens, total_ms)
            VALUES 
            ('t1', ?, 'p1', 'm1', 'ok', 0.04, 1000, 500),
            ('t2', ?, 'p1', 'm1', 'ok', 0.06, 2000, 1000)
        """, (now - 1000, now - 2000))
        
        # Yesterday
        conn.execute("""
            INSERT INTO request_facts (trace_id, ts_start, provider, model, status, cost_usd, total_ms)
            VALUES 
            ('t3', ?, 'p2', 'm2', 'error', 0.00, 100)
        """, (now - day_ms - 1000,))
    
    # Test Today Summary
    summary = reporter.today_summary()
    assert summary.total_cost == 0.10
    assert summary.request_count == 2
    assert summary.total_tokens == 3000
    assert summary.error_rate == 0.0

    # Test Trends (ordering might depend on exact time, but we check buckets)
    # Note: daily_trend groups by local date. 
    # If test runs at 23:59 vs 00:01, buckets shift. 
    # For robustness, we trust the SQL logic tested above or verify list length.
    trends = reporter.daily_trend(7)
    assert len(trends) >= 1
    total_trends_cost = sum(t.cost for t in trends)
    assert abs(total_trends_cost - 0.10) < 0.0001 
    # Wait, yesterday's cost is 0.0 (error).
    
    # Test Top Consumer
    tops = reporter.top_consumers("model", 7)
    assert len(tops) > 0
    assert tops[0].key == 'm1'
    assert abs(tops[0].cost - 0.10) < 0.0001
    
    # Test Health (with error yesterday)
    health = reporter.health_check(7)
    assert health.total_reqs == 3
    assert abs(health.error_rate - 0.3333) < 0.01

def test_rebuild_facts(temp_ledger):
    """Test migration utility."""
    # 1. Insert raw transaction directly
    with temp_ledger._get_conn() as conn:
        conn.execute("""
            INSERT INTO transactions 
            (id, timestamp, provider, model, cost, status, event_type, trace_id, usage_json, timing_json, input_tokens)
            VALUES 
            ('old1', 1000.0, 'legacy_p', 'legacy_m', 0.5, 'success', 'commit', 'trace_old', '{"tokens_in":10}', '{}', 10)
        """)
    
    # 2. Run Migration
    temp_ledger.rebuild_facts()
    
    # 3. Verify projection
    with temp_ledger._get_conn() as conn:
        row = conn.execute("SELECT * FROM request_facts WHERE trace_id='trace_old'").fetchone()
        assert row is not None
        assert row[3] == 'legacy_p' # provider
        assert row[7] == 0.5 # cost
        assert row[8] == 10 # input_tokens
