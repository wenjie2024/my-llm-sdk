"""
Test Gemini Image Generation Enhancement
- image_size and aspect_ratio parameters
- Mixed input types (str + PIL.Image)
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import ContentPart

def test_image_config():
    """Test image_size and aspect_ratio parameters"""
    print("=" * 50)
    print("Test 1: image_size + aspect_ratio parameters")
    print("=" * 50)
    
    client = LLMClient()
    
    try:
        response = client.generate(
            prompt="A beautiful sunset over mountains, digital art style",
            model_alias="gemini-3-pro-image-preview",
            full_response=True,
            config={
                "response_modalities": ["TEXT", "IMAGE"],
                "image_size": "1K",
                "aspect_ratio": "16:9"
            }
        )
        
        print(f"✅ Text response: {response.content[:100]}..." if response.content else "✅ No text")
        print(f"📊 Finish reason: {response.finish_reason}")
        print(f"🖼️ Images generated: {len(response.media_parts)}")
        
        if response.media_parts:
            # Save first image
            img_data = response.media_parts[0].inline_data
            output_path = "tests/test_output_image_config.jpg"
            with open(output_path, "wb") as f:
                f.write(img_data)
            print(f"💾 Saved to: {output_path}")
        elif response.finish_reason == "safety_blocked":
            print(f"⚠️ Safety blocked: {response.content}")
            
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_mixed_input():
    """Test mixed content types (str + ContentPart)"""
    print("\n" + "=" * 50)
    print("Test 2: Mixed input types")
    print("=" * 50)
    
    client = LLMClient()
    
    try:
        # Test with str + ContentPart mix
        response = client.generate(
            model_alias="gemini-3-pro-image-preview",
            full_response=True,
            contents=[
                "Describe this scene and enhance it:",
                ContentPart(type="text", text="A peaceful garden with flowers"),
            ],
            config={
                "response_modalities": ["TEXT", "IMAGE"],
                "aspect_ratio": "1:1"
            }
        )
        
        print(f"✅ Text response: {response.content[:100]}..." if response.content else "✅ No text")
        print(f"📊 Finish reason: {response.finish_reason}")
        print(f"🖼️ Images generated: {len(response.media_parts)}")
        
        if response.media_parts:
            output_path = "tests/test_output_mixed.jpg"
            with open(output_path, "wb") as f:
                f.write(response.media_parts[0].inline_data)
            print(f"💾 Saved to: {output_path}")
            
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_pil_image_input():
    """Test PIL.Image input (optional - requires test image)"""
    print("\n" + "=" * 50)
    print("Test 3: PIL.Image input (optional)")
    print("=" * 50)
    
    try:
        from PIL import Image
    except ImportError:
        print("⚠️ Skipped: PIL not available")
        return True
    
    # Create a simple test image
    test_img = Image.new('RGB', (100, 100), color='blue')
    
    client = LLMClient()
    
    try:
        response = client.generate(
            model_alias="gemini-3-pro-image-preview",
            full_response=True,
            contents=[
                "Transform this blue square into a colorful abstract pattern",
                test_img,
            ],
            config={
                "response_modalities": ["TEXT", "IMAGE"],
                "image_size": "1K"
            }
        )
        
        print(f"✅ Text response: {response.content[:100]}..." if response.content else "✅ No text")
        print(f"📊 Finish reason: {response.finish_reason}")
        print(f"🖼️ Images generated: {len(response.media_parts)}")
        
        if response.media_parts:
            output_path = "tests/test_output_pil.jpg"
            with open(output_path, "wb") as f:
                f.write(response.media_parts[0].inline_data)
            print(f"💾 Saved to: {output_path}")
            
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Testing Gemini Image Generation Enhancement\n")
    
    results = []
    results.append(("image_config", test_image_config()))
    results.append(("mixed_input", test_mixed_input()))
    results.append(("pil_image", test_pil_image_input()))
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
