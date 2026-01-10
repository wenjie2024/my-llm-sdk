from google import genai
from google.genai import errors
from google.genai import types
import time
import base64
from typing import Iterator, AsyncIterator, Optional, Any, Dict, List
from .base import BaseProvider
from my_llm_sdk.schemas import (
    GenerationResponse, TokenUsage, StreamEvent,
    ContentInput, ContentPart, normalize_content
)


def _convert_to_gemini_parts(contents: ContentInput) -> List[Any]:
    """
    Convert SDK ContentInput to Gemini-compatible parts.
    
    Gemini SDK accepts:
    - str: simple text
    - List of dicts/Part objects for multimodal
    """
    if isinstance(contents, str):
        return contents  # Gemini SDK handles str directly
    
    gemini_parts = []
    for part in contents:
        if part.type == "text":
            gemini_parts.append(part.text or "")
        elif part.type in ("image", "audio", "video", "file"):
            if part.inline_data:
                # Use base64 inline data
                b64_data = base64.standard_b64encode(part.inline_data).decode("utf-8")
                gemini_parts.append({
                    "inline_data": {
                        "mime_type": part.mime_type or "application/octet-stream",
                        "data": b64_data
                    }
                })
            elif part.file_uri:
                # Use file URI (gs://, https://)
                gemini_parts.append({
                    "file_data": {
                        "mime_type": part.mime_type or "application/octet-stream",
                        "file_uri": part.file_uri
                    }
                })
    
    return gemini_parts if gemini_parts else ""


class GeminiProvider(BaseProvider):
    def _extract_usage(self, response_or_chunk) -> TokenUsage:
        """Helper to extract token usage from a response or chunk."""
        p_tokens = 0
        o_tokens = 0
        t_tokens = 0
        
        usage = getattr(response_or_chunk, "usage_metadata", None)
        if usage:
            p_tokens = usage.prompt_token_count or 0
            o_tokens = usage.candidates_token_count or 0
            t_tokens = getattr(usage, "total_token_count", None)
            if t_tokens is None:
                t_tokens = p_tokens + o_tokens
        
        return TokenUsage(
            input_tokens=p_tokens,
            output_tokens=o_tokens,
            total_tokens=t_tokens
        )
    
    def _build_config(self, kwargs: Dict[str, Any]) -> Optional[types.GenerateContentConfig]:
        """Constructs GenerateContentConfig from kwargs."""
        if 'config' in kwargs:
            return kwargs['config']

        config_params = {}
        
        if 'max_output_tokens' in kwargs:
            config_params['max_output_tokens'] = kwargs['max_output_tokens']
        if 'temperature' in kwargs:
            config_params['temperature'] = kwargs['temperature']
        if 'top_p' in kwargs:
            config_params['top_p'] = kwargs['top_p']
        if 'top_k' in kwargs:
            config_params['top_k'] = kwargs['top_k']
        if 'stop_sequences' in kwargs:
            config_params['stop_sequences'] = kwargs['stop_sequences']
        if 'response_mime_type' in kwargs:
            config_params['response_mime_type'] = kwargs['response_mime_type']

        if not config_params:
            return None
            
        return types.GenerateContentConfig(**config_params)

    def generate(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        t0 = time.time()
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        config = self._build_config(kwargs)
        gemini_contents = _convert_to_gemini_parts(contents)

        with genai.Client(api_key=api_key) as client:
            try:
                response = client.models.generate_content(
                    model=model_id,
                    contents=gemini_contents,
                    config=config
                )
                
                content = response.text
                usage = self._extract_usage(response)
                
                finish_reason = "unknown"
                if response.candidates:
                    raw_reason = str(response.candidates[0].finish_reason)
                    finish_reason = raw_reason.lower().replace("finishreason.", "")
                    
                t1 = time.time()
                return GenerationResponse(
                    content=content,
                    model=model_id,
                    provider="google",
                    usage=usage,
                    finish_reason=finish_reason,
                    timing={"total": t1 - t0}
                )
            except errors.APIError as e:
                raise RuntimeError(f"Gemini API Error [{e.code}]: {e.message}")
            except Exception as e:
                raise RuntimeError(f"Gemini API Error: {str(e)}")

    def stream(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        if not api_key:
            raise ValueError("API key required for Gemini")
        
        config = self._build_config(kwargs)
        gemini_contents = _convert_to_gemini_parts(contents)
            
        with genai.Client(api_key=api_key) as client:
            try:
                response_stream = client.models.generate_content_stream(
                    model=model_id,
                    contents=gemini_contents,
                    config=config
                )
                
                last_usage = None
                last_finish_reason = "unknown"
                
                for chunk in response_stream:
                    if chunk.text:
                        yield StreamEvent(delta=chunk.text)
                    
                    usage = self._extract_usage(chunk)
                    if usage.total_tokens > 0:
                        last_usage = usage
                    
                    if chunk.candidates:
                        raw_reason = str(chunk.candidates[0].finish_reason)
                        last_finish_reason = raw_reason.lower().replace("finishreason.", "")

                yield StreamEvent(
                    delta="", 
                    is_finish=True, 
                    usage=last_usage or TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0), 
                    finish_reason=last_finish_reason
                )
            except errors.APIError as e:
                yield StreamEvent(delta="", error=f"Gemini Stream Error [{e.code}]: {e.message}")
            except Exception as e:
                yield StreamEvent(delta="", error=e)

    async def generate_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        t0 = time.time()
        if not api_key:
            raise ValueError("API key required for Gemini")
        
        config = self._build_config(kwargs)
        gemini_contents = _convert_to_gemini_parts(contents)
            
        async with genai.Client(api_key=api_key).aio as aclient:
            try:
                response = await aclient.models.generate_content(
                    model=model_id,
                    contents=gemini_contents,
                    config=config
                )
                
                content = response.text
                usage = self._extract_usage(response)
                
                finish_reason = "unknown"
                if response.candidates:
                    raw_reason = str(response.candidates[0].finish_reason)
                    finish_reason = raw_reason.lower().replace("finishreason.", "")
                    
                t1 = time.time()
                return GenerationResponse(
                    content=content,
                    model=model_id,
                    provider="google",
                    usage=usage,
                    finish_reason=finish_reason,
                    timing={"total": t1 - t0}
                )
            except errors.APIError as e:
                raise RuntimeError(f"Gemini Async API Error [{e.code}]: {e.message}")
            except Exception as e:
                raise RuntimeError(f"Gemini Async API Error: {str(e)}")

    async def stream_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> AsyncIterator[StreamEvent]:
        if not api_key:
            raise ValueError("API key required for Gemini")
        
        config = self._build_config(kwargs)
        gemini_contents = _convert_to_gemini_parts(contents)
            
        async with genai.Client(api_key=api_key).aio as aclient:
            try:
                response_stream = await aclient.models.generate_content_stream(
                    model=model_id,
                    contents=gemini_contents,
                    config=config
                )
                
                last_usage = None
                last_finish_reason = "unknown"
                
                async for chunk in response_stream:
                    if chunk.text:
                        yield StreamEvent(delta=chunk.text)
                    
                    usage = self._extract_usage(chunk)
                    if usage.total_tokens > 0:
                        last_usage = usage
                    
                    if chunk.candidates:
                        raw_reason = str(chunk.candidates[0].finish_reason)
                        last_finish_reason = raw_reason.lower().replace("finishreason.", "")

                yield StreamEvent(
                    delta="", 
                    is_finish=True, 
                    usage=last_usage or TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0), 
                    finish_reason=last_finish_reason
                )
            except errors.APIError as e:
                yield StreamEvent(delta="", error=f"Gemini Async Stream Error [{e.code}]: {e.message}")
            except Exception as e:
                yield StreamEvent(delta="", error=e)

