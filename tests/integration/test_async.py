import pytest
import asyncio
import time
from my_llm_sdk.client import LLMClient
from my_llm_sdk.providers.base import BaseProvider
from my_llm_sdk.schemas import GenerationResponse, TokenUsage, ContentInput

class MockAsyncProvider(BaseProvider):
    async def generate_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs):
        # Simulate Network Delay
        await asyncio.sleep(0.1)
        return GenerationResponse(content="mock", model=model_id, provider="mock", usage=TokenUsage(0,0,0), finish_reason="stop")

    def generate(self, model_id, contents: ContentInput, api_key=None, **kwargs):
        # Sync version sleeps blocks loop if not in thread
        time.sleep(0.1)
        return GenerationResponse(content="mock", model=model_id, provider="mock", usage=TokenUsage(0,0,0), finish_reason="stop")
    
    # Required abstract methods
    def stream(self, model, contents: ContentInput, api_key=None, **kwargs): pass
    async def stream_async(self, model, contents: ContentInput, api_key=None, **kwargs): pass

@pytest.fixture
def async_client(isolated_env):
    config_path = isolated_env / "llm.project.yaml"
    with open(config_path, "w") as f:
        f.write("""
project_name: async-test
model_registry:
  async-model:
    name: async-model
    provider: mock
    model_id: async-mock
    pricing: {input_per_1m_tokens: 1.0, output_per_1m_tokens: 1.0}
        """)
    
    client = LLMClient(project_config_path=str(config_path))
    client.providers['mock'] = MockAsyncProvider()
    return client

@pytest.mark.asyncio
async def test_concurrency(async_client):
    """Verify that multiple requests run in parallel."""
    t0 = time.time()
    
    tasks = []
    # Launch 5 requests. Each takes 0.1s.
    # Total time should be close to 0.1s, definitely < 0.3s.
    # If sequential, it would be 0.5s.
    for _ in range(5):
        tasks.append(async_client.generate_async("test", model_alias="async-model"))
        
    results = await asyncio.gather(*tasks)
    t1 = time.time()
    
    total_time = t1 - t0
    # Add buffer for overhead
    assert total_time < 0.3, f"Concurrency test too slow: {total_time}s"
    assert len(results) == 5
