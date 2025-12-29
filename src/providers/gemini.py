import google.generativeai as genai
from .base import BaseProvider

class GeminiProvider(BaseProvider):
    def generate(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> str:
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        genai.configure(api_key=api_key)
        
        # Instantiate model. 
        # model_id should be like "gemini-pro" or "gemini-1.5-flash"
        model = genai.GenerativeModel(model_id)
        
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            # Wrap error or let it bubble
            raise RuntimeError(f"Gemini API Error: {str(e)}")
