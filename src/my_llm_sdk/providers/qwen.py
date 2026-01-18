from http import HTTPStatus
import dashscope
import time
import base64
import os
import requests
from typing import Iterator, List, Dict, Any, Optional
from .base import BaseProvider
from my_llm_sdk.schemas import (
    GenerationResponse, TokenUsage, StreamEvent,
    ContentInput, ContentPart, normalize_content,
    TaskType, GenConfig
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
        import os
        os.environ["DASHSCOPE_API_KEY"] = api_key
        if can_connect_to_google(timeout=1.5):
            dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
        else:
            # Default/CN endpoint
            dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

    def _generate_image(self, model_id: str, prompt: str, config: Dict[str, Any]) -> GenerationResponse:
        """Handle Image Generation task."""
        from dashscope import ImageSynthesis
        
        t0 = time.time()
        
        # Parse config for image params
        raw_size = config.get("image_size", "1K")
        # Standardize size for dashscope (e.g. "1K" -> "1024*1024")
        size_map = {
            "1K": "1024*1024",
            "2K": "2048*2048", # Fallback if model supports it
        }
        size = size_map.get(raw_size, raw_size)
        if "*" not in size and raw_size != "1K":
             # If it's still not formatted and not 1K, default to 1K for safety
             size = "1024*1024"
             
        n = config.get("image_count", 1)
        
        rsp = ImageSynthesis.call(
            model=model_id,
            prompt=prompt,
            n=n,
            size=size,
            prompt_extend=True  # Default to True for better quality
        )
        
        if rsp.status_code == HTTPStatus.OK and rsp.output and rsp.output.results:
            media_parts = []
            for res in rsp.output.results:
                if res.url:
                    # Download image content
                    img_data = requests.get(res.url).content
                    media_parts.append(ContentPart(
                        type="image",
                        inline_data=img_data,
                        mime_type="image/png"
                    ))
            
            t1 = time.time()
            usage = TokenUsage(images_generated=len(media_parts))
            
            return GenerationResponse(
                content="",  # specific content handled in media_parts
                model=model_id,
                provider="dashscope",
                usage=usage,
                finish_reason="stop",
                timing={"total": t1 - t0},
                media_parts=media_parts
            )
        else:
            raise RuntimeError(f"Qwen Image Gen Failed: {rsp.code} - {rsp.message}")

    def _generate_speech_realtime(self, model_id: str, text: str, config: Dict[str, Any]) -> GenerationResponse:
        """Handle TTS using Realtime API (WebSocket) - Required for some models."""
        try:
            from dashscope.audio.qwen_tts_realtime import (
                QwenTtsRealtime,
                QwenTtsRealtimeCallback,
                AudioFormat,
            )
            import threading
            import io
        except ImportError:
            raise RuntimeError("dashscope >= 1.20 required for Qwen Realtime TTS")

        t0 = time.time()
        voice_cfg = config.get("voice_config", {})
        voice_id = voice_cfg.get("voice_name", "qwen-tts-vc-father-voice-20251207194748170-5620") # Default to verified voice?
        
        # Audio accumulator callback
        class SDKRealtimeCallback(QwenTtsRealtimeCallback):
            def __init__(self):
                super().__init__()
                self.finished_event = threading.Event()
                self.error = None
                self.audio_buffer = io.BytesIO()

            def on_event(self, response: dict):
                try:
                    if response.get("type") == "response.audio.delta":
                        b64 = response.get("delta")
                        if b64:
                            self.audio_buffer.write(base64.b64decode(b64))
                    elif response.get("type") == "session.finished":
                        self.finished_event.set()
                except Exception as e:
                    self.error = str(e)
                    self.finished_event.set()
            
            def on_close(self, code, msg):
                if code != 1000:
                    self.error = f"WebSocket Closed {code}: {msg}"
                self.finished_event.set()

        # Determine URL based on network environment
        # Match WebSocket endpoint with HTTP API endpoint (which is set by _setup_endpoint based on Google connectivity)
        if "dashscope-intl" in dashscope.base_http_api_url:
            # Using INTL endpoint
            url = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
        else:
            # Using CN endpoint (default for most users in China)
            url = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"

        callback = SDKRealtimeCallback()
        try:
            client = QwenTtsRealtime(
                model=model_id,
                url=url,
                callback=callback
            )
            client.connect()
            
            # Format object
            af = AudioFormat.PCM_24000HZ_MONO_16BIT
            
            client.update_session(
                voice=voice_id,
                response_format=af,
                language_type="Chinese"
            )
            
            client.append_text(text)
            client.finish()
            
            if not callback.finished_event.wait(timeout=60):
                raise RuntimeError("Qwen Realtime TTS Timeout")
                
            if callback.error:
                raise RuntimeError(f"Qwen Realtime TTS Error: {callback.error}")
                
            # Success
            audio_data = callback.audio_buffer.getvalue()
            t1 = time.time()
            
            media_part = ContentPart(
                type="audio",
                inline_data=audio_data,
                mime_type="audio/wav" # Actually PCM, but saving as wav needs header? 
                # Wav file needs header. PCM is raw.
                # Client persists as binary. User can wrap in container. 
                # Let's add basic WAV header if possible or just return PCM and denote mime=audio/pcm?
                # The prompt requested "Save to .wav". The experiment script used 'wave' lib to write frames.
                # Here we just have bytes. Let's wrap in WAV container for usability.
            )
            
            # Convert PCM to WAV in-memory
            try:
                import wave
                wav_buf = io.BytesIO()
                with wave.open(wav_buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2) # 16bit
                    wf.setframerate(24000)
                    wf.writeframes(audio_data)
                media_part.inline_data = wav_buf.getvalue()
                media_part.mime_type = "audio/wav"
            except:
                pass # Return raw PCM if wave fails
            
            return GenerationResponse(
                content="",
                model=model_id,
                provider="dashscope",
                usage=TokenUsage(tts_input_characters=len(text)),
                finish_reason="stop",
                timing={"total": t1 - t0},
                media_parts=[media_part]
            )
            
        except Exception as e:
            raise RuntimeError(f"Qwen Realtime TTS Failed: {e}")

    def _generate_speech(self, model_id: str, text: str, config: Dict[str, Any]) -> GenerationResponse:
        """Handle Text-to-Speech task."""
        # Route to Realtime API if needed
        if "realtime" in model_id.lower():
            return self._generate_speech_realtime(model_id, text, config)
            
        from dashscope.audio.tts import SpeechSynthesizer
        
        # Standard REST API path
        t0 = time.time()
        voice_cfg = config.get("voice_config", {})
        voice = voice_cfg.get("voice_name", "sambert-zhichu-v1")
        fmt = config.get("audio_format", "mp3")
        
        call_args = {
            "model": model_id,
            "text": text,
            "format": fmt
        }
        
        # Cloning support (REST API specific)
        ref_audio = voice_cfg.get("reference_audio_uri")
        if ref_audio:
             # Standard REST cloning logic (failed with 401 for user, but kept for completeness)
             prompt_speech_path = None
             if ref_audio.startswith("file://"):
                 prompt_speech_path = ref_audio[7:]
             elif os.path.exists(ref_audio):
                 prompt_speech_path = ref_audio
             
             if prompt_speech_path:
                 try:
                     from pydub import AudioSegment
                     import tempfile
                     import os
                     ref_seg = AudioSegment.from_file(prompt_speech_path)
                     ref_seg = ref_seg.set_channels(1).set_frame_rate(16000)
                     if len(ref_seg) > 30000: ref_seg = ref_seg[:30000]
                     fd, temp_wav = tempfile.mkstemp(suffix=".wav")
                     os.close(fd)
                     ref_seg.export(temp_wav, format="wav")
                     call_args["prompt_speech"] = temp_wav
                 except Exception:
                     call_args["prompt_speech"] = prompt_speech_path
             else:
                 call_args["prompt_speech"] = ref_audio
                 
             if "reference_text" in voice_cfg:
                 call_args["prompt_text"] = voice_cfg["reference_text"]
        else:
             call_args["voice"] = voice

        result = SpeechSynthesizer.call(**call_args)
        
        if result.get_audio_data() is not None:
            audio_data = result.get_audio_data()
            t1 = time.time()
            
            media_part = ContentPart(
                type="audio",
                inline_data=audio_data,
                mime_type=f"audio/{fmt}"
            )
            
            return GenerationResponse(
                content="",
                model=model_id,
                provider="dashscope",
                usage=TokenUsage(tts_input_characters=len(text)),
                finish_reason="stop",
                timing={"total": t1 - t0},
                media_parts=[media_part]
            )
        else:
            # Enhanced Error Logging
            err_code = getattr(result, 'code', 'Unknown')
            err_msg = getattr(result, 'message', str(result))
            if hasattr(result, 'get_response'):
                try:
                    resp = result.get_response()
                    if isinstance(resp, dict):
                        err_code = resp.get('code', resp.get('status_code', err_code))
                        err_msg = resp.get('message', err_msg)
                except Exception:
                    pass
            raise RuntimeError(f"Qwen TTS Failed [{err_code}]: {err_msg}")

    def _recognize_speech(self, model_id: str, contents: ContentInput, config: Dict[str, Any]) -> GenerationResponse:
        """Handle ASR task using MultiModalConversation (matching ASRClient)."""
        import io
        
        t0 = time.time()
        
        # Extract audio content
        audio_part = None
        if isinstance(contents, list):
            for p in contents:
                if p.type == "audio":
                    audio_part = p
                    break
        
        if not audio_part:
             raise ValueError("ASR task requires audio content part.")
        
        # Prepare content for DashScope MultiModalConversation
        # Needs list of messages: [{"role": "user", "content": [{"audio": "..."}]}]
        
        audio_item = {}
        processed_data_b64 = None
        mime = "audio/mp3" # Default
        
        # Helper to convert/read audio to base64
        def prepare_audio_data(uri=None, raw_data=None, raw_mime=None):
            # Logic adapted from asr_client.py: Convert to 16k mono wav for best results
            try:
                from pydub import AudioSegment
                import io
                
                seg = None
                if uri:
                    if uri.startswith("file://"):
                        fpath = uri[7:]
                    else:
                        fpath = uri
                    seg = AudioSegment.from_file(fpath)
                elif raw_data:
                     # Load from bytes
                     # Need to know format or try guessing? 
                     # AudioSegment.from_file can accept file-like object
                     seg = AudioSegment.from_file(io.BytesIO(raw_data))
                
                if seg:
                    # Convert to 16k mono
                    seg = seg.set_channels(1).set_frame_rate(16000)
                    
                    # Export to WAV
                    buf = io.BytesIO()
                    seg.export(buf, format="wav")
                    return buf.getvalue(), "audio/wav"
            except Exception as e:
                # Fallback to authentic read if pydub fails or missing
                # logger.warning(f"Audio conversion failed: {e}")
                pass
                
            if uri:
                path = uri[7:] if uri.startswith("file://") else uri
                with open(path, "rb") as f:
                    return f.read(), "audio/mp3" # Assume mp3 or rely on header
            elif raw_data:
                return raw_data, raw_mime or "audio/mp3"
            return None, None

        # Logic
        final_bytes = None
        final_mime = None
        
        if audio_part.file_uri and (audio_part.file_uri.startswith("file://") or os.path.exists(audio_part.file_uri)):
             # Local File
             final_bytes, final_mime = prepare_audio_data(uri=audio_part.file_uri)
             
        elif audio_part.file_uri and not audio_part.file_uri.startswith("file://"):
             # Remote URL?
             audio_item["audio"] = audio_part.file_uri
             
        elif audio_part.inline_data:
             final_bytes, final_mime = prepare_audio_data(raw_data=audio_part.inline_data, raw_mime=audio_part.mime_type)
        
        if final_bytes:
            b64_data = base64.standard_b64encode(final_bytes).decode("utf-8")
            audio_item["audio"] = f"data:{final_mime};base64,{b64_data}"
        
        if "audio" not in audio_item:
             raise ValueError("Failed to prepare audio input for ASR.")

        messages = [
            # System prompt could be useful for specific instructions
            {
                "role": "user", 
                "content": [audio_item]
            }
        ]
        
        # Call MultiModalConversation
        response = dashscope.MultiModalConversation.call(
            model=model_id,
            messages=messages,
            result_format='message'
        )
        
        if response.status_code == HTTPStatus.OK:
            content = ""
            if response.output and response.output.choices:
                choice = response.output.choices[0]
                if choice.message and choice.message.content:
                    # Content is a list of items for MultiModal
                    for item in choice.message.content:
                        if 'text' in item:
                            content += item['text']
            
            t1 = time.time()
            return GenerationResponse(
                content=content,
                model=model_id,
                provider="dashscope",
                usage=TokenUsage(output_tokens=len(content)),
                finish_reason="stop",
                timing={"total": t1 - t0}
            )
        else:
             raise RuntimeError(f"Qwen ASR Failed: {response.code} - {response.message}")

    def generate(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        if not api_key:
            raise ValueError("API key required for Qwen")
            
        self._setup_endpoint(api_key)
        
        # Check TaskType routing
        config = kwargs.get("config", {})
        task = config.get("task")
        
        # 1. Image Generation
        if task == TaskType.IMAGE_GENERATION or "image" in model_id:
            # Normalize prompt
            prompt = ""
            if isinstance(contents, str):
                prompt = contents
            else:
                prompt = " ".join([p.text for p in contents if p.type == "text" and p.text])
            return self._generate_image(model_id, prompt, config)
            
        # 2. TTS
        if task == TaskType.TTS:
            text = ""
            if isinstance(contents, str):
                text = contents
            else:
                text = " ".join([p.text for p in contents if p.type == "text" and p.text])
            return self._generate_speech(model_id, text, config)

        # 3. ASR
        if task == TaskType.ASR:
            return self._recognize_speech(model_id, contents, config)
            
        # 4. Default: Text Generation / Multimodal Understanding
        t0 = time.time()
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
        # Stream only supported for Text Generation currently
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

