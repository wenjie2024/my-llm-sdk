
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import TaskType, GenConfig, ContentPart

def main():
    print("=====================================================")
    print("🎙️ Qwen ASR SDK Verification (Local File)")
    print("=====================================================")
    
    # Init client
    client = LLMClient()
    print("✅ Client initialized")
    
    # Target File
    # Using the user's provided file from previous steps if available, or fall back to known file
    # User mentioned: audio/Dad_voice.m4a (M4A format)
    target_file = os.path.abspath("audio/Dad_voice.m4a")
    
    if not os.path.exists(target_file):
        print(f"❌ Target file not found: {target_file}")
        # Try fall back to test_output_father.wav if exists?
        alt = os.path.abspath("data/test_output_father.wav")
        if os.path.exists(alt):
            target_file = alt
            print(f"⚠️ Using alternate file: {target_file}")
        else:
            return

    print(f"📄 Processing: {target_file}")
    
    # Config
    # Explicitly set audio_format logic if needed, but our Provider now auto-detects/converts
    config = GenConfig(
        task=TaskType.ASR,
        persist_media=False,
        audio_format="wav" # Our provider converts to wav internally if using local path logic
    )
    
    try:
        # Override contents handling if needed
        # Let's manually construct ContentPart for audio
        
        audio_part = ContentPart(
            type="audio",
            file_uri=f"file://{target_file}"
        )
        
        response = client.generate(
            model_alias="qwen3-asr-flash",
            contents=[audio_part],
            config=config,
            full_response=True
        )
        
        print("\n✅ ASR Success!")
        print(f"📝 Transcription: {response.content}")
        
    except Exception as e:
        print(f"\n❌ ASR Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
