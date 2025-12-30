import time
from typing import Optional
from my_llm_sdk.budget.ledger import Ledger

class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""
    pass

class RateLimiter:
    def __init__(self, ledger: Ledger):
        self.ledger = ledger

    def check_limits(self, model_id: str, rpm: Optional[int] = None, rpd: Optional[int] = None, tpm: Optional[int] = None, estimated_tokens: int = 0):
        """
        Check if the request exceeds global rate limits using the Ledger.
        
        Args:
            model_id: The model identifier.
            rpm: Requests per minute limit.
            rpd: Requests per day limit.
            tpm: Tokens per minute limit.
            estimated_tokens: Estimated token usage for this request.
            
        Raises:
            RateLimitExceededError: If any limit is exceeded.
        """
        # If no limits validation needed, return early
        if not any([rpm, rpd, tpm]):
            return

        now = time.time()
        
        with self.ledger._get_conn() as conn:
            # 1. Check RPM (Last 60 seconds)
            if rpm:
                window_start = now - 60
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM transactions 
                    WHERE model = ? AND timestamp > ?
                """, (model_id, window_start))
                current_rpm = cursor.fetchone()[0]
                
                if current_rpm >= rpm:
                    raise RateLimitExceededError(f"Rate limit exceeded (RPM). Limit: {rpm}, Used: {current_rpm}")

            # 2. Check RPD (Last 24 hours)
            if rpd:
                window_start = now - 86400 # 24 * 60 * 60
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM transactions 
                    WHERE model = ? AND timestamp > ?
                """, (model_id, window_start))
                current_rpd = cursor.fetchone()[0]
                
                if current_rpd >= rpd:
                    raise RateLimitExceededError(f"Rate limit exceeded (RPD). Limit: {rpd}, Used: {current_rpd}")
            
            # 3. Check TPM (Last 60 seconds)
            if tpm and estimated_tokens > 0:
                # We need to sum input_tokens + output_tokens for usage in last minute
                # Note: 'estimated_tokens' is for THIS request. We check if (past_usage + this_request) > limit
                window_start = now - 60
                cursor = conn.execute("""
                    SELECT SUM(input_tokens + output_tokens) FROM transactions 
                    WHERE model = ? AND timestamp > ?
                """, (model_id, window_start))
                result = cursor.fetchone()[0]
                current_tpm = result if result else 0
                
                if (current_tpm + estimated_tokens) > tpm:
                     raise RateLimitExceededError(f"Rate limit exceeded (TPM). Limit: {tpm}, Used: {current_tpm}, Requested: {estimated_tokens}")
