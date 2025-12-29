# LLM SDK – Vibe Edition 完整 Roadmap

## V0.1.0 ✅（已完成）

**定位**：核心管控闭环（能用、能控、能诊断）
**已完成**

* 双层配置（Project/User）+ 合并策略
* SQLite Ledger + Pre-check 预算拦截
* 多模型：Gemini(Flash/Pro), Qwen(Max/Plus/Flash)
* Doctor + 动态路由（CN/SG）
* RPM/TPM/RPD 多维限流（SQLite 滑动窗口）
* 基础 Router（策略/合规/endpoint 可达性）

**产出**：可在真实网络环境稳定调用，具备“不会破产”的安全气囊。

---

## V0.2.0 ✅（已完成：稳定性 + 结构化响应 + Streaming）

**定位**：从“能用”到“像产品”

> 核心目标：**不再因网络/限流轻易失败**，长输出不再“卡死”，每次调用都有统一可审计的元数据。

### 0.2.0-A：Resilience（包含 Circuit Breaker）✅

**范围**

* Auto-Retry（timeout / 5xx / 可选 429）
* Exponential Backoff + jitter
* `wait_on_rate_limit=True` + `max_wait_timeout_s`（避免无限等待）

**设计点**

* 错误分类：可重试 vs 不可重试（401/403/4xx 参数错误 fail-fast）
* `retry_budget_s`（总重试耗时上限）
* 重试信息写入 debug + ledger

**DoD**

* 断网短抖动可恢复；可重试错误不会直接失败
* `wait_on_rate_limit=True` 时等待超过 `max_wait_timeout_s` 必须抛出异常（不允许无穷等待）
* 重试次数/总等待时间/最后错误原因可追踪

---

### 0.2.0-B：Structured Output（统一响应结构）✅

**范围**

* `GenerationResponse`（非流式）结构化输出：

  * `content`
  * `usage`（可空）
  * `finish_reason`
  * `provider_meta`（provider/profile/endpoint/model/request_id）
  * `timing`（ttft_ms/total_ms）
  * `cost_est_usd/cost_actual_usd`（可空）

**DoD**

* Gemini/Qwen 都能返回统一结构（字段可空但结构一致）
* Ledger 能记录并关联 `trace_id` + response 元数据

---

### 0.2.0-C：Streaming（Generator/Iterator）✅

**范围**

* `generate(stream=True) -> Iterator[StreamEvent]`
* `StreamEvent`：`delta` / `final` / `error`（最小集合）
* 支持用户 `break` 早停（记录 cancelled）

**设计点**

* provider 适配：OpenAI-compat 的 chunk、Gemini 的 streamGenerateContent 映射到统一事件
* Streaming 结束时产出 `final(GenerationResponse)`，用于 ledger 结算

**DoD**

* 长输出 TTFT 明显降低（能快速看到 token 增量）
* 早停可关闭连接，不挂死；写入 `status=cancelled` 的 ledger

---

### 0.2.0-D：Circuit Breaker（Merged into Resilience）✅

**范围**

* endpoint 连续失败 N 次 → open；cooldown 后 half-open 探测恢复
* Router 默认避开 open endpoint

**DoD**

* 某 endpoint 持续失败时，后续请求不再反复撞墙
* debug 能看到 breaker 状态变化

---

## V0.3.0 ✅（已完成：Async 全链路）

**定位**：高吞吐、服务化可用（每秒 50+ 请求级别）

> 核心风险点：SQLite 同步写会阻塞 event loop，所以 **Async Ledger** 是关键。

### 0.3.0-A：Async API ✅

**范围**

* `async def generate_async(...)`
* `async stream`：`AsyncIterator[StreamEvent]`
* httpx.AsyncClient（连接池复用）

**DoD**

* async 与 sync 行为一致（同请求同语义）
* 支持取消（cancel）且不导致资源泄漏

### 0.3.0-B：Async Ledger（深水区，必须）✅

**状态**: ✅ **已完成 (Implemented)**
**实现方案**: Async Queue + Single Writer Worker + Event Sourcing (`LedgerEvent`)
**Spec**: [plan_06_Async_Ledger_Spec.md](plan/plan_06_Async_Ledger_Spec.md)

**推荐方案**

* **Async Queue + 单写入 Worker**（后台 task 批量 flush）
* 支持两种模式：

  * `best_effort`（默认）：不阻塞主路径
  * `strict_budget`：预占用（hold）需同步点确认落盘，防并发超扣

**DoD**

* ✅ 1000+ 并发写入无 `database is locked`
* ✅ event loop 不因 ledger 阻塞（关键路径无同步 sqlite 写）
* ✅ strict_budget 下并发不会“同时通过 precheck 导致超预算”

---

### 0.3.0-C：Async Rate Limit ✅

**范围**

* limiter 在 async 场景可用（可沿用 SQLite 窗口 + async wrapper）
* `wait_on_rate_limit` 与 retry 协同工作

**DoD**

* 高并发下限流稳定，且不会阻塞整个 loop

---

## V0.4.0 🖼️🎙️（Multimodal：多模态输入输出 + 多维计费）

**定位**：能力扩展（图像/音频）

> 前置要求：V0.2 的结构化响应 + V0.2/0.3 的 streaming/async 已稳定，否则多模态会把复杂度放大。

### 0.4.0-A：统一多模态接口（InputPart/OutputPart）

**范围**

* 输入统一为 parts：`text | image | audio | file_ref`
* 新增方法（或扩展 generate）：

  * `transcribe()`（ASR）
  * `speak()`（TTS）
  * `paint()`（Image Gen）
* Streaming 在多模态场景可用（尤其 TTS/ASR）

**DoD**

* 至少跑通：一条图片理解（vision）+ 一条 ASR 或 TTS + 一条 image gen

---

### 0.4.0-B：Ledger 计费升级（多维单位）

**范围**

* ledger 记录升级：`usage_json`（tokens/images/audio_seconds…）
* pricing registry 升级：支持 `unit_type = token | image | audio_seconds`
* 报表按维度拆分 cost breakdown

**DoD**

* 同一账本能同时记录 token 与 image/audio 的消耗
* budget precheck 仍能工作（宽估算，准结算）

---

## V0.5.0 📊（Ops：报表、趋势、质量/成本优化）

**定位**：可运营、可优化、可持续迭代

### 0.5.0-A：Reporting（CLI）

**范围**

* `llm budget today`
* `llm budget report --days 7`
* `llm budget top --by model|provider`
* 导出 CSV/JSON

**DoD**

* 能回答：最近 7 天花在哪、哪些模型最贵、失败率最高的 endpoint 是谁

---

### 0.5.0-B：Cost-aware Router（基于真实 usage/价格）

**范围**

* 基于 ledger 的真实 usage + pricing 做成本优选（替代当前粗估）
* router score 引入：p50/p95 latency、fail_rate、cost、quality_tier
* 自动降级（超预算 / endpoint 不健康）策略完善

**DoD**

* cheap 策略在真实账单上可证明更便宜（对比基线）
* smart 策略在失败率/延迟上不显著劣化（有 fallback 保障）

---

## V0.6.0 🎯（Accuracy：token 估算与兼容性治理）

**定位**：长期维护与准确性

### 0.6.0-A：Tokenizer（可选轻量集成）

**范围**

* 对 OpenAI-compat：可选 tiktoken 精准估算
* 对 Gemini/Qwen：优先使用 provider usage 字段后结算
* 对没有 usage 的响应：标记 `usage_unknown=True`

**DoD**

* precheck 误差可控（明显减少“误杀/漏放”）
* “宽估算，准结算”闭环完整

### 0.6.0-B：Contract Tests（契约测试）

**范围**

* DRY_RUN 全链路契约测试（config→router→adapter→ledger）
* 真实 provider 的最小探测（可选、可跳过）

**DoD**

* provider API 升级导致结构变化时，CI 能第一时间发现

---

# 版本依赖关系总览（很关键）

* **Structured Output（0.2）** 是 streaming/async/multimodal/reporting 的共同地基
* **Streaming（0.2）** 强烈建议早做，否则长输出体验会持续拖累使用
* **Async（0.3）** 必须绑定 **Async Ledger**，否则“async 只是表面 async”
* **Multimodal（0.4）** 必须在 response/event/ledger 结构稳定之后做
* **Cost-aware Router（0.5）** 依赖 ledger 的真实 usage 与 pricing registry 的多维结构

---

# 推荐落地顺序

1. **V0.2.0：Structured Output + Streaming + Retry/Backoff + max_wait_timeout + Breaker**
2. **V0.3.0：Async + Async Ledger（队列单写入 worker + strict 预占用同步点）**
3. **V0.4.0：Multimodal + 多维计费 schema**
4. **V0.5.0：Reporting + Router cost-aware**
