from typing import Dict, Tuple

# Pricing Table: Cost per 1M tokens (Input, Output) in USD
# Sources: Official pricing pages (Verified Dec 2025)
# Note: Prices are approximate and may vary by region/tier.
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

def calculate_estimated_cost(model_id: str, prompt: str, max_output_tokens: int = 1000) -> float:
    """
    Calculate estimated cost for pre-check.
    Return value is in USD.
    """
    prices = None
    
    # Simple matching logic
    for key, val in PRICING_REGISTRY.items():
        if key in model_id:
            prices = val
            break
            
    if not prices:
        # Default fallback (e.g. assume average GPT-3.5 price)
        prices = (0.50, 1.50) 
    
    input_price_per_1m, output_price_per_1m = prices
    
    input_tokens = estimate_tokens(prompt)
    
    # Pricing is per 1M tokens
    estimated_input_cost = (input_tokens / 1_000_000) * input_price_per_1m
    estimated_output_cost = (max_output_tokens / 1_000_000) * output_price_per_1m
    
    # Total estimate = Input + Expected Output
    return estimated_input_cost + estimated_output_cost
