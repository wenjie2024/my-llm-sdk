---
level: 1
file_id: plan_01
status: pending
created: 2025-12-29 16:45
children: [plan_02, plan_03, plan_04, plan_05]
---

# 总体计划：LLM SDK - Vibe Edition

## 1. 项目概述

### 项目背景
开发一个自用的 LLM SDK，旨在平衡企业级合规管控与个人开发者的灵活性。解决传统 SDK 配置死板、Key 管理不安全、预算无感知的痛点。

### 项目目标
- **双层配置**：Project (Git) + User (Local) 自动合并。
- **预算控制**：本地 SQLite 账本，每日限额拦截。
- **开箱即用**：内置网络诊断 (Doctor) 和 Python 客户端封装。

### 项目价值
消除开发者“因误操作破产”的恐惧，同时满足企业数据驻留（Residency）合规要求，提升开发体验。

---

## 2. 可视化视图

### 系统逻辑图
```mermaid
flowchart TD
    UserConfig[User Config (~/.config)] --> Merger
    ProjectConfig[Project Config (repo/llm.project.yaml)] --> Merger
    Merger{MergedConfig Config Loader} --> Client[LLM Client]
    
    Client --> Budget{Budget Control}
    Budget -- Pre-check --> Ledger[(SQLite Ledger)]
    Budget -- Pass --> Provider[LLM Provider]
    Provider --> Client
    Client -- Post-update --> Ledger
    
    Doctor[Doctor / Diagnostic] -.-> Provider
```

### 模块关系矩阵
| 模块 | 主要输入 | 主要输出 | 责任角色 | 依赖 |
| --- | --- | --- | --- | --- |
| **Config System** | yaml files, env vars | MergedConfig Object | 核心基础 | PyYAML |
| **Budget Control** | MergedConfig, Request Cost | Decision (Allow/Deny) | 安全守卫 | SQLite, MergedConfig |
| **Doctor** | Endpoints List | Health Report | 辅助工具 | MergedConfig |
| **Client API** | User Prompt | LLM Response | 用户入口 | All of above |

---

## 3. 任务分解树

```
plan_01 总体计划
├── plan_02 [配置系统 Core] (预估 4h)
│   ├── plan_02_01 [Loader & Parser]
│   └── plan_02_02 [Merged Logic Implementation]
├── plan_03 [预算控制 Budget] (预估 6h)
│   ├── plan_03_01 [SQLite Ledger Schema]
│   └── plan_03_02 [Interceptor & Pre-check]
├── plan_04 [诊断模块 Doctor] (预估 3h)
│   └── plan_04_01 [Network & Connectivity Check]
└── plan_05 [客户端封装 Client] (预估 3h)
    └── plan_05_01 [BaseClient & Provider Adapters]
```

---

## 4. 任务清单

- [ ] plan_02 - **配置系统 (Configuration System)**
  - 核心：实现 Project 和 User 配置的加载与合并（覆盖/追加/过滤策略）。
- [ ] plan_03 - **预算控制 (Budget Control)**
  - 核心：SQLite 账本设计，WAL 模式，并发安全的扣费拦截逻辑。
- [ ] plan_04 - **诊断模块 (Doctor)**
  - 核心：针对配置的 endpoints 进行连通性测试。
- [ ] plan_05 - **客户端封装 (Client Wrapper)**
  - 核心：对外暴露简洁的 `LLM` 类，集成上述所有模块。

---

## 5. 技术栈

- **语言**: Python 3.10+
- **配置**: PyYAML (`yaml`)
- **存储**: SQLite3 (Standard Lib)
- **依赖管理**: Poetry (推荐) 或 requirements.txt
- **HTTP**: `httpx` 或 `requests`

---

## 6. 验收标准

### 功能验收
- [ ] **配置合并**: 能够正确合并 Project 和 User 配置，优先级正确。
- [ ] **预算拦截**: 当当日消费超过限额时，SDK 必须抛出异常阻止请求。
- [ ] **网络诊断**: `sdk.doctor()` 能准确报告网络通断。

### 质量验收
- [ ] 核心逻辑（合并、扣费）需有单元测试覆盖。
- [ ] SQLite 开启 WAL 模式，高并发下无锁死。

---
