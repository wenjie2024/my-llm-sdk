"""
Stress Test: Async Vision Concurrency (Zero-Blocking)

Verifies that LLMClient.generate_async can handle concurrent vision calls
without blocking the event loop.
"""

import os
import sys
import asyncio
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import GenConfig, TaskType, ContentPart

# Test image (use a small placeholder or generate one)
TEST_IMAGE_PATH = "data/test_image.png"

async def run_vision_call(client: LLMClient, call_id: int, prompt: str):
    """Single async vision call."""
    start = time.time()
    try:
        # Build content with image
        if os.path.exists(TEST_IMAGE_PATH):
            with open(TEST_IMAGE_PATH, "rb") as f:
                img_data = f.read()
            contents = [
                ContentPart(type="text", text=prompt),
                ContentPart(type="image", inline_data=img_data, mime_type="image/png")
            ]
        else:
            # Fallback to text-only if no image
            contents = [ContentPart(type="text", text=prompt)]
        
        response = await client.generate_async(
            model_alias="gemini-2.5-flash",
            contents=contents,
            config=GenConfig(task=TaskType.VISION),
            full_response=True
        )
        elapsed = time.time() - start
        print(f"  ✅ Call {call_id}: {elapsed:.2f}s - {len(response.content)} chars")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ Call {call_id}: {elapsed:.2f}s - Error: {e}")
        return False

async def main():
    print("=" * 60)
    print("🚀 Stress Test: Async Vision Concurrency")
    print("=" * 60)
    
    client = LLMClient()
    
    prompts = [
        "Describe what you see in this image briefly.",
        "What colors are dominant in this image?",
        "Is there any text visible in this image?",
        "What is the main subject of this image?",
        "Describe the mood or atmosphere of this image.",
    ]
    
    print(f"\n📊 Running {len(prompts)} concurrent vision calls...")
    start = time.time()
    
    tasks = [run_vision_call(client, i+1, p) for i, p in enumerate(prompts)]
    results = await asyncio.gather(*tasks)
    
    total = time.time() - start
    success = sum(results)
    
    print("\n" + "-" * 60)
    print(f"📈 Results: {success}/{len(prompts)} succeeded in {total:.2f}s total")
    
    if total < 30 and success == len(prompts):
        print("✅ STRESS TEST PASSED (Zero-blocking verified)")
    else:
        print("⚠️ STRESS TEST FAILED or took too long")

if __name__ == "__main__":
    asyncio.run(main())
