"""
TEST Qwen TTS Functionality (Reproduction Script - Adapted)

Usage:
    python tests/test_qwen_tts.py
"""
import os
import sys
import time
import threading
import wave
import base64
import dashscope
# Try importing QwenTtsRealtime - might need specific version or it's in dashscope.audio?
# User script said: from dashscope.audio.qwen_tts_realtime import ...
# Let's trust user's import path.
try:
    from dashscope.audio.qwen_tts_realtime import (
        QwenTtsRealtime,
        QwenTtsRealtimeCallback,
        AudioFormat,
    )
except ImportError:
    # Fallback or check availability
    print("⚠️ QwenTtsRealtime not found in dashscope.audio. Checking dashscope version...")
    print(dashscope.__version__)
    raise

# Hardcoded or Env Config
# User's config.yaml has this key: sk-ca653b0fadc343d6a5ae3b97f6deacd2
# I will use os.getenv first, then fallback to the one seen in config.yaml if needed for repro
API_KEY = os.getenv("DASHSCOPE_API_KEY") or "sk-ca653b0fadc343d6a5ae3b97f6deacd2"

# Configuration
VOICE_ID = "qwen-tts-vc-father-voice-20251207194748170-5620"
MODEL = "qwen3-tts-vc-realtime-2025-11-27"
OUTPUT_FILE = "tts_test_output.wav"
TEXT = "你好，这是一个测试语音。"

class TestCallback(QwenTtsRealtimeCallback):
    def __init__(self):
        super().__init__()
        self.finished_event = threading.Event()
        self.error = None
        self.file = open(OUTPUT_FILE, "wb")
        self.wav = wave.open(self.file, "wb")
        self.wav.setnchannels(1)
        self.wav.setsampwidth(2)
        self.wav.setframerate(24000)
        self.first_frame_received = False

    def on_event(self, response: dict):
        try:
            # print(f"Event: {response.get('type')}")
            if response.get("type") == "response.audio.delta":
                b64 = response.get("delta")
                if b64:
                    if not self.first_frame_received:
                        print("  ✅ Audio data receiving...")
                        self.first_frame_received = True
                    self.wav.writeframes(base64.b64decode(b64))
            elif response.get("type") == "session.finished":
                print("  ✅ Session finished.")
                self.finished_event.set()
        except Exception as e:
            self.error = str(e)
            self.finished_event.set()
    
    def on_close(self, code, msg):
        print(f"  ⚠️ Connection closed: {code} {msg}")
        self.wav.close()
        self.file.close()
        self.finished_event.set()
        if code != 1000:
             self.error = f"Legacy Code {code}: {msg}"

    def wait(self):
        return self.finished_event.wait(timeout=30)

def test_tts():
    print("🚀 Starting Qwen TTS Test (Adapted)...")
    
    if not API_KEY:
        print("❌ API Key Missing")
        return

    dashscope.api_key = API_KEY
    print(f"🔑 API Key: {API_KEY[:6]}...")
    print(f"🎙️ Voice ID: {VOICE_ID}")
    print(f"🤖 Model: {MODEL}")
    
    # URL from user script - INTL
    url = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
    print(f"🌐 URL: {url}")

    callback = TestCallback()
    try:
        client = QwenTtsRealtime(
            model=MODEL,
            url=url,
            callback=callback
        )
    except Exception as e:
        print(f"❌ Client Init Error: {e}")
        return

    try:
        af = AudioFormat.PCM_24000HZ_MONO_16BIT
        print(f"🤖 AUDIO_FORMAT Inspection:")
        print(f"   Value: {af}")
        print(f"   Type: {type(af)}")
        print(f"   Has .format? {'format' in dir(af)}")
        # print(f"   Dir: {dir(af)}")
        
        print("🔌 Connecting to DashScope TTS...")
        client.connect()
        print("  ✅ Connected.")
        
        print("📝 Sending text...")
        client.update_session(
             voice=VOICE_ID,
             response_format=af, # Revert to object
             language_type="Chinese"
        )
        
        client.append_text(TEXT)
        client.finish()
        
        print("⏳ Waiting for synthesis...")
        callback.wait()
        
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return

    print("-" * 50)
    if callback.error:
        print(f"❌ TEST FAILED with error: {callback.error}")
    else:
        print(f"✅ TEST PASSED. Audio saved to {OUTPUT_FILE}")
        if os.path.exists(OUTPUT_FILE):
             print(f"   File size: {os.path.getsize(OUTPUT_FILE)} bytes")

if __name__ == "__main__":
    test_tts()
