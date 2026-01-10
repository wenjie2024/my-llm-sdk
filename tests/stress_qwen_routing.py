"""
Stress Test: Qwen Provider Routing Stability

Verifies that QwenProvider can rapidly switch between text-only and image+text calls
without errors or state corruption.
"""

import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import GenConfig, TaskType, ContentPart

# Test image path
TEST_IMAGE_PATH = "data/test_image.png"

def run_test():
    print("=" * 60)
    print("🚀 Stress Test: Qwen Provider Routing Stability")
    print("=" * 60)
    
    client = LLMClient()
    iterations = 10
    success = 0
    errors = []
    
    # Load test image if available
    img_data = None
    if os.path.exists(TEST_IMAGE_PATH):
        with open(TEST_IMAGE_PATH, "rb") as f:
            img_data = f.read()
        print(f"📷 Test image loaded: {len(img_data)} bytes")
    else:
        print("⚠️ No test image found, using text-only for both paths")
    
    print(f"\n📊 Running {iterations} iterations (alternating text/image)...\n")
    
    for i in range(iterations):
        start = time.time()
        call_type = "TEXT" if i % 2 == 0 else "IMAGE"
        
        try:
            if call_type == "TEXT":
                # Text-only call
                response = client.generate(
                    model_alias="qwen-max",
                    contents="Say 'Hello' in one word.",
                    full_response=True
                )
            else:
                # Image+Text call (if image available, else text)
                if img_data:
                    contents = [
                        ContentPart(type="text", text="What do you see? One word answer."),
                        ContentPart(type="image", inline_data=img_data, mime_type="image/png")
                    ]
                else:
                    contents = [ContentPart(type="text", text="Say 'Image' in one word.")]
                
                response = client.generate(
                    model_alias="qwen-vl-max",
                    contents=contents,
                    config=GenConfig(task=TaskType.VISION),
                    full_response=True
                )
            
            elapsed = time.time() - start
            print(f"  ✅ Iter {i+1:2d} [{call_type:5s}]: {elapsed:.2f}s - '{response.content[:30]}...'")
            success += 1
            
        except Exception as e:
            elapsed = time.time() - start
            print(f"  ❌ Iter {i+1:2d} [{call_type:5s}]: {elapsed:.2f}s - Error: {e}")
            errors.append((i+1, str(e)))
    
    print("\n" + "-" * 60)
    print(f"📈 Results: {success}/{iterations} succeeded")
    
    if success == iterations:
        print("✅ STRESS TEST PASSED (Routing stable)")
    else:
        print("⚠️ STRESS TEST FAILED")
        for idx, err in errors:
            print(f"   - Iter {idx}: {err[:50]}...")

if __name__ == "__main__":
    run_test()
