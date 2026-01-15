import pytest
import time
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from unittest.mock import MagicMock, Mock
from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import StreamEvent, ContentPart

class MockProvider:
    def __init__(self, fail_count=0, error_type=RuntimeError("503 Service Unavailable")):
        self.fail_count = fail_count
        self.calls = 0
        self.error_type = error_type

    def stream(self, model_id, contents, api_key=None):
        self.calls += 1
        print(f"MockProvider.stream called ({self.calls})")
        if self.calls <= self.fail_count:
            # Raise error immediately (or on first yield)
            # To simulate stream failure on connection, we can yield an error or raise.
            # Usually client.stream logic calls next(gen), so raising inside gen is key.
            raise self.error_type
            yield # Unreachable
            
        yield StreamEvent(delta="Hello")
        yield StreamEvent(delta=" World")

    async def stream_async(self, model_id, contents, api_key=None):
        self.calls += 1
        print(f"MockProvider.stream_async called ({self.calls})")
        if self.calls <= self.fail_count:
            # Async generator raising on first yield
            raise self.error_type
            yield # unreachable
        
        yield StreamEvent(delta="Hello")
        yield StreamEvent(delta=" World")

@pytest.fixture
def mock_client():
    client = LLMClient()
    # Replace provider registry to use our mock
    # We need to inject a mock provider for "gemini-mock"
    client.budget = MagicMock()
    client.budget.check_budget = MagicMock()
    client.budget.acheck_budget = MagicMock()
    # For async, acheck_budget should complete
    async def _async_mock(*args, **kwargs): return None
    client.budget.acheck_budget.side_effect = _async_mock
    client.budget.atrack.side_effect = _async_mock
    
    return client

def test_sync_stream_retry(mock_client):
    # Setup
    provider = MockProvider(fail_count=2) # Fail twice, succeed third
    mock_client.providers["mock"] = provider
    
    # Register a mock model
    mock_client.config.final_model_registry["mock-model"] = MagicMock(
        provider="mock", 
        model_id="mock-model",
        rpm=1000, rpd=1000, tpm=1000,
        input_price=0.0, output_price=0.0
    )
    
    # Modify retry config to be fast
    mock_client.retry_manager.config.base_delay_s = 0.1
    
    # Run
    print("\n--- Testing Sync Retry ---")
    events = list(mock_client.stream("biu", model_alias="mock-model"))
    
    # Verify
    assert len(events) == 2
    assert events[0].delta == "Hello"
    assert events[1].delta == " World"
    assert provider.calls == 3 # 2 fails + 1 success

@pytest.mark.asyncio
async def test_async_stream_retry(mock_client):
    # Setup
    provider = MockProvider(fail_count=2)
    mock_client.providers["mock"] = provider
    
    mock_client.config.final_model_registry["mock-model"] = MagicMock(
        provider="mock", 
        model_id="mock-model",
        rpm=1000, rpd=1000, tpm=1000,
        input_price=0.0, output_price=0.0
    )
    
    mock_client.retry_manager.config.base_delay_s = 0.1
    
    # Run
    print("\n--- Testing Async Retry ---")
    events = []
    async for e in mock_client.stream_async("biu", model_alias="mock-model"):
        events.append(e)
        
    # Verify
    assert len(events) == 2
    assert events[0].delta == "Hello"
    assert provider.calls == 3

def test_sync_stream_retry_exhausted(mock_client):
    # Setup - Fail more than max retries (default 3)
    provider = MockProvider(fail_count=5) 
    mock_client.providers["mock"] = provider
    
    mock_client.config.final_model_registry["mock-model"] = MagicMock(
        provider="mock", 
        model_id="mock-model", 
        rpm=1000, rpd=1000, tpm=1000,
        input_price=0.0, output_price=0.0
    )
    mock_client.retry_manager.config.base_delay_s = 0.1
    
    # Run
    print("\n--- Testing Sync Retry Exhaustion ---")
    with pytest.raises(RuntimeError) as exc:
        list(mock_client.stream("biu", model_alias="mock-model"))
    
    assert "503" in str(exc.value)
    assert provider.calls >= 3 

if __name__ == "__main__":
    print("Running manual tests...")
    # Mock client fixture replacement
    client = LLMClient()
    client.budget = MagicMock()
    client.budget.check_budget = MagicMock()
    # For async, acheck_budget should complete
    async def _async_mock(*args, **kwargs): return None
    client.budget.acheck_budget = MagicMock(side_effect=_async_mock)
    client.budget.atrack = MagicMock(side_effect=_async_mock)
    
    try:
        print("Running test_sync_stream_retry...")
        test_sync_stream_retry(client)
        print("✅ test_sync_stream_retry Passed")
    except Exception as e:
        print(f"❌ test_sync_stream_retry Failed: {e}")
        import traceback; traceback.print_exc()

    # Reset client provider for next test
    client = LLMClient()
    client.budget = MagicMock()
    client.budget.check_budget = MagicMock()
    
    try:
        print("Running test_sync_stream_retry_exhausted...")
        test_sync_stream_retry_exhausted(client)
        print("✅ test_sync_stream_retry_exhausted Passed")
    except Exception as e:
        print(f"❌ test_sync_stream_retry_exhausted Failed: {e}")
        import traceback; traceback.print_exc()

    # Async test runner
    client = LLMClient()
    client.budget = MagicMock()
    client.budget.acheck_budget = MagicMock(side_effect=_async_mock)
    client.budget.atrack = MagicMock(side_effect=_async_mock)
    
    try:
        print("Running test_async_stream_retry...")
        asyncio.run(test_async_stream_retry(client))
        print("✅ test_async_stream_retry Passed")
    except Exception as e:
        print(f"❌ test_async_stream_retry Failed: {e}")
        import traceback; traceback.print_exc() 
