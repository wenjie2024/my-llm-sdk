import asyncio
import time
from src.client import LLMClient

async def concurrency_test():
    print("🚀 Starting Async Concurrency Verification")
    print("-" * 50)
    
    client = LLMClient(user_config_path="config.yaml")
    
    # 1. Test generate_async concurrency
    print("\n⚡ Testing generate_async (5 concurrent requests)")
    print("   Models: gemini-2.5-flash (Native) & qwen-max (Thread-wrapped)")
    
    prompts = [
        ("gemini-2.5-flash", "Say 'Gemini' and wait 1s"), 
        ("gemini-2.5-flash", "Say 'Gemini' and wait 1s"), 
        ("qwen-max", "Say 'Qwen' and wait 1s"), 
        ("qwen-max", "Say 'Qwen' and wait 1s")
    ]
    
    t0 = time.time()
    
    tasks = []
    for model, prompt in prompts:
        tasks.append(client.generate_async(prompt, model_alias=model))
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    t1 = time.time()
    
    total_time = t1 - t0
    print(f"\n   ⏱️  Total Time: {total_time:.2f}s")
    print(f"   (If sequential, expected > {len(prompts)}s)")
    
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            print(f"   ❌ Task {i}: Failed {res}")
        else:
            print(f"   ✅ Task {i}: Success ({len(str(res))} chars)")

    # 2. Test stream_async
    print("\n🌊 Testing stream_async (Gemini)")
    try:
        t0 = time.time()
        # client.stream_async is an async generator function, so calling it returns an async generator immediately.
        # It is NOT a coroutine that returns a generator.
        stream = client.stream_async("Count to 5 very quickly", model_alias="gemini-2.5-flash")
        
        print("   Stream: ", end="", flush=True)
        async for event in stream:
            if event.delta:
                print(event.delta, end="", flush=True)
        print("\n   🏁 Stream Finished")
        t1 = time.time()
        print(f"   ⏱️  Stream Time: {t1-t0:.2f}s")
        
    except Exception as e:
        print(f"   ❌ Stream Error: {e}")
        
    # Check Ledger eventually?
    # Ledger is async best effort, might need a moment to flush.
    await client.budget.ledger._ensure_worker() # Make sure queue is init
    # Wait a bit for worker to flush queue
    await asyncio.sleep(1.0)
    
    # Force close to ensure everything written?
    # client.budget.ledger.aclose() # Not implemented publicly on controller but ledger has it.
    
if __name__ == "__main__":
    asyncio.run(concurrency_test())
