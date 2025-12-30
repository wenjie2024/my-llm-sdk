import pytest
import asyncio
import sqlite3
import time
from my_llm_sdk.budget.ledger import Ledger, LedgerEvent

@pytest.fixture
def temp_ledger(tmp_path):
    db_path = tmp_path / "test_async_ledger.db"
    return Ledger(str(db_path))

@pytest.mark.asyncio
async def test_async_write_best_effort(temp_ledger):
    # 1. Write event (Best Effort)
    ev = LedgerEvent(
        event_type="test_async",
        trace_id="trace_1",
        provider="google",
        model="gemini-test",
        usage={"tokens_in": 10},
        cost_actual_usd=0.01
    )
    
    await temp_ledger.awrite_event(ev, sync=False)
    
    # 2. Assert queue has item
    assert temp_ledger._queue.qsize() == 1
    
    # 3. Wait for worker to flush (it runs every loop or when pending)
    # Give it a moment to run
    await asyncio.sleep(0.2)
    
    # 4. Check DB
    spend = await temp_ledger.aspend_today()
    assert spend == 0.01

@pytest.mark.asyncio
async def test_async_write_strict(temp_ledger):
    # 1. Write event (Strict/Sync)
    ev = LedgerEvent(
        event_type="test_strict",
        trace_id="trace_2",
        provider="google",
        model="gemini-test",
        usage={"tokens_in": 20},
        cost_actual_usd=0.02
    )
    
    # Should block until written
    await temp_ledger.awrite_event(ev, sync=True)
    
    # 2. Check DB immediately
    spend = await temp_ledger.aspend_today()
    assert spend == 0.02

@pytest.mark.asyncio
async def test_worker_lifecycle(temp_ledger):
    # Ensure worker starts on first write
    assert temp_ledger._worker_task is None
    
    ev = LedgerEvent("startup", "t1", "p", "m", {}, 0.0)
    await temp_ledger.awrite_event(ev, sync=False)
    
    assert temp_ledger._worker_task is not None
    assert not temp_ledger._worker_task.done()
    
    # Close gracefully
    await temp_ledger.aclose()
    
    assert temp_ledger._worker_task.cancelled() or temp_ledger._worker_task.done()

def test_legacy_compat(temp_ledger):
    # Sync write should still work
    temp_ledger.record_transaction("legacy_id", "google", "gemini", 0.05)
    
    spend = temp_ledger.get_daily_spend()
    assert spend == 0.05
    
    # Check if extended columns are populated (with defaults)
    with temp_ledger._get_conn() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE id='legacy_id'").fetchone() # Actually id is uuid now in new schema helper? 
        # Wait, record_transaction calls write_event_sync which generates NEW uuid PK.
        # But legacy `record_transaction` took `tx_id`.
        # My implementation of `_insert_event` generated a NEW UUID for PK, but stored `trace_id` as the legacy ID?
        # Let's check `_insert_event`: 
        # PK = str(uuid.uuid4())
        # trace_id = ev.trace_id (which is tx_id from record_transaction)
        
        # So specific ID query on `id` column will FAIL if I look for 'legacy_id'.
        # I should look for trace_id='legacy_id'.
        pass 
    
    with temp_ledger._get_conn() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE trace_id='legacy_id'").fetchone()
        assert row is not None
        assert row['cost'] == 0.05
        assert row['event_type'] == 'commit'
