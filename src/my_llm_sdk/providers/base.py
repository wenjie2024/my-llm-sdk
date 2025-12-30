from typing import Any, Dict, Union, Iterator
from abc import ABC, abstractmethod
from my_llm_sdk.schemas import GenerationResponse, TokenUsage, StreamEvent

class BaseProvider(ABC):
    @abstractmethod
    def generate(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> GenerationResponse:
        pass

    @abstractmethod
    def stream(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        pass

    @abstractmethod
    async def generate_async(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> GenerationResponse:
        pass

    @abstractmethod
    async def stream_async(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        pass

class EchoProvider(BaseProvider):
    """A dummy provider that just echos the prompt."""
    def generate(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> GenerationResponse:
        content = f"[ECHO {model_id}] {prompt}"
        usage = TokenUsage(input_tokens=len(prompt), output_tokens=len(content), total_tokens=len(prompt)+len(content))
        return GenerationResponse(
            content=content,
            model=model_id,
            provider="echo",
            usage=usage,
            finish_reason="stop"
        )
    
    def stream(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        content = f"[ECHO {model_id}] {prompt}"
        chunk_size = 5
        for i in range(0, len(content), chunk_size):
            yield StreamEvent(delta=content[i:i+chunk_size])
            
        usage = TokenUsage(input_tokens=len(prompt), output_tokens=len(content), total_tokens=len(prompt)+len(content))
        yield StreamEvent(delta="", is_finish=True, usage=usage, finish_reason="stop")

    async def generate_async(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> GenerationResponse:
        import asyncio
        await asyncio.sleep(0.1) # Simulate network latency
        return self.generate(model_id, prompt, api_key, **kwargs)

    async def stream_async(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        import asyncio
        await asyncio.sleep(0.1)
        content = f"[ECHO {model_id}] {prompt}"
        chunk_size = 5
        for i in range(0, len(content), chunk_size):
            yield StreamEvent(delta=content[i:i+chunk_size])
            await asyncio.sleep(0.05) # Simulate chunk latency
            
        usage = TokenUsage(input_tokens=len(prompt), output_tokens=len(content), total_tokens=len(prompt)+len(content))
        yield StreamEvent(delta="", is_finish=True, usage=usage, finish_reason="stop")
