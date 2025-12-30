import pytest
from unittest.mock import MagicMock, call
import time
from my_llm_sdk.utils.resilience import RetryManager
from my_llm_sdk.config.models import ResilienceConfig

class TestResilience:
    def test_retry_success(self):
        """Test that it retries and eventually succeeds."""
        config = ResilienceConfig(max_retries=3, base_delay_s=0.1)
        manager = RetryManager(config)
        
        mock_func = MagicMock(side_effect=[RuntimeError("Fail 1"), RuntimeError("Fail 2"), "Success"])
        
        decorated = manager.retry_policy(mock_func)
        result = decorated()
        
        assert result == "Success"
        assert mock_func.call_count == 3
        
    def test_max_retries_exceeded(self):
        """Test that it fails after max retries."""
        config = ResilienceConfig(max_retries=2, base_delay_s=0.1)
        manager = RetryManager(config)
        
        mock_func = MagicMock(side_effect=RuntimeError("Fail Forever"))
        
        decorated = manager.retry_policy(mock_func)
        
        with pytest.raises(RuntimeError, match="Fail Forever"):
            decorated()
            
        # Call count: initial + 2 retries = 3 calls
        assert mock_func.call_count == 3

    def test_rate_limit_wait(self):
        """Test that it waits on 429."""
        config = ResilienceConfig(max_retries=1, base_delay_s=0.1, wait_on_rate_limit=True)
        manager = RetryManager(config)
        
        # Mock calculation to ensure measurable delay (or just trust logic)
        # We can inspect print or time, but unit test usually mocks time.sleep if needed.
        # Here we just check logic flow.
        
        mock_func = MagicMock(side_effect=[RuntimeError("429 Too Many Requests"), "Success"])
        
        decorated = manager.retry_policy(mock_func)
        result = decorated()
        
        assert result == "Success"
        assert mock_func.call_count == 2
        
    def test_rate_limit_no_wait(self):
        """Test that it fails fast on 429 if wait_on_rate_limit=False."""
        config = ResilienceConfig(max_retries=3, wait_on_rate_limit=False)
        manager = RetryManager(config)
        
        mock_func = MagicMock(side_effect=RuntimeError("429 Too Many Requests"))
        
        decorated = manager.retry_policy(mock_func)
        
        with pytest.raises(RuntimeError, match="429"):
            decorated()
            
        # Should call only once (no retry allowed for rate limit if wait disabled? 
        # Logic says: if is_rate_limit and not wait: raise.
        assert mock_func.call_count == 1
