import pytest
respx = pytest.importorskip("respx")
httpx = pytest.importorskip("httpx")
from my_llm_sdk.doctor.checker import Doctor
from my_llm_sdk.config.models import MergedConfig, Endpoint
from my_llm_sdk.budget.ledger import Ledger

# Mock Config
def get_mock_config():
    endpoints = [
        Endpoint(name="google", url="https://google.com", region="us"),
        Endpoint(name="bad-host", url="https://bad.host", region="us"),
    ]
    from my_llm_sdk.config.models import ResilienceConfig
    return MergedConfig(
        final_routing_policies=[],
        final_model_registry={},
        final_endpoints=endpoints,
        allow_logging=True,
        daily_spend_limit=1.0,
        api_keys={},
        resilience=ResilienceConfig(),
        budget_strict_mode=True
    )

@pytest.fixture
def doctor_instance(tmp_path):
    # Temp ledger
    db_path = tmp_path / "ledger.db"
    ledger = Ledger(str(db_path))
    config = get_mock_config()
    return Doctor(config, ledger)

@pytest.mark.asyncio
async def test_connectivity_check(doctor_instance):
    # Use a single respx mock for all hosts
    with respx.mock:
        # 1. Success case
        respx.head("https://google.com/").mock(return_value=httpx.Response(200))
        
        # 2. Failure case
        respx.head("https://bad.host/").mock(side_effect=httpx.ConnectError("Connection refused"))

        report = await doctor_instance.run_diagnostics()
        
        # Check results
        categories = [r.category for r in report.results]
        
        assert "Config" in categories
        assert "Budget" in categories
        assert "Network" in categories
        
        # Find google result
        google_res = next(r for r in report.results if r.name == "google")
        assert google_res.status == "PASS"
        
        # Find bad host result
        bad_res = next(r for r in report.results if r.name == "bad-host")
        assert bad_res.status == "FAIL"
