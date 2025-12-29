---
level: 2
file_id: plan_05
parent: plan_01
status: pending
created: 2025-12-29 17:15
children: [plan_05_01]
estimated_time: 180分钟
---

# 模块：客户端封装 (Client API)

## 1. 模块概述

### 模块目标
对外暴露统一的 SDK 入口。将配置(Config)、预算(Budget)、诊断(Doctor)集成在一起，提供简洁的 `check_and_generate` (或类似) 接口。

### 在项目中的位置
最顶层。用户直接实例化的类。

---

## 2. 依赖关系

### 前置条件
- **Modules**: `config`, `budget`, `doctor`.

### 后续影响
- **输出**: LLM Response (String / Stream).

---

## 3. 子任务分解

- [ ] plan_05_01 - **实现 Client 类**
  - 简述: `LLMClient` 类初始化时自动加载配置。提供 `generate(prompt, model)` 方法，内部先 Check Budget，再调用 Provider，成功后 Record Transaction。
- [ ] plan_05_02 - **实现 CLI 工具**
  - 简述: `llm-sdk` 命令行工具，支持 `llm-sdk doctor`。

---

## 4. 技术方案

### 核心流程 (Client.generate)
1. **Load Config**: `self.config = load_config()`
2. **Resolve Model**: 查表 `final_model_registry`，找到对应的 Provider 和 ModelID。
3. **Pre-check Budget**: `budget.check_budget(estimated_cost)`
4. **Call Provider**: `provider.completion(...)` (Mock for now or simple httpx)
5. **Post-update Ledger**: `budget.track(..., cost=actual_cost)`
6. **Return**: Result.

### 命令行 (CLI)
使用 `argparse` 或标准库。
- `llm-sdk doctor`: 运行 `Doctor.run_diagnostics()` 并打印报告。

---

## 5. 交付物清单

### 代码
- `src/client.py`: `LLMClient`.
- `src/cli.py`: Entry point.
- `src/providers/base.py`: Unification interface.

### 测试
- `tests/test_client_flow.py`: 集成测试，Mock Provider，验证完整调用链。

---
