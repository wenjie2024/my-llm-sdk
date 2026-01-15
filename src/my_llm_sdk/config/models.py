from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field, validator

class RoutingPolicy(BaseModel):
    name: str
    strategy: str  # e.g., "least_latency", "random", "priority"
    params: Dict[str, str] = Field(default_factory=dict)

class ModelPricing(BaseModel):
    input_per_1m_tokens: float
    output_per_1m_tokens: float
    
    # V0.4.0 Multimodal Pricing (Optional)
    per_image_input: Optional[float] = None      # USD per input image
    per_image_output: Optional[float] = None     # USD per output image (image generation)
    per_audio_second_input: Optional[float] = None   # USD per second of input audio
    per_audio_second_output: Optional[float] = None  # USD per second of output audio (TTS)
    
    # P1: TTS character-based billing (some models bill by input text length)
    per_output_character: Optional[float] = None  # USD per character for TTS input text

class ModelDefinition(BaseModel):
    name: str  # e.g., "gpt-4"
    provider: str  # e.g., "openai"
    model_id: str  # e.g., "gpt-4-0613"
    api_version: Optional[str] = None
    
    # Rate Limits
    rpm: Optional[int] = None  # Requests Per Minute
    tpm: Optional[int] = None  # Tokens Per Minute
    rpd: Optional[int] = None  # Requests Per Day
    
    # Pricing
    pricing: Optional[ModelPricing] = None

class Endpoint(BaseModel):
    name: str
    url: str
    region: str
    is_active: bool = True

class ResilienceConfig(BaseModel):
    max_retries: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 60.0
    wait_on_rate_limit: bool = True
    
    # Circuit Breaker defaults can go here too if needed


class NetworkConfig(BaseModel):
    """Network configuration for proxy handling."""
    # Master switch for this feature
    proxy_bypass_enabled: bool = Field(
        default=True,
        description="Master switch to enable/disable proxy bypass logic"
    )

    # Providers that should bypass system proxy (direct connection)
    # Useful for China LLM providers when using VPN
    bypass_proxy: List[str] = Field(
        default_factory=lambda: ["alibaba", "dashscope", "volcengine", "baidu", "zhipu"],
        description="Provider names to bypass system proxy"
    )
    
class ProjectConfig(BaseModel):
    """Configuration loaded from project root (Git tracked)."""
    project_name: str
    allowed_regions: List[str] = Field(default_factory=list)
    routing_policies: List[RoutingPolicy] = Field(default_factory=list)
    model_registry: Dict[str, ModelDefinition] = Field(default_factory=dict)
    
    # Policies
    allow_logging: bool = False
    budget_strict_mode: bool = True
    
    # Resilience
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig)
    
    # Network
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    
    # Project Settings (V0.4.0)
    settings: Dict[str, Any] = Field(default_factory=dict)

class UserConfig(BaseModel):
    """Configuration loaded from user home (Local only)."""
    api_keys: Dict[str, str] = Field(default_factory=dict)
    endpoints: List[Endpoint] = Field(default_factory=list)
    personal_routing_policies: List[RoutingPolicy] = Field(default_factory=dict)
    personal_model_overrides: Dict[str, ModelDefinition] = Field(default_factory=dict)
    
    # Network
    network: Optional[NetworkConfig] = None
    
    # Budget
    daily_spend_limit: float = 1.0


class MergedConfig(BaseModel):
    """Runtime configuration after merging Project and User configs."""
    final_routing_policies: List[RoutingPolicy]
    final_model_registry: Dict[str, ModelDefinition]
    final_endpoints: List[Endpoint]
    
    # Merged Flags
    allow_logging: bool
    budget_strict_mode: bool
    daily_spend_limit: float
    api_keys: Dict[str, str]
    
    # Resilience
    resilience: ResilienceConfig
    
    # Network (proxy bypass)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    
    # Merged Settings
    settings: Dict[str, Any]

