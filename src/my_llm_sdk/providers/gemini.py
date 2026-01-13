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
    
    Supports flexible input types:
    - str: simple text (as single item or in list)
    - PIL.Image: converted via types.Part.from_image()
    - ContentPart: mapped to Gemini Part format
    - List of mixed types above
    """
    # Handle single string
    if isinstance(contents, str):
        return contents  # Gemini SDK handles str directly
    
    # Handle PIL.Image directly (single image)
    if HAS_PILLOW and isinstance(contents, Image.Image):
        buf = io.BytesIO()
        contents.save(buf, format='PNG')
        b64_data = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
        return [{"inline_data": {"mime_type": "image/png", "data": b64_data}}]
    
    # Handle list of mixed content
    gemini_parts = []
    for part in contents:
        # String in list -> text
        if isinstance(part, str):
            gemini_parts.append(part)
        # PIL.Image -> convert to bytes
        elif HAS_PILLOW and isinstance(part, Image.Image):
            buf = io.BytesIO()
            part.save(buf, format='PNG')
            b64_data = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
            gemini_parts.append({"inline_data": {"mime_type": "image/png", "data": b64_data}})
        # ContentPart -> convert based on type
        elif hasattr(part, 'type'):
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
        """Constructs GenerateContentConfig from kwargs or config dict."""
        
        # Start with empty dict for params
        config_params = {}
        
        # 1. If 'config' passed, extract valid Gemini params
        if 'config' in kwargs:
            raw_cfg = kwargs['config']
            if hasattr(raw_cfg, 'model_dump'): # Pydantic model
                 # If it's already a GenerateContentConfig or similar options
                 if isinstance(raw_cfg, types.GenerateContentConfig):
                     return raw_cfg
            elif isinstance(raw_cfg, dict):
                 # Filter GenConfig fields to valid Gemini fields
                 valid_keys = [
                     'max_output_tokens', 'temperature', 'top_p', 'top_k', 
                     'stop_sequences', 'response_mime_type', 'response_modalities',
                     'candidate_count', 'presence_penalty', 'frequency_penalty'
                 ]
                 for k, v in raw_cfg.items():
                     if k in valid_keys:
                         config_params[k] = v
                     elif k == 'image_size' or k == 'aspect_ratio':
                         # These go to image_generation_config if needed
                         pass
                     elif k == 'voice_config':
                         pass # Handled explicitly below
        
        # 2. Merge with explicit kwargs (kwargs override config dict)
        # Standard params
        for key in ['max_output_tokens', 'temperature', 'top_p', 'top_k', 'stop_sequences', 'response_mime_type', 'response_modalities']:
            if key in kwargs:
                config_params[key] = kwargs[key]
        
        # 3. Handle specific nested configs
        
        # Helper to look in kwargs first, then config dict
        def get_arg(k):
             if k in kwargs: return kwargs[k]
             if 'config' in kwargs and isinstance(kwargs['config'], dict):
                 return kwargs['config'].get(k)
             return None

        # Voice/Speech Config
        voice_cfg = get_arg('voice_config')
        
        # Construct SpeechConfig if voice_cfg is present
        if voice_cfg:
            voice_name = voice_cfg.get('voice_name') or "Puck"
            try:
                prebuilt = types.PrebuiltVoiceConfig(voice_name=voice_name)
                v_config = types.VoiceConfig(prebuilt_voice_config=prebuilt)
                config_params['speech_config'] = types.SpeechConfig(voice_config=v_config)
            except Exception:
                 # Fallback
                 config_params['speech_config'] = {
                    "voice_config": {
                        "prebuilt_voice_config": {"voice_name": voice_name}
                    }
                }

        # Image Generation Config (image_size, aspect_ratio)
        img_size = get_arg('image_size')
        aspect_ratio = get_arg('aspect_ratio')
        if img_size or aspect_ratio:
            img_cfg_params = {}
            if img_size:
                img_cfg_params['image_size'] = img_size
            if aspect_ratio:
                img_cfg_params['aspect_ratio'] = aspect_ratio
            try:
                config_params['image_config'] = types.ImageConfig(**img_cfg_params)
            except Exception:
                pass  # Let API handle invalid values

        # Infer Modalities from Task Type if not explicit
        task_type = get_arg('task')
        current_mods = config_params.get('response_modalities', [])
        if not isinstance(current_mods, list): current_mods = []
        
        if task_type == "tts":
             if "AUDIO" not in current_mods:
                 current_mods.append("AUDIO")
        elif task_type == "image_generation":
             if "IMAGE" not in current_mods:
                 current_mods.append("IMAGE")
        
        if current_mods:
            config_params['response_modalities'] = current_mods

        if not config_params:
            return None
            
        try:
             return types.GenerateContentConfig(**config_params)
        except Exception:
             return None

    def generate(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        t0 = time.time()
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        config = self._build_config(kwargs)
        
        # Check routing: Detect Imagen models or explicit Image Generation task
        is_imagen = "imagen-" in model_id
        
        # Detect Task Type
        task_type = None
        if 'config' in kwargs:
             task_type = getattr(kwargs['config'], 'get', lambda k: None)('task')
        
        is_image_task = (task_type == "image_generation")
        is_tts_task = (task_type == "tts")
            
        with genai.Client(api_key=api_key) as client:
            try:
                # --- 1. Imagen Model Routing (generate_images) ---
                if is_imagen:
                    # .. (Imagen logic same as before) ..
                    prompt_text = ""
                    if isinstance(contents, str):
                        prompt_text = contents
                    else:
                        prompt_text = " ".join([p.text for p in contents if p.text])
                        
                    img_cfg = types.GenerateImagesConfig(number_of_images=1)
                        
                    response = client.models.generate_images(
                        model=model_id,
                        prompt=prompt_text,
                        config=img_cfg
                    )
                    
                    media_parts = []
                    if response.generated_images:
                        for img in response.generated_images:
                            img_bytes = None
                            if hasattr(img, 'image'):
                                if hasattr(img.image, 'image_bytes'):
                                    img_bytes = img.image.image_bytes
                                else:
                                    img_bytes = img.image
                            
                            if img_bytes:
                                opt_bytes = self._process_image_response(img_bytes, optimize=True)
                                media_parts.append(ContentPart(
                                    type="image",
                                    inline_data=opt_bytes,
                                    mime_type="image/jpeg"
                                ))
                                
                    t1 = time.time()
                    usage = TokenUsage(images_generated=len(media_parts))
                    
                    return GenerationResponse(
                        content="",
                        model=model_id,
                        provider="google",
                        usage=usage,
                        finish_reason="stop",
                        timing={"total": t1 - t0},
                        media_parts=media_parts
                    )

                # --- 2. Standard Content Generation (Text/Multimodal/Gemini-Image/TTS) ---
                
                # Check for neededModalities
                needed_modalities = []
                if is_image_task and not is_imagen:
                    needed_modalities.append("IMAGE")
                if is_tts_task:
                    needed_modalities.append("AUDIO")
                
                if needed_modalities:
                    if not config:
                        config = types.GenerateContentConfig()
                    
                    # Ensure modalities set
                    # If config is from _build_config, it's a GenerateContentConfig object.
                    # We need to set 'response_modalities' if not present.
                    current_mods = getattr(config, 'response_modalities', []) or []
                    # Merge uniqueness
                    new_mods = list(set(current_mods + needed_modalities))
                    
                    try:
                        config.response_modalities = new_mods
                    except:
                        # Fallback if immutable or error
                        pass

                gemini_contents = _convert_to_gemini_parts(contents)
                response = client.models.generate_content(
                    model=model_id,
                    contents=gemini_contents,
                    config=config
                )

                
                # Extract multimodal response
                text_content = ""
                media_parts = []
                
                if response.candidates:
                    # Read optimize_images from kwargs config
                    raw_config = kwargs.get("config", {})
                    optimize_images = raw_config.get("optimize_images", True) if isinstance(raw_config, dict) else True
                    
                    for part in response.candidates[0].content.parts:
                        if part.text:
                            text_content += part.text
                        elif part.inline_data:
                            # Map back to ContentPart
                            m = part.inline_data.mime_type or ""
                            raw_data = part.inline_data.data
                            
                            # Simple heuristic for type
                            p_type = "image"
                            if "audio" in m: p_type = "audio"
                            elif "video" in m: p_type = "video"
                            
                            # Image optimization: Convert PNG to JPEG if enabled
                            if p_type == "image" and optimize_images and "png" in m.lower():
                                try:
                                    from PIL import Image
                                    import io
                                    img = Image.open(io.BytesIO(raw_data))
                                    # Convert RGBA to RGB for JPEG
                                    if img.mode == "RGBA":
                                        img = img.convert("RGB")
                                    # Resize if too large (> 1920px width)
                                    if img.width > 1920:
                                        ratio = 1920 / img.width
                                        new_size = (1920, int(img.height * ratio))
                                        img = img.resize(new_size, Image.LANCZOS)
                                    # Export as JPEG
                                    buf = io.BytesIO()
                                    img.save(buf, format="JPEG", quality=85)
                                    raw_data = buf.getvalue()
                                    m = "image/jpeg"
                                except ImportError:
                                    pass  # Pillow not available, keep original
                                except Exception:
                                    pass  # Any error, keep original
                            
                            media_parts.append(ContentPart(
                                type=p_type,
                                inline_data=raw_data,
                                mime_type=m
                            ))

                usage = self._extract_usage(response)
                
                # Track quantities
                usage.images_processed = sum(1 for p in normalize_content(contents) if p.type == "image")
                
                finish_reason = "unknown"
                if response.candidates:
                    raw_reason = str(response.candidates[0].finish_reason)
                    finish_reason = raw_reason.lower().replace("finishreason.", "")
                
                # Safety block detection: IMAGE requested but no media returned
                requested_modalities = config_params.get('response_modalities', []) if 'config_params' in dir() else []
                raw_cfg = kwargs.get('config', {})
                if isinstance(raw_cfg, dict):
                    requested_modalities = raw_cfg.get('response_modalities', [])
                if "IMAGE" in requested_modalities and len(media_parts) == 0:
                    finish_reason = "safety_blocked"
                    
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

