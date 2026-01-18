"""
E2E Test: Full Model Matrix - Image Generation & Vision Understanding

Part 1: Generate images with ALL models using the SAME prompt for comparison
Part 2: Use Gemini 3 Pro to generate a golden image, then test vision understanding across models
Part 3: Translate understanding results to Chinese and save both versions
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import TaskType, GenConfig, ContentPart

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "outputs" / "tests" / "model_matrix"
OUTPUT_DIR.mkdir(exist_ok=True)

# Common prompt for all image generation models
IMAGE_PROMPT = "A cozy coffee shop interior with warm lighting, wooden furniture, plants by the window, and a cat sleeping on a chair. Digital art style, high detail."

# Vision understanding prompt
VISION_PROMPT = "Describe this image in detail. Include: 1) Main subjects 2) Setting/environment 3) Colors and lighting 4) Mood/atmosphere 5) Any notable details"


def save_image(data: bytes, provider: str, model: str, ext: str = "png") -> str:
    """Save image with provider_model naming."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_clean = model.replace("-", "_").replace(".", "_")
    filename = f"{provider}_{model_clean}_{timestamp}.{ext}"
    filepath = OUTPUT_DIR / filename
    
    with open(filepath, "wb") as f:
        f.write(data)
    
    print(f"    💾 Saved: {filepath.name} ({len(data)//1024} KB)")
    return str(filepath)


def save_text(content: str, provider: str, model: str, suffix: str = "understanding", lang: str = "en") -> str:
    """Save text output for comparison."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_clean = model.replace("-", "_").replace(".", "_")
    filename = f"{provider}_{model_clean}_{suffix}_{lang}_{timestamp}.txt"
    filepath = OUTPUT_DIR / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"    📝 Saved: {filepath.name}")
    return str(filepath)


def translate_to_chinese(client: LLMClient, text: str) -> str:
    """Translate English text to Chinese using Gemini via SDK."""
    try:
        response = client.generate(
            model_alias="gemini-2.5-flash",
            prompt=f"请将以下英文翻译为中文，保持格式和结构：\n\n{text}"
        )
        return response if isinstance(response, str) else response.content
    except Exception as e:
        print(f"    ⚠️ Translation error: {e}")
        return ""


# ============================================================
# Part 1: Image Generation Models (Using SDK Routing)
# ============================================================

def test_image_gen(client: LLMClient, model_alias: str, provider_name: str, model_name: str):
    """Generic image generation test using SDK."""
    print(f"\n  🎨 {model_alias}")
    try:
        # P1: Use TaskType to route to Image Generation
        config: GenConfig = {
            "task": TaskType.IMAGE_GENERATION,
            "image_size": "1024x1024",
            "persist_media": False
        }
        
        response = client.generate(
            model_alias=model_alias,
            prompt=IMAGE_PROMPT,
            config=config,
            full_response=True
        )
        
        # Check media parts
        if response.media_parts:
            # We assume the first image is the one
            img_part = next((p for p in response.media_parts if p.type == "image"), None)
            if img_part and img_part.inline_data:
                return save_image(img_part.inline_data, provider_name, model_name, "png")
        
        print("    ❌ No image in response media_parts")
        return None
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return None


# ============================================================
# Part 2: Vision Understanding Models (Using SDK Multimodal)
# ============================================================

def test_vision(client: LLMClient, model_alias: str, provider_name: str, model_name: str, image_path: str):
    """Generic vision test using SDK."""
    print(f"\n  👁️ {model_alias} (Vision)")
    try:
        with open(image_path, "rb") as f:
            img_data = f.read()
            
        # Construct multimodal contents
        contents = [
            ContentPart(type="image", inline_data=img_data, mime_type="image/png"),
            ContentPart(type="text", text=VISION_PROMPT)
        ]
        
        config: GenConfig = {
            "task": TaskType.VISION, # Explicit task type helps (though auto-detection also works)
            "persist_media": False
        }

        # Response
        response = client.generate(
            model_alias=model_alias,
            contents=contents,
            config=config,
            full_response=True
        )
        
        content = response.content
        
        if content:
            # Save English
            save_text(content, provider_name, f"{model_name}-vision", lang="en")
            print(f"    ✅ Generated {len(content)} chars")
            
            # Translate
            zh_content = translate_to_chinese(client, content)
            if zh_content:
                 save_text(zh_content, provider_name, f"{model_name}-vision", lang="zh")
                 print(f"    🌏 Translated to Chinese ({len(zh_content)} chars)")
                 
            return content
        
        print("    ❌ No text content generated")
        return None
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return None


def main():
    print("=" * 70)
    print("🧪 Full Model Matrix Test Suite (SDK Integrated)")
    print(f"📁 Output: {OUTPUT_DIR}")
    print("=" * 70)
    
    # Initialize SDK Client
    try:
        client = LLMClient()
        print("✅ SDK Client Initialized")
    except Exception as e:
        print(f"❌ SDK Client Init Failed: {e}")
        return

    # ========== Part 1: Image Generation ==========
    print("\n" + "=" * 70)
    print("📸 PART 1: Image Generation Comparison")
    print(f"   Prompt: \"{IMAGE_PROMPT[:60]}...\"")
    print("=" * 70)
    
    image_results = {}
    
    # Gemini models (Using model aliases from llm.project.yaml)
    image_results["gemini-2.5-flash-image"] = test_image_gen(client, "gemini-2.5-flash-image", "gemini", "2.5-flash-image")
    image_results["gemini-3-pro-image"] = test_image_gen(client, "gemini-3-pro-image-preview", "gemini", "3-pro-image-preview")
    
    image_results["imagen-4.0"] = test_image_gen(client, "imagen-4.0-generate", "gemini", "imagen-4.0") 
    
    # Qwen models
    image_results["qwen-image-plus"] = test_image_gen(client, "qwen-image-plus", "qwen", "image-plus")
    
    # Summary
    print("\n" + "-" * 50)
    print("📊 Image Generation Results:")
    for model, path in image_results.items():
        status = "✅" if path else "❌"
        print(f"   {status} {model}")
    
    # ========== Part 2: Vision Understanding ==========
    print("\n" + "=" * 70)
    print("👁️ PART 2: Vision Understanding Comparison")
    print("=" * 70)
    
    # Use first successful image as golden
    golden_image = None
    for model, path in image_results.items():
        if path and os.path.exists(path):
            golden_image = path
            print(f"\n   🏆 Using golden image from: {model}")
            print(f"      Path: {path}")
            break
    
    if not golden_image:
        print("\n   ⚠️ No golden image available, skipping vision tests")
        return
    
    vision_results = {}
    
    # Test vision models (using standard aliases)
    vision_results["gemini-2.5-flash"] = test_vision(client, "gemini-2.5-flash", "gemini", "2.5-flash", golden_image)
    vision_results["gemini-2.5-pro"] = test_vision(client, "gemini-2.5-pro", "gemini", "2.5-pro", golden_image)
    vision_results["qwen-vl-max"] = test_vision(client, "qwen-vl-max", "qwen", "vl-max", golden_image)
    
    # Summary
    print("\n" + "-" * 50)
    print("📊 Vision Understanding Results:")
    for model, text in vision_results.items():
        status = "✅" if text else "❌"
        chars = len(text) if text else 0
        print(f"   {status} {model} ({chars} chars)")
    
    # ========== Final Summary ==========
    print("\n" + "=" * 70)
    print("📋 FINAL SUMMARY")
    print("=" * 70)
    
    # List all generated files
    all_files = sorted(OUTPUT_DIR.glob("*"))
    print("\n📁 Generated Files:")
    for f in all_files:
        if f.is_file():
            size = f.stat().st_size
            if size > 1024 * 1024:
                size_str = f"{size / 1024 / 1024:.1f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} B"
            print(f"   📄 {f.name} ({size_str})")


if __name__ == "__main__":
    main()
