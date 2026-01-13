import pytest
from unittest.mock import MagicMock, patch
from my_llm_sdk.client import LLMClient
from my_llm_sdk.config.models import MergedConfig, ResilienceConfig, ModelDefinition

def test_max_output_tokens_injection():
    """Test that max_output_tokens in global settings is injected into provider config."""
    
    # Mock Config
    mock_settings = {"max_output_tokens": 12345, "optimize_images": True}
    
    config = MergedConfig(
        final_routing_policies=[],
        final_model_registry={
            "test-model": ModelDefinition(name="tm", provider="mock", model_id="tm-1")
        },
        final_endpoints=[],
        allow_logging=True,
        daily_spend_limit=1.0,
        api_keys={"mock": "key"},
        resilience=ResilienceConfig(),
        budget_strict_mode=True,
        settings=mock_settings
    )
    
    # Mock Provider
    mock_provider = MagicMock()
    mock_provider.generate.return_value = MagicMock(usage=None)
    
    # Setup Client
    client = LLMClient()
    client.config = config
    client.providers = {"mock": mock_provider}
    client.rate_limiter = MagicMock()
    client.rate_limiter.check_limits.return_value = True
    client.budget = MagicMock()
    
    # 1. Test Injection (Caller provides no config)
    client.generate("prompt", "test-model")
    
    # Verify provider called with injected config
    call_kwargs = mock_provider.generate.call_args.kwargs
    assert "config" in call_kwargs
    assert call_kwargs["config"]["max_output_tokens"] == 12345
    
    # 2. Test Override (Caller provides config)
    client.generate("prompt", "test-model", config={"max_output_tokens": 99})
    
    call_kwargs_2 = mock_provider.generate.call_args.kwargs
    assert call_kwargs_2["config"]["max_output_tokens"] == 99
    
    # 3. Test Mixed (Caller provides other config, should still inject default)
    client.generate("prompt", "test-model", config={"temperature": 0.5})
    
    call_kwargs_3 = mock_provider.generate.call_args.kwargs
    assert call_kwargs_3["config"]["max_output_tokens"] == 12345
    assert call_kwargs_3["config"]["temperature"] == 0.5

if __name__ == "__main__":
    pytest.main([__file__])
