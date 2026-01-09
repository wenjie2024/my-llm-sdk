import pytest
import sys
import shutil
import os
from pathlib import Path
from io import StringIO
from my_llm_sdk.cli import main
from unittest.mock import patch

@pytest.fixture
def setup_cli_env(isolated_env, mock_config_path, fake_ledger_db):
    """Setup CLI environment: configs and ledger in correct place."""
    # 1. Configs are already in root thanks to mock_config_path (mock_config_path is in isolated_env root)
    # LLMClient looks for 'llm.project.yaml' and 'config.yaml' in CWD by default or args.
    # mock_config_path writes to 'config.yaml'.
    # We also need 'llm.project.yaml' for the project config.
    
    with open("llm.project.yaml", "w") as f:
        f.write("""
project_name: test
model_registry:
  gemini-3.0-pro:
    name: gemini-3.0-pro
    provider: google
    model_id: gemini-3-pro-preview
    pricing:
      input_per_1m_tokens: 1.0
      output_per_1m_tokens: 1.0
        """)
        
    # 2. Ledger - LLMClient uses ~/.llm-sdk/ledger.db if not overridden.
    # isolated_env sets HOME to temp_dir.
    dot_dir = isolated_env / ".llm-sdk"
    dot_dir.mkdir(exist_ok=True)
    
    # Copy fake ledger
    target_db = dot_dir / "ledger.db"
    shutil.copy(fake_ledger_db, target_db)
    
    return isolated_env

def test_budget_status_cli(setup_cli_env, capsys):
    """Test 'llm budget status' command."""
    with patch.object(sys, 'argv', ["llm", "budget", "status"]):
        main()
        
    captured = capsys.readouterr()
    assert "Today's Budget Status" in captured.out
    assert "Cost:" in captured.out
    # Checking for data seeded in fake_ledger_db fixture (0.5 USD for today)
    assert "$0.5" in captured.out or "0.5000" in captured.out

def test_budget_report_cli(setup_cli_env, capsys):
    """Test 'llm budget report' command."""
    with patch.object(sys, 'argv', ["llm", "budget", "report", "--days", "7"]):
        main()
        
    captured = capsys.readouterr()
    assert "Cost Trend" in captured.out
    # T2 timestamp in fixture is today, T1 is 3 days ago
    assert "Total Cost: $1.5000" in captured.out

def test_budget_top_cli(setup_cli_env, capsys):
    """Test 'llm budget top' command."""
    with patch.object(sys, 'argv', ["llm", "budget", "top", "--by", "model"]):
        main()
        
    captured = capsys.readouterr()
    assert "Top Consumers by model" in captured.out
    assert "gemini-3.0-pro" in captured.out
    assert "gpt-4" in captured.out
