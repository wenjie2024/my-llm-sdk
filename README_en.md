**English** | [中文](README.md)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)

# My LLM SDK

**One codebase, multiple models.**

> Use the same `client.generate()` / `stream()` for Gemini, Qwen, and OpenAI-compatible APIs.  
> Built-in budget control, 429 auto-retry, and Ledger for cost tracking.  
> For: Team-shared model policies + local API key isolation + batch jobs / high concurrency / cost tracking.

---

## 🚀 Quickstart

### Using in Your Project

```bash
# 1. Install (from local path, future: pip install my-llm-sdk)
pip install -e <path-to-sdk>/my-llm-sdk
# e.g. pip install -e ~/projects/my-llm-sdk      (macOS/Linux)
#      pip install -e C:\Users\you\my-llm-sdk    (Windows)

# 2. Initialize config in your project directory
python -m my_llm_sdk.cli init

# 3. Edit config.yaml with your API keys

# 4. Call
python -m my_llm_sdk.cli generate --model gemini-2.5-flash --prompt "Hello"
```

### Contributing to SDK Development

```bash
git clone https://github.com/your-org/my-llm-sdk.git
cd my-llm-sdk
pip install -e .
python -m my_llm_sdk.cli doctor
```

---

## 💡 Why Use It

| Need | My LLM SDK Solution |
| :--- | :--- |
| **One integration, multiple providers** | Switch models by changing `model_alias`, no code changes |
| **Cost control** | Pre-request budget check + unified Ledger |
| **429 / timeout handling** | Auto exponential backoff, configurable max wait |
| **Team collaboration** | `llm.project.yaml` (Git) + `config.yaml` (local) separation |
| **Batch / concurrency** | Async + Streaming + structured returns (cost/token unified) |

---

## 🧪 Typical Use Cases

### 1. Batch Jobs: Budget Cap + Auto Retry
For nightly jobs / data labeling / eval scripts: auto-reject over budget, auto-retry on 429.

### 2. Online Services: Streaming + Usage Tracking
`stream=True` for streaming output, with precise token/cost logging to Ledger.

### 3. Team Collaboration: Shared Policies, Keys Never Committed
`llm.project.yaml` in Git; `config.yaml` local only (supports personal overrides).

---

## 🎯 Core Features

| Feature | Description |
| :--- | :--- |
| **Unified API** | One `client.generate()` for all providers |
| **Multi-model** | Gemini 2.5/3.0, Qwen Max/Plus/Flash, OpenAI Compatible |
| **Async + Streaming** | `generate_async` / `stream_async` for high concurrency |
| **Structured Response** | `full_response=True` for usage/cost/token |
| **Budget Control** | Pre-check spend, auto-reject if over limit |
| **Auto Retry** | 429/timeout backoff, configurable `max_retries` / `max_delay_s` |
| **Two-layer Config** | Project rules vs API keys separated |

---

## ✅ Reliability

- **Auto Retry**: 429/timeout exponential backoff (configurable max retries and wait time)
- **Ledger Logging**: Every request logs cost / token / provider / model / latency
- **Structured Response**: `full_response=True` for unified usage/cost
- **Test Coverage**: `pytest` unit tests + E2E verification scripts

---

## 📦 Python API

```python
from my_llm_sdk.client import LLMClient

client = LLMClient()

# Basic call
response = client.generate("Hello", model_alias="gemini-2.5-flash")
print(response)

# Structured object (with cost/token)
res = client.generate("Hello", full_response=True)
print(f"Cost: ${res.cost}, Tokens: {res.usage.total_tokens}")

# Streaming
for event in client.stream("Count to 5", model_alias="qwen-max"):
    print(event.delta, end="", flush=True)
```

---

## 🔧 Configuration Reference

### config.yaml (Local, do NOT commit to Git)
```yaml
api_keys:
  google: "AIzaSy..."
  dashscope: "sk-..."
daily_spend_limit: 5.0
```

### llm.project.yaml (Can commit to Git)
```yaml
model_registry:
  gemini-2.5-flash:
    provider: google
    model_id: gemini-2.5-flash
    rpm: 1000
```

### Retry Configuration
```yaml
resilience:
  max_retries: 3
  wait_on_rate_limit: true
  max_delay_s: 60
```

### Local Model Overrides (e.g., Ollama)
```yaml
personal_model_overrides:
  llama-3-local:
    provider: openai
    model_id: llama3
    api_base: "http://localhost:11434/v1"
```

---

## 📊 Benchmark (Dec 2025)

| Model | Simple Task | Complex Task | Response Length | Notes |
| :--- | :--- | :--- | :--- | :--- |
| qwen-flash | **3.70s** | 48.53s | 11414c | Fastest response |
| gemini-3.0-flash | 4.49s | **14.85s** | 5403c | Fastest for complex |
| qwen-plus | 3.95s | 33.15s | 7968c | Fast for simple |
| gemini-2.5-pro | 16.47s | 53.80s | 9988c | Deep reasoning |
| qwen-max | 9.75s | 31.36s | 3822c | Concise |

> **Reproduce**: `python benchmark.py` (dev mode)  
> **Environment**: macOS + home network, varies by region  
> **Task definitions**: Simple = general Q&A; Complex = multi-threaded crawler code

---

## 🗺️ Roadmap

- [ ] Publish to PyPI (`pip install my-llm-sdk`)
- [ ] OpenTelemetry tracing
- [ ] More OpenAI-compatible providers
- [ ] Multimodal support (Vision / Audio)
- [ ] Per-provider retry strategies

---

## 🤝 Contributing

1. Fork this repo
2. Add a new Provider in `src/my_llm_sdk/providers/` (extend `BaseProvider`)
3. Register it in `src/my_llm_sdk/client.py` under `self.providers`
4. Submit a PR

---

## 📄 License

[Apache 2.0](LICENSE)
