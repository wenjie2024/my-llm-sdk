from typing import Dict, Any
import uuid
from src.config.models import MergedConfig
from .ledger import Ledger
from src.config.exceptions import ConfigurationError

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
