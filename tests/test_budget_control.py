import pytest
import threading
import tempfile
import os
from my_llm_sdk.budget.ledger import Ledger
from my_llm_sdk.budget.controller import BudgetController, QuotaExceededError
from my_llm_sdk.config.models import MergedConfig, Endpoint, RoutingPolicy

# Mock Config
def get_mock_config(limit: float):
    from my_llm_sdk.config.models import ResilienceConfig
    return MergedConfig(
        final_routing_policies=[],
        final_model_registry={},
        final_endpoints=[],
        allow_logging=True,
        daily_spend_limit=limit,
        api_keys={},
        resilience=ResilienceConfig(),
        budget_strict_mode=True,
        settings={}
    )

@pytest.fixture
def temp_ledger():
    # Use a temporary file for DB
    fd, path = tempfile.mkstemp()
    os.close(fd)
    ledger = Ledger(db_path=path)
    yield ledger
    try:
        os.remove(path)
    except PermissionError:
        pass
    except OSError:
        pass

def test_ledger_daily_spend(temp_ledger):
    # Empty
    assert temp_ledger.get_daily_spend() == 0.0

    # Add transaction
    temp_ledger.record_transaction("1", "openai", "gpt-4", 0.5)
    assert temp_ledger.get_daily_spend() == 0.5

    # Add another
    temp_ledger.record_transaction("2", "openai", "gpt-4", 0.3)
    assert temp_ledger.get_daily_spend() == 0.8

def test_budget_interceptor_block(temp_ledger):
    config = get_mock_config(limit=1.0)
    controller = BudgetController(config, temp_ledger)

    # First check OK
    controller.check_budget(0.5)
    # Record it
    controller.track("openai", "gpt-4", 0.5)

    # Second check OK
    controller.check_budget(0.4)
    # Record it
    controller.track("openai", "gpt-4", 0.4) # Total 0.9

    # Third check FAIL (0.9 + 0.2 > 1.0)
    with pytest.raises(QuotaExceededError):
        controller.check_budget(0.2)
        
    # Transaction shouldn't be recorded if check failed (logic in client)
    # But let's say we force a failed track record:
    controller.track("openai", "gpt-4", 0.0, status='failed')
    # Failed status should not add to total
    assert temp_ledger.get_daily_spend() == 0.9

def test_concurrency_safe(temp_ledger):
    """Test that multiple threads can write without crashing."""
    def worker():
        for i in range(10):
            temp_ledger.record_transaction(f"{threading.get_ident()}-{i}", "mock", "m", 0.1)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 5 threads * 10 records * 0.1 cost = 5.0 total
    import math
    assert math.isclose(temp_ledger.get_daily_spend(), 5.0)
