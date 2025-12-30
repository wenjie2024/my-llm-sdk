from http import HTTPStatus
import dashscope
import time
from typing import Iterator
from .base import BaseProvider
from my_llm_sdk.schemas import GenerationResponse, TokenUsage, StreamEvent
from my_llm_sdk.utils.network import can_connect_to_google

class QwenProvider(BaseProvider):
    def generate(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> GenerationResponse:
        t0 = time.time()
        if not api_key:
            raise ValueError("API key required for Qwen")
            
        dashscope.api_key = api_key
        
        # Dynamic Endpoint Switching via Network Check
        if can_connect_to_google(timeout=1.5):
            dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
        else:
            dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"
        
        try:
            # Simple Generation Call
            response = dashscope.Generation.call(
                model=model_id,
                prompt=prompt,
                result_format='message',  # Use 'message' format for common chat structure
            )
            
            if response.status_code == HTTPStatus.OK:
                content = response.output.choices[0].message.content
                finish_reason = response.output.choices[0].finish_reason
                
                # Usage
                p_tokens = 0
                o_tokens = 0
                if response.usage:
                    p_tokens = response.usage.input_tokens
                    o_tokens = response.usage.output_tokens
                
                t1 = time.time()
                
                usage = TokenUsage(
                    input_tokens=p_tokens,
                    output_tokens=o_tokens,
                    total_tokens=p_tokens + o_tokens
                )
                
                return GenerationResponse(
                    content=content,
                    model=model_id,
                    provider="dashscope",
                    usage=usage,
                    finish_reason=finish_reason,
                    timing={"total": t1 - t0}
                )
            else:
                raise RuntimeError(f"Qwen API Error: {response.code} - {response.message}")
                
        except Exception as e:
            raise RuntimeError(f"Qwen Request Failed: {str(e)}")

    def stream(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        if not api_key:
            raise ValueError("API key required for Qwen")
            
        dashscope.api_key = api_key
        
        # Re-check network or rely on global config setting? 
        # For performance, maybe skip check if already set? 
        # But provider is stateless-ish. Let's do check or trust generate's check? 
        # Let's simple check.
        if can_connect_to_google(timeout=1.5):
            dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
        else:
            dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

        try:
            responses = dashscope.Generation.call(
                model=model_id,
                prompt=prompt,
                result_format='message',
                stream=True,
                incremental_output=True 
            )
            
            p_tokens = 0
            o_tokens = 0
            
            for response in responses:
                if response.status_code == HTTPStatus.OK:
                    if response.output and response.output.choices:
                        delta = response.output.choices[0].message.content
                        if delta:
                            yield StreamEvent(delta=delta)
                            
                        # Usage often in last chunk
                        if response.usage:
                            p_tokens = response.usage.input_tokens
                            o_tokens = response.usage.output_tokens
                else:
                    yield StreamEvent(delta="", error=RuntimeError(f"Qwen Stream Error: {response.code} - {response.message}"))
                    return

            # Final Event with Usage
            usage = TokenUsage(
                input_tokens=p_tokens,
                output_tokens=o_tokens,
                total_tokens=p_tokens + o_tokens
            )
            yield StreamEvent(delta="", is_finish=True, usage=usage, finish_reason="stop")

        except Exception as e:
            yield StreamEvent(delta="", error=e)

    async def generate_async(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> GenerationResponse:
        import asyncio
        # DashScope is sync, so we wrap in thread
        return await asyncio.to_thread(self.generate, model_id, prompt, api_key, **kwargs)

    async def stream_async(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        # DashScope stream is a generator. We can't simple wrap `stream` with to_thread because we need to iterate it.
        # However, to_thread runs the *whole function* in a thread. 
        # If we run `self.stream(...)` in a thread, it returns an iterator *in that thread*.
        # We need to iterate that iterator in a way that doesn't block the loop.
        
        # Strategy:
        # 1. Define a sync worker that consumes the generator and puts items into a queue.
        # 2. Start that worker in a thread.
        # 3. Async consume the queue.
        
        import asyncio
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        
        def producer():
            try:
                # Call sync stream
                iterator = self.stream(model_id, prompt, api_key, **kwargs)
                for item in iterator:
                    # Put into queue thread-safely
                    loop.call_soon_threadsafe(queue.put_nowait, item)
                
                # Signal done
                loop.call_soon_threadsafe(queue.put_nowait, None)
            except Exception as e:
                # Signal error?
                # We can put an Error Event
                err_ev = StreamEvent(delta="", error=e)
                loop.call_soon_threadsafe(queue.put_nowait, err_ev)
                loop.call_soon_threadsafe(queue.put_nowait, None)

        # Start producer in thread
        # We use a future to track if producer crashes hard (outside try/except)
        future = loop.run_in_executor(None, producer)
        
        # Consumer loop
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
            
        await future # Ensure clean exit
