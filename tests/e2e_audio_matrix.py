
import os
import time
import sys
from typing import Optional

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import TaskType, GenConfig, ContentPart

def print_header(title):
    print("\n" + "="*70)
    print(f"🔊 {title}")
    print("="*70)

def test_tts(client: LLMClient, model_alias: str, text: str, provider: str) -> Optional[ContentPart]:
    print(f"\n🗣️  Testing TTS with [{model_alias}]...")
    try:
        config = GenConfig(
            task=TaskType.TTS,
            voice_config={"voice_name": "Puck" if provider == "gemini" else "sambert-zhichu-v1"},
            persist_media=True
        )
        
        response = client.generate(
            model_alias=model_alias,
            contents=text,
            config=config,
            full_response=True
        )
        
        if response.media_parts:
            audio = response.media_parts[0]
            print(f"  ✅ TTS Success. Duration: {response.usage.audio_seconds_generated or 'Unknown'}s")
            print(f"  💾 Saved to: {audio.local_path}")
            
            # Verify file exists
            if audio.local_path and os.path.exists(audio.local_path):
                print(f"  📁 File existence verified.")
                return audio
            else:
                print(f"  ❌ Persistence Failed: File not found at {audio.local_path}")
        else:
            print("  ❌ No audio parts returned.")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
    return None

def test_asr(client: LLMClient, model_alias: str, audio_part: ContentPart, expected_text: str):
    print(f"\n👂 Testing ASR with [{model_alias}]...")
    try:
        config = GenConfig(
            task=TaskType.ASR,
            persist_media=True # Maybe save result? or just text
        )
        
        # Audio part already has local_path from persistence
        # We can pass specific audio part as content
        
        # If part has file_uri, SDK handles it. If not (inline), SDK handles it.
        # But for ASR we need to be careful. Qwen provider should handle both.
        # Let's pass the audio part directly.
        
        response = client.generate(
            model_alias=model_alias,
            contents=[audio_part],
            config=config,
            full_response=True
        )
        
        print(f"  📝 Result: {response.content}")
        
        if expected_text.lower() in response.content.lower():
             print("  ✅ Content Validation: PASS")
        else:
             print(f"  ⚠️ Content Validation: Expected '{expected_text}' in '{response.content}'")

    except Exception as e:
        print(f"  ❌ Error: {e}")


def main():
    print_header("Audio & Persistence E2E Test Suite")
    
    # Initialize Client (uses default config paths or local)
    client = LLMClient()
    print("✅ SDK Client Initialized")
    
    test_phrase = "Hello, this is a test of the multimodal SDK audio capabilities."
    
    # 1. Qwen TTS & ASR Loop
    print_header("PART 1: Qwen Audio Loop")
    qwen_tts_model = "qwen3-tts-flash" # Alias from layout
    qwen_asr_model = "qwen3-asr-flash"
    
    audio_part = test_tts(client, qwen_tts_model, test_phrase, "qwen")
    
    if audio_part:
        # Feed back to ASR
        test_asr(client, qwen_asr_model, audio_part, "Hello")
    else:
        print("⚠️ Skipping ASR test due to TTS failure.")
        
    # 2. Gemini TTS
    print_header("PART 2: Gemini TTS")
    gemini_tts_model = "gemini-2.5-flash-preview-tts"
    
    test_tts(client, gemini_tts_model, "Welcome to the future of AI.", "gemini")
    
    print("\n✅ Verification Complete.")

if __name__ == "__main__":
    main()
