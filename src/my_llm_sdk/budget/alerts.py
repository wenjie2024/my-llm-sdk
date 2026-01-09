import sys
from typing import Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class AlertLevel(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class BudgetAlert:
    level: AlertLevel
    current_spend: float
    limit: float
    percentage: float
    message: str

def emit_alert(alert: BudgetAlert):
    """
    Emit alert to console (stderr) and logger.
    """
    # 1. Log Structured
    if alert.level == AlertLevel.CRITICAL:
        logger.critical(alert.message, extra={"alert": alert})
    else:
        logger.warning(alert.message, extra={"alert": alert})
        
    # 2. Console Output (User facing)
    try:
        from rich.console import Console
        console = Console(stderr=True)
        
        style = "bold red" if alert.level == AlertLevel.CRITICAL else "bold yellow"
        title = "🚨 BUDGET CRITICAL" if alert.level == AlertLevel.CRITICAL else "⚠️ BUDGET WARNING"
        
        console.print(f"[{style}]{title}: {alert.message} ({alert.percentage:.1f}%) [/{style}]")
    except ImportError:
        # Fallback
        prefix = "🚨 [CRITICAL]" if alert.level == AlertLevel.CRITICAL else "⚠️ [WARNING]"
        print(f"{prefix} {alert.message} ({alert.percentage:.1f}%)", file=sys.stderr)
