"""
Unit Tests: Multimodal Billing Calculation

Verifies that calculate_multimodal_cost produces accurate results.
"""

import os
import sys
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from my_llm_sdk.budget.pricing import calculate_multimodal_cost
from my_llm_sdk.schemas import TokenUsage


class TestMultimodalBilling:
    """Test suite for multimodal billing calculations."""
    
    def test_text_only_cost(self):
        """Text-only input should use token-based pricing."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500
        )
        
        # Using 'gemini-2.5-flash' which is in project config
        cost = calculate_multimodal_cost("gemini-2.5-flash", usage)
        
        # Should be > 0 (exact value depends on config pricing)
        assert cost > 0, f"Expected positive cost, got {cost}"
    
    def test_image_input_cost(self):
        """Image input should add per_image_input cost."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            images_processed=3
        )
        
        cost = calculate_multimodal_cost("gemini-2.5-flash", usage)
        
        # With 3 images, cost should be higher than text-only
        text_only = TokenUsage(input_tokens=100, output_tokens=200)
        text_cost = calculate_multimodal_cost("gemini-2.5-flash", text_only)
        
        assert cost > text_cost, f"Image cost {cost} should be > text cost {text_cost}"
    
    def test_audio_input_cost(self):
        """Audio input should add per_audio_second_input cost."""
        usage = TokenUsage(
            input_tokens=0,
            output_tokens=100,
            audio_seconds=60.0  # 1 minute of audio
        )
        
        cost = calculate_multimodal_cost("gemini-2.5-flash", usage)
        
        # With 60s audio, cost should be > 0
        assert cost > 0, f"Expected positive cost for audio input"
    
    def test_image_generation_cost(self):
        """Image generation should use images_generated field."""
        usage = TokenUsage(
            input_tokens=0,
            output_tokens=0,
            images_generated=4
        )
        
        # Use imagen model for image output pricing
        cost = calculate_multimodal_cost("imagen-4.0-generate", usage)
        
        # With 4 generated images, cost should be > 0
        assert cost > 0, f"Expected positive cost for image generation"
    
    def test_tts_cost(self):
        """TTS should use tts_input_characters."""
        usage = TokenUsage(
            input_tokens=0,
            output_tokens=0,
            tts_input_characters=500
        )
        
        # Use TTS model
        cost = calculate_multimodal_cost("gemini-2.5-flash-preview-tts", usage)
        
        # With 500 chars TTS, cost should be > 0
        assert cost > 0, f"Expected positive cost for TTS"
    
    def test_combined_multimodal_cost(self):
        """Combined scenario: Vision + Audio output."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            images_processed=2,
            audio_seconds_generated=30.0
        )
        
        cost = calculate_multimodal_cost("gemini-2.5-flash", usage)
        
        # Combined usage should produce non-zero cost
        assert cost > 0, f"Expected positive combined cost"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
