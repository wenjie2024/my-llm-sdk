import pytest
import asyncio
import os
import warnings
from my_llm_sdk.client import LLMClient
from my_llm_sdk.providers.gemini import GeminiProvider
from my_llm_sdk.schemas import GenerationResponse, StreamEvent

# Load API Key from LLMClient config
try:
    client = LLMClient()
    API_KEY = client.config.api_keys.get("google")
except Exception:
    API_KEY = os.environ.get("GOOGLE_API_KEY")

@pytest.fixture
def provider():
    return GeminiProvider()

def test_gemini_generate_contract(provider):
    if not API_KEY:
        pytest.skip("GOOGLE_API_KEY not found in config or environment")
        
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        
        response = provider.generate(
            model_id="gemini-2.5-flash", 
            prompt="Hello, return simply 'OK'",
            api_key=API_KEY
        )
        
        # 1. Contract Equivalence
        assert isinstance(response, GenerationResponse)
        assert response.provider == "google"
        assert response.content is not None
        assert response.timing["total"] > 0
        assert response.finish_reason in ["stop", "unknown"] # Standardized to lowercase
        
        # 2. Usage Consistency
        usage = response.usage
        assert usage.input_tokens > 0
        assert usage.output_tokens > 0
        assert usage.total_tokens >= usage.input_tokens + usage.output_tokens
        
        print(f"\n✅ Sync Generate Contract OK: {usage.total_tokens} tokens")

def test_gemini_stream_contract(provider):
    if not API_KEY:
        pytest.skip("GOOGLE_API_KEY not found in config or environment")
        
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        
        events = list(provider.stream(
            model_id="gemini-2.5-flash",
            prompt="Count from 1 to 3",
            api_key=API_KEY
        ))
        
        # 1. Sequence Contract
        finish_events = [e for e in events if e.is_finish]
        assert len(finish_events) == 1, "Exactly one finish event required"
        
        # 2. Usage in last event
        final_event = finish_events[0]
        assert final_event.usage.total_tokens > 0
        assert final_event.finish_reason is not None
        
        # 3. Content 
        full_text = "".join(e.delta for e in events)
        assert len(full_text) > 0
        
        print(f"\n✅ Sync Stream Contract OK: {final_event.usage.total_tokens} tokens")

@pytest.mark.asyncio
async def test_gemini_generate_async_contract(provider):
    if not API_KEY:
        pytest.skip("GOOGLE_API_KEY not found in config or environment")
        
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        
        response = await provider.generate_async(
            model_id="gemini-2.5-flash",
            prompt="Async test, reply 'OK'",
            api_key=API_KEY
        )
        
        assert response.usage.total_tokens > 0
        print(f"\n✅ Async Generate Contract OK: {response.usage.total_tokens} tokens")

@pytest.mark.asyncio
async def test_gemini_stream_async_contract(provider):
    if not API_KEY:
        pytest.skip("GOOGLE_API_KEY not found in config or environment")
        
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        
        events = []
        async for event in provider.stream_async(
            model_id="gemini-2.5-flash",
            prompt="Count from 1 to 3 async",
            api_key=API_KEY
        ):
            events.append(event)
            
        finish_events = [e for e in events if e.is_finish]
        assert len(finish_events) == 1
        assert finish_events[0].usage.total_tokens > 0
        
        print(f"\n✅ Async Stream Contract OK: {finish_events[0].usage.total_tokens} tokens")

def test_gemini_error_mapping(provider):
    """Verify that specific API errors are caught and wrapped with code/message."""
    with pytest.raises(RuntimeError) as excinfo:
        provider.generate(
            model_id="gemini-2.5-flash",
            prompt="Fail expected",
            api_key="BAD_KEY_12345"
        )
    assert "Gemini API Error" in str(excinfo.value)
    # The new SDK includes error codes like [INVALID_ARGUMENT] or [401]
    # Adjust assertion as needed based on actual output
    print(f"\n✅ Error Mapping OK: {str(excinfo.value)}")
