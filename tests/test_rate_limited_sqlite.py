import pytest
import time
import sqlite3
from my_llm_sdk.budget.ledger import Ledger
from my_llm_sdk.budget.rate_limiter import RateLimiter, RateLimitExceededError

@pytest.fixture
def mock_ledger(tmp_path):
    # Use a fresh DB for each test
    db_path = tmp_path / "test_ledger.db"
    return Ledger(str(db_path))

def test_rpm_limit(mock_ledger):
    limiter = RateLimiter(mock_ledger)
    model = "test-model-rpm"
    rpm = 2
    
    # 1. First call - OK (DB has 0)
    limiter.check_limits(model, rpm=rpm)
    mock_ledger.record_transaction("id1", "test", model, 0.0)
    
    # 2. Second call - OK (DB has 1)
    limiter.check_limits(model, rpm=rpm)
    mock_ledger.record_transaction("id2", "test", model, 0.0)
    
    # 3. Third call - Should Fail (2 records in last 60s)
    # Note: check_limits checks existing records first. 
    # If we have 2 records, count is 2. If RPM is 2, creating a 3rd is checking if current usage (2) >= limit (2)?
    # Implementation says: if current_rpm >= rpm. 
    # Yes, if we already have 2, next one is rejected.
    with pytest.raises(RateLimitExceededError) as exc:
        limiter.check_limits(model, rpm=rpm)
    assert "RPM" in str(exc.value)

def test_rpd_limit(mock_ledger):
    limiter = RateLimiter(mock_ledger)
    model = "test-model-rpd"
    rpd = 3
    
    # Insert 3 transactions
    for i in range(3):
        mock_ledger.record_transaction(f"id{i}", "test", model, 0.0)
        
    # 4th check should fail
    with pytest.raises(RateLimitExceededError) as exc:
        limiter.check_limits(model, rpd=rpd)
    assert "RPD" in str(exc.value)

def test_sliding_window_expiration(mock_ledger):
    limiter = RateLimiter(mock_ledger)
    model = "test-window"
    rpm = 1
    
    # 1. Insert old transaction (> 60s ago)
    with mock_ledger._get_conn() as conn:
        conn.execute("""
            INSERT INTO transactions (id, timestamp, provider, model, cost, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("old_id", time.time() - 65, "test", model, 0.0, 'success'))
        
    # 2. Check limits - should pass because old tx is outside window
    # Validates that we are using a sliding window, not total count
    try:
        limiter.check_limits(model, rpm=rpm)
    except RateLimitExceededError:
        pytest.fail("Rate limit raised but transaction should be expired")

def test_tpm_limit(mock_ledger):
    limiter = RateLimiter(mock_ledger)
    model = "test-tpm"
    tpm = 100
    
    # 1. Insert transaction with 80 tokens
    mock_ledger.record_transaction("id1", "test", model, 0.0, input_tokens=40, output_tokens=40)
    
    # 2. Check limit for request with 10 tokens 
    # Total = 80 + 10 = 90 < 100. OK.
    limiter.check_limits(model, tpm=tpm, estimated_tokens=10)
    
    # 3. Check limit for request with 30 tokens
    # Total = 80 + 30 = 110 > 100. Fail.
    with pytest.raises(RateLimitExceededError) as exc:
        limiter.check_limits(model, tpm=tpm, estimated_tokens=30)
    assert "TPM" in str(exc.value)
