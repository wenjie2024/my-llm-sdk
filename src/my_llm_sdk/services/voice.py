"""
Voice management service for voice enrollment and management.

This service handles stateful voice operations like:
- Voice enrollment (cloning)
- Voice listing
- Voice deletion
"""

from typing import Optional, Dict, Any
import os
import base64
import json

# Import will be done lazily to avoid circular imports


class VoiceService:
    """
    Voice management service providing voice enrollment functionality.
    
    Usage:
        client = LLMClient()
        voice_id = client.voice.enroll(audio_path="sample.wav", name="my_voice", provider="qwen")
    """
    
    def __init__(self, client):
        """
        Initialize VoiceService with reference to LLMClient.
        
        Args:
            client: LLMClient instance for accessing config and providers
        """
        self._client = client
    
    def enroll(
        self,
        audio_path: str,
        name: str,
        provider: str = "qwen",
        **kwargs
    ) -> str:
        """
        Enroll a voice for voice cloning.
        
        Args:
            audio_path: Path to the audio sample file (WAV/MP3, 10-60 seconds)
            name: Preferred name for the voice
            provider: Provider to use ("qwen" currently supported)
            **kwargs: Additional provider-specific parameters
            
        Returns:
            voice_id: The enrolled voice ID for use in TTS
            
        Raises:
            ValueError: If provider not supported or file not found
            RuntimeError: If enrollment fails
        """
        if not os.path.exists(audio_path):
            raise ValueError(f"Audio file not found: {audio_path}")
        
        if provider == "qwen":
            return self._enroll_qwen(audio_path, name, **kwargs)
        else:
            raise ValueError(f"Voice enrollment not supported for provider: {provider}")
    
    def _enroll_qwen(self, audio_path: str, name: str, **kwargs) -> str:
        """
        Enroll voice using Qwen/DashScope Voice Enrollment API.
        
        This uses the HTTP API directly as the SDK doesn't wrap enrollment.
        """
        import urllib.request
        import urllib.error
        
        # Get API key from client config
        api_key = self._client.config.api_keys.get("dashscope")
        if not api_key:
            raise ValueError("DashScope API key not found in config")
        
        # Read and encode audio file
        with open(audio_path, "rb") as f:
            audio_data = f.read()
        
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")
        
        # Determine MIME type
        ext = os.path.splitext(audio_path)[1].lower()
        if ext in (".wav", ".wave"):
            mime_type = "audio/wav"
        elif ext in (".m4a",):
            mime_type = "audio/mp4"
        else:
            mime_type = "audio/mpeg"
        
        audio_data_uri = f"data:{mime_type};base64,{audio_b64}"
        
        # Prepare request
        url = "https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization"
        
        payload = {
            "model": "qwen-voice-enrollment",
            "input": {
                "action": "create",
                "target_model": kwargs.get("target_model", "qwen3-tts-vc-realtime-2025-11-27"),
                "preferred_name": name,
                "audio": {
                    "data": audio_data_uri
                }
            }
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Make request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                if "output" in result:
                    voice_id = result["output"].get("voice") or result["output"].get("voice_id")
                    if voice_id:
                        return voice_id
                    raise RuntimeError(f"Voice ID not found in response: {result}")
                else:
                    raise RuntimeError(f"Unexpected response format: {result}")
                    
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else str(e)
            raise RuntimeError(f"Voice enrollment failed: {e.code} - {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error during voice enrollment: {e}")
    
    def list_voices(self, provider: str = "qwen") -> list:
        """
        List enrolled voices (placeholder for future implementation).
        """
        # TODO: Implement voice listing
        raise NotImplementedError("Voice listing not yet implemented")
    
    def delete_voice(self, voice_id: str, provider: str = "qwen") -> bool:
        """
        Delete an enrolled voice (placeholder for future implementation).
        """
        # TODO: Implement voice deletion
        raise NotImplementedError("Voice deletion not yet implemented")
