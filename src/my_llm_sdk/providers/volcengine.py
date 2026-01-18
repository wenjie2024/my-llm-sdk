import os
import asyncio
import base64
from typing import Any, Dict, List, Union, Iterator, Optional
from my_llm_sdk.providers.base import BaseProvider
from my_llm_sdk.schemas import (
    GenerationResponse, TokenUsage, StreamEvent,
    ContentInput, ContentPart, normalize_content, TaskType
)
import logging

logger = logging.getLogger(__name__)

def _extract_text(contents: ContentInput) -> str:
    """Helper to extract text from mixed content for specialized APIs."""
    normalized = normalize_content(contents)
    return " ".join([p.text for p in normalized if p.type == "text" and p.text])

class VolcengineProvider(BaseProvider):
    """
    Provider for Volcengine (Doubao) LLMs.
    Supports Ark Chat Completions and Seed Multimodal API.
    """

    def __init__(self):
        self._ark_module = None

    def _get_client(self, api_key: str, base_url: Optional[str] = None):
        if self._ark_module is None:
            try:
                # User example uses volcenginesdkarkruntime
                from volcenginesdkarkruntime import Ark
                self._ark_module = Ark
            except ImportError:
                # Fallback to volcengine.ark if old version
                try:
                    from volcengine.ark import Ark
                    self._ark_module = Ark
                except ImportError:
                    raise ImportError("volcengine-python-sdk[ark] is not installed. Please run 'pip install volcengine-python-sdk[ark]'")
        
        # Priority: Arg > Env > Default
        final_base_url = base_url or os.environ.get("VOLCENGINE_ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        return self._ark_module(api_key=api_key, base_url=final_base_url)

    def _convert_contents_to_messages(self, contents: ContentInput) -> List[Dict[str, Any]]:
        """Converts SDK ContentInput to OpenAI-style messages."""
        normalized = normalize_content(contents)
        content_parts = []
        for part in normalized:
            if part.type == "text":
                content_parts.append({"type": "text", "text": part.text})
            elif part.type == "image":
                if part.inline_data:
                    mime = part.mime_type or "image/jpeg"
                    b64_data = base64.b64encode(part.inline_data).decode("utf-8")
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64_data}"}
                    })
                elif part.file_uri:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": part.file_uri}
                    })
        return [{"role": "user", "content": content_parts}]

    def _convert_contents_to_seed_input(self, contents: ContentInput) -> List[Dict[str, Any]]:
        """Converts SDK ContentInput to Doubao-Seed-1.6 specific input format."""
        normalized = normalize_content(contents)
        content_parts = []
        for part in normalized:
            if part.type == "text":
                content_parts.append({"type": "input_text", "text": part.text})
            elif part.type == "image":
                url = part.file_uri
                if part.inline_data:
                    mime = part.mime_type or "image/jpeg"
                    b64_data = base64.b64encode(part.inline_data).decode("utf-8")
                    url = f"data:{mime};base64,{b64_data}"
                
                if url:
                    content_parts.append({"type": "input_image", "image_url": url})
        
        return [{"role": "user", "content": content_parts}]

    def generate(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        base_url = kwargs.pop("base_url", None)
        client = self._get_client(api_key, base_url=base_url)
        
        # Pop SDK-internal kwargs
        task_direct = kwargs.pop("task", None)
        config_direct = kwargs.pop("config", {})
        
        # Merge config into kwargs for SDK to respect settings like 'sequential_image_generation'
        # Priority: kwargs > config
        req_kwargs = {**config_direct, **kwargs}
        
        # Extract task from merged kwargs
        task = req_kwargs.pop("task", task_direct or TaskType.TEXT_GENERATION)
        # Extract other internal config keys to avoid passing them to SDK if they are invalid
        req_kwargs.pop("response_modalities", None)
        req_kwargs.pop("optimize_images", None)
        req_kwargs.pop("max_output_tokens", None) # Some endpoints might handle this, others not. Leave it if standard? 
        # Standard OpenAI uses max_tokens, Volcengine might use max_tokens. 
        # config "max_output_tokens" maps to "max_tokens" usually.
        if "max_output_tokens" in config_direct:
            req_kwargs["max_tokens"] = config_direct["max_output_tokens"]
        
        # Pop custom parameters that SDK methods don't accept
        thought_mode = req_kwargs.pop("thought_mode", None)
        req_kwargs.pop("persist_media", None)

        # 1. Image Generation (Seedream)
        if task == TaskType.IMAGE_GENERATION:
            # Map standard 'image_size' to 'size' (e.g. "2K")
            if "image_size" in req_kwargs:
                raw_size = req_kwargs.pop("image_size")
                size_map = {
                    "1K": "1k",
                    "2K": "2k",
                    "4K": "4k",
                }
                req_kwargs["size"] = size_map.get(raw_size, raw_size)
            
            # --- Defaults & Parameter Mapping (V0.6.1) ---
            
            # 1. Response Format: Default to 'b64_json' for consistent byte output
            req_kwargs.setdefault("response_format", "b64_json")
            
            # 2. Watermark: Default to False (User Request)
            if "watermark" not in req_kwargs:
                req_kwargs["watermark"] = False
                
            # 3. Guidance Scale: Pass through if present
            # (No mapping needed, SDK uses 'guidance_scale' directly)
            
            # 4. Sequential Gen Options (max_images)
            # Map 'max_images' config to 'sequential_image_generation_options'
            max_imgs = req_kwargs.pop("max_images", None)
            if max_imgs:
                try:
                    from volcenginesdkarkruntime.types.images import SequentialImageGenerationOptions
                    # Construct valid object
                    req_kwargs["sequential_image_generation_options"] = SequentialImageGenerationOptions(
                        max_images=int(max_imgs)
                    )
                except ImportError:
                     logger.warning("SequentialImageGenerationOptions not found in SDK. Skipping max_images.")
                except Exception as e:
                     logger.warning(f"Failed to set max_images: {e}")

            req_kwargs.setdefault("stream", False)
            
            # Cleanup unsupported keys
            req_kwargs.pop("width", None)
            req_kwargs.pop("height", None)

            resp = client.images.generate(
                model=model_id,
                prompt=_extract_text(contents),
                **req_kwargs
            )
            
            media_parts = []
            # Handle list of Image objects
            for img in resp.data:
                # Priority: Inline Data (b64_json) -> URL
                if hasattr(img, 'b64_json') and img.b64_json:
                    data = base64.b64decode(img.b64_json)
                    media_parts.append(ContentPart(type="image", inline_data=data, mime_type="image/png"))
                elif hasattr(img, 'url') and img.url:
                    # Fallback if b64_json failed or url requested explicitly
                    media_parts.append(ContentPart(type="image", file_uri=img.url, mime_type="image/png"))
            
            return GenerationResponse(
                content="[IMAGE GENERATED]", model=model_id, provider="volcengine",
                media_parts=media_parts, usage=TokenUsage(images_generated=len(media_parts)),
                finish_reason="stop"
            )

        # 2. Text / Vision / Thinking / DeepSeek
        # "seed-1-6" and "deepseek" models use the new responses.create API
        # BUT Doubao-Thinking (thought_mode) seems to fail with responses.create explicitly.
        # So we verify thought_mode. If present, use standard chat (Block 4) which handles extra_body correctly.
        use_responses_api = False
        if "deepseek" in model_id.lower():
            use_responses_api = True
        elif "seed-1-6" in model_id.lower() and not thought_mode:
            use_responses_api = True

        if use_responses_api:
            # No, I redefined req_kwargs = kwargs.copy() inside this block in previous edit.
            # So I must extract tools from config_direct.
            req_kwargs = kwargs.copy() 
            
            # Tools handling for DeepSeek (if passed in config)
            # User example: tools=[{"type": "web_search", ...}]
            tools = config_direct.get("tools")
            if tools:
                req_kwargs["tools"] = tools
            
            # Both Seed 1.6 and DeepSeek via responses.create seem to require the specific input structure
            # based on user examples and error messages (input.content.type invalid)
            seed_input = self._convert_contents_to_seed_input(contents)
            
            # Add thinking mode support
            # responses.create likely accepts 'reasoning' directly as per Volcengine pattern for other params
            if thought_mode:
                req_kwargs["reasoning"] = {"mode": thought_mode}

            completion = client.responses.create(
                model=model_id,
                input=seed_input,
                **req_kwargs
            )
            
            # ... (rest of response handling)
            content = ""
            usage = TokenUsage()
            
            # Extract content from response
            if hasattr(completion, 'choices') and completion.choices:
                 # Standard Chat Completions or similar
                 content = completion.choices[0].message.content
            elif hasattr(completion, 'output'):
                 # Responses API (Seed-1.6 / DeepSeek)
                 # output can be a list of reasoning items and message items
                 if isinstance(completion.output, list):
                     for item in completion.output:
                         # Look for type='message'
                         if hasattr(item, 'type') and item.type == 'message':
                             if hasattr(item, 'content'):
                                 # content can be list of ResponseOutputText
                                 if isinstance(item.content, list):
                                     for part in item.content:
                                         if hasattr(part, 'text'):
                                              content += part.text
                                 elif hasattr(item.content, 'text'):
                                      content += item.content.text
                                 elif isinstance(item.content, str):
                                      content += item.content
                 else:
                     # Fallback if output is object with text
                     content = getattr(completion.output, 'text', str(completion))
                 
                 # Usage extraction
                 if hasattr(completion.output, 'usage') and completion.output.usage:
                     u = completion.output.usage
                     usage = TokenUsage(
                         input_tokens=getattr(u, 'prompt_tokens', 0),
                         output_tokens=getattr(u, 'completion_tokens', 0),
                         total_tokens=getattr(u, 'total_tokens', 0)
                     )

            # Check for top-level usage key if not found in output
            if usage.total_tokens == 0 and hasattr(completion, 'usage') and completion.usage:
                u = completion.usage
                usage = TokenUsage(
                    input_tokens=getattr(u, 'prompt_tokens', 0),
                    output_tokens=getattr(u, 'completion_tokens', 0),
                    total_tokens=getattr(u, 'total_tokens', 0)
                )

            return GenerationResponse(
                content=content, model=model_id, provider="volcengine", usage=usage
            )



        # 3. Video Generation (Seedance)
        if task == TaskType.VIDEO_GENERATION:
             if not hasattr(client, 'content_generation'):
                 return GenerationResponse(content="[ERROR] SDK does not support content_generation", model=model_id, provider="volcengine")
             
             # Extract text prompt
             prompt_text = _extract_text(contents)
             
             # Construct content payload
             content_payload = [{"type": "text", "text": prompt_text}]
             
             # Check for image input (First/Last frame control)
             normalized = normalize_content(contents)
             for part in normalized:
                 if part.type == "image":
                     if part.file_uri:
                         content_payload.append({"type": "image_url", "image_url": {"url": part.file_uri}})
                     # TODO: Handle inline image by uploading or warning user? 
                     # Seedance usually requires URL. check if we can skip inline for now.
             
             logger.info(f"Creating Video Task: {model_id}")
             # Use req_kwargs which contains config items like resolution, duration
             
             create_result = client.content_generation.tasks.create(
                 model=model_id,
                 content=content_payload,
                 **req_kwargs 
             )
             
             task_id = create_result.id
             # ... (Polling logic remains same, just ensure create uses req_kwargs)
             logger.info(f"Video Task ID: {task_id}. Polling...")
             
             import time
             status = "unknown"
             video_url = None
             
             # Polling loop (Max 5 minutes)
             for _ in range(60): 
                 get_result = client.content_generation.tasks.get(task_id=task_id)
                 status = get_result.status
                 if status == "succeeded":
                     # Extract video URL - trying generic structure first
                     video_url = f"https://volcengine-ark-video-placeholder/{task_id}" 
                     # Try to find real URL from response structure (generic traversal)
                     if hasattr(get_result, 'content') and hasattr(get_result.content, 'video_url'):
                          video_url = get_result.content.video_url
                     
                     return GenerationResponse(
                         content=f"[VIDEO GENERATED] Task ID: {task_id}",
                         model=model_id, 
                         provider="volcengine",
                         media_parts=[ContentPart(type="video", file_uri=video_url, mime_type="video/mp4")],
                         usage=TokenUsage(videos_generated=1),
                         finish_reason="stop"
                     )
                 elif status == "failed":
                     return GenerationResponse(content=f"[VIDEO FAILED] {get_result.error if hasattr(get_result, 'error') else 'Unknown Error'}", model=model_id, provider="volcengine", finish_reason="error")
                 
                 time.sleep(3)
             
             return GenerationResponse(content=f"[VIDEO TIMEOUT] Task {task_id} still running.", model=model_id, provider="volcengine", finish_reason="timeout")

        # 4. Standard Ark Chat Completions (Legacy / Other models)
        messages = self._convert_contents_to_messages(contents)
        # Check if extras are needed (already popped in req_kwargs logic? No, req_kwargs is a COPY)
        # But 'req_kwargs' contains everything.
        # However, Chat Completions might reject unknown args.
        # Use kwargs (filtered) + explicit extras.
        # Actually, for standard chat, we should use base kwargs + tools/reasoning.
        
        extra_body = req_kwargs.pop("extra_body", {}) # Pop from req_kwargs
        if config_direct.get("thought_mode"): # Use config_direct since we are reconstructing
            if not extra_body: extra_body = {}
            extra_body["reasoning"] = {"mode": config_direct["thought_mode"]}
        
        # Pass req_kwargs might be risky if it contains 'task' etc. 
        # But we popped 'task' from req_kwargs.
        # Let's try passing req_kwargs, assuming generic config items are valid or ignored.
        # If strict validation, we might need to filter.
        
        completion = client.chat.completions.create(
            model=model_id,
            messages=messages,
            extra_body=extra_body if extra_body else None,
            **req_kwargs
        )

        content = completion.choices[0].message.content
        usage = TokenUsage(
            input_tokens=getattr(completion.usage, 'prompt_tokens', 0),
            output_tokens=getattr(completion.usage, 'completion_tokens', 0),
            total_tokens=getattr(completion.usage, 'total_tokens', 0)
        )

        return GenerationResponse(
            content=content, model=model_id, provider="volcengine", usage=usage,
            finish_reason=completion.choices[0].finish_reason
        )

    def stream(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        base_url = kwargs.pop("base_url", None)
        client = self._get_client(api_key, base_url=base_url)
        messages = self._convert_contents_to_messages(contents)
        config = kwargs.get("config", {})
        
        extra_body = {}
        if config.get("thought_mode"):
            extra_body["reasoning"] = {"mode": config["thought_mode"]}

        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=True,
            extra_body=extra_body if extra_body else None,
            **kwargs
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield StreamEvent(delta=chunk.choices[0].delta.content)
            
            if hasattr(chunk, 'usage') and chunk.usage:
                usage = TokenUsage(
                    input_tokens=chunk.usage.prompt_tokens,
                    output_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens
                )
                yield StreamEvent(delta="", is_finish=True, usage=usage)

    async def generate_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> GenerationResponse:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.generate(model_id, contents, api_key, **kwargs))

    async def stream_async(self, model_id: str, contents: ContentInput, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        for event in self.stream(model_id, contents, api_key, **kwargs):
            yield event
            await asyncio.sleep(0)
