from dataclasses import dataclass, field
from typing import Dict, Optional, Any

@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

@dataclass
class GenerationResponse:
    content: str
    model: str
    provider: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: float = 0.0
    finish_reason: Optional[str] = None  # 'stop', 'length', 'filter', etc.
    trace_id: Optional[str] = None
    timing: Dict[str, float] = field(default_factory=dict)  # {'ttft': 0.1, 'total': 2.5}

    def __str__(self):
        return self.content  # Allow easy printing: print(response)

@dataclass
class StreamEvent:
    delta: str
    is_finish: bool = False
    usage: Optional[TokenUsage] = None # Present only on final event
    error: Optional[Exception] = None
    finish_reason: Optional[str] = None

