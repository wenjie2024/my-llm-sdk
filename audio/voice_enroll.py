import os
import sys
import json
import base64
import argparse
import requests

# Constants
API_URL = "https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization"
VOICES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "voices.json")

def get_api_key():
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("Error: DASHSCOPE_API_KEY environment variable not set.")
        sys.exit(1)
    return api_key

def enroll_voice(file_path, speaker_name):
    api_key = get_api_key()
    
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
        
    print(f"Reading audio file: {file_path}...")
    with open(file_path, "rb") as f:
        audio_data = f.read()
        
    audio_b64 = base64.b64encode(audio_data).decode("utf-8")
    audio_data_uri = f"data:audio/mpeg;base64,{audio_b64}" # Note: API accepts data URI, mime type check might be needed if strictly validated, but usually mpeg works for mp3/wav? Let's assume standard handling or use wave if wav.
    # Actually, for WAV it should be audio/wav. Let's detect extension.
    if file_path.lower().endswith(".wav"):
        audio_data_uri = f"data:audio/wav;base64,{audio_b64}"
    
    print("Sending enrollment request to DashScope...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "qwen-voice-enrollment",
        "input": {
            "action": "create",
            "target_model": "qwen3-tts-vc-realtime-2025-11-27", # As per doc
            "preferred_name": speaker_name,
            "audio": {
                "data": audio_data_uri
            }
        }
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        if "output" in result:
            # API might return 'voice' or 'voice_id' depending on version
            voice_id = result["output"].get("voice") or result["output"].get("voice_id")
            
            if voice_id:
                print(f"Successfully enrolled voice! Voice ID: {voice_id}")
                save_voice(speaker_name, voice_id)
            else:
                print("Error: Voice ID not found in response.")
                print(json.dumps(result, indent=2, ensure_ascii=False))
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if e.response is not None:
             print(e.response.text)
        sys.exit(1)

def save_voice(speaker_name, voice_id):
    data = {}
    if os.path.exists(VOICES_FILE):
        try:
            with open(VOICES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            pass
            
    data[speaker_name] = {
        "voice_id": voice_id,
        "model": "qwen3-tts-vc-realtime-2025-11-27",
        "provider": "qwen",
        "enrolled_at": str(os.path.getmtime(VOICES_FILE) if os.path.exists(VOICES_FILE) else "new") # Placeholder
    }
    
    os.makedirs(os.path.dirname(VOICES_FILE), exist_ok=True)
    with open(VOICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved voice info to {VOICES_FILE}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enroll a voice for Qwen TTS")
    parser.add_argument("--speaker", required=True, help="Speaker name (e.g., father)")
    parser.add_argument("--file", required=True, help="Path to audio file (wav/mp3)")
    
    args = parser.parse_args()
    enroll_voice(args.file, args.speaker)
