import asyncio
import os
from typing import Optional, Dict
from my_llm_sdk.config.loader import load_config
from my_llm_sdk.budget.controller import BudgetController
from my_llm_sdk.budget.pricing import calculate_estimated_cost, calculate_actual_cost
from my_llm_sdk.doctor.checker import Doctor
from my_llm_sdk.doctor.report import print_report
from my_llm_sdk.providers.base import BaseProvider, EchoProvider
from my_llm_sdk.providers.gemini import GeminiProvider
from my_llm_sdk.providers.qwen import QwenProvider
from my_llm_sdk.config.exceptions import ConfigurationError

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
            "dashscope": QwenProvider()
        }
        
        # 6. Init Resilience Manager [NEW]
        from my_llm_sdk.utils.resilience import RetryManager
        self.retry_manager = RetryManager(self.config.resilience)

    from typing import Union
    from my_llm_sdk.schemas import GenerationResponse

    def generate(self, prompt: str, model_alias: str = "default", full_response: bool = False) -> Union[str, "GenerationResponse"]:
        """
        Main entry point for generation.
        1. Resolve model alias
        2. Check budget & rate limits
        3. Call provider (with Retry)
        4. Track cost
        """
        
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
        # Estimate cost & tokens
        estimated_cost = calculate_estimated_cost(model_def.model_id, prompt, max_output_tokens=1000, config=self.config)
        
        # Simple token estimation for TPM check (chars / 4)
        estimated_tokens = len(prompt) // 4
        
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
                return provider_instance.generate(model_def.model_id, prompt, api_key)
            
            # Decorate it manually
            retriable_op = self.retry_manager.retry_policy(_op)
            
            # Execute
            response_obj = retriable_op()
            
            # 4. Post-update Ledger (Using accurate data)
            # Calculate cost based on ACTUAL usage if available
            final_cost = estimated_cost 
            
            input_tokens = 0
            output_tokens = 0
            
            if response_obj.usage:
                input_tokens = response_obj.usage.input_tokens
                output_tokens = response_obj.usage.output_tokens
                
                # Re-calculate based on actual tokens
                # We need a pricing calculator that accepts token counts
                # For now, we reuse calculate_estimated_cost but with "tokens * 4" length approximation 
                # or better: we trust the provider? 
                # The pricing module handles price per 1k chars/tokens. 
                # Let's approximate back to chars for the pricing function: tokens * 4
                
                # FUTURE: Update pricing logic to accept TokenUsage directly.
                # For now, stick to estimate logic or simple update
                # Actually, let's just use the estimated cost logic using the RESPONSE CONTENT LENGTH + PROMPT LENGTH
                final_cost = calculate_actual_cost(model_def.model_id, response_obj.usage, self.config)

            # Recalculate cost based on actual response content length
            # If we trust estimated_cost for input, we just add output cost
            if not response_obj.usage:
                final_cost = calculate_estimated_cost(model_def.model_id, prompt + response_obj.content, max_output_tokens=0, config=self.config)
            
            # Attach timing/meta to ledger? V0.2 extensions support usage_json.
            # We can pass extended metadata if we modify track()
            
            self.budget.track(
                provider=provider_name,
                model=model_def.model_id,
                cost=final_cost,
                status=status,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
        except Exception as e:
            status = 'failed'
            # Track failure cost (usually 0, or estimated input cost if provider charged)
            self.budget.track(
                provider=provider_name,
                model=model_def.model_id,
                cost=0.0, # Failures don't cost? or should we count input? Usually 0 for API errors.
                status=status
            )
            raise e
            
        if full_response:
            # Populate cost in response object too
            response_obj.cost = final_cost
            return response_obj
        else:
            return response_obj.content

    from typing import Iterator
    from my_llm_sdk.schemas import StreamEvent

    def stream(self, prompt: str, model_alias: str = "default") -> Iterator["StreamEvent"]:
        """
        Stream generation.
        1. Pre-check budget/limits.
        2. Yield events.
        3. On finish, record to Ledger.
        """
        # 1. Resolve Model
        model_def = self.config.final_model_registry.get(model_alias)
        if not model_def:
            raise ValueError(f"Model alias '{model_alias}' not found in registry.")
            
        provider_name = model_def.provider
        provider_instance = self.providers.get(provider_name)
        if not provider_instance:
            provider_instance = EchoProvider()
            
        # 2. Pre-check (Estimate)
        estimated_cost = calculate_estimated_cost(model_def.model_id, prompt, max_output_tokens=1000, config=self.config)
        self.budget.check_budget(estimated_cost)
        
        # Check Rate Limits
        self.rate_limiter.check_limits(
            model_id=model_def.model_id,
            rpm=model_def.rpm,
            rpd=model_def.rpd,
            tpm=model_def.tpm,
            estimated_tokens=len(prompt) // 4
        )
        
        # 3. Stream
        status = 'success'
        stream_gen = provider_instance.stream(model_def.model_id, prompt, self.config.api_keys.get(provider_name))
        
        accumulated_content = ""
        final_usage = None
        
        try:
            for event in stream_gen:
                if event.delta:
                    accumulated_content += event.delta
                
                # Check for usage
                if event.usage:
                    final_usage = event.usage
                
                # Yield to user
                yield event
                
                if event.error:
                    status = 'failed'
                    # Should we re-raise? Or just let the error event handle it?
                    # We continue to let final logic run if possible, but usually error ends stream.
                    
        except Exception as e:
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
                 final_cost = calculate_estimated_cost(model_def.model_id, prompt + accumulated_content, max_output_tokens=0, config=self.config)
            
            self.budget.track(
                provider=provider_name,
                model=model_def.model_id,
                cost=final_cost,
                status=status,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
    async def generate_async(self, prompt: str, model_alias: str = "default", full_response: bool = False) -> Union[str, "GenerationResponse"]:
        """Async version of generate."""
        
        # 1. Resolve Model
        model_def = self.config.final_model_registry.get(model_alias)
        if not model_def:
            raise ValueError(f"Model alias '{model_alias}' not found in registry.")
            
        provider_name = model_def.provider
        provider_instance = self.providers.get(provider_name)
        if not provider_instance:
            provider_instance = EchoProvider()
            
        # 2. Pre-check Budget & Rate Limits (Async Check)
        estimated_cost = calculate_estimated_cost(model_def.model_id, prompt, max_output_tokens=1000, config=self.config)
        
        # Async check using Ledger cache/query
        await self.budget.acheck_budget(estimated_cost)
        
        # Rate Limit check (Local checks usually fast, but we might want async lock if SQLite contention high?
        # Current RateLimiter is sync. V0.3 Scope: keep RL sync or make async?
        # RL uses sqlite. In high concurrency, sync sqlite might block loop.
        # Ideally should use run_in_executor or make RL async.
        # For V0.3 Phase 4 Step 1: Wrap sync RL check in to_thread?
        # Or just accept blocking for ms? Let's wrap.
        estimated_tokens = len(prompt) // 4
        
        # Reuse sync check logic but in thread to avoid blocking loop on SQL
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
             
             # Reuse Retry Manager logic?
             # RetryManager supports async decorators.
             
             async def _op():
                 return await provider_instance.generate_async(model_def.model_id, prompt, api_key)
             
             retriable_op = self.retry_manager.retry_policy(_op)
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
                 final_cost = calculate_estimated_cost(model_def.model_id, prompt + response_obj.content, max_output_tokens=0, config=self.config)
             
             await self.budget.atrack(
                 provider=provider_name,
                 model=model_def.model_id,
                 cost=final_cost,
                 status=status,
                 input_tokens=input_tokens,
                 output_tokens=output_tokens
             )
             
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

    from typing import AsyncIterator
    
    async def stream_async(self, prompt: str, model_alias: str = "default") -> AsyncIterator["StreamEvent"]:
        """Async stream generation."""
        # 1. Resolve Model
        model_def = self.config.final_model_registry.get(model_alias)
        if not model_def:
            raise ValueError(f"Model alias '{model_alias}' not found in registry.")
            
        provider_name = model_def.provider
        provider_instance = self.providers.get(provider_name)
        if not provider_instance:
            provider_instance = EchoProvider()
            
        # 2. Pre-check
        estimated_cost = calculate_estimated_cost(model_def.model_id, prompt, max_output_tokens=1000, config=self.config)
        await self.budget.acheck_budget(estimated_cost)
        
        estimated_tokens = len(prompt) // 4
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
        stream_gen = provider_instance.stream_async(model_def.model_id, prompt, self.config.api_keys.get(provider_name))
        
        accumulated_content = ""
        final_usage = None
        
        try:
            async for event in stream_gen:
                if event.delta:
                     accumulated_content += event.delta
                if event.usage:
                     final_usage = event.usage
                
                yield event
                
                if event.error:
                    status = 'failed'
                    
        except Exception as e:
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
                 final_cost = calculate_estimated_cost(model_def.model_id, prompt + accumulated_content, max_output_tokens=0, config=self.config)
            
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
