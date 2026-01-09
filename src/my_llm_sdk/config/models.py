from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, validator

class RoutingPolicy(BaseModel):
    name: str
    strategy: str  # e.g., "least_latency", "random", "priority"
    params: Dict[str, str] = Field(default_factory=dict)

class ModelPricing(BaseModel):
    input_per_1m_tokens: float
    output_per_1m_tokens: float

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

class UserConfig(BaseModel):
    """Configuration loaded from user home (Local only)."""
    api_keys: Dict[str, str] = Field(default_factory=dict)
    endpoints: List[Endpoint] = Field(default_factory=list)
    personal_routing_policies: List[RoutingPolicy] = Field(default_factory=dict)
    personal_model_overrides: Dict[str, ModelDefinition] = Field(default_factory=dict)
    
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
