import asyncio
import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from my_llm_sdk.client import LLMClient

async def benchmark_latency():
    client = LLMClient()
    
    models = [
        "gemini-2.5-flash", 
        "gemini-3.0-flash",
        "qwen-plus",
        "gemini-3.0-pro"
    ]
    
    prompt = "Explain the importance of latency in LLM applications in one paragraph."
    
    results = []
    
    print(f"\n🚀 Benchmarking Latency (prompt: '{prompt[:30]}...')", flush=True)
    print("-" * 80, flush=True)
    print(f"{'Model':<20} | {'Status':<8} | {'TTFT (s)':<10} | {'Total (s)':<10} | {'Speed (t/s)':<12}", flush=True)
    print("-" * 80, flush=True)
    
    for model in models:
        t0 = time.time()
        ttft = 0.0
        first_token_received = False
        token_count = 0
        status = "✅"
        
        try:
            # Use streaming to measure TTFT
            iterator = client.stream(prompt, model_alias=model)
            
            for event in iterator:
                if not first_token_received:
                    ttft = time.time() - t0
                    first_token_received = True
                
                if event.delta:
                    token_count += 1
            
            total_time = time.time() - t0
            speed = token_count / total_time if total_time > 0 else 0
            
            # Print row immediately
            print(f"{model:<20} | {status:<8} | {ttft:<10.4f} | {total_time:<10.4f} | {speed:<12.2f}", flush=True)
            
            results.append({
                "model": model,
                "ttft": ttft,
                "total": total_time,
                "speed": speed
            })
            
        except Exception as e:
            status = "❌"
            error_msg = str(e).split('\n')[0][:30]
            print(f"{model:<20} | {status:<8} | {'-':<10} | {'-':<10} | Error: {error_msg}")

    print("-" * 80)

if __name__ == "__main__":
    asyncio.run(benchmark_latency())
