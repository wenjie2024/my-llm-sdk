"""
Unified Benchmark Script for LLM SDK

Features:
1. Text Generation - Simple/Complex prompts with timing
2. Latency Metrics - TTFT, Total time, Tokens/sec (streaming)
3. Image Generation - Multi-provider comparison
4. Markdown Report - Consolidated output

Usage:
    python scripts/benchmark_unified.py
    python scripts/benchmark_unified.py --skip-image  # Text only
"""
import os
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import TaskType, GenConfig

# --- Configuration ---
OUTPUT_DIR = Path(__file__).parent.parent / "outputs" / "scripts" / "benchmark"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEXT_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.0-flash",
    "qwen-max",
    "qwen-plus", 
    "deepseek-v3",
]

IMAGE_MODELS = [
    ("gemini-3-pro-image-preview", "gemini"),
    ("qwen-image-plus", "qwen"),
]

PROMPTS = {
    "Simple": "鲁迅和周树人是什么关系？",
    "Complex": "请编写一个 Python 脚本，使用 asyncio 实现并发 HTTP 请求，包含超时和重试逻辑。"
}

IMAGE_PROMPT = "A serene Japanese garden with cherry blossoms, a koi pond, and a traditional wooden bridge. Digital art style."


def benchmark_text(client: LLMClient) -> list:
    """Benchmark text generation models."""
    print("\n" + "=" * 60)
    print("📝 PART 1: Text Generation Benchmark")
    print("=" * 60)
    
    results = []
    
    for model in TEXT_MODELS:
        row = {"Model": model}
        print(f"\n[{model}]")
        
        for p_name, p_text in PROMPTS.items():
            start_time = time.time()
            try:
                print(f"  - {p_name}...", end="", flush=True)
                res = client.generate(p_text, model_alias=model, full_response=True, config={"persist_media": False})
                elapsed = time.time() - start_time
                
                content = res.content or ""
                resp_len = len(content)
                
                row[f"{p_name}_Time"] = f"{elapsed:.2f}s"
                row[f"{p_name}_Len"] = str(resp_len)
                
                print(f" Done ({elapsed:.2f}s, {resp_len} chars)")
                
            except Exception as e:
                row[f"{p_name}_Time"] = "FAIL"
                row[f"{p_name}_Len"] = "-"
                print(f" FAILED: {str(e)[:50]}")
        
        results.append(row)
    
    return results


def benchmark_latency(client: LLMClient) -> list:
    """Benchmark streaming latency (TTFT)."""
    print("\n" + "=" * 60)
    print("⚡ PART 2: Latency Benchmark (Streaming)")
    print("=" * 60)
    
    prompt = "Explain the importance of latency in LLM applications in one paragraph."
    results = []
    
    print(f"\n{'Model':<25} | {'TTFT':<10} | {'Total':<10} | {'Speed':<12}")
    print("-" * 65)
    
    for model in TEXT_MODELS[:4]:  # Test subset for speed
        t0 = time.time()
        ttft = 0.0
        first_token = False
        token_count = 0
        
        try:
            iterator = client.stream(prompt, model_alias=model)
            
            for event in iterator:
                if not first_token:
                    ttft = time.time() - t0
                    first_token = True
                if event.delta:
                    token_count += 1
            
            total = time.time() - t0
            speed = token_count / total if total > 0 else 0
            
            print(f"{model:<25} | {ttft:<10.3f} | {total:<10.3f} | {speed:<12.1f}")
            results.append({"Model": model, "TTFT": ttft, "Total": total, "Speed": speed})
            
        except Exception as e:
            print(f"{model:<25} | {'FAIL':<10} | {'-':<10} | Error: {str(e)[:20]}")
    
    return results


def benchmark_image(client: LLMClient) -> list:
    """Benchmark image generation models."""
    print("\n" + "=" * 60)
    print("🖼️ PART 3: Image Generation Benchmark")
    print("=" * 60)
    
    results = []
    
    for model_alias, provider in IMAGE_MODELS:
        print(f"\n[{model_alias}]")
        start_time = time.time()
        
        try:
            config = GenConfig(
                task=TaskType.IMAGE_GENERATION,
                persist_media=False
            )
            if provider == "volcengine":
                config.image_size = "2K"
            
            response = client.generate(
                model_alias=model_alias,
                prompt=IMAGE_PROMPT,
                config=config,
                full_response=True
            )
            
            elapsed = time.time() - start_time
            
            if response.media_parts:
                part = response.media_parts[0]
                size_kb = len(part.inline_data) / 1024 if part.inline_data else 0
                
                # Save image
                ext = "png" if "png" in (part.mime_type or "") else "jpg"
                img_path = OUTPUT_DIR / f"{provider}_{model_alias.replace('-', '_')}.{ext}"
                if part.inline_data:
                    with open(img_path, "wb") as f:
                        f.write(part.inline_data)
                
                print(f"  ✅ Success ({elapsed:.2f}s, {size_kb:.1f} KB)")
                results.append({"Model": model_alias, "Time": elapsed, "Size": size_kb, "Status": "OK"})
            else:
                print(f"  ❌ No image returned")
                results.append({"Model": model_alias, "Time": elapsed, "Size": 0, "Status": "FAIL"})
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ❌ Error: {str(e)[:60]}")
            results.append({"Model": model_alias, "Time": elapsed, "Size": 0, "Status": "FAIL"})
    
    return results


def generate_report(text_results, latency_results, image_results) -> str:
    """Generate markdown report."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = OUTPUT_DIR / f"benchmark_{timestamp}.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# LLM SDK Unified Benchmark Report\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Text Results
        f.write("## Text Generation\n\n")
        f.write("| Model | Simple (Time) | Simple (Len) | Complex (Time) | Complex (Len) |\n")
        f.write("|:---|:---|:---|:---|:---|\n")
        for r in text_results:
            f.write(f"| {r['Model']} | {r.get('Simple_Time', '-')} | {r.get('Simple_Len', '-')} | {r.get('Complex_Time', '-')} | {r.get('Complex_Len', '-')} |\n")
        
        # Latency Results
        f.write("\n## Streaming Latency\n\n")
        f.write("| Model | TTFT (s) | Total (s) | Speed (tok/s) |\n")
        f.write("|:---|:---|:---|:---|\n")
        for r in latency_results:
            f.write(f"| {r['Model']} | {r['TTFT']:.3f} | {r['Total']:.3f} | {r['Speed']:.1f} |\n")
        
        # Image Results
        if image_results:
            f.write("\n## Image Generation\n\n")
            f.write("| Model | Time (s) | Size (KB) | Status |\n")
            f.write("|:---|:---|:---|:---|\n")
            for r in image_results:
                f.write(f"| {r['Model']} | {r['Time']:.2f} | {r['Size']:.1f} | {r['Status']} |\n")
    
    return str(report_path)


def main():
    parser = argparse.ArgumentParser(description="LLM SDK Unified Benchmark")
    parser.add_argument("--skip-image", action="store_true", help="Skip image generation tests")
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 LLM SDK Unified Benchmark")
    print(f"📁 Output: {OUTPUT_DIR}")
    print("=" * 60)
    
    client = LLMClient()
    print("✅ SDK Client Initialized")
    
    # Run benchmarks
    text_results = benchmark_text(client)
    latency_results = benchmark_latency(client)
    
    image_results = []
    if not args.skip_image:
        image_results = benchmark_image(client)
    
    # Generate report
    report_path = generate_report(text_results, latency_results, image_results)
    
    print("\n" + "=" * 60)
    print(f"📊 Report saved: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
