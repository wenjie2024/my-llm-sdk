from http import HTTPStatus
import dashscope
from .base import BaseProvider
from src.utils.network import can_connect_to_google

class QwenProvider(BaseProvider):
    def generate(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> str:
        if not api_key:
            raise ValueError("API key required for Qwen")
            
        dashscope.api_key = api_key
        
        # Dynamic Endpoint Switching via Network Check
        # If we can reach Google, we assume we are outside CN GFW (or using Proxy) -> Use SG Endpoint
        if can_connect_to_google(timeout=1.5):
            dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
        else:
            dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"
        
        try:
            # Simple Generation Call
            response = dashscope.Generation.call(
                model=model_id,
                prompt=prompt,
                result_format='message',  # Use 'message' format for common chat structure
            )
            
            if response.status_code == HTTPStatus.OK:
                return response.output.choices[0].message.content
            else:
                raise RuntimeError(f"Qwen API Error: {response.code} - {response.message}")
                
        except Exception as e:
            raise RuntimeError(f"Qwen Request Failed: {str(e)}")
