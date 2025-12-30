from typing import Dict, Any
import uuid
from my_llm_sdk.config.models import MergedConfig
from .ledger import Ledger
from my_llm_sdk.config.exceptions import ConfigurationError

class QuotaExceededError(Exception):
    """Raised when budget limit is exceeded."""
    pass

class BudgetController:
    def __init__(self, config: MergedConfig, ledger: Ledger = None):
        self.config = config
        # If ledger not provided, use default
        self.ledger = ledger or Ledger()

    def check_budget(self, estimated_cost: float = 0.0):
        """
        Check if adding estimated_cost would exceed daily limit.
        Raises QuotaExceededError if limit breached.
        """
        if self.config.daily_spend_limit <= 0:
            return  # No limit
            
        current_spend = self.ledger.get_daily_spend()
        if (current_spend + estimated_cost) > self.config.daily_spend_limit:
            raise QuotaExceededError(
                f"Daily limit exceeded! Used: ${current_spend:.4f}, Tried to add: ${estimated_cost:.4f}, Limit: ${self.config.daily_spend_limit:.4f}"
            )

    async def acheck_budget(self, estimated_cost: float = 0.0):
        """
        Async version of budget check.
        Uses non-blocking ledger query if available.
        """
        if self.config.daily_spend_limit <= 0:
            return
            
        # Use async query
        current_spend = await self.ledger.aspend_today()
        
        if (current_spend + estimated_cost) > self.config.daily_spend_limit:
            raise QuotaExceededError(
                f"Daily limit exceeded! Used: ${current_spend:.4f}, Tried to add: ${estimated_cost:.4f}, Limit: ${self.config.daily_spend_limit:.4f}"
            )

    def track(self, provider: str, model: str, cost: float, **kwargs):
        """Record the transaction."""
        tx_id = str(uuid.uuid4())
        self.ledger.record_transaction(
            tx_id=tx_id,
            provider=provider,
            model=model,
            cost=cost,
            **kwargs
        )
        
    async def atrack(self, provider: str, model: str, cost: float, **kwargs):
        """
        Async version of track. 
        Uses awrite_event for non-blocking persistence.
        """
        # Import internally or top-level? Top level avoids circular if careful.
        # But ledger.py is already imported.
        from my_llm_sdk.budget.ledger import LedgerEvent
        
        # Build usage dict from kwargs if present, similar to record_transaction wrapper?
        # record_transaction logic:
        # ev = LedgerEvent(usage={"tokens_in": input_tokens, "tokens_out": output_tokens}, ...)
        
        input_tokens = kwargs.get('input_tokens', 0)
        output_tokens = kwargs.get('output_tokens', 0)
        status = kwargs.get('status', 'success')
        
        tx_id = str(uuid.uuid4())
        
        ev = LedgerEvent(
            event_type='commit',
            trace_id=tx_id,
            provider=provider,
            model=model,
            usage={"tokens_in": input_tokens, "tokens_out": output_tokens},
            cost_actual_usd=cost,
            status=status
        )
        
        # Sync=False for best performance (fire and forget to queue)
        # Using strict mode config?
        # self.config.budget_strict_mode usually applies to CHECK, not TRACK.
        # Track is "post-fact", so usually non-blocking is fine unless we really fear data loss on crash.
        # Let's use sync=False by default for perf.
        
        await self.ledger.awrite_event(ev, sync=False)
