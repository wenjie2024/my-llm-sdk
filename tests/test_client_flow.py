import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from src.client import LLMClient
from src.config.models import ProjectConfig, UserConfig, MergedConfig, ModelDefinition

# Mock Config Loader to avoid file dependencies in unit test
@pytest.fixture
def mock_loader():
    with patch('src.client.load_config') as mock:
        # valid config
        p_def = ModelDefinition(name="test-model", provider="echo", model_id="echo-v1")
        config = MergedConfig(
            final_routing_policies=[],
            final_model_registry={"test-model": p_def},
            final_endpoints=[],
            allow_logging=True,
            daily_spend_limit=1.0,
            api_keys={"echo": "secret"}
        )
        mock.return_value = config
        yield mock

def test_client_generate_success(mock_loader, tmp_path):
    # Use temp DB for ledger
    db_path = tmp_path / "ledger.db"
    
    # We need to ensure Ledger uses this path. 
    # But Client init creates BudgetController -> Ledger with default path if not injected.
    # LLMClient code isn't easily injectable without modification or patching Ledger init.
    # Let's patch Ledger initialization.
    
    with patch('src.budget.ledger.Ledger.__init__', return_value=None) as mock_ledger_init:
        # We also need to mock Ledger methods since __init__ is None
        with patch('src.budget.ledger.Ledger.get_daily_spend', return_value=0.0):
            with patch('src.budget.ledger.Ledger.record_transaction') as mock_record:
                
                client = LLMClient()
                response = client.generate("Hello", "test-model")
                
                assert "Hello" in response
                assert "echo-v1" in response
                
                # Verify budget track called
                mock_record.assert_called_once()
                # Check args: kwargs usually in call_args
                call_kwargs = mock_record.call_args[1]
                assert call_kwargs['provider'] == "echo"
                assert call_kwargs['cost'] > 0

def test_client_unknown_model(mock_loader):
    client = LLMClient()
    with pytest.raises(ValueError, match="not found"):
        client.generate("Hello", "unknown-alias")
