from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List, Union, Literal
from typing_extensions import TypedDict
from enum import Enum

# --- P1: Task Type Enumeration ---

class TaskType(str, Enum):
    """Explicit task types for multimodal routing."""
    TEXT_GENERATION = "text_generation"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    TTS = "tts"
    ASR = "asr"
    VISION = "vision"
    OMNI = "omni"


# --- P1: Generation Configuration ---

class GenConfig(TypedDict, total=False):
    """Configuration for multimodal generation requests."""
    # [Required] Explicit task type for routing
    task: TaskType
    
    # [Optional] Response modalities (auxiliary validation)
    response_modalities: List[str]  # ["TEXT", "AUDIO", "IMAGE"]
    
    # Image generation parameters
    image_size: str                 # "1K", "2K", "4K"
    aspect_ratio: str               # "1:1","2:3","3:2","3:4","4:3","4:5","5:4","9:16","16:9","21:9"
    image_count: int                # Number of images to generate
    
    # Audio parameters
    voice_config: Dict[str, Any]    # {"voice_name": "...", "rate": 1.0}
    audio_format: str               # "wav", "mp3"
    
    # Engineering parameters
    max_output_tokens: int          # For long-form content (>8k)
    persist_media: bool             # Auto-save media to local files (default True)
    persist_dir: str                # Directory to save media files
    idempotency_key: str            # Prevent duplicate billing on retries
    
    # Provider-specific passthrough
    extra_options: Dict[str, Any]
    
    # Image optimization (B+A config pattern)
    optimize_images: bool  # Convert PNG to JPEG (default True from project config)


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
    
    # P1: Media persistence fields
    local_path: Optional[str] = None     # Path to locally saved file
    metadata: Dict[str, Any] = field(default_factory=dict)  # {"duration_seconds": 12.5, "width": 1024}


# Type alias for unified content input
# - str: Simple text prompt (backward compatible)
# - List[ContentPart]: Multimodal parts
ContentInput = Union[str, List[ContentPart]]


def normalize_content(content: ContentInput) -> List[ContentPart]:
    """
    Convert ContentInput to a normalized List[ContentPart].
    Handles mixed types: str, PIL.Image, ContentPart.
    """
    if isinstance(content, str):
        return [ContentPart(type="text", text=content)]
    
    # Handle mixed list
    result = []
    for item in content:
        if isinstance(item, str):
            result.append(ContentPart(type="text", text=item))
        elif hasattr(item, 'type'):  # ContentPart
            result.append(item)
        # PIL.Image will be handled separately in provider
        # For normalize_content, we skip non-ContentPart items
    return result


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # V0.4.0 Multimodal Input Tracking
    images_processed: int = 0
    audio_seconds: float = 0.0
    
    # P1: Multimodal Output Tracking (billing-critical)
    images_generated: int = 0              # Output images count
    videos_generated: int = 0              # Output videos count
    audio_seconds_generated: float = 0.0   # Output audio duration (TTS)
    tts_input_characters: int = 0          # TTS input text length (some models bill by chars)
    
    # Extensible metadata
    extra_info: Dict[str, Any] = field(default_factory=dict)

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
    
    # V0.4.0 Multimodal Output
    media_parts: List[ContentPart] = field(default_factory=list)

    @property
    def images(self) -> List[bytes]:
        return [p.inline_data for p in self.media_parts if p.type == "image" and p.inline_data]

    @property
    def audio(self) -> Optional[bytes]:
        parts = [p.inline_data for p in self.media_parts if p.type == "audio" and p.inline_data]
        return parts[0] if parts else None

    @property
    def videos(self) -> List[bytes]:
        return [p.inline_data for p in self.media_parts if p.type == "video" and p.inline_data]

    def __str__(self):
        return self.content  # Allow easy printing: print(response)

@dataclass
class StreamEvent:
    delta: str
    is_finish: bool = False
    usage: Optional[TokenUsage] = None # Present only on final event
    error: Optional[Exception] = None
    finish_reason: Optional[str] = None

