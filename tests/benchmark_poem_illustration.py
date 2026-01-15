import os
import time
from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import TaskType, ContentPart

# --- Benchmark Configuration ---
POEM = """
画
远看山有色，近听水无声。
春去花还在，人来鸟不惊。
"""

TEACHER_PROMPT = "请你以一名亲切、专业的小学语文老师身份，为学生详细解读这首古诗。要求：解读内容要生动有趣，富有画面感，能够帮助学生理解诗句的意境。字数在 300 字左右。"

IMAGE_PROMPT_TEMPLATE = "请根据以下对古诗《画》的专家解读，生成一张精美的、富有诗意的、具有中国传统美学风格的插画。解读内容如下：\n\n{interpretation}"

OUTPUT_DIR = "e2e_outputs/benchmark"

MODELS = {
    "doubao": {
        "text": "doubao-thinking",
        "image": "doubao-image"
    },
    "qwen": {
        "text": "qwen-max",
        "image": "qwen-image-plus"
    },
    "gemini": {
        "text": "gemini-3.0-pro",
        "image": "gemini-3-pro-image-preview"
    }
}

def ensure_dir(d):
    if not os.path.exists(d):
        os.makedirs(d)

def run_benchmark():
    client = LLMClient()
    ensure_dir(OUTPUT_DIR)
    
    print(f"🚀 Starting Multi-Provider Benchmark: Poem Interpretation & Illustration")
    print(f"Poem: \n{POEM}")
    print("-" * 50)

    for provider, model_config in MODELS.items():
        print(f"\n[Provider: {provider.upper()}]")
        
        # Step 1: Text Interpretation
        print(f"  Step 1: Interpreting text using '{model_config['text']}'...")
        start_time = time.time()
        try:
            text_res = client.generate(
                prompt=f"古诗：\n{POEM}\n\n指令：{TEACHER_PROMPT}",
                model_alias=model_config['text'],
                full_response=True
            )
            interpretation = text_res.content
            latency_text = time.time() - start_time
            print(f"  ✅ Interpretation completed ({latency_text:.2f}s)")
            
            # Save interpretation
            text_path = os.path.join(OUTPUT_DIR, f"{provider}_interpretation.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(interpretation)
            
        except Exception as e:
            print(f"  ❌ Text generation failed: {e}")
            continue

        # Step 2: Image Generation
        print(f"  Step 2: Generating image using '{model_config['image']}'...")
        start_time = time.time()
        try:
            # Using the interpretation as context for the image
            image_prompt = IMAGE_PROMPT_TEMPLATE.format(interpretation=interpretation)
            
            # Determine size based on provider
            i_size = "1K"
            if provider == "doubao": i_size = "2K" # seedream requires 2k?
            
            image_res = client.generate(
                model_alias=model_config['image'],
                prompt=image_prompt,
                config={
                    "task": TaskType.IMAGE_GENERATION,
                    "image_size": i_size
                },
                full_response=True
            )
            
            if image_res.media_parts:
                part = image_res.media_parts[0]
                img_data = part.inline_data or (b"" if not part.file_uri else b"URL") # simple check
                
                # Save image
                ext = "png"
                if "jpeg" in (part.mime_type or "").lower(): ext = "jpg"
                
                img_path = os.path.join(OUTPUT_DIR, f"{provider}_illustration.{ext}")
                
                if part.inline_data:
                    with open(img_path, "wb") as f:
                        f.write(part.inline_data)
                    print(f"  ✅ Image saved to {img_path} ({len(part.inline_data)/1024:.1f} KB)")
                elif part.file_uri:
                    # In case it's a URL (though we tried to unify to bytes)
                    with open(img_path + ".url.txt", "w") as f:
                        f.write(part.file_uri)
                    print(f"  ✅ Image URL saved: {part.file_uri}")
                
                latency_image = time.time() - start_time
                print(f"  ✅ Image generation completed ({latency_image:.2f}s)")
            else:
                print("  ❌ No image generated in response.")
                
        except Exception as e:
            print(f"  ❌ Image generation failed: {e}")

    print("\n" + "="*50)
    print(f"🎉 Benchmark Finished. Artifacts saved in: {OUTPUT_DIR}")

if __name__ == "__main__":
    run_benchmark()
