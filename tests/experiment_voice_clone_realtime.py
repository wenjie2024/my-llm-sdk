"""
Voice Clone Experiment (Realtime API)

This script synthesizes audio using the Qwen Realtime API and the verified pre-enrolled Voice ID.
It bypasses the REST API (SpeechSynthesizer) which is currently unavailable in this environment.
"""

import os
import sys
import threading
import wave
import base64
import dashscope

try:
    from dashscope.audio.qwen_tts_realtime import (
        QwenTtsRealtime,
        QwenTtsRealtimeCallback,
        AudioFormat,
    )
except ImportError:
    print("❌ Failed to import QwenTtsRealtime. Please ensure dashscope SDK is installed.")
    sys.exit(1)

# Verification Settings
API_KEY = os.getenv("DASHSCOPE_API_KEY") or "sk-ca653b0fadc343d6a5ae3b97f6deacd2"
VOICE_ID = "qwen-tts-vc-father-voice-20251207194748170-5620" # Pre-enrolled "Dad Voice"
MODEL = "qwen3-tts-vc-realtime-2025-11-27"
URL = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime" # Verified INTL endpoint
OUTPUT_FILE = "outputs/cloned_dad_voice_output.wav"

class ExperimentCallback(QwenTtsRealtimeCallback):
    def __init__(self):
        super().__init__()
        self.finished_event = threading.Event()
        self.error = None
        self.output_path = OUTPUT_FILE
        
        # Ensure dir
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        
        self.file = open(self.output_path, "wb")
        self.wav = wave.open(self.file, "wb")
        self.wav.setnchannels(1)
        self.wav.setsampwidth(2)
        self.wav.setframerate(24000)
        self.frames_received = 0

    def on_event(self, response: dict):
        try:
            if response.get("type") == "response.audio.delta":
                b64 = response.get("delta")
                if b64:
                    data = base64.b64decode(b64)
                    self.wav.writeframes(data)
                    self.frames_received += 1
            elif response.get("type") == "session.finished":
                print(f"  ✅ Session finished. Received {self.frames_received} audio frames.")
                self.finished_event.set()
        except Exception as e:
            self.error = str(e)
            self.finished_event.set()
    
    def on_close(self, code, msg):
        self.wav.close()
        self.file.close()
        self.finished_event.set()
        if code != 1000:
             self.error = f"WebSocket Closed {code}: {msg}"

    def wait(self):
        return self.finished_event.wait(timeout=60)

def run_experiment():
    print("🧬 Starting Voice Clone Experiment (Realtime API)")
    print("=" * 60)
    print(f"🔑 API Key: {'Set' if API_KEY else 'Missing'}")
    print(f"🎙️ Voice ID: {VOICE_ID}")
    print(f"📡 Endpoint: {URL}")
    print(f"💾 Output: {OUTPUT_FILE}")
    
    dashscope.api_key = API_KEY
    callback = ExperimentCallback()
    
    try:
        client = QwenTtsRealtime(
            model=MODEL,
            url=URL,
            callback=callback
        )
        
        print("\nStep 1: Connecting...")
        client.connect()
        print("✅ Connected.")
        
        print("Step 2: Synthesizing...")
        text = "你好，我是您的专属语音助手。我正在使用您的声音为您朗读这段文字，现在的效果听起来怎么样？"
        print(f"📜 Text: {text}")
        
        # Use verified AudioFormat object directly (not .value)
        # Assuming AudioFormat is available and works as object as per Step 1322
        af = AudioFormat.PCM_24000HZ_MONO_16BIT
        
        client.update_session(
            voice=VOICE_ID,
            response_format=af,
            language_type="Chinese"
        )
        
        client.append_text(text)
        client.finish()
        
        print("Step 3: Waiting for audio...")
        callback.wait()
        
        if callback.error:
            print(f"\n❌ Experiment Failed: {callback.error}")
        else:
            print("\n✅ Experiment Success!")
            if os.path.exists(OUTPUT_FILE):
                size = os.path.getsize(OUTPUT_FILE)
                print(f"📊 Saved {size} bytes to {OUTPUT_FILE}")
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_experiment()
