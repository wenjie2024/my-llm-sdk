import asyncio
from typing import Optional, Dict
from src.config.loader import load_config
from src.budget.controller import BudgetController
from src.budget.pricing import calculate_estimated_cost
from src.doctor.checker import Doctor
from src.doctor.report import print_report
from src.providers.base import BaseProvider, EchoProvider
from src.providers.gemini import GeminiProvider
from src.providers.qwen import QwenProvider

class LLMClient:
    def __init__(self, project_config_path: str = None, user_config_path: str = None):
        # 1. Load Config
        # In real usage, might default paths or traverse up
        p_path = project_config_path or "llm.project.yaml"
        u_path = user_config_path or "~/.config/llm-sdk/config.yaml"
        
        self.config = load_config(p_path, u_path)
        
        # 2. Init Budget Controller
        self.budget = BudgetController(self.config)
        
        # 3. Init Diagnostics
        self.doctor = Doctor(self.config, self.budget.ledger)
        
        # 4. Init Rate Limiter [NEW]
        from src.budget.rate_limiter import RateLimiter
        self.rate_limiter = RateLimiter(self.budget.ledger)
        
        # 5. Init Providers
        self.providers: Dict[str, BaseProvider] = {
            "openai": EchoProvider(),
            "echo": EchoProvider(),
            "google": GeminiProvider(),
            "dashscope": QwenProvider()
        }

    def generate(self, prompt: str, model_alias: str = "default") -> str:
        """
        Main entry point for generation.
        1. Resolve model alias
        2. Check budget & rate limits
        3. Call provider
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
            
        # 2. Pre-check Budget & Rate Limits
        # Estimate cost & tokens
        estimated_cost = calculate_estimated_cost(model_def.model_id, prompt, max_output_tokens=1000)
        
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
        
        # 3. Execute
        try:
            api_key = self.config.api_keys.get(provider_name)
            response = provider_instance.generate(model_def.model_id, prompt, api_key)
            status = 'success'
        except Exception as e:
            status = 'failed'
            response = ""
            raise e
        finally:
            # 4. Post-update Ledger
            # In real world, calculate token usage from response
            # For strict correctness, we should re-calculate actual cost based on response length
            actual_input_cost = estimated_cost # Simplify: assume input checked matches
            # Re-calculate output cost based on actual response length
            # Note: This is an approximation. Real-world would use Tokenizer count of response.
            actual_output_cost = calculate_estimated_cost(model_def.model_id, response, max_output_tokens=0) 
            
            # Simple approximation for now: just use estimated input + estimated/actual output
            # Let's just use the calculate_estimated_cost utility again
            final_cost = calculate_estimated_cost(model_def.model_id, prompt + response, max_output_tokens=0)
            
            self.budget.track(
                provider=provider_name,
                model=model_def.model_id,
                cost=final_cost,
                status=status
            )
            
        return response

    async def run_doctor(self):
        """Run diagnostics and print report."""
        report = await self.doctor.run_diagnostics()
        print_report(report)
