from http import HTTPStatus
import dashscope
import time
import base64
from typing import Iterator, List, Dict, Any
from .base import BaseProvider
from my_llm_sdk.schemas import (
    GenerationResponse, TokenUsage, StreamEvent,
    ContentInput, ContentPart, normalize_content
)
from my_llm_sdk.utils.network import can_connect_to_google


def _convert_to_qwen_content(contents: ContentInput) -> Dict[str, Any]:
    """
    Convert SDK ContentInput to DashScope-compatible format.
    
    DashScope uses:
    - prompt: str for simple text
    - messages: list for chat/multimodal format
    
    Returns dict with either 'prompt' or 'messages' key.
    """
    if isinstance(contents, str):
        return {"prompt": contents}
    
    # Check if all parts are text-only
    all_text = all(p.type == "text" for p in contents)
    if all_text:
        combined_text = " ".join(p.text or "" for p in contents)
        return {"prompt": combined_text}
    
    # Multimodal: Build messages format
    # DashScope multimodal uses content array with type-specific keys
    content_parts = []
    for part in contents:
        if part.type == "text":
            content_parts.append({"text": part.text or ""})
        elif part.type == "image":
            if part.inline_data:
                b64_data = base64.standard_b64encode(part.inline_data).decode("utf-8")
                content_parts.append({
                    "image": f"data:{part.mime_type or 'image/png'};base64,{b64_data}"
                })
            elif part.file_uri:
                content_parts.append({"image": part.file_uri})
        elif part.type == "audio":
            if part.file_uri:
                content_parts.append({"audio": part.file_uri})
        elif part.type == "video":
            if part.file_uri:
                content_parts.append({"video": part.file_uri})
    
    messages = [{"role": "user", "content": content_parts}]
    return {"messages": messages}


class QwenProvider(BaseProvider):
    def _setup_endpoint(self, api_key: str):
        """Configure API key and endpoint based on network."""
        dashscope.api_key = api_key
        if can_connect_to_google(timeout=1.5):
            dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
        else:
            dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

    def generate(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        t0 = time.time()
        if not api_key:
            raise ValueError("API key required for Qwen")
            
        self._setup_endpoint(api_key)
        qwen_params = _convert_to_qwen_content(contents)
        
        try:
            response = dashscope.Generation.call(
                model=model_id,
                result_format='message',
                **qwen_params
            )
            
            if response.status_code == HTTPStatus.OK:
                content = response.output.choices[0].message.content
                finish_reason = response.output.choices[0].finish_reason
                
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

    def stream(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        if not api_key:
            raise ValueError("API key required for Qwen")
            
        self._setup_endpoint(api_key)
        qwen_params = _convert_to_qwen_content(contents)

        try:
            responses = dashscope.Generation.call(
                model=model_id,
                result_format='message',
                stream=True,
                incremental_output=True,
                **qwen_params
            )
            
            p_tokens = 0
            o_tokens = 0
            
            for response in responses:
                if response.status_code == HTTPStatus.OK:
                    if response.output and response.output.choices:
                        delta = response.output.choices[0].message.content
                        if delta:
                            yield StreamEvent(delta=delta)
                            
                        if response.usage:
                            p_tokens = response.usage.input_tokens
                            o_tokens = response.usage.output_tokens
                else:
                    yield StreamEvent(delta="", error=RuntimeError(f"Qwen Stream Error: {response.code} - {response.message}"))
                    return

            usage = TokenUsage(
                input_tokens=p_tokens,
                output_tokens=o_tokens,
                total_tokens=p_tokens + o_tokens
            )
            yield StreamEvent(delta="", is_finish=True, usage=usage, finish_reason="stop")

        except Exception as e:
            yield StreamEvent(delta="", error=e)

    async def generate_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        import asyncio
        return await asyncio.to_thread(self.generate, model_id, contents, api_key, **kwargs)

    async def stream_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        import asyncio
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        
        def producer():
            try:
                iterator = self.stream(model_id, contents, api_key, **kwargs)
                for item in iterator:
                    loop.call_soon_threadsafe(queue.put_nowait, item)
                loop.call_soon_threadsafe(queue.put_nowait, None)
            except Exception as e:
                err_ev = StreamEvent(delta="", error=e)
                loop.call_soon_threadsafe(queue.put_nowait, err_ev)
                loop.call_soon_threadsafe(queue.put_nowait, None)

        future = loop.run_in_executor(None, producer)
        
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
            
        await future

