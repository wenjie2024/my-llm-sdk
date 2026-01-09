import pytest
import os
import sqlite3
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

@pytest.fixture
def isolated_env(monkeypatch):
    """Create isolated config/ledger environment."""
    # Robust cleanup for Windows (handled manually instead of Context Manager)
    temp_dir = tempfile.mkdtemp()
    
    # Override common env paths
    monkeypatch.setenv("HOME", temp_dir)
    monkeypatch.setenv("USERPROFILE", temp_dir)
    
    original_cwd = os.getcwd()
    os.chdir(temp_dir)
    
    yield Path(temp_dir)
    
    os.chdir(original_cwd)
    # Cleanup attempt
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def mock_config_path(isolated_env):
    """Write dummy config.yaml in temp dir."""
    config_path = isolated_env / "config.yaml"
    with open(config_path, "w") as f:
        f.write("""
project_name: test-proj
allow_logging: true
budget_strict_mode: true
model_registry:
  test-model:
    name: test-model
    provider: echo
    model_id: test-model
    rpm: 1000
    tpm: 100000
    pricing:
      input_per_1m_tokens: 1.0
      output_per_1m_tokens: 1.0
api_keys:
  echo: "mock-key"
daily_spend_limit: 100.0
        """)
    return str(config_path)

@pytest.fixture
def fake_ledger_db(isolated_env):
    """Seed a ledger.db with sample data."""
    db_path = isolated_env / "ledger.db"
    
    # Initialize basic schema (could import init_db from ledger but keep simple)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS transactions (tx_id TEXT PRIMARY KEY, provider TEXT, model TEXT, cost REAL, timestamp REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS request_facts (trace_id TEXT PRIMARY KEY, ts_start INTEGER, ts_end INTEGER, provider TEXT, model TEXT, status TEXT, cost_usd REAL, input_tokens INTEGER, output_tokens INTEGER, total_ms INTEGER)")
    
    # Seed data
    # 3 days ago: $1.0
    conn.execute("INSERT INTO request_facts VALUES ('t1', (strftime('%s','now')-3*86400)*1000, 0, 'openai', 'gpt-4', 'success', 1.0, 100, 100, 500)")
    # Today: $0.5
    conn.execute("INSERT INTO request_facts VALUES ('t2', (strftime('%s','now')*1000), 0, 'google', 'gemini-3.0-pro', 'success', 0.5, 100, 100, 200)")
    
    conn.commit()
    conn.close()
    
    return str(db_path)
