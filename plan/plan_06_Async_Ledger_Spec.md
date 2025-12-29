# 📋 Async Ledger Design Specification (V0.2.0 Target)

**Status**: Draft
**Owner**: System
**Date**: 2025-12-29

## 1. 设计目标 (Design Goals)

*   **不阻塞 Event Loop (Non-blocking)**: 任何 DB 写入不允许在 `async def generate_async()` 的主路径里同步阻塞。
*   **吞吐优先 (High Throughput)**: 高并发下 ledger 写入要“可批量、可延迟、可降级”，但不丢关键账。
*   **一致性可控 (Controllable Consistency)**: 支持 `strict_budget`（强一致/同步点）与 `best_effort`（最终一致）两种模式。
*   **多模态预留 (Multimodal Ready)**: Usage/Cost 结构通用化，为将来 image/audio 计费预留空间。

---

## 2. 核心抽象 (Core Abstraction)

### 2.1 数据结构: LedgerEvent (Event Sourcing)

不再直接覆盖“最终行”，而是记录不可变的账本事件。

*   `LedgerEvent`:
    *   `event_type`: `precheck_hold` | `commit` | `cancel` | `adjust`
    *   `trace_id`: UUID
    *   `provider`: (e.g., Google, DashScope)
    *   `model`: (e.g., gemini-3.0-flash)
    *   `usage`: `{ "tokens_in": 10, "tokens_out": 20, "images": 0, ... }` (JSON)
    *   `cost_est_usd`: 预估费用
    *   `cost_actual_usd`: 实际费用
    *   `status`: `ok` | `error` | `cancelled`
    *   `timing`: `{ "ttft_ms": 100, "total_ms": 500 }`
    *   `timestamp`: float

> **设计意图**: 实现“宽估算，准结算”。Precheck 阶段写入 Hold 事件，Final 阶段写入 Commit/Adjust 事件。

### 2.2 接口定义 (Dual Stack)

```python
class Ledger:
    # --- Budget Query ---
    def spend_today(self, *, scope="all", profile_id=None) -> float: ...
    async def aspend_today(self, *, scope="all", profile_id=None) -> float: ...

    # --- Write Events (Non-blocking Preferred) ---
    def write_event(self, ev: LedgerEvent) -> None: ...
    # 在 best_effort 模式下立即返回；在 strict_budget 模式下可能根据策略等待 flush
    async def awrite_event(self, ev: LedgerEvent, sync: bool = False) -> None: ...

    # --- Lifecycle ---
    def close(self) -> None: ...
    async def aclose(self) -> None: ...
```

---

## 3. 实现架构: Async Queue + Single Writer Worker (Option #2)

**核心选型**: 推荐方案 #2。

### 3.1 架构描述
1.  **Producer (`generate_async`)**: 只负责将 `LedgerEvent` 放入内存队列 (`asyncio.Queue`)，不进行任何 DB IO。
2.  **Consumer (Worker Task)**: 后台启动一个 `asyncio.Task`，负责循环从队列取数据。
3.  **Batch Flush**: Worker 只有在满足以下条件之一时才进行 DB 写入：
    *   队列积压达到了 N 条 (e.g., 100)。
    *   距离上次写入超过 T 时间 (e.g., 200ms)。
4.  **DB Connection**: Worker 内部持有唯一的 DB 连接（或通过 `run_in_executor` 调用同步连接），确保写入串行化，避免锁竞争。

**优点**:
*   吞吐极高，主线程 0 IO。
*   避免了 SQLite 多线程/多协程锁竞争 (`database is locked`)。
*   不强依赖 `aiosqlite`。

---

## 4. 预算一致性模式 (Budget Consistency Modes)

### 4.1 Best Effort (默认)
*   **机制**: `precheck` 只读取内存缓存或最近一次快照。`write_event` 纯异步入队。
*   **适用场景**: 个人开发、批处理、对偶尔超额几分钱不敏感的场景。
*   **特点**: 极速，永不阻塞业务。

### 4.2 Strict Budget (防破产模式)
*   **机制**: “宁可错杀，不可漏放”。
*   **流程**:
    1.  **Budget Snapshot**: 从 DB 读（或强一致缓存）当日消费。
    2.  **Reserve (Precheck Hold)**: 
        *   构建 `precheck_hold` 事件。
        *   调用 `awrite_event(ev, sync=True)`。
        *   **同步点**: 该调用会创建一个 `Future`，Worker 在将此事件成功落盘后，通过 `set_result` 唤醒主流程。
    3.  **Execute**: 只有落盘成功，才发起 LLM 请求。
    4.  **Final Commit**: 请求结束后异步写入 `commit` 事件。

---

## 5. 数据库策略 (Persistence)

*   **Mode**: WAL (Write-Ahead Logging) 必须开启。
*   **Timeout**: `busy_timeout` 设置为 5000ms+。
*   **Transaction**: Batch Write 必须包裹在 Transaction (`BEGIN` ... `COMMIT`) 中。
*   **Schema**:
    *   拆分 `usage` 和 `cost` 为 JSON 字段，以适应多模态。
    *   索引: `timestamp`, `trace_id`。

## 6. Rate Limiting 增强 (Resilience)

配合 Async Ledger，Rate Limiter 也需支持异步等待：

*   **参数**:
    *   `wait_on_rate_limit: bool`
    *   `max_wait_timeout_s: int` (e.g., 60)
    *   `retry_budget_s: int` (e.g., 90)
*   **行为**:
    *   若开启 Wait，遇到 Limit 时不抛错，而是 `await asyncio.sleep(retry_after)`。
    *   等待/重试行为也作为事件写入 Ledger (便于 Debug)。

## 7. 多模态扩展 (Multimodal)

为 V0.3.0+ 预留的 Schema 变更 (Minimal Change)：

*   **Usage Field**: JSON 类型。
    *   `{"tokens_in": 100, "audio_seconds": 15.5}`
*   **Model Registry**:
    *   Pricing Unit: 支持 `token` | `image` | `second`。

---
