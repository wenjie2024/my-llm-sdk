from typing import Any, Dict, Union, Iterator
from abc import ABC, abstractmethod
from my_llm_sdk.schemas import (
    GenerationResponse, TokenUsage, StreamEvent,
    ContentInput, ContentPart, normalize_content
)


class BaseProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement these methods to handle ContentInput,
    which can be either a simple str or a List[ContentPart] for multimodal.
    """
    
    @abstractmethod
    def generate(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        pass

    @abstractmethod
    def stream(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        pass

    @abstractmethod
    async def generate_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        pass

    @abstractmethod
    async def stream_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        pass


def _extract_text(contents: ContentInput) -> str:
    """Helper to extract text representation from ContentInput for echo/debug purposes."""
    if isinstance(contents, str):
        return contents
    
    texts = []
    for part in contents:
        if part.type == "text" and part.text:
            texts.append(part.text)
        elif part.type == "image":
            texts.append("[IMAGE]")
        elif part.type == "audio":
            texts.append("[AUDIO]")
        elif part.type == "video":
            texts.append("[VIDEO]")
        elif part.type == "file":
            texts.append("[FILE]")
    return " ".join(texts) if texts else "[NO TEXT]"


class EchoProvider(BaseProvider):
    """A dummy provider that just echos the input content."""
    
    def generate(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        text_repr = _extract_text(contents)
        content = f"[ECHO {model_id}] {text_repr}"
        usage = TokenUsage(
            input_tokens=len(text_repr), 
            output_tokens=len(content), 
            total_tokens=len(text_repr) + len(content)
        )
        return GenerationResponse(
            content=content,
            model=model_id,
            provider="echo",
            usage=usage,
            finish_reason="stop"
        )
    
    def stream(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        text_repr = _extract_text(contents)
        content = f"[ECHO {model_id}] {text_repr}"
        chunk_size = 5
        for i in range(0, len(content), chunk_size):
            yield StreamEvent(delta=content[i:i+chunk_size])
            
        usage = TokenUsage(
            input_tokens=len(text_repr), 
            output_tokens=len(content), 
            total_tokens=len(text_repr) + len(content)
        )
        yield StreamEvent(delta="", is_finish=True, usage=usage, finish_reason="stop")

    async def generate_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        import asyncio
        await asyncio.sleep(0.1)  # Simulate network latency
        return self.generate(model_id, contents, api_key, **kwargs)

    async def stream_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        import asyncio
        await asyncio.sleep(0.1)
        text_repr = _extract_text(contents)
        content = f"[ECHO {model_id}] {text_repr}"
        chunk_size = 5
        for i in range(0, len(content), chunk_size):
            yield StreamEvent(delta=content[i:i+chunk_size])
            await asyncio.sleep(0.05)  # Simulate chunk latency
            
        usage = TokenUsage(
            input_tokens=len(text_repr), 
            output_tokens=len(content), 
            total_tokens=len(text_repr) + len(content)
        )
        yield StreamEvent(delta="", is_finish=True, usage=usage, finish_reason="stop")

