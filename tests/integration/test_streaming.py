import pytest
import datetime
import asyncio
import json
from unittest.mock import MagicMock
from my_llm_sdk.client import LLMClient
from my_llm_sdk.providers.base import BaseProvider
from my_llm_sdk.schemas import StreamEvent, TokenUsage, GenerationResponse

class MockStreamProvider(BaseProvider):
    def generate(self, model: str, prompt: str, api_key: str = None, **kwargs):
        # Fallback for estimated cost cost calculation? No, generate is separate.
        return GenerationResponse(content="mock", model=model, provider="mock", usage=TokenUsage(0,0,0))
        
    async def generate_async(self, model: str, prompt: str, api_key: str = None, **kwargs):
        return self.generate(model, prompt, api_key, **kwargs)

    def stream(self, model_id, prompt, api_key=None, **kwargs):
        chunks = ["one", " ", "two", " ", "three"]
        for c in chunks:
            yield StreamEvent(delta=c)
        
        # Finish event
        usage = TokenUsage(input_tokens=5, output_tokens=5, total_tokens=10)
        yield StreamEvent(delta="", is_finish=True, usage=usage, finish_reason="stop")
        
    async def stream_async(self, model_id, prompt, api_key=None, **kwargs):
        chunks = ["one", " ", "two", " ", "three"]
        for c in chunks:
            yield StreamEvent(delta=c)
        yield StreamEvent(delta="", is_finish=True, usage=TokenUsage(5,5,10), finish_reason="stop")

@pytest.fixture
def streaming_client(isolated_env):
    """Client with Mock Stream Provider."""
    # Write a config that uses 'mock-stream'
    config_path = isolated_env / "llm.project.yaml"
    with open(config_path, "w") as f:
        f.write("""
project_name: stream-test
model_registry:
  stream-model:
    name: stream-model
    provider: mock
    model_id: mock-stream
    pricing: {input_per_1m_tokens: 1.0, output_per_1m_tokens: 1.0}
        """)
    
    client = LLMClient(project_config_path=str(config_path))
    client.providers['mock'] = MockStreamProvider()
    return client

def test_sync_streaming_flow(streaming_client):
    """Verify stream() yields chunks and records usage."""
    
    print("Starting stream...")
    iterator = streaming_client.stream("Prompt", model_alias="stream-model")
    
    chunks = []
    final_event = None
    
    for event in iterator:
        if event.delta:
            chunks.append(event.delta)
        if event.is_finish:
            final_event = event
            
    assert "".join(chunks) == "one two three"
    assert final_event is not None
    assert final_event.usage.total_tokens == 10
    
    # Verify Ledger
    ledger = streaming_client.budget.ledger
    with ledger._get_conn() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE model='mock-stream'").fetchone()
        assert row is not None
        # Check usage json
        u = json.loads(row['usage_json'])
        assert u['tokens_in'] == 5
        assert u['tokens_out'] == 5
        # Check cost (5+5 tokens * 1.0/1m = tiny)
        assert row['cost'] > 0

@pytest.mark.asyncio
async def test_async_streaming_flow(streaming_client):
    """Verify stream_async() yields chunks and records usage."""
    
    iterator = streaming_client.stream_async("Prompt", model_alias="stream-model")
    
    chunks = []
    final_event = None
    
    async for event in iterator:
        if event.delta:
            chunks.append(event.delta)
        if event.is_finish:
            final_event = event
            
    assert "".join(chunks) == "one two three"
    assert final_event is not None
    
    # Ledger check might need wait if Client uses async fire-and-forget?
    # Client.stream_async calls `await self.budget.atrack(...)`
    # BudgetController.atrack uses `await self.ledger.awrite_event(..., sync=False)`
    # So it queues it. We need to wait for worker or flush.
    
    # Force flush
    ledger = streaming_client.budget.ledger
    # Wait a bit for worker to pick up in background
    await asyncio.sleep(0.5)
    
    # Or explicitly wait for queue to be empty?
    # ledger._queue.join()? (Not exposed publicly)
    
    with ledger._get_conn() as conn:
        # Should have 2 transactions now (sync test + async test)
        rows = conn.execute("SELECT * FROM transactions WHERE model='mock-stream'").fetchall()
        # Note: If sync test runs first in same session, it might be in same DB if fixture not scoped functionality function?
        # fixture uses 'isolated_env' which is function scoped?
        # isolated_env fixture code: defaults to function scope unless specificed.
        # Yes, pytest fixtures are function scope by default.
        # So each test gets clean environment.
        pass

    # Re-check DB in THIS test (it should have 1 txn)
    with ledger._get_conn() as conn:
        row = conn.execute("SELECT * FROM transactions").fetchone()
        # If absent, it means worker didn't finish.
        # In 'test_async_ledger.py', we usually explicitly flush or wait.
        pass
    
    # Since we can't easily force flush without internal API, let's retry loop check
    found = False
    for _ in range(5):
        with ledger._get_conn() as conn:
             if conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] > 0:
                 found = True
                 break
        await asyncio.sleep(0.1)
    
    assert found, "Transaction not flushed to DB in Async Stream test"

