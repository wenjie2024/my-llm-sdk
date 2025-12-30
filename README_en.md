**English** | [中文](README.md)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

# My LLM SDK

**One codebase, multiple models.**

A unified Python SDK for Gemini, Qwen, OpenAI, and more. Single API interface for all providers.

## 🎯 Core Features

| Feature | Description |
| :--- | :--- |
| **Unified API** | One `client.generate()` for all providers. No need to learn each SDK. |
| **Multi-model** | Gemini 2.5/3.0, Qwen Max/Plus/Flash, OpenAI Compatible |
| **Budget Control** | Pre-checks spend before each request. Auto-blocks if over limit. |
| **Auto-retry** | Handles 429 and timeouts automatically. |
| **Two-layer Config** | Project rules vs API keys separated. Prevents accidental commits. |
*   **🔌 Multi-Engine Support**:
    *   **Google Gemini**: Supports 1.5, 2.5, and 3.0 (Preview) series.
    *   **Alibaba Qwen**: Supports Max, Plus, and Flash (DashScope).
    *   **OpenAI/Compatible**: Generic interface support.
## 🛠️ Installation
```bash
# 1. Dev Install (Recommended)
# From the root of this project:
pip install -e .

# 2. Install in Another Project (Local Path)
# To use this SDK in a different project:
pip install -e /path/to/documents/my-llm-sdk

# 3. Production Install (Wheel)
# Build and install the .whl
pip install build
python -m build
pip install dist/my_llm_sdk-0.1.0-py3-none-any.whl
```
## ⚡ Quick Start
### 1. Initialize Config
Run the following command in your project root:
```bash
python -m my_llm_sdk.cli init
```
This generates:
*   `llm.project.yaml`: Project rules (Commit this).
*   `config.yaml`: Local secrets template (Add to **.gitignore**).

### 2. Configure Keys
Edit `config.yaml` and add your API keys:
```yaml
api_keys:
  google: "AIzaSy..."
```

### 3. Run Diagnostics (Doctor)
Check connection and keys:
```bash
python -m my_llm_sdk.cli doctor
```
### 3. Generate Text (CLI)
**Using Gemini 2.5:**
```bash
python -m my_llm_sdk.cli generate --prompt "Explain Quantum Mechanics" --model gemini-2.5-flash
```
**Using Qwen Max:**
```bash
python -m my_llm_sdk.cli generate --prompt "Write a poem" --model qwen-max
```
## 📦 Python API Usage
```python
from my_llm_sdk.client import LLMClient
# Initialize (loads config automatically)
client = LLMClient()
try:
    # Generate content
    response = client.generate(
        prompt="Design a Python class for a Bank Account", 
        model_alias="gemini-2.5-pro"
    )
    print(response)
    
except Exception as e:
    print(f"Generation failed: {e}")
# Check Diagnostics programmatically
import asyncio
asyncio.run(client.run_doctor())
```
## 📂 Project Structure
```
my-llm-sdk/
│   └── my_llm_sdk/     # Python Package
│       ├── budget/     # Budget Control & Pricing Logic
│       ├── config/     # Config Loader & Pydantic Models
│       ├── doctor/     # Connectivity & Health Checks
│       ├── providers/  # Adapters (Gemini, Qwen, Echo)
│       ├── utils/      # Network utils
│       ├── client.py   # Main Entry Point
│       └── cli.py      # Command Line Interface
├── tests/              # Pytest Suite
├── config.yaml         # Local Secrets (Ignored)
├── llm.project.yaml    # Project Rules (Committed)
└── ledger.db           # Local Transaction Log
```
## 📝 Configuration Reference
### llm.project.yaml
Defines the **Model Registry** (aliases mapping to real Model IDs) and **Allowed Regions**.
### config.yaml
Defines **API Keys** and **Endpoints**. By default, Qwen endpoints connect to CN, but flexible routing is supported.

## 📊 Benchmark Results (Dec 2025)

Based on `tests/benchmark.py` (Simple: General Knowledge, Complex: Multithreaded Crawler Coding):

| Model | Simple Time | Complex Time | Complex Length | Key Characteristic |
| :--- | :--- | :--- | :--- | :--- |
| **qwen-flash** | **3.70s** | 48.53s | **11414 c** | **Fastest & Most Verbose** |
| **qwen-plus** | 3.95s | 33.15s | 7968 c | Extremely fast for simple tasks |
| **gemini-3.0-flash** | 4.49s | **14.85s** | 5403 c | **Fastest for Complex Tasks** |
| **gemini-2.5-pro** | 16.47s | 53.80s | 9988 c | Deep reasoning, detailed output |
| **qwen-max** | 9.75s | 31.36s | 3822 c | Concise interactions |

> *Note: Latency depends on local network conditions.*

## 🤝 Contributing
1.  Fork the repo.
2.  Add a new Provider in `src/providers/`.
3.  Register it in `src/client.py`.
4.  Submit a PR!
