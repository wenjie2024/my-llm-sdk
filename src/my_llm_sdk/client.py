import asyncio
import os
import time
from typing import Optional, Dict, Union, Iterator, AsyncIterator, List
from contextlib import contextmanager, nullcontext
from my_llm_sdk.config.loader import load_config
from my_llm_sdk.budget.controller import BudgetController
from my_llm_sdk.budget.pricing import calculate_estimated_cost, calculate_actual_cost, estimate_content_tokens
from my_llm_sdk.doctor.checker import Doctor
from my_llm_sdk.doctor.report import print_report
from my_llm_sdk.providers.base import BaseProvider, EchoProvider
from my_llm_sdk.providers.gemini import GeminiProvider
from my_llm_sdk.providers.qwen import QwenProvider
from my_llm_sdk.providers.volcengine import VolcengineProvider
from my_llm_sdk.config.exceptions import ConfigurationError
from my_llm_sdk.utils.network import bypass_proxy
from my_llm_sdk.schemas import (
    GenerationResponse, StreamEvent, ContentInput, ContentPart, normalize_content
)


def _resolve_contents(prompt: str = None, contents: ContentInput = None) -> ContentInput:
    """
    Resolve input parameters to ContentInput.
    Supports backward compatibility: if `prompt` is provided, use it.
    Otherwise use `contents`.
    """
    if prompt is not None:
        return prompt
    if contents is not None:
        return contents
    raise ValueError("Either 'prompt' or 'contents' must be provided.")


def _get_text_for_estimation(contents: ContentInput) -> str:
    """
    Extract text representation for cost estimation.
    Handles mixed types: str, PIL.Image, ContentPart.
    """
    if isinstance(contents, str):
        return contents
    
    parts = []
    for p in contents:
        # Handle str directly
        if isinstance(p, str):
            parts.append(p)
        # Handle PIL.Image
        elif hasattr(p, 'mode') and hasattr(p, 'size'):  # Duck-type PIL.Image check
            parts.append("[IMAGE:1000tokens]")
        # Handle ContentPart
        elif hasattr(p, 'type'):
            if p.type == "text" and p.text:
                parts.append(p.text)
            elif p.type == "image":
                parts.append("[IMAGE:1000tokens]")
            elif p.type == "audio":
                parts.append("[AUDIO:500tokens]")
            elif p.type == "video":
                parts.append("[VIDEO:2000tokens]")
    return " ".join(parts)

class LLMClient:
    def __init__(self, project_config_path: str = None, user_config_path: str = None):
        # 1. Load Config
        # Priority: explicit path > ./config.yaml > ~/.config/llm-sdk/config.yaml
        p_path = project_config_path or "llm.project.yaml"
        
        if user_config_path:
            u_path = user_config_path
        elif os.path.exists("config.yaml"):
            u_path = "config.yaml"  # CWD first
        else:
            u_path = "~/.config/llm-sdk/config.yaml"  # Fallback
        
        self.config = load_config(p_path, u_path)
        
        # 2. Init Budget Controller
        self.budget = BudgetController(self.config)
        
        # 3. Init Diagnostics
        self.doctor = Doctor(self.config, self.budget.ledger)
        
        # 4. Init Rate Limiter [NEW]
        from my_llm_sdk.budget.rate_limiter import RateLimiter
        self.rate_limiter = RateLimiter(self.budget.ledger)
        
        # 5. Init Providers
        self.providers: Dict[str, BaseProvider] = {
            "openai": EchoProvider(),
            "echo": EchoProvider(),
            "google": GeminiProvider(),
        }
        
        # Init DashScope/Qwen with network context awareness
        # This ensures endpoint selection (INTL vs China) respects bypass settings
        with self._get_network_context("dashscope"):
            self.providers["dashscope"] = QwenProvider()

        # Init Volcengine
        with self._get_network_context("volcengine"):
            self.providers["volcengine"] = VolcengineProvider()
        
        # 6. Init Resilience Manager [NEW]
        from my_llm_sdk.utils.resilience import RetryManager
        self.retry_manager = RetryManager(self.config.resilience)
        
        # 7. Init Voice Service [P1]
        from my_llm_sdk.services.voice import VoiceService
        self.voice = VoiceService(self)

    def _get_network_context(self, provider_name: str):
        """
        Returns appropriate network context for a provider.
        China providers (alibaba, volcengine, etc.) bypass system proxy for direct connection.
        """
        if not self.config.network.proxy_bypass_enabled:
             return nullcontext()
             
        bypass_list = self.config.network.bypass_proxy
        if provider_name in bypass_list:
            return bypass_proxy()
        return nullcontext()


    def generate(
        self, 
        prompt: str = None, 
        model_alias: str = "default", 
        full_response: bool = False,
        *,
        contents: ContentInput = None,
        config: 'GenConfig' = None
    ) -> Union[str, GenerationResponse]:
        """
        Main entry point for generation.
        1. Resolve model alias
        2. Check budget & rate limits
        3. Call provider (with Retry)
        4. Track cost
        
        Args:
            prompt: Text prompt (backward compatible)
            model_alias: Model alias from registry
            full_response: Return full GenerationResponse or just content string
            contents: Multimodal content input
            config: GenConfig for multimodal task configuration
        """
        # 0. Resolve input (backward compatible)
        resolved_contents = _resolve_contents(prompt, contents)
        text_for_estimation = _get_text_for_estimation(resolved_contents)
        
        # 1. Resolve Model
        model_def = self.config.final_model_registry.get(model_alias)
        if not model_def:
            raise ValueError(f"Model alias '{model_alias}' not found in registry.")
            
        provider_name = model_def.provider
        provider_instance = self.providers.get(provider_name)
        if not provider_instance:
            provider_instance = EchoProvider()
        
        # 1.5. Validate API Key (Early fail with clear error)
        api_key = self.config.api_keys.get(provider_name)
        if not api_key and provider_name not in ["echo"]:
            raise ConfigurationError(
                f"Missing API key for provider '{provider_name}'. "
                f"Please add 'api_keys.{provider_name}' to your config.yaml."
            )
            
        # 2. Pre-check Budget & Rate Limits
        estimated_cost = calculate_estimated_cost(model_def.model_id, text_for_estimation, max_output_tokens=1000, config=self.config)
        estimated_tokens = len(text_for_estimation) // 4
        
        # Check Budget
        self.budget.check_budget(estimated_cost)
        
        # Check Rate Limits
        self.rate_limiter.check_limits(
            model_id=model_def.model_id,
            rpm=model_def.rpm,
            rpd=model_def.rpd,
            tpm=model_def.tpm,
            estimated_tokens=estimated_tokens
        )
        
        # 3. Execute with Retry
        response_obj = None
        status = 'success'
        try:
            
            # Wrap generation with Retry Policy
            # Note: We want to retry the provider call, not the whole generate method (which re-checks budget)
            # We use the retry_policy decorator on the fly or pre-wrap.
            # Easiest: use the manager to wrap the unbound method or just a closure.
            
            # Define the operation to retry
            def _op():
                # P1: Resolve optimize_images (B+A pattern)
                effective_config = dict(config) if config else {}
                if effective_config.get("optimize_images") is None:
                    # Fix: User exposed settings dict in MergedConfig
                    project_settings = getattr(self.config, "settings", {})
                    effective_config["optimize_images"] = project_settings.get("optimize_images", True)
                    
                    # P2: Inject global max_output_tokens default if not set in request
                    if "max_output_tokens" not in effective_config and "max_output_tokens" in project_settings:
                         effective_config["max_output_tokens"] = project_settings["max_output_tokens"]
                         
                # Check for configured endpoint
                # Config structure: config.yaml -> endpoints -> provider_name
                # self.config is MergedConfig which wraps project and user config.
                base_url = None
                # Access via attribute 'provider_endpoints' (Dict[str, str])
                if hasattr(self.config, "provider_endpoints"):
                    base_url = self.config.provider_endpoints.get(provider_name)
                    
                # Pass base_url if found
                gen_kwargs = {
                    "model_id": model_def.model_id, 
                    "contents": resolved_contents, 
                    "api_key": api_key,
                    "config": effective_config
                }
                if base_url:
                    gen_kwargs["base_url"] = base_url
                
                return provider_instance.generate(**gen_kwargs)
            
            # Decorate it manually
            retriable_op = self.retry_manager.retry_policy(_op)
            
            # Execute (with proxy bypass for China providers)
            with self._get_network_context(provider_name):
                response_obj = retriable_op()
            
            # 4. Post-update Ledger (Using accurate data)
            # Calculate cost based on ACTUAL usage if available
            final_cost = estimated_cost 
            
            input_tokens = 0
            output_tokens = 0
            
            if response_obj.usage:
                input_tokens = response_obj.usage.input_tokens
                output_tokens = response_obj.usage.output_tokens
                final_cost = calculate_actual_cost(model_def.model_id, response_obj.usage, self.config)

            # Recalculate cost based on actual response content length
            if not response_obj.usage:
                final_cost = calculate_estimated_cost(model_def.model_id, text_for_estimation + response_obj.content, max_output_tokens=0, config=self.config)
            
            self.budget.track(
                provider=provider_name,
                model=model_def.model_id,
                cost=final_cost,
                status=status,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            # 5. Persist Media [P2]
            # Default to True unless explicitly disabled
            should_persist = True
            persist_dir = None
            if config:
                should_persist = config.get('persist_media', True)
                persist_dir = config.get('persist_dir')
            
            if should_persist and response_obj.media_parts:
                self._persist_media(response_obj, persist_dir)
            
        except Exception as e:
            status = 'failed'
            # Track failure cost
            self.budget.track(
                provider=provider_name,
                model=model_def.model_id,
                cost=0.0,
                status=status
            )
            raise e
            
        if full_response:
            # Populate cost in response object too
            response_obj.cost = final_cost
            return response_obj
        else:
            return response_obj.content

    def _persist_media(self, response: GenerationResponse, save_dir: Optional[str] = None):
        """Helper to save media parts to local filesystem."""
        from my_llm_sdk.utils.media import save_artifact
        import datetime
        
        if not save_dir:
            # Default: outputs/YYYYMMDD
            date_str = datetime.date.today().strftime("%Y%m%d")
            save_dir = os.path.join(os.getcwd(), "outputs", date_str)
            
        for part in response.media_parts:
            if part.inline_data:
                # Use provider/model as prefix
                prefix = f"{response.provider}_{response.model.split('/')[-1]}_{part.type}"
                
                saved_path = save_artifact(
                    data=part.inline_data,
                    mime_type=part.mime_type or "application/octet-stream",
                    save_dir=save_dir,
                    filename_prefix=prefix
                )
                part.local_path = saved_path



    def stream(
        self, 
        prompt: str = None, 
        model_alias: str = "default",
        *,
        contents: ContentInput = None
    ) -> Iterator[StreamEvent]:
        """
        Stream generation.
        1. Pre-check budget/limits.
        2. Yield events.
        3. On finish, record to Ledger.
        """
        # 0. Resolve input
        resolved_contents = _resolve_contents(prompt, contents)
        text_for_estimation = _get_text_for_estimation(resolved_contents)
        
        # 1. Resolve Model
        model_def = self.config.final_model_registry.get(model_alias)
        if not model_def:
            raise ValueError(f"Model alias '{model_alias}' not found in registry.")
            
        provider_name = model_def.provider
        provider_instance = self.providers.get(provider_name)
        if not provider_instance:
            provider_instance = EchoProvider()
            
        # 2. Pre-check (Estimate)
        estimated_cost = calculate_estimated_cost(model_def.model_id, text_for_estimation, max_output_tokens=1000, config=self.config)
        self.budget.check_budget(estimated_cost)
        
        # Check Rate Limits
        self.rate_limiter.check_limits(
            model_id=model_def.model_id,
            rpm=model_def.rpm,
            rpd=model_def.rpd,
            tpm=model_def.tpm,
            estimated_tokens=len(text_for_estimation) // 4
        )
        
        # 3. Stream
        retry_manager = self.retry_manager
        retries = 0
        
        status = 'success'
        accumulated_content = ""
        final_usage = None
        
        try:
            with self._get_network_context(provider_name):
                while True:
                    try:
                        stream_gen = provider_instance.stream(model_def.model_id, resolved_contents, self.config.api_keys.get(provider_name))
                        
                        # Fetch first item to validate connection
                        try:
                            first_event = next(stream_gen)
                        except StopIteration:
                            # Healthy but empty
                            break
                        
                        # If success, yield first event
                        yield first_event
                        
                        if first_event.delta:
                             accumulated_content += first_event.delta
                        if first_event.usage:
                             final_usage = first_event.usage
                        
                        # Yield remainder
                        for event in stream_gen:
                            if event.delta:
                                accumulated_content += event.delta
                            
                            if event.usage:
                                final_usage = event.usage
                            
                            yield event
                            
                            if event.error:
                                status = 'failed'
                        
                        break # Done
    
                    except StopIteration:
                        break
                    except Exception as e:
                        if retry_manager.should_retry(e, retries):
                             delay = retry_manager.calculate_delay(retries)
                             print(f"⚠️ Stream Retry ({retries+1}) due to: {e}. Waiting {delay:.2f}s...")
                             time.sleep(delay)
                             retries += 1
                             continue
                        status = 'failed'
                        raise e
        finally:
            # 4. Post-Update Ledger
            # If we got usage, usage it. Else estimate.
            input_tokens = 0
            output_tokens = 0
            
            if final_usage:
                input_tokens = final_usage.input_tokens
                output_tokens = final_usage.output_tokens
                # Recalculate cost? For now approximate with estimate logic using full content
                final_cost = calculate_actual_cost(model_def.model_id, final_usage, self.config)
            else:
                final_cost = calculate_estimated_cost(model_def.model_id, text_for_estimation + accumulated_content, max_output_tokens=0, config=self.config)
            
            self.budget.track(
                provider=provider_name,
                model=model_def.model_id,
                cost=final_cost,
                status=status,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
    async def generate_async(
        self, 
        prompt: str = None, 
        model_alias: str = "default", 
        full_response: bool = False,
        *,
        contents: ContentInput = None,
        config: 'GenConfig' = None
    ) -> Union[str, GenerationResponse]:
        """Async version of generate."""
        # 0. Resolve input
        resolved_contents = _resolve_contents(prompt, contents)
        text_for_estimation = _get_text_for_estimation(resolved_contents)
        
        # 1. Resolve Model
        model_def = self.config.final_model_registry.get(model_alias)
        if not model_def:
            raise ValueError(f"Model alias '{model_alias}' not found in registry.")
            
        provider_name = model_def.provider
        provider_instance = self.providers.get(provider_name)
        if not provider_instance:
            provider_instance = EchoProvider()
            
        # 2. Pre-check Budget & Rate Limits (Async Check)
        estimated_cost = calculate_estimated_cost(model_def.model_id, text_for_estimation, max_output_tokens=1000, config=self.config)
        await self.budget.acheck_budget(estimated_cost)
        
        estimated_tokens = len(text_for_estimation) // 4
        await asyncio.to_thread(
            self.rate_limiter.check_limits, 
            model_id=model_def.model_id,
            rpm=model_def.rpm,
            rpd=model_def.rpd,
            tpm=model_def.tpm,
            estimated_tokens=estimated_tokens
        )
        
        # 3. Execute Async
        response_obj = None
        status = 'success'
        try:
             api_key = self.config.api_keys.get(provider_name)
             
             async def _op():
                 # P1: Resolve optimize_images (B+A pattern) - same as sync
                 effective_config = dict(config) if config else {}
                 if effective_config.get("optimize_images") is None:
                     project_settings = getattr(self.config, "settings", {})
                     effective_config["optimize_images"] = project_settings.get("optimize_images", True)

                 base_url = None
                 if hasattr(self.config, "provider_endpoints"):
                     base_url = self.config.provider_endpoints.get(provider_name)
                 
                 gen_kwargs = {
                     "model_id": model_def.model_id, 
                     "contents": resolved_contents, 
                     "api_key": api_key,
                     "config": effective_config
                 }
                 if base_url:
                     gen_kwargs["base_url"] = base_url

                 return await provider_instance.generate_async(**gen_kwargs)
             
             retriable_op = self.retry_manager.retry_policy(_op)
             
             # Execute (with proxy bypass for China providers)
             with self._get_network_context(provider_name):
                 response_obj = await retriable_op()
             
             # 4. Post-Update Ledger (Async)
             final_cost = estimated_cost
             input_tokens = 0
             output_tokens = 0
             
             if response_obj.usage:
                 input_tokens = response_obj.usage.input_tokens
                 output_tokens = response_obj.usage.output_tokens
                 final_cost = calculate_actual_cost(model_def.model_id, response_obj.usage, self.config)
             else:
                 final_cost = calculate_estimated_cost(model_def.model_id, text_for_estimation + response_obj.content, max_output_tokens=0, config=self.config)
             
             await self.budget.atrack(
                 provider=provider_name,
                 model=model_def.model_id,
                 cost=final_cost,
                 status=status,
                 input_tokens=input_tokens,
                 output_tokens=output_tokens
             )
             
             # 5. Persist Media [P2]
             should_persist = True
             persist_dir = None
             if config:
                 should_persist = config.get('persist_media', True)
                 persist_dir = config.get('persist_dir')
             
             if should_persist and response_obj.media_parts:
                 # Run in thread to allow non-blocking save
                 await asyncio.to_thread(self._persist_media, response_obj, persist_dir)
             
        except Exception as e:
            status = 'failed'
            await self.budget.atrack(
                 provider=provider_name,
                 model=model_def.model_id,
                 cost=0.0,
                 status=status
            )
            raise e

        if full_response:
            response_obj.cost = final_cost if 'final_cost' in locals() else 0.0
            return response_obj
        else:
            return response_obj.content

    async def stream_async(
        self, 
        prompt: str = None, 
        model_alias: str = "default",
        *,
        contents: ContentInput = None
    ) -> AsyncIterator[StreamEvent]:
        """Async stream generation."""
        # 0. Resolve input
        resolved_contents = _resolve_contents(prompt, contents)
        text_for_estimation = _get_text_for_estimation(resolved_contents)
        
        # 1. Resolve Model
        model_def = self.config.final_model_registry.get(model_alias)
        if not model_def:
            raise ValueError(f"Model alias '{model_alias}' not found in registry.")
        
        provider_name = model_def.provider
        provider_instance = self.providers.get(provider_name)
        if not provider_instance:
            provider_instance = EchoProvider()
            
        # 2. Pre-check
        estimated_cost = calculate_estimated_cost(model_def.model_id, text_for_estimation, max_output_tokens=1000, config=self.config)
        await self.budget.acheck_budget(estimated_cost)
        
        estimated_tokens = len(text_for_estimation) // 4
        await asyncio.to_thread(
            self.rate_limiter.check_limits,
            model_id=model_def.model_id,
            rpm=model_def.rpm,
            rpd=model_def.rpd,
            tpm=model_def.tpm,
            estimated_tokens=estimated_tokens
        )
        
        # 3. Stream
        status = 'success'
        retry_manager = self.retry_manager
        retries = 0
        
        accumulated_content = ""
        final_usage = None

        try:
            with self._get_network_context(provider_name):
                while True:
                    try:
                        stream_gen = provider_instance.stream_async(model_def.model_id, resolved_contents, self.config.api_keys.get(provider_name))
                        
                        # Fetch first item to validate connection
                        try:
                            first_event = await stream_gen.__anext__()
                        except StopAsyncIteration:
                            break
                        
                        # If success, yield first event
                        yield first_event
                        
                        if first_event.delta:
                             accumulated_content += first_event.delta
                        if first_event.usage:
                             final_usage = first_event.usage
                        
                        # Yield remainder
                        async for event in stream_gen:
                            if event.delta:
                                accumulated_content += event.delta
                            if event.usage:
                                final_usage = event.usage
                            
                            yield event
                            
                            if event.error:
                                status = 'failed'
                        
                        break
    
                    except StopAsyncIteration:
                        break
                    except Exception as e:
                        if retry_manager.should_retry(e, retries):
                             delay = retry_manager.calculate_delay(retries)
                             print(f"⚠️ Async Stream Retry ({retries+1}) due to: {e}. Waiting {delay:.2f}s...")
                             await asyncio.sleep(delay)
                             retries += 1
                             continue
                        status = 'failed'
                        raise e
        finally:
            # 4. Post-Update Ledger (Async)
            input_tokens = 0
            output_tokens = 0
            
            if final_usage:
                input_tokens = final_usage.input_tokens
                output_tokens = final_usage.output_tokens
                final_cost = calculate_actual_cost(model_def.model_id, final_usage, self.config)
            else:
                final_cost = calculate_estimated_cost(model_def.model_id, text_for_estimation + accumulated_content, max_output_tokens=0, config=self.config)
            
            await self.budget.atrack(
                provider=provider_name,
                model=model_def.model_id,
                cost=final_cost,
                status=status,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
    async def run_doctor(self):
        """Run diagnostics and print report."""
        report = await self.doctor.run_diagnostics()
        print_report(report)
