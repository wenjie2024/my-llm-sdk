import time
import asyncio
import functools
import random
from typing import Callable, Any, Type, Union, Tuple
from my_llm_sdk.config.models import ResilienceConfig

# Exceptions that should trigger a retry
RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    RuntimeError, # Often wraps API errors
)

class RetryManager:
    """
    Manages retry logic based on ResilienceConfig.
    """
    def __init__(self, config: ResilienceConfig):
        self.config = config

    def retry_policy(self, func: Callable):
        """
        Decorator to apply retry logic.
        Supports both sync and async functions.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if asyncio.iscoroutinefunction(func):
                return self._async_retry(func, *args, **kwargs)
            else:
                return self._sync_retry(func, *args, **kwargs)
        
        # Determine if we should return async wrapper or sync wrapper based on func type?
        # Actually functools.wraps preserves metadata, but invocation depends.
        # If func is async, wrapper normally returns awaitable.
        # But here we are blocking inside wrapper for sync logic?
        # Better pattern: Check asyncio.iscoroutinefunction(func) inside decorator factory
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self._async_retry(func, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return self._sync_retry(func, *args, **kwargs)
            return sync_wrapper

    def _sync_retry(self, func, *args, **kwargs):
        retries = 0
        while True:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if not self.should_retry(e, retries):
                    raise e
                
                delay = self.calculate_delay(retries)
                
                # Check 429 special handling
                # Assuming exception message or type indicates 429
                if self._is_rate_limit(e):
                    if not self.config.wait_on_rate_limit:
                        raise e
                    # For Rate Limit, wait might be longer or specific retry-after
                    # Simple approach: standard backoff with higher cap or just backoff
                    print(f"⚠️ Rate Limit hit. Waiting {delay:.2f}s...")
                else:
                    print(f"⚠️ Retryable error: {e}. Retrying ({retries+1}/{self.config.max_retries}) in {delay:.2f}s...")
                
                time.sleep(delay)
                retries += 1

    async def _async_retry(self, func, *args, **kwargs):
        retries = 0
        while True:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if not self.should_retry(e, retries):
                    raise e
                
                delay = self.calculate_delay(retries)
                
                if self._is_rate_limit(e):
                    if not self.config.wait_on_rate_limit:
                        raise e
                    print(f"⚠️ Rate Limit hit. Waiting {delay:.2f}s...")
                else:
                    print(f"⚠️ Retryable error: {e}. Retrying ({retries+1}/{self.config.max_retries}) in {delay:.2f}s...")
                
                await asyncio.sleep(delay)
                retries += 1

    def should_retry(self, e: Exception, current_retries: int) -> bool:
        if current_retries >= self.config.max_retries:
            return False
        
        # Check if exception is in allowed types
        # Also check for specific status codes if possible (need provider specific logic?)
        # For now, simplistic approach: catch broad runtime errors that are likely transient
        # In a real SDK, we'd have specific ValidationErrors (fatal) vs ApiErrors (retryable)
        
        if isinstance(e, RETRYABLE_EXCEPTIONS):
            return True
            
        # Check string for common error codes if Exception type is generic
        msg = str(e).lower()
        if "timeout" in msg or "500" in msg or "502" in msg or "503" in msg:
            return True
        if "429" in msg or "too many requests" in msg or "rate limit" in msg:
            return True
            
        return False

    def _is_rate_limit(self, e: Exception) -> bool:
        msg = str(e).lower()
        return "429" in msg or "rate limit" in msg or "too many requests" in msg

    def calculate_delay(self, retries: int) -> float:
        # Exponential backoff: base * 2^retries + jitter
        delay = self.config.base_delay_s * (2 ** retries)
        jitter = random.uniform(0, 0.1 * delay)
        return min(delay + jitter, self.config.max_delay_s)
