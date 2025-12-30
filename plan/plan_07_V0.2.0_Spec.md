# 📋 V0.2.0 Implementation Plan: Resilience & Streaming

**Version**: V0.2.0
**Status**: Draft
**Objectives**: Transform SDK from "Functional" to "Production Ready" (Robustness + DX).

## 1. Resilience (容错与重试) 🛡️

### 1.1 Requirements
*   **Auto-Retry**: Retry on transient errors (5xx, Timeout).
*   **Rate Limit Handling**: Smart wait on 429 (if `wait_on_rate_limit=True`).
*   **Circuit Breaker**: Stop hitting dead endpoints.

### 1.2 Configuration (`config.yaml`)
```yaml
resilience:
  max_retries: 3
  base_delay_s: 1.0
  max_delay_s: 60.0
  wait_on_rate_limit: true
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout_s: 300
```

### 1.3 Implementation Strategy
*   **Decorator Approach**: `@retry_policy` on `Provider.generate`.
*   **Exceptions**:
    *   `RetryableError` (502, 503, Timeout) -> Retry.
    *   `RateLimitError` (429) -> Wait (if allowed) then Retry.
    *   `FatalError` (400, 401) -> Fail fast.
*   **Circuit Breaker**: In `Router` or `Provider`, track failure counts in memory (or shared dict).

---

## 2. Structured Output & Unified Response 🏗️

### 2.1 The Problem
Currently `generate() -> str`. We lose usage, cost, and finish reason.

### 2.2 New Schema: `GenerationResponse`
```python
@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

@dataclass
class GenerationResponse:
    content: str
    model: str
    provider: str
    usage: TokenUsage
    cost: float
    finish_reason: str  # 'stop', 'length', 'filter'
    trace_id: str
    timing: Dict[str, float]  # {'ttft': 0.1, 'total': 2.5}

    def __str__(self):
        return self.content  # Allow easy printing
```

### 2.3 Interface Update
*   **Approach**: Backward Compatibility Wrapper.
*   `generate(..., return_json: bool = False)` (Legacy)
*   **New**: `generate_response(...) -> GenerationResponse` (Recommended)
*   *Correction*: To keep API clean, we might just update `generate` signature or use a flag.
*   **Decision**: `client.generate(..., full_response=False)`. Default returns str. If True, returns object.

---

## 3. Streaming (流式输出) 🌊

### 3.1 Interface
```python
def stream(self, prompt: str, ...) -> Iterator[StreamEvent]:
    ...
```

### 3.2 `StreamEvent` Schema
```python
@dataclass
class StreamEvent:
    delta: str
    is_finish: bool
    usage: Optional[TokenUsage] = None  # Last event carries usage
    error: Optional[Exception] = None
```

### 3.3 Implementation Details
*   **Gemini**: `model.generate_content(stream=True)` -> yield chunks.
*   **Qwen**: `dashscope.Generation.call(stream=True)` -> yield delta.
*   **Ledger Integration**:
    *   Accumulate token usage/cost in generic wrapper.
    *   On `is_finish`, create `LedgerEvent(type='commit')` synchronously (or async queue).

---

## 4. Execution Steps (Task Breakdown)

### Phase 1: Structured Foundation
1.  [ ] Define `GenerationResponse` and `TokenUsage` dataclasses.
2.  [ ] Refactor `BaseProvider.generate` to return `GenerationResponse`.
3.  [ ] Update `GeminiProvider` and `QwenProvider` to populate usage/meta.
4.  [ ] Update `LLMClient.generate` to handle the object (and support `full_response=False`).
5.  [ ] Update `Ledger` to record from `GenerationResponse`.

### Phase 2: Resilience
6.  [ ] Implement `RetryManager` (Decorator/Wrapper).
7.  [ ] Apply retry to `LLMClient` or `Providers`.
8.  [ ] Implement `wait_on_rate_limit` logic.

### Phase 3: Streaming
9.  [ ] Define `stream()` interface in BaseProvider.
10. [ ] Implement `stream()` in Gemini/Qwen.
11. [ ] Implement `LLMClient.stream()` with budget pre-check (approximate) and post-tracking.

### Phase 4: Verification
12. [ ] Unit Tests for new Event/Response classes.
13. [ ] Simulation Tests for Retry/Backoff.
14. [ ] E2E Test (Stream print to console).

---
