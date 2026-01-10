import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple, Callable
from openai import OpenAI
import google.generativeai as genai

# Import Host Config
from host.config import HostConfig

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, provider: str = "auto"):
        """
        Initialize LLMClient using HostConfig.
        """
        self.qwen_api_key = HostConfig.get_dashscope_api_key()
        self.gemini_api_key = HostConfig.get_gemini_api_key()
        
        self.preferred_provider = provider
        self.providers = {}

        # Initialize Qwen
        if self.qwen_api_key:
            try:
                self.qwen_client = OpenAI(
                    api_key=self.qwen_api_key,
                    base_url=HostConfig.get_openai_base_url()
                )
                self.providers["qwen"] = True
            except Exception as e:
                logger.warning(f"Failed to initialize Qwen client: {e}")

        # Initialize Gemini
        if self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.providers["gemini"] = True
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")

        if not self.providers:
            logger.error("No LLM providers available.")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"LLM Client initialized with providers: {list(self.providers.keys())}")

    def _execute_strategy(self, strategy: List[Tuple[str, str]], operation_func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """
        Executes a strategy list of (provider, model_name).
        """
        if not self.enabled:
            return {}

        for provider, model_name in strategy:
            # Filter by preference if strictly set (not auto)
            if self.preferred_provider != 'auto' and provider != self.preferred_provider:
                continue

            if provider not in self.providers:
                continue

            try:
                logger.info(f"Strategy executing: {provider.upper()} ({model_name})")
                return operation_func(provider, model_name, *args, **kwargs)
            except Exception as e:
                logger.warning(f"Strategy failed for {provider}/{model_name}: {e}")
                continue
        
        logger.error("All strategies failed.")
        return {}

    def generate_metadata(self, prompt_template: str, folder_name: str, track_list: List[str]) -> Dict[str, Any]:
        strategy = [
            ("gemini", "gemini-2.5-flash"),
            ("qwen", "qwen-plus"),
            ("qwen", "qwen-max")
        ]
        
        def _op(provider, model, tmpl, f_name, t_list):
            if provider == "gemini":
                return self._generate_metadata_gemini_single(model, tmpl, f_name, t_list)
            elif provider == "qwen":
                return self._generate_metadata_qwen_single(model, tmpl, f_name, t_list)
        
        return self._execute_strategy(strategy, _op, prompt_template, folder_name, track_list)

    def generate_grading(self, prompt_template: str, metadata: Dict[str, Any], child_age: int = 7) -> Dict[str, Any]:
        strategy = [
            ("gemini", "gemini-2.5-flash"),
            ("qwen", "qwen-turbo")
        ]

        input_payload = {
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "summary": metadata.get("summary"),
            "tags": metadata.get("tags"),
            "child_age": child_age
        }
        user_content = json.dumps(input_payload, ensure_ascii=False, indent=2)

        def _op(provider, model, tmpl, u_content):
            if provider == "gemini":
                return self._call_gemini_json_single(model, tmpl, u_content)
            elif provider == "qwen":
                return self._call_qwen_json_single(model, tmpl, u_content)

        return self._execute_strategy(strategy, _op, prompt_template, user_content)

    # --- Single implementations ---

    def _generate_metadata_gemini_single(self, model_name, prompt_template, folder_name, track_list):
        user_content = f"Folder Name: \"{folder_name}\"\nTrack List: {json.dumps(track_list, ensure_ascii=False)}"
        full_prompt = f"{prompt_template}\n\n**Input:**\n{user_content}"
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(full_prompt)
        res = self._parse_json(response.text)
        res['provider'] = f"gemini ({model_name})"
        return res

    def _generate_metadata_qwen_single(self, model_name, prompt_template, folder_name, track_list):
        user_content = f"Folder Name: \"{folder_name}\"\nTrack List: {json.dumps(track_list, ensure_ascii=False)}"
        response = self.qwen_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": prompt_template},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        res = self._parse_json(content)
        res['provider'] = f"qwen ({model_name})"
        return res

    def _call_gemini_json_single(self, model_name, system_prompt, user_content):
        full_prompt = f"{system_prompt}\n\n**Input:**\n{user_content}"
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(full_prompt)
        res = self._parse_json(response.text)
        res['provider'] = f"gemini ({model_name})"
        return res

    def _call_qwen_json_single(self, model_name, system_prompt, user_content):
        response = self.qwen_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        res = self._parse_json(content)
        res['provider'] = f"qwen ({model_name})"
        return res

    def _parse_json(self, content):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())

    # --- Image Generation ---
    def generate_cover_image(self, prompt: str, save_path: str) -> bool:
        if "qwen" in self.providers:
             return self._generate_cover_qwen(prompt, save_path)
        logger.warning("No suitable provider for Image Generation.")
        return False

    def _generate_cover_qwen(self, prompt: str, save_path: str) -> bool:
        try:
            from dashscope import ImageSynthesis
            import dashscope
            import requests

            # Ensure initialized (though HostConfig.init_dashscope() is for script global, 
            # here we might want to ensure it inside the method or rely on caller?
            # Better: Call init_dashscope() here to be safe locally if using native SDK)
            HostConfig.init_dashscope()
            
            # Note: HostConfig sets up dashscope.api_key and base_http_api_url global.
            
            logger.info(f"Generating Qwen AI cover: {prompt[:30]}...")
            rsp = ImageSynthesis.call(
                model="qwen-image-plus",
                prompt=prompt,
                n=1,
                size='1328*1328',
                prompt_extend=True
            )
            if rsp.status_code == 200:
                if rsp.output and rsp.output.results:
                    img_url = rsp.output.results[0].url
                    img_data = requests.get(img_url).content
                    with open(save_path, "wb") as f:
                        f.write(img_data)
                    logger.info(f"AI Cover saved to {save_path}")
                    return True
            logger.warning(f"Qwen Image failed: {rsp.code} - {rsp.message}")
        except Exception as e:
            logger.error(f"Qwen Cover Gen Error: {e}")
        return False
    # --- Speech Generation ---
    def generate_speech(self, text: str, voice: str, output_path: str, provider: str = "gemini") -> bool:
        """
        Generate speech from text using the specified provider.
        """
        if provider == "gemini" and "gemini" in self.providers:
            return self._generate_speech_gemini(text, voice, output_path)
        # Future: elif provider == "qwen": ...
        else:
             logger.warning(f"Provider {provider} not supported or not enabled for TTS.")
             return False

    def _generate_speech_gemini(self, text: str, voice: str, output_path: str) -> bool:
        # Retry loop for 429/Resource Exhausted
        import time
        max_retries = 3
        
        for attempt in range(max_retries + 1):
            try:
                # Use the NEW SDK explicitly
                from google import genai as new_genai
                from google.genai import types
                import wave
                
                logger.info(f"Generating Gemini TTS (Attempt {attempt+1}): Voice={voice}, Text={text[:20]}...")
                
                # Simple helper for wav saving
                def save_wave(filename, pcm, channels=1, rate=24000, sample_width=2):
                    with wave.open(filename, "wb") as wf:
                        wf.setnchannels(channels)
                        wf.setsampwidth(sample_width)
                        wf.setframerate(rate)
                        wf.writeframes(pcm)

                model_name = "gemini-2.5-flash-preview-tts"
                
                # Initialize with the new Client class
                client = new_genai.Client(api_key=self.gemini_api_key)
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice,
                                )
                            )
                        ),
                    )
                )
                
                if response.candidates and response.candidates[0].content.parts:
                    data = response.candidates[0].content.parts[0].inline_data.data
                    save_wave(output_path, data)
                    logger.info(f"Gemini TTS saved to {output_path}")
                    return True
                else:
                    logger.error("Gemini TTS response contained no audio data.")
                    return False
                    
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if attempt < max_retries:
                        # Extract wait time if possible or default to 32s (safe buffer)
                        wait_seconds = 32
                        import re
                        match = re.search(r"retry in (\d+(\.\d+)?)s", err_str)
                        if match:
                            wait_seconds = float(match.group(1)) + 2.0 # Add 2s buffer
                        
                        logger.warning(f"Gemini 429 limit hit. Waiting {wait_seconds:.1f}s before retry...")
                        time.sleep(wait_seconds)
                        continue
                    else:
                         logger.error(f"Gemini TTS failed after retries: {e}")
                         return False
                
                logger.error(f"Gemini TTS Error: {e}")
                return False
