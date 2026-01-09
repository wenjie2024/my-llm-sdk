import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from my_llm_sdk.providers.gemini import GeminiProvider
from google.genai import types

@pytest.fixture
def provider():
    return GeminiProvider()

def test_config_building(provider):
    # Test valid kwargs mapping
    kwargs = {
        "max_output_tokens": 8192,
        "temperature": 0.7,
        "top_p": 0.9,
        "unknown_param": "ignored"
    }
    config = provider._build_config(kwargs)
    
    assert isinstance(config, types.GenerateContentConfig)
    assert config.max_output_tokens == 8192
    assert config.temperature == 0.7
    assert config.top_p == 0.9
    # top_k should be None
    assert config.top_k is None

def test_config_pass_through(provider):
    # Test passing raw config object
    raw_config = types.GenerateContentConfig(stop_sequences=["STOP"])
    config = provider._build_config({"config": raw_config})
    assert config == raw_config
    assert config.stop_sequences == ["STOP"]

@patch("google.genai.Client")
def test_generate_passes_config(MockClient, provider):
    mock_instance = MockClient.return_value.__enter__.return_value
    mock_instance.models.generate_content.return_value.text = "OK"
    mock_instance.models.generate_content.return_value.usage_metadata = None
    
    provider.generate(
        model_id="gemini-test", 
        prompt="Hi", 
        api_key="key", 
        max_output_tokens=100
    )
    
    # Check if config was passed
    args, kwargs = mock_instance.models.generate_content.call_args
    assert "config" in kwargs
    assert kwargs["config"].max_output_tokens == 100

@patch("google.genai.Client")
@pytest.mark.asyncio
async def test_generate_async_passes_config(MockClient, provider):
    # Mock async client
    mock_aio = AsyncMock()
    mock_client_instance = MagicMock()
    mock_client_instance.aio = mock_aio
    
    # Setup context manager return
    mock_aio.__aenter__.return_value = mock_aio
    
    # Setup generate_content return
    mock_response = MagicMock()
    mock_response.text = "OK"
    mock_response.usage_metadata = None
    mock_aio.models.generate_content.return_value = mock_response
    
    # Patch Client constructor to return our mock
    MockClient.return_value = mock_client_instance
    
    await provider.generate_async(
        model_id="gemini-test",
        prompt="Hi",
        api_key="key",
        temperature=0.5
    )
    
    # Check call arguments
    args, kwargs = mock_aio.models.generate_content.call_args
    assert "config" in kwargs
    assert kwargs["config"].temperature == 0.5
