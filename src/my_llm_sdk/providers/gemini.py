from google import genai
from google.genai import errors
from google.genai import types
import time
import base64
from typing import Iterator, AsyncIterator, Optional, Any, Dict, List
import io
try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

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

    def _process_image_response(self, raw_bytes: bytes, optimize: bool = True) -> bytes:
        """
        Optimizes image bytes:
        1. Convert to JPEG (Quality 85)
        2. Resize if width > 1920
        """
        if not optimize or not raw_bytes or not HAS_PILLOW:
            return raw_bytes
            
        try:
            # Threshold: only optimize if > 500KB to save CPU for small icons
            if len(raw_bytes) < 500 * 1024:
                return raw_bytes

            with io.BytesIO(raw_bytes) as input_io:
                img = Image.open(input_io)
                
                # 1. Resize if needed
                max_width = 1920
                if img.width > max_width:
                    aspect_ratio = img.height / img.width
                    new_height = int(max_width * aspect_ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                
                # 2. Convert to RGB (if RGBA/P)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # 3. Save as JPEG
                with io.BytesIO() as output_io:
                    img.save(output_io, format="JPEG", quality=85)
                    return output_io.getvalue()
        except Exception:
            # Fallback to original if any error occurs
            return raw_bytes

    
    def _build_config(self, kwargs: Dict[str, Any]) -> Optional[types.GenerateContentConfig]:
        """Constructs GenerateContentConfig from kwargs."""
        if 'config' in kwargs:
            return kwargs['config']

        config_params = {}
        
        # Standard params
        for key in ['max_output_tokens', 'temperature', 'top_p', 'top_k', 'stop_sequences', 'response_mime_type']:
            if key in kwargs:
                config_params[key] = kwargs[key]
        
        # V0.4.0 Multimodal params
        if 'response_modalities' in kwargs:
            config_params['response_modalities'] = kwargs['response_modalities']
            
        # Image Generation specific
        if 'image_size' in kwargs or 'aspect_ratio' in kwargs:
            img_config = {}
            if 'image_size' in kwargs: img_config['image_size'] = kwargs['image_size']
            if 'aspect_ratio' in kwargs: img_config['aspect_ratio'] = kwargs['aspect_ratio']
            config_params['image_generation_config'] = types.ImageGenerationConfig(**img_config)

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
                
                # Extract multimodal response
                text_content = ""
                media_parts = []
                
                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if part.text:
                            text_content += part.text
                        elif part.inline_data:
                            # Map back to ContentPart
                            m = part.inline_data.mime_type or ""
                            # Simple heuristic for type
                            p_type = "image"
                            if "audio" in m: p_type = "audio"
                            elif "video" in m: p_type = "video"
                            
                            media_parts.append(ContentPart(
                                type=p_type,
                                inline_data=part.inline_data.data,
                                mime_type=m
                            ))

                usage = self._extract_usage(response)
                
                # Track quantities
                usage.images_processed = sum(1 for p in normalize_content(contents) if p.type == "image")
                
                finish_reason = "unknown"
                if response.candidates:
                    raw_reason = str(response.candidates[0].finish_reason)
                    finish_reason = raw_reason.lower().replace("finishreason.", "")
                    
                t1 = time.time()
                return GenerationResponse(
                    content=text_content,
                    model=model_id,
                    provider="google",
                    usage=usage,
                    finish_reason=finish_reason,
                    timing={"total": t1 - t0},
                    media_parts=media_parts
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

