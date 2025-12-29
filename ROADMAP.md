# 🗺️ 产品路线图 (Roadmap)

本文档记录了基于 V0.1.0 版本的实施复盘，以及针对 V0.2.0+ 的功能增强清单。

## ✅ 已完成 (V0.1.0)
- [x] **核心架构**: 双层配置系统 (Project/User Config)
- [x] **预算控制**: SQLite 本地账本, Pre-check 拦截
- [x] **多模型支持**: Gemini (Flash/Pro), Qwen (Max/Plus/Flash)
- [x] **网络诊断**: Doctor 模块 & 动态路由 (CN/SG)
- [x] **速率限制**: RPM/TPM/RPD 多维限流 (SQLite 滑动窗口)

---

## 🚀 待增强清单 (Future Enhancements)

以下功能计划在后续版本中通过增量迭代实现。

### P0: 核心稳定性 (Stability) 🛡️

#### 1. 容错与重试机制 (Resilience)
*   **痛点**: 网络波动或 429 限流会导致任务直接失败。
*   **计划**:
    *   实现 **自动重试 (Auto-Retry)**: 针对 5xx 错误和超时。
    *   实现 **指数退避 (Exponential Backoff)**: 避免在拥塞时加重负载。
    *   支持 `wait_on_rate_limit=True` 选项，超限时自动休眠而非报错。

---

### P1: 性能与能力扩展 (Performance & Capability) 🚀

#### 2. 高并发与异步支持 (Async Support)
*   **痛点**: 目前 `client.generate()` 是同步阻塞的，难以支持高吞吐场景（如每秒处理 50+ 请求）。
*   **计划**:
    *   引入 `httpx.AsyncClient` 替代同步调用。
    *   新增 `async def generate_async()` 接口，支持原生 `await`。
    *   优化 `Ledger` 锁机制以适应 Event Loop。

#### 3. 多模态支持 (Multimodal Support) 🖼️🎙️
*   **痛点**: 目前接口仅支持纯文本，无法处理语音 (ASR/TTS) 和图像生成 (Image Gen) 需求。
*   **涉及模型**:
    *   **Qwen**: `Qwen3-ASR/TTS`, `Qwen-Image-Plus`。
    *   **Google**: `gemini-3-pro-image`, `imagen-4.0`.
*   **计划**:
    *   **接口重构**: 扩展 `generate()` 或新增 `transcribe()`, `paint()` 等方法。
    *   **计费升级**: Ledger 支持按张 (Image)、按秒 (Audio) 计费。

---

### P2: 开发者体验 (DX & UX) ✨

#### 4. 流式输出 (Streaming)
*   **痛点**: 长文本生成时首字延迟 (TTFT) 较高。
*   **计划**: 支持 `stream=True` 并返回 Generator。

#### 5. 结构化输出 (Structured Output)
*   **痛点**: 缺乏 Token 消耗统计和结束原因等元数据。
*   **计划**: 封装 `GenerationResponse` 对象，包含 `{ content, usage, finish_reason }`。

---

### P3: 运营与优化 (Ops) 📊

#### 6. 可视化账单报告 (Reporting)
*   **痛点**: 缺乏历史趋势分析。
*   **计划**: CLI 新增 `budget report --days 7` 等命令。

#### 7. 精准 Token 计算 (Accuracy)
*   **痛点**: 基于长度估算误差较大。
*   **计划**: 集成轻量级 Tokenizer (如 `tiktoken`)。
