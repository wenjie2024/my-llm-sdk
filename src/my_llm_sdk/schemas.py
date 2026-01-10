from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List, Union, Literal

# --- Multimodal Input Abstractions ---

@dataclass
class ContentPart:
    """
    A single part of multimodal content.
    
    For text: ContentPart(type="text", text="Hello")
    For image (inline): ContentPart(type="image", inline_data=b"...", mime_type="image/png")
    For image (URI): ContentPart(type="image", file_uri="gs://bucket/image.png", mime_type="image/png")
    """
    type: Literal["text", "image", "audio", "video", "file"]
    text: Optional[str] = None
    inline_data: Optional[bytes] = None  # Raw binary data (will be base64 encoded for API)
    mime_type: Optional[str] = None      # e.g., "image/png", "audio/mp3"
    file_uri: Optional[str] = None       # Remote URI (gs://, https://, etc.)


# Type alias for unified content input
# - str: Simple text prompt (backward compatible)
# - List[ContentPart]: Multimodal parts
ContentInput = Union[str, List[ContentPart]]


def normalize_content(content: ContentInput) -> List[ContentPart]:
    """
    Convert ContentInput to a normalized List[ContentPart].
    Ensures backward compatibility with str prompts.
    """
    if isinstance(content, str):
        return [ContentPart(type="text", text=content)]
    return content

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

