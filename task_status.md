# Codebase Review Task List

- [x] Explore project structure
- [x] Review configuration and dependency files
- [x] Review core source code
- [x] Review tests
- [x] Generate review report
- [x] Explain installation and budget control mechanism
- [x] Fix dependencies and update installation docs
- [x] Implement Rate Limiting (RPM, TPM, RPD)
- [x] Verify all models and budget functionality
- [x] Benchmark models (Simple vs Complex)
- [x] Prioritize Roadmap items

# V0.2.0 Async Support & Resilience
- [x] **Async Ledger**
    - [x] Define `LedgerEvent` data structure
    - [x] Implement `awrite_event` (Producer) and Worker (Consumer)
    - [x] Implement `aspend_today` query
    - [x] Verify Async Ledger with a test script

# V0.2.0 Structured Output (Phase 1)
- [x] **Define Schemas** (`GenerationResponse`, `TokenUsage`)
- [x] **Refactor Providers** (`Base`, `Gemini`, `Qwen`) to return `GenerationResponse`
- [x] **Update Client** (`generate` supports `return_json` flag)
- [x] **Update Ledger** (Record from structured response)
- [x] **Verify Structured Output**

# V0.2.0 Resilience (Phase 2)
- [x] **Config**: Add `resilience` section to `config.yaml` & models
- [x] **Logic**: Implement `src/utils/resilience.py` (Decorator & Wait Logic)
- [x] **Integration**: Apply retry policy to `LLMClient`
- [x] **Verification**: Verify Retry & Rate Limit Wait
- [x] **Verification**: Verify Retry & Rate Limit Wait

# V0.2.0 Streaming (Phase 3)
- [x] **Schema**: Add `StreamEvent` to `schemas.py`
- [x] **Base**: Add `stream()` method to `BaseProvider`
- [x] **Providers**: Implement `stream()` in `Gemini` & `Qwen`
- [x] **Client**: Implement `stream()` in `LLMClient` (with Usage Aggregation)
- [x] **Verification**: E2E Streaming Test

# V0.3.0 Async API (Phase 4)
- [x] **Budget**: Add `acheck_budget` & `atrack` to `BudgetController`
- [x] **Base**: Add `generate_async` & `stream_async` to `BaseProvider`
- [x] **Providers**: Implement Async in `Gemini` & `Qwen`
- [x] **Client**: Implement `generate_async` & `stream_async` in `LLMClient`
- [x] **Verification**: Concurrent Async Test Script

# V0.3.5 Refactor: Best Practice Src Layout
- [x] **Restructure**: Move code from `src/*` to `src/my_llm_sdk/*`
- [x] **Imports**: Mass update `from src` to `from my_llm_sdk`
- [x] **Config**: Update `pyproject.toml` package discovery
- [x] **Scripts**: Update `verify_*.py` and `tests/` imports
- [x] **Docs**: Update README usage examples
- [x] **Verify**: Full regression test (`pip install -e .` + `verify_all.py`)

# V0.3.6 Repo Audit Fixes
- [x] **pyproject.toml**: Fix `[dependencies]` to `[project.dependencies]`
- [x] **__init__.py**: Add `__version__ = "0.3.5"`
- [x] **client.py**: Align config path (CWD first), add API key validation
- [x] **Verified**: `pip install`, `__version__`, `verify_all.py` all passed

# 🚀 V0.4.0 Multimodal & Advanced (Pending)
- [ ] **Unified Multimodal Input**: Support text/image/audio inputs in `generate()`
- [ ] **Ledger Upgrade**: Support non-token billing units (images, seconds)
- [ ] **Vision**: Implement Gemini/Qwen vision capabilities
- [ ] **Audio**: Implement Gemini audio capabilities

# 📊 V0.5.0 Operations & Reporting (Pending)
- [ ] **CLI Reports**: `llm budget report --days 7`
- [ ] **Cost Analysis**: Breakdown by model/provider
- [ ] **Cost-Aware Routing**: Route based on historical cost/quality

# 📦 Ecosystem (Pending)
- [ ] **PyPI Release**: Publish package to PyPI
- [ ] **Tracing**: OpenTelemetry integration
- [ ] **More Providers**: Anthropic, DeepSeek support
