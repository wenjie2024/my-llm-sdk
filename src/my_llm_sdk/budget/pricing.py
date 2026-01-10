from typing import Dict, Tuple, Optional, Union, List
from my_llm_sdk.config.models import MergedConfig, ModelDefinition
from my_llm_sdk.schemas import TokenUsage, ContentInput, ContentPart

# Pricing Table: Cost per 1M tokens (Input, Output) in USD
# Sources: Official pricing pages (Verified Dec 2025)
# Note: Prices are approximate and may vary by region/tier.
# Kept as fallback for models not defined in config.
PRICING_REGISTRY: Dict[str, Tuple[float, float]] = {
    # OpenAI & Echo (Echo mimics GPT-4 pricing)
    "gpt-4": (30.0, 60.0),
    "echo-gpt-4-turbo": (10.0, 30.0),
    
    # Google Gemini
    # Gemini 1.5 Flash (Paid Tier)
    "gemini-1.5-flash": (0.15, 0.60),
    
    # Gemini 2.5 Series
    "gemini-2.5-flash": (0.10, 0.40), # Based on Flash-Lite successor pricing
    "gemini-2.5-pro": (1.25, 10.00),  # Based on 2.5 Pro pricing (<200k)
    
    # Gemini 3.0 Series (Preview)
    # Note: Preview effectively free in AI Studio but has rates for API tiers. Using API rates.
    "gemini-3-flash-preview": (0.15, 0.60), # Estimating similar to 1.5 Flash for now as data was scarce, assuming low cost
    "gemini-3-pro-preview": (2.00, 12.00),  # Confirmed: Input $2, Output $12 (<200k context)
    
    # Alibaba Qwen (International/Singapore Rates)
    # Input: $1.20 / 1M, Output: $6.00 / 1M
    "qwen-max": (1.20, 6.00), 
    
    # Qwen-Turbo (Cheaper)
    "qwen-turbo": (0.002 * 1000 / 7.2, 0.006 * 1000 / 7.2), # Rough RMB->USD conversion if using CN
}

def estimate_tokens(text: str) -> int:
    """
    Rough estimation: 1 token ~= 4 characters (English) or 1 character (Chinese).
    For safety/upper bound, let's assume 1 char = 0.5 token to be safe? 
    Standard rule of thumb: len(text) / 4 
    """
    if not text:
        return 0
    return len(text) // 3 + 1


def estimate_content_tokens(contents: ContentInput) -> int:
    """
    Estimate tokens for ContentInput (text or multimodal).
    
    For multimodal content, uses conservative estimates:
    - Text: standard character-based estimation
    - Image: ~1000 tokens (conservative estimate for vision models)
    - Audio: ~500 tokens per part
    - Video: ~2000 tokens per part
    """
    if isinstance(contents, str):
        return estimate_tokens(contents)
    
    total_tokens = 0
    for part in contents:
        if part.type == "text" and part.text:
            total_tokens += estimate_tokens(part.text)
        elif part.type == "image":
            total_tokens += 1000  # Conservative image token estimate
        elif part.type == "audio":
            total_tokens += 500
        elif part.type == "video":
            total_tokens += 2000
        elif part.type == "file":
            total_tokens += 500  # Generic file estimate
    
    return total_tokens

def _get_pricing_for_model(model_id: str, config: Optional[MergedConfig] = None) -> Tuple[float, float]:
    """
    Resolve pricing tuple (input_cost_per_1m, output_cost_per_1m) for a given model ID.
    Priority:
    1. Exact match in Config (if config provided)
    2. Exact match in Registry
    3. Partial match in Registry
    4. Default Fallback
    """
    # 1. Check Config
    if config and config.final_model_registry:
        # Check by user-friendly alias OR actual model_id?
        # The 'model_id' arg here might be the Alias (e.g. 'gemini-3.0-pro') or ID ('gemini-3-pro-preview').
        # We should check both.
        
        # Check alias keys first
        if model_id in config.final_model_registry:
            m_def = config.final_model_registry[model_id]
            if m_def.pricing:
                return (m_def.pricing.input_per_1m_tokens, m_def.pricing.output_per_1m_tokens)
        
        # Check internal model_ids (iterate)
        for _, m_def in config.final_model_registry.items():
            if m_def.model_id == model_id:
                if m_def.pricing:
                    return (m_def.pricing.input_per_1m_tokens, m_def.pricing.output_per_1m_tokens)
                break
    
    # 2. Check Registry (Exact)
    if model_id in PRICING_REGISTRY:
        return PRICING_REGISTRY[model_id]

    # 3. Check Registry (Partial)
    for key, val in PRICING_REGISTRY.items():
        if key in model_id:
            return val
            
    # 4. Fallback
    return (0.50, 1.50)

def calculate_estimated_cost(model_id: str, prompt: str, max_output_tokens: int = 1000, config: Optional[MergedConfig] = None) -> float:
    """
    Calculate estimated cost for pre-check.
    Return value is in USD.
    """
    input_price_per_1m, output_price_per_1m = _get_pricing_for_model(model_id, config)
    
    input_tokens = estimate_tokens(prompt)
    
    # Pricing is per 1M tokens
    estimated_input_cost = (input_tokens / 1_000_000) * input_price_per_1m
    estimated_output_cost = (max_output_tokens / 1_000_000) * output_price_per_1m
    
    # Total estimate = Input + Expected Output
    return estimated_input_cost + estimated_output_cost

def calculate_actual_cost(model_id: str, usage: TokenUsage, config: Optional[MergedConfig] = None) -> float:
    """
    Calculate actual cost based on real usage.
    """
    if not usage:
        return 0.0
        
    input_price_per_1m, output_price_per_1m = _get_pricing_for_model(model_id, config)
    
    input_cost = (usage.input_tokens / 1_000_000) * input_price_per_1m
    output_cost = (usage.output_tokens / 1_000_000) * output_price_per_1m
    
    return input_cost + output_cost
