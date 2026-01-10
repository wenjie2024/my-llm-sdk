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


def _get_model_pricing_object(model_id: str, config: Optional[MergedConfig] = None):
    """
    Get the full ModelPricing object for a model (for multimodal fields).
    Returns None if not found in config.
    """
    if not config or not config.final_model_registry:
        return None
        
    # Check by alias
    if model_id in config.final_model_registry:
        return config.final_model_registry[model_id].pricing
        
    # Check by internal model_id
    for _, m_def in config.final_model_registry.items():
        if m_def.model_id == model_id:
            return m_def.pricing
            
    return None


# Default multimodal pricing fallbacks (USD)
DEFAULT_MULTIMODAL_PRICING = {
    "per_image_input": 0.001,
    "per_image_output": 0.04,
    "per_audio_second_input": 0.0001,
    "per_audio_second_output": 0.0005,
    "per_output_character": 0.00001,  # Per TTS input character
}


def calculate_multimodal_cost(
    model_id: str,
    usage: TokenUsage,
    config: Optional[MergedConfig] = None
) -> float:
    """
    Calculate total cost including multimodal components.
    
    Formula:
    Total = TokenCost + (ImagesIn * ImageInputRate) + (ImagesOut * ImageOutputRate)
          + (AudioSecsIn * AudioInputRate) + (AudioSecsOut * AudioOutputRate)
          + (TTSChars * CharRate)
    
    Args:
        model_id: Model identifier
        usage: TokenUsage with multimodal fields populated
        config: Merged configuration with pricing info
        
    Returns:
        Total cost in USD
    """
    if not usage:
        return 0.0
    
    # 1. Base token cost
    token_cost = calculate_actual_cost(model_id, usage, config)
    
    # 2. Get multimodal pricing
    pricing = _get_model_pricing_object(model_id, config)
    
    # Resolve rates with fallbacks
    per_image_input = DEFAULT_MULTIMODAL_PRICING["per_image_input"]
    per_image_output = DEFAULT_MULTIMODAL_PRICING["per_image_output"]
    per_audio_sec_input = DEFAULT_MULTIMODAL_PRICING["per_audio_second_input"]
    per_audio_sec_output = DEFAULT_MULTIMODAL_PRICING["per_audio_second_output"]
    per_char = DEFAULT_MULTIMODAL_PRICING["per_output_character"]
    
    if pricing:
        per_image_input = pricing.per_image_input or per_image_input
        per_image_output = pricing.per_image_output or per_image_output
        per_audio_sec_input = pricing.per_audio_second_input or per_audio_sec_input
        per_audio_sec_output = pricing.per_audio_second_output or per_audio_sec_output
        per_char = pricing.per_output_character or per_char
    
    # 3. Calculate multimodal costs
    # Input side
    image_input_cost = usage.images_processed * per_image_input
    audio_input_cost = usage.audio_seconds * per_audio_sec_input
    
    # Output side
    image_output_cost = usage.images_generated * per_image_output
    audio_output_cost = usage.audio_seconds_generated * per_audio_sec_output
    tts_char_cost = usage.tts_input_characters * per_char
    
    # 4. Sum all components
    total = (
        token_cost
        + image_input_cost
        + audio_input_cost
        + image_output_cost
        + audio_output_cost
        + tts_char_cost
    )
    
    return total
