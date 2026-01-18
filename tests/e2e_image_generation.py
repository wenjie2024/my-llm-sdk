"""
E2E Test: Multimodal Image Generation

Tests image generation across Gemini and Qwen providers.
Generated images are saved to tests/e2e_outputs/ with naming: {provider}_{model}_{timestamp}.{ext}
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import TaskType, GenConfig

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "outputs" / "tests" / "image_gen"
OUTPUT_DIR.mkdir(exist_ok=True)


def save_image(data: bytes, provider: str, model: str, ext: str = "png") -> str:
    """Save image with provider_model naming."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Clean model name for filename
    model_clean = model.replace("-", "_").replace(".", "_")
    filename = f"{provider}_{model_clean}_{timestamp}.{ext}"
    filepath = OUTPUT_DIR / filename
    
    with open(filepath, "wb") as f:
        f.write(data)
    
    print(f"  ✅ Saved: {filepath}")
    return str(filepath)


def test_qwen_image_plus():
    """Test Qwen Image-Plus generation."""
    print("\n🖼️ Testing Qwen Image-Plus...")
    
    try:
        from dashscope import ImageSynthesis
        import dashscope
        import requests
        
        # Ensure API key is set
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            print("  ⚠️ DASHSCOPE_API_KEY not set, skipping Qwen tests")
            return False
        
        dashscope.api_key = api_key
        
        prompt = "A cute cartoon cat sitting on a rainbow, digital art style, vibrant colors"
        
        print(f"  Prompt: {prompt[:50]}...")
        
        rsp = ImageSynthesis.call(
            model="qwen-image-plus",
            prompt=prompt,
            n=1,
            size='1024*1024'
        )
        
        if rsp.status_code == 200:
            if rsp.output and rsp.output.results:
                img_url = rsp.output.results[0].url
                img_data = requests.get(img_url).content
                save_image(img_data, "qwen", "image_plus", "png")
                print("  ✅ Qwen Image-Plus: SUCCESS")
                return True
        
        print(f"  ❌ Qwen Image-Plus failed: {rsp.code} - {rsp.message}")
        return False
        
    except Exception as e:
        print(f"  ❌ Qwen Image-Plus error: {e}")
        return False


def test_gemini_flash_image():
    """Test Gemini Flash Image generation."""
    print("\n🖼️ Testing Gemini 2.5 Flash Image...")
    
    try:
        from google import genai
        from google.genai import types
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("  ⚠️ GEMINI_API_KEY not set, skipping Gemini tests")
            return False
        
        client = genai.Client(api_key=api_key)
        
        prompt = "A majestic dragon flying over a medieval castle at sunset, fantasy art"
        
        print(f"  Prompt: {prompt[:50]}...")
        
        # Use correct model name
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )
        
        # Extract image from response
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    img_data = part.inline_data.data
                    mime = part.inline_data.mime_type
                    ext = "png" if "png" in mime else "jpg"
                    save_image(img_data, "gemini", "2_5_flash_image", ext)
                    print("  ✅ Gemini Flash Image: SUCCESS")
                    return True
        
        print("  ❌ Gemini Flash Image: No image in response")
        return False
        
    except Exception as e:
        print(f"  ❌ Gemini Flash Image error: {e}")
        return False


def test_imagen_4():
    """Test Imagen 4.0 generation."""
    print("\n🖼️ Testing Imagen 4.0...")
    
    try:
        from google import genai
        from google.genai import types
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return False
        
        client = genai.Client(api_key=api_key)
        
        prompt = "A photorealistic image of a futuristic city with flying cars, cyberpunk style"
        
        print(f"  Prompt: {prompt[:50]}...")
        
        # Use correct model name: imagen-4.0-generate-001
        response = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1
            )
        )
        
        if response.generated_images:
            for i, img in enumerate(response.generated_images):
                if hasattr(img, 'image') and img.image:
                    # Image might be bytes or have image_bytes attribute
                    if hasattr(img.image, 'image_bytes'):
                        img_data = img.image.image_bytes
                    else:
                        img_data = img.image
                    save_image(img_data, "gemini", "imagen_4_0", "png")
                    print("  ✅ Imagen 4.0: SUCCESS")
                    return True
        
        print("  ❌ Imagen 4.0: No image generated")
        return False
        
    except Exception as e:
        print(f"  ❌ Imagen 4.0 error: {e}")
        return False


def main():
    print("=" * 60)
    print("🧪 E2E Image Generation Test Suite")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print("=" * 60)
    
    results = {
        "Qwen Image-Plus": test_qwen_image_plus(),
        "Gemini Flash Image": test_gemini_flash_image(),
        "Imagen 4.0": test_imagen_4(),
    }
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    print("=" * 60)
    
    # List generated images
    images = list(OUTPUT_DIR.glob("*.png")) + list(OUTPUT_DIR.glob("*.jpg"))
    if images:
        print("\n📷 Generated Images:")
        for img in images:
            print(f"  - {img.name}")


if __name__ == "__main__":
    main()
