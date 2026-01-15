"""
Test Gemini image generation with user's storyboard prompt.
Verify what TEXT is returned.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from dotenv import load_dotenv
load_dotenv()

from my_llm_sdk.client import LLMClient

PROMPT = """IMAGE_1_PROMPT:
Image1 Mode: 模式A：电影分镜条 Storyboard. A 4-panel sequential comic layout for the story "时间箴言". 
Layout: Standard 4-panel grid. Row 1: Panel 1 (Top Left), Panel 2 (Top Right). Row 2: Panel 3 (Bottom Left), Panel 4 (Bottom Right).
Style Description: Voxel blocks, isometric diorama, pixel-like texture. 所有物体必须由方块/体素构成；等距视角；像Minecraft一样构建场景。. 
Parameters: Body Ratio M, Saturation Mid.
Visual Layout: The top of the image features a wide light-colored header with the TITLE_EXACT "时间箴言" and the SOURCE_EXACT "出处：《增广贤文》" in large, clear, horizontal Kaishu (Regular Script). 
Text Rules: Each panel has a bottom caption bar. COPY-PASTE RULE: Render Chinese strings verbatim. No typos. Kaishu font. Horizontal only. Clean light text boxes.
NEGATIVE (Global): No cropped characters (no half-body/bust), no cross-panel leakage, no English words, no watermark, no panel labels (no "Panel 1", "Panel 2" text in image).

PANEL_PROMPTS:
 * Frame 1:
   - Camera: Mid Shot.
   - Caption (Bottom Text Box): "一年之计在于春，"
   - Scene Description: Isometric view. A voxel child character wearing ancient Chinese tunic planting a small blocky green sapling in a voxelated field. The ground is made of grass blocks. Minimalist background emphasizing the vitality of spring. Bright, fresh colors.
   - Motion: STATIC

 * Frame 2:
   - Camera: Mid Shot.
   - Caption (Bottom Text Box): "一日之计在于晨。"
   - Scene Description: The voxel child sits at a blocky wooden desk by a square window reading a voxel book. Outside the window, a square red sun is rising (Low-to-High visual flow), casting soft morning pixelated light rays into the room. Focus on study and morning atmosphere.
   - Motion: LOW->HIGH

 * Frame 3:
   - Camera: Close-up.
   - Caption (Bottom Text Box): "一寸光阴一寸金，"
   - Scene Description: Close-up on the child's blocky hands. One hand holds a shiny yellow voxel gold coin, the other holds a voxel hourglass. The background is a solid, neutral color to highlight the contrast between the two objects. 3D voxel render style.
   - Motion: STATIC

 * Frame 4:
   - Camera: Mid Shot.
   - Caption (Bottom Text Box): "寸金难买寸光阴。"
   - Scene Description: The voxel child is sitting on the floor, tightly hugging the voxel hourglass, cherishing it. Next to the child is a pile of voxel gold coins that are being ignored. The child's pixelated face shows a serious, appreciative expression. Emphasize the value of time over money.
   - Motion: STATIC

TEXT_LAYER_PROMPT:
Render only text on a clean, light-colored background. 
Top Header: "时间箴言" (Large), "出处：《增广贤文》" (Medium).
Panel Captions (Bottom-aligned boxes):
 [1]. "一年之计在于春，" 
 [2]. "一日之计在于晨。" 
 [3]. "一寸光阴一寸金，" 
 [4]. "寸金难买寸光阴。" 
All text must be in Kaishu, horizontal, high contrast black on off-white."""

def test_storyboard_generation():
    client = LLMClient()
    
    print("=" * 70)
    print("Testing Storyboard Image Generation")
    print("=" * 70)
    
    response = client.generate(
        prompt=PROMPT,
        model_alias="gemini-3-pro-image-preview",  # 正确的图像生成模型
        config={
            "response_modalities": ["TEXT", "IMAGE"],
        },
        full_response=True
    )
    
    print(f"\n📋 Response Type: {type(response)}")
    print(f"\n📝 TEXT Content Returned:")
    print("-" * 70)
    print(response.content if response.content else "(Empty)")
    print("-" * 70)
    
    print(f"\n🖼️  Media Parts: {len(response.media_parts) if response.media_parts else 0}")
    print(f"⚙️  Finish Reason: {response.finish_reason}")
    
    if response.usage:
        print(f"📊 Usage: input={response.usage.input_tokens}, output={response.usage.output_tokens}")
    
    # Save image if available
    if response.media_parts:
        for i, part in enumerate(response.media_parts):
            fname = f"tests/storyboard_output_{i}.jpg"
            with open(fname, "wb") as f:
                f.write(part.inline_data)
            print(f"📁 Image {i} saved to: {fname}")
    
    return response

if __name__ == "__main__":
    try:
        response = test_storyboard_generation()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
