from google import genai
import time
import asyncio
from typing import Iterator, AsyncIterator
from .base import BaseProvider
from my_llm_sdk.schemas import GenerationResponse, TokenUsage, StreamEvent

class GeminiProvider(BaseProvider):
    def _extract_usage(self, response_or_chunk) -> TokenUsage:
        """Helper to extract token usage from a response or chunk."""
        p_tokens = 0
        o_tokens = 0
        t_tokens = 0
        
        # New SDK structure: metadata is usually in response.usage_metadata
        # During stream, it's chunk.usage_metadata
        usage = getattr(response_or_chunk, "usage_metadata", None)
        if usage:
            p_tokens = usage.prompt_token_count or 0
            o_tokens = usage.candidates_token_count or 0
            # Expert advice: use total_token_count if available to cover thoughts/cache/etc.
            t_tokens = getattr(usage, "total_token_count", None)
            if t_tokens is None:
                t_tokens = p_tokens + o_tokens
        
        return TokenUsage(
            input_tokens=p_tokens,
            output_tokens=o_tokens,
            total_tokens=t_tokens
        )

    def generate(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> GenerationResponse:
        t0 = time.time()
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        with genai.Client(api_key=api_key) as client:
            try:
                response = client.models.generate_content(
                    model=model_id,
                    contents=prompt
                )
                
                content = response.text
                usage = self._extract_usage(response)
                
                # Extract Finish Reason
                finish_reason = "unknown"
                if response.candidates:
                    finish_reason = str(response.candidates[0].finish_reason)
                    
                t1 = time.time()
                return GenerationResponse(
                    content=content,
                    model=model_id,
                    provider="google",
                    usage=usage,
                    finish_reason=finish_reason,
                    timing={"total": t1 - t0}
                )
            except Exception as e:
                raise RuntimeError(f"Gemini API Error: {str(e)}")

    def stream(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        with genai.Client(api_key=api_key) as client:
            try:
                # Generate iterator
                response_stream = client.models.generate_content_stream(
                    model=model_id,
                    contents=prompt
                )
                
                last_usage = None
                last_finish_reason = "stop"
                
                for chunk in response_stream:
                    # Chunk text
                    if chunk.text:
                        yield StreamEvent(delta=chunk.text)
                    
                    # Track metadata from last available chunk
                    usage = self._extract_usage(chunk)
                    if usage.total_tokens > 0:
                        last_usage = usage
                    
                    if chunk.candidates:
                        last_finish_reason = str(chunk.candidates[0].finish_reason)

                # Construct final finish event
                yield StreamEvent(
                    delta="", 
                    is_finish=True, 
                    usage=last_usage or TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0), 
                    finish_reason=last_finish_reason
                )
                
            except Exception as e:
                yield StreamEvent(delta="", error=e)

    async def generate_async(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> GenerationResponse:
        t0 = time.time()
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        # Manually manage async client lifecycle
        client = genai.Client(api_key=api_key)
        try:
            response = await client.aio.models.generate_content(
                model=model_id,
                contents=prompt
            )
            
            content = response.text
            usage = self._extract_usage(response)
            
            finish_reason = "unknown"
            if response.candidates:
                finish_reason = str(response.candidates[0].finish_reason)
                
            t1 = time.time()
            return GenerationResponse(
                content=content,
                model=model_id,
                provider="google",
                usage=usage,
                finish_reason=finish_reason,
                timing={"total": t1 - t0}
            )
        except Exception as e:
            raise RuntimeError(f"Gemini Async API Error: {str(e)}")
        finally:
            # New SDK pattern for aio closure
            await client.aio.aclose()

    async def stream_async(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> AsyncIterator[StreamEvent]:
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        client = genai.Client(api_key=api_key)
        try:
            # Correct syntax: result is an async iterator
            response_stream = await client.aio.models.generate_content_stream(
                model=model_id,
                contents=prompt
            )
            
            last_usage = None
            last_finish_reason = "stop"
            
            async for chunk in response_stream:
                if chunk.text:
                    yield StreamEvent(delta=chunk.text)
                
                usage = self._extract_usage(chunk)
                if usage.total_tokens > 0:
                    last_usage = usage

                if chunk.candidates:
                    last_finish_reason = str(chunk.candidates[0].finish_reason)

            yield StreamEvent(
                delta="", 
                is_finish=True, 
                usage=last_usage or TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0), 
                finish_reason=last_finish_reason
            )
            
        except Exception as e:
            yield StreamEvent(delta="", error=e)
        finally:
            await client.aio.aclose()
