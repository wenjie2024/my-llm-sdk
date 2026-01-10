
import dashscope
from dashscope.audio.tts import SpeechSynthesizer
import os

# Use INTL endpoint explicitly
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"

# API Key
api_key = os.getenv("DASHSCOPE_API_KEY") or "sk-ca653b0fadc343d6a5ae3b97f6deacd2"
dashscope.api_key = api_key

def test_rest_intl():
    print("🚀 Testing REST API with INTL Endpoint...")
    print(f"URL: {dashscope.base_http_api_url}")
    print(f"API Key: {api_key[:6]}...")
    
    model = "cosyvoice-v1"
    voice = "longxiaochun"
    text = "Hello, testing REST API on INTL endpoint."
    
    try:
        result = SpeechSynthesizer.call(
            model=model,
            text=text,
            voice=voice,
            format='mp3'
        )
        
        if result.get_audio_data():
            print(f"✅ Success! Audio size: {len(result.get_audio_data())}")
        else:
            print("❌ Failed (No Audio)")
            # Standard error dumping
            if hasattr(result, 'code'): print(f"Code: {result.code}")
            if hasattr(result, 'message'): print(f"Message: {result.message}")
            if hasattr(result, 'get_response'):
                print(f"Hidden Response: {result.get_response()}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_rest_intl()
