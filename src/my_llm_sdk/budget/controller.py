from typing import Dict, Any, Optional
import uuid
from datetime import date
from my_llm_sdk.config.models import MergedConfig
from .ledger import Ledger
from my_llm_sdk.config.exceptions import ConfigurationError
from my_llm_sdk.budget.alerts import BudgetAlert, AlertLevel, emit_alert

class QuotaExceededError(Exception):
    """Raised when budget limit is exceeded."""
    pass

class BudgetController:
    def __init__(self, config: MergedConfig, ledger: Ledger = None):
        self.config = config
        # If ledger not provided, use default
        self.ledger = ledger or Ledger()
        
        # Alert State tracking
        self._alert_date = date.today()
        self._alerts_fired = {
            AlertLevel.WARNING: False,
            AlertLevel.CRITICAL: False
        }

    def _reset_alerts_if_new_day(self):
        today = date.today()
        if today != self._alert_date:
            self._alert_date = today
            self._alerts_fired = {
                AlertLevel.WARNING: False,
                AlertLevel.CRITICAL: False
            }

    def _check_alerts(self, current_spend: float):
        """Check and emit alerts based on current spend."""
        if self.config.daily_spend_limit <= 0:
            return

        self._reset_alerts_if_new_day()
        
        limit = self.config.daily_spend_limit
        percentage = (current_spend / limit) * 100
        
        # Check Critical (100%)
        if percentage >= 100:
            if not self._alerts_fired[AlertLevel.CRITICAL]:
                emit_alert(BudgetAlert(
                    level=AlertLevel.CRITICAL,
                    current_spend=current_spend,
                    limit=limit,
                    percentage=percentage,
                    message=f"Daily budget exceeded! Reached ${current_spend:.2f} / ${limit:.2f}"
                ))
                self._alerts_fired[AlertLevel.CRITICAL] = True
                # Also mark warning as fired to avoid double noise? 
                # Or keep them independent? Usually if you hit 100 you hit 80.
                self._alerts_fired[AlertLevel.WARNING] = True 
        
        # Check Warning (80%)
        elif percentage >= 80:
             if not self._alerts_fired[AlertLevel.WARNING]:
                emit_alert(BudgetAlert(
                    level=AlertLevel.WARNING,
                    current_spend=current_spend,
                    limit=limit,
                    percentage=percentage,
                    message=f"Daily budget approaching limit. Reached ${current_spend:.2f} / ${limit:.2f}"
                ))
                self._alerts_fired[AlertLevel.WARNING] = True

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
        # Check alerts after spend update
        # Using get_daily_spend() again might be expensive? 
        # But we just added cost. 
        # Ideally ledger breaks down, but for safety let's query.
        # Or optimization: pass current_spend from check? No, generate takes time.
        try:
            current_spend = self.ledger.get_daily_spend()
            self._check_alerts(current_spend)
        except Exception:
            # Don't fail the request if alerting fails
            pass
        
    async def atrack(self, provider: str, model: str, cost: float, **kwargs):
        """
        Async version of track. 
        Uses awrite_event for non-blocking persistence.
        """
        # Import internally or top-level? Top level avoids circular if careful.
        # But ledger.py is already imported.
        from my_llm_sdk.budget.ledger import LedgerEvent
        
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
        
        await self.ledger.awrite_event(ev, sync=False)
        
        # Async Alert Check
        # We need the NEW total. 
        # If awrite_event is async queue, the DB might not be updated yet!
        # This is a tricky part of Async Ledger + Alerts.
        # If strict_mode=False (default), usage is eventually consistent.
        # We can estimate current spend by adding cost to last known?
        # Or just query the DB and accept it might lag by the latest transaction?
        # Since alerts are 80%/100% "soft" notifications (hard block is done in pre-check), lagging by 1 tx is fine.
        try:
             # We can't easily wait for the write if sync=False.
             # So we query current DB state. It might NOT include this tx.
             # Let's manually add `cost` to the DB result for the alert check.
             current_spend_db = await self.ledger.aspend_today()
             total_spend = current_spend_db + cost
             self._check_alerts(total_spend)
        except Exception:
             pass
