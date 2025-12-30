import google.generativeai as genai
import time
from typing import Iterator
from .base import BaseProvider
from my_llm_sdk.schemas import GenerationResponse, TokenUsage, StreamEvent

class GeminiProvider(BaseProvider):
    def generate(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> GenerationResponse:
        t0 = time.time()
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        genai.configure(api_key=api_key)
        
        # Instantiate model. 
        # model_id should be like "gemini-pro" or "gemini-1.5-flash"
        model = genai.GenerativeModel(model_id)
        
        try:
            response = model.generate_content(prompt)
            
            # Extract content
            content = response.text
            
            # Extract Usage
            # usage_metadata might be None if stream=True or error, but here is sync
            p_tokens = 0
            o_tokens = 0
            if response.usage_metadata:
                p_tokens = response.usage_metadata.prompt_token_count
                o_tokens = response.usage_metadata.candidates_token_count
            
            usage = TokenUsage(
                input_tokens=p_tokens,
                output_tokens=o_tokens,
                total_tokens=p_tokens + o_tokens
            )
            
            # Extract Finish Reason (Map proto enum to string)
            # Candidate finish_reason is an int/enum. Best effort string conversion.
            finish_reason = "unknown"
            if response.candidates:
                finish_reason = str(response.candidates[0].finish_reason)
                
            t1 = time.time()
            return GenerationResponse(
                content=content,
                model=model_id,
                provider="google",
                usage=usage,
                finish_reason=finish_reason,
                timing={"total": t1 - t0}
            )
            
        except Exception as e:
            # Wrap error or let it bubble
            raise RuntimeError(f"Gemini API Error: {str(e)}")

    def stream(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)
        
        try:
            response = model.generate_content(prompt, stream=True)
            
            p_tokens = 0
            o_tokens = 0
            
            for chunk in response:
                # Chunk text
                if chunk.text:
                    yield StreamEvent(delta=chunk.text)
                
                # Check for usage in this chunk (usually final one has it)
                if chunk.usage_metadata:
                    p_tokens = chunk.usage_metadata.prompt_token_count
                    o_tokens = chunk.usage_metadata.candidates_token_count

            # Re-yield usage at the end if we captured it
            # Note: Gemini python SDK might need explicit iteration to end to get attributes?
            # The loop above iterates.
            # If usage_metadata was found in last chunk, we have it.
            # But the last chunk logic inside yield above might not have emitted finish.
            
            # Construct final finish event
            usage = TokenUsage(
                input_tokens=p_tokens,
                output_tokens=o_tokens,
                total_tokens=p_tokens + o_tokens
            )
            
            # Finish reason?
            # response.candidates[0].finish_reason might availability on stream object?
            # Usually strict iteration is needed.
            # safe defaults
             
            yield StreamEvent(delta="", is_finish=True, usage=usage, finish_reason="stop")
            
        except Exception as e:
            yield StreamEvent(delta="", error=e)

    async def generate_async(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> GenerationResponse:
        t0 = time.time()
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)
        
        try:
            # Native Async Call
            response = await model.generate_content_async(prompt)
            
            content = response.text
            
            p_tokens = 0
            o_tokens = 0
            if response.usage_metadata:
                p_tokens = response.usage_metadata.prompt_token_count
                o_tokens = response.usage_metadata.candidates_token_count
            
            usage = TokenUsage(
                input_tokens=p_tokens,
                output_tokens=o_tokens,
                total_tokens=p_tokens + o_tokens
            )
            
            finish_reason = "unknown"
            if response.candidates:
                finish_reason = str(response.candidates[0].finish_reason)
                
            t1 = time.time()
            return GenerationResponse(
                content=content,
                model=model_id,
                provider="google",
                usage=usage,
                finish_reason=finish_reason,
                timing={"total": t1 - t0}
            )
            
        except Exception as e:
            raise RuntimeError(f"Gemini Async API Error: {str(e)}")

    async def stream_async(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> Iterator[StreamEvent]:
        if not api_key:
            raise ValueError("API key required for Gemini")
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)
        
        try:
            # Native Async Stream
            response = await model.generate_content_async(prompt, stream=True)
            
            p_tokens = 0
            o_tokens = 0
            
            async for chunk in response:
                if chunk.text:
                    yield StreamEvent(delta=chunk.text)
                
                if chunk.usage_metadata:
                    p_tokens = chunk.usage_metadata.prompt_token_count
                    o_tokens = chunk.usage_metadata.candidates_token_count

            usage = TokenUsage(
                input_tokens=p_tokens,
                output_tokens=o_tokens,
                total_tokens=p_tokens + o_tokens
            )
             
            yield StreamEvent(delta="", is_finish=True, usage=usage, finish_reason="stop")
            
        except Exception as e:
            yield StreamEvent(delta="", error=e)

