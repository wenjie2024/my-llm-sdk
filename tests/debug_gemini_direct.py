import os
import time
import asyncio
from dotenv import load_dotenv
from google import genai

# Load env
load_dotenv()

async def debug_direct_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in env")
        return

    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})
    
    model = "gemini-2.0-pro-exp-02-05" # Trying a known valid alias or the one from config
    # The user used "gemini-3.0-pro" in sdk which maps to "gemini-3-pro-preview" probably?
    # Let's check what model_id was used in config.
    # In llm.project.yaml: gemini-3.0-pro -> gemini-3-pro-preview
    
    model_id = "gemini-2.0-pro-exp-02-05" # Default high-end model often used
    # Wait, let's use the exact model ID from the failing test
    # The user config had "gemini-3-pro-preview" 
    # But wait, gemini-3.0-pro doesn't exist yet publicly as stable? 
    # Maybe the user has access to a preview or it's a typo for 1.5 pro?
    # Actually, let's check llm.project.yaml again to be exact.
    
    # Reading llm.project.yaml content from context:
    # gemini-3.0-pro -> model_id: gemini-3-pro-preview
    
    target_model = "gemini-2.0-flash-exp" # Let's try something we validly know OR 
    # Actually, I should use the EXACT ID that failed: "gemini-3-pro-preview" if that's what was configured.
    # But "gemini-3-pro-preview" might not exist? 
    # In the benchmark output, "gemini-3.0-pro" was consistent.
    
    # Let's try to query available models first, or just use "gemini-1.5-pro-latest" as a control-pro,
    # and "gemini-2.0-flash-exp"
    
    # I will use the string the SDK uses: "gemini-3-pro-preview"
    target_model = "gemini-2.0-pro-exp-02-05" # I suspect user meant 2.0 Pro Exp or 1.5 Pro. 
    # If the SDK benchmark used "gemini-3.0-pro" alias, it mapped to "gemini-3-pro-preview".
    # If that model ID is invalid/hallucinated, THAT causes the hang/timeout?
    
    # Exact IDs from llm.project.yaml
    test_models = [
        "gemini-2.0-flash-exp", # Known good
        "gemini-3-flash-preview", # From config
        "gemini-3-pro-preview",   # From config (Suspected cause)
    ]
    
    print("🚀 Direct API Benchmark (Bypassing SDK)")
    print("-" * 60)
    
    for m in test_models:
        print(f"Testing {m}...", end="", flush=True)
        t0 = time.time()
        try:
            # Sync call for simplicity or async
            # google-genai supports async
            response = await client.aio.models.generate_content(
                model=m,
                contents="Explain latency.",
                config=None
            )
            ttft = time.time() - t0 # For non-streaming, this is Total Time
            print(f" Done. Total: {ttft:.2f}s")
        except Exception as e:
            print(f" Failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_direct_gemini())
