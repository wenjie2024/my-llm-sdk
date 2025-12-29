import asyncio
import time
from src.client import LLMClient
from tabulate import tabulate # You might need to install this, or I can formatting manually. 
# Let's format manually to avoid dependencies.

async def run_benchmark():
    client = LLMClient(user_config_path="config.yaml")
    
    # Models to test
    # Note: User asked for "gemini 2.0 pro", "3.0 flash", "3.0 pro". 
    # Config has "gemini-2.5-pro" (likely what was meant or available).
    # We will test the full suite for comparison.
    models = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.0-flash",
        "gemini-3.0-pro",
        "qwen-max",
        "qwen-plus",
        "qwen-flash"
    ]
    
    # Prompts
    prompts = {
        "Simple": "鲁迅和周树人是什么关系？",
        "Complex": "请编写一个 Python 脚本，使用这里的 `src.client.LLMClient` 实现一个多线程的爬虫框架雏形，要求包含详细注释和异常处理。"
    }
    
    results = []
    
    print(f"🚀 Starting Benchmark on {len(models)} models...")
    print("-" * 60)
    
    for model in models:
        row = {"Model": model}
        print(f"🤖 Testing {model}...")
        
        for p_name, p_text in prompts.items():
            start_time = time.time()
            try:
                print(f"   - Running {p_name} prompt...", end="", flush=True)
                response = client.generate(p_text, model_alias=model)
                elapsed = time.time() - start_time
                
                # Check quality (subjective, but we can check length)
                resp_len = len(response)
                snippet = response[:30].replace("\n", " ") + "..."
                
                row[f"{p_name}_Time"] = f"{elapsed:.2f}s"
                row[f"{p_name}_Len"] = f"{resp_len} chars"
                row[f"{p_name}_Resp"] = snippet
                print(f" Done ({elapsed:.2f}s)")
                
            except Exception as e:
                row[f"{p_name}_Time"] = "FAIL"
                row[f"{p_name}_Len"] = "-"
                row[f"{p_name}_Resp"] = str(e)[:30] + "..."
                print(f" Failed: {e}")
        
        results.append(row)
        print("-" * 60)

    # Output Table
    print("\n📊 Benchmark Results Comparison")
    print("=" * 100)
    
    # Header
    headers = ["Model", "Simple (Time)", "Simple (Len)", "Complex (Time)", "Complex (Len)", "Complex (Snippet)"]
    print(f"{headers[0]:<18} | {headers[1]:<12} | {headers[2]:<12} | {headers[3]:<12} | {headers[4]:<12} | {headers[5]}")
    print("-" * 100)
    
    for r in results:
        complex_snippet = r.get('Complex_Resp', '').ljust(30)
        print(f"{r['Model']:<18} | {r.get('Simple_Time'):<12} | {r.get('Simple_Len'):<12} | {r.get('Complex_Time'):<12} | {r.get('Complex_Len'):<12} | {complex_snippet}")
        
    print("=" * 100)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
