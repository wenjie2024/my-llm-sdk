
import os
import sys
import time

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import TaskType, GenConfig, ContentPart

def print_header(title):
    print("\n" + "="*70)
    print(f"🧬 {title}")
    print("="*70)

def main():
    print_header("Voice Clone E2E Experiment")
    
    # Initialize Client
    client = LLMClient()
    print("✅ SDK Client Initialized")
    
    # Paths
    ref_audio_path = os.path.abspath("audio/Dad_voice.m4a")
    if not os.path.exists(ref_audio_path):
        print(f"❌ Reference audio not found at: {ref_audio_path}")
        return

    print(f"🎤 Reference Audio: {ref_audio_path}")
    
    # Test Phrases
    test_text = "Hello, this is a cloned voice test. I am speaking with your voice."
    
    # 0. Sanity Check (Standard Model)
    # print_header("Step 0: Sanity Check (sambert-zhichu-v1)")
    # try:
    #     import dashscope
    #     print(f"DashScope SDK Version: {dashscope.__version__}")
        
    # except Exception as e:
    #     print(f"SDK Check Failed: {e}")

    # 1. Generate Cloned Audio (CosyVoice)
    print_header("Step 1: Cloning Voice (CosyVoice)")
    
    # Note: 'cosyvoice-v1' added to llm.project.yaml
    model_alias = "cosyvoice-v1" 
    
    # Need absolute file URI for provider
    ref_uri = f"file://{ref_audio_path}"
    
    # Optional prompt text derived from audio if known, but CosyVoice often does zero-shot without it
    # If the user script knows the content of Dad_voice.m4a, providing it helps quality.
    # We will try zero-shot first.
    
    config = GenConfig(
        task=TaskType.TTS,
        voice_config={
            "reference_audio_uri": ref_uri,
            # "reference_text": "Content of dad voice if known..." 
        },
        persist_media=True # Save the output
    )
    
    try:
        response = client.generate(
            model_alias=model_alias,
            contents=test_text,
            config=config,
            full_response=True
        )
        
        cloned_audio_part = None
        if response.media_parts:
            cloned_audio_part = response.media_parts[0]
            print(f"  ✅ Cloning Success!")
            print(f"  💾 Saved to: {cloned_audio_part.local_path}")
        else:
            print("  ❌ No audio returned.")
            return

    except Exception as e:
        print(f"  ❌ Cloning Failed: {e}")
        return

    # 2. Verify with ASR (Qwen ASR)
    print_header("Step 2: Verification (ASR)")
    
    try:
        asr_config = GenConfig(
            task=TaskType.ASR,
            persist_media=False
        )
        
        # Pass the generated audio part back
        asr_response = client.generate(
            model_alias="qwen3-asr-flash",
            contents=[cloned_audio_part],
            config=asr_config,
            full_response=True
        )
        
        print(f"  📝 Transcribed: {asr_response.content}")
        
        # Save transcription to file
        output_txt_path = cloned_audio_part.local_path + ".txt"
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write(f"Original Text: {test_text}\n")
            f.write(f"Transcribed: {asr_response.content}\n")
            f.write(f"Model: {model_alias}\n")
            f.write(f"Reference: {ref_audio_path}\n")
            
        print(f"  📄 Result saved to: {output_txt_path}")
        
    except Exception as e:
        print(f"  ❌ ASR Verification Failed: {e}")

if __name__ == "__main__":
    main()
