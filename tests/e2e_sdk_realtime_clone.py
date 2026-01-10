
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import TaskType, GenConfig

def main():
    print("=====================================================")
    print("🎙️ SDK Realtime Voice Clone Verification")
    print("=====================================================")
    
    # Init client
    client = LLMClient()
    
    # Text to speak
    text = "Hello, this is a test of the SDK integration for Realtime Voice Cloning. If you hear this, it works!"
    
    # Config
    # Model alias 'qwen-tts-realtime' defined in project.yaml points to 'qwen3-tts-vc-realtime...'
    model_alias = "qwen-tts-realtime"
    
    # Voice Config (Confirmed Voice ID)
    voice_id = "qwen-tts-vc-father-voice-20251207194748170-5620"
    
    print(f"🤖 Model: {model_alias}")
    print(f"🎙️ Voice: {voice_id}")
    
    config = GenConfig(
        task=TaskType.TTS,
        persist_media=True,
        voice_config={
            "voice_name": voice_id
        },
        audio_format="wav" # Realtime handler outputs wav container
    )
    
    try:
        response = client.generate(
            model_alias=model_alias,
            contents=text,
            config=config,
            full_response=True
        )
        
        print("\n✅ Generation Success!")
        if response.media_parts:
            print(f"📂 Saved to: {response.media_parts[0].local_path}")
            print(f"📊 Usage: {response.usage}")
        else:
            print("⚠️ No media parts returned.")
            
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
