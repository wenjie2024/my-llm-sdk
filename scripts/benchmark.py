"""
Benchmark Script for LLM Text Generation

Tests multiple models across different providers with simple and complex prompts.
Results are saved to benchmark_outputs/ as markdown report.
"""
import os
import time
from datetime import datetime
from my_llm_sdk.client import LLMClient

# --- Configuration ---
OUTPUT_DIR = "benchmark_outputs"

MODELS = [
    # Google Gemini
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3.0-flash",
    "gemini-3.0-pro",
    # Qwen
    "qwen-max",
    "qwen-plus",
    "qwen-flash",
    # Volcengine
    "deepseek-v3",
    "doubao-thinking"
]

PROMPTS = {
    "Simple": "鲁迅和周树人是什么关系？",
    "Complex": "请编写一个 Python 脚本，使用 `LLMClient` 实现一个多线程的爬虫框架雏形，要求包含详细注释和异常处理。"
}

def ensure_dir(d):
    if not os.path.exists(d):
        os.makedirs(d)

def run_benchmark():
    client = LLMClient()
    ensure_dir(OUTPUT_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(OUTPUT_DIR, f"benchmark_{timestamp}.md")
    
    results = []
    
    print(f"Starting Benchmark on {len(MODELS)} models...")
    print(f"Output: {report_path}")
    print("-" * 60)
    
    for model in MODELS:
        row = {"Model": model}
        print(f"[{model}]")
        
        for p_name, p_text in PROMPTS.items():
            start_time = time.time()
            try:
                print(f"  - {p_name}...", end="", flush=True)
                res = client.generate(p_text, model_alias=model, full_response=True)
                elapsed = time.time() - start_time
                
                content = res.content or ""
                resp_len = len(content)
                snippet = content[:50].replace("\n", " ").strip() + "..."
                
                row[f"{p_name}_Time"] = f"{elapsed:.2f}s"
                row[f"{p_name}_Len"] = f"{resp_len}"
                row[f"{p_name}_Snippet"] = snippet
                
                # Save full response
                response_file = os.path.join(OUTPUT_DIR, f"{model}_{p_name.lower()}.txt")
                with open(response_file, "w", encoding="utf-8") as f:
                    f.write(content)
                
                print(f" Done ({elapsed:.2f}s, {resp_len} chars)")
                
            except Exception as e:
                elapsed = time.time() - start_time
                row[f"{p_name}_Time"] = "FAIL"
                row[f"{p_name}_Len"] = "-"
                row[f"{p_name}_Snippet"] = str(e)[:40] + "..."
                print(f" FAILED: {e}")
        
        results.append(row)
        print("-" * 60)

    # Generate Markdown Report
    headers = ["Model", "Simple (Time)", "Simple (Len)", "Complex (Time)", "Complex (Len)", "Complex (Snippet)"]
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# LLM Benchmark Report\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Models Tested**: {len(MODELS)}\n\n")
        f.write("## Prompts\n\n")
        for name, text in PROMPTS.items():
            f.write(f"- **{name}**: {text[:80]}{'...' if len(text) > 80 else ''}\n")
        f.write("\n## Results\n\n")
        f.write(f"| {' | '.join(headers)} |\n")
        f.write("|:---|:---|:---|:---|:---|:---|\n")
        for r in results:
            f.write(f"| {r['Model']} | {r.get('Simple_Time', '-')} | {r.get('Simple_Len', '-')} | {r.get('Complex_Time', '-')} | {r.get('Complex_Len', '-')} | {r.get('Complex_Snippet', '-')[:50]} |\n")
    
    print(f"\nResults saved to: {report_path}")
    print("Full responses saved to individual .txt files in benchmark_outputs/")

if __name__ == "__main__":
    run_benchmark()
