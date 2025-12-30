# 📘 项目上下文文档 (Project Context Document)

## 一、项目概要 (Project Overview)
- **项目名称**: LLM SDK - Vibe Edition
- **项目背景**: 开发一个自用的 LLM SDK，旨在平衡企业级合规管控与个人开发者的灵活性。解决传统 SDK 配置死板、Key 管理不安全、预算无感知的痛点。
- **目标与目的**:
  - 提供安全的双层配置管理（Project vs User）。
  - 实现精细化的预算控制（Budget Control）。
  - 提供开箱即用的网络诊断与连通性检查。
- **要解决的问题**:
  - 灵活性与管控的矛盾。
  - 开发者“忘关循环导致破产”的恐惧。
  - 复杂的网络环境适配（代理、Residency）。
- **整体愿景**: 打造一个“扎实且具备生产级水准”的 Python LLM SDK，既能适应严格的企业合规，又能提供极致的本地开发体验。

## 二、范围定义 (Scope Definition)
- **当前范围**:
  - 核心配置系统 (MergedConfig)。
  - 预算控制系统 (SQLite Ledger)。
  - 基础网络诊断 (Doctor)。
  - Python 客户端封装。
- **非本次范围**:
  - 具体的 LLM 模型训练/微调。
  - 复杂的 UI 界面（仅提供 CLI/SDK）。
- **约束条件**:
  - 语言：Python。
  - 必须支持 Global Residency 和本地代理。
  - 必须处理好并发写入 SQLite 的问题。

## 三、关键实体与关系 (Key Entities & Relationships)
- **核心实体**:
  - `ProjectConfig`: 团队规则（Git 托管）。
  - `UserConfig`: 个人凭证（本地独有）。
  - `MergedConfig`: 运行时融合态。
  - `Ledger`: 消耗账本。
  - `Provider`: LLM 服务商适配器。
- **实体关系**:
  - `MergedConfig` = `ProjectConfig` + `UserConfig` (按特定策略合并)。
  - `Client` 持有 `MergedConfig` 和 `Ledger`。
  - `Ledger` 记录每一次 `Generation` 的 Cost。

## 四、功能模块拆解 (Functional Decomposition)
- **1. 配置系统 (Configuration System)**
  - 输入: `llm.project.yaml`, `~/.config/llm-sdk/config.yaml`, 环境变量。
  - 输出: `MergedConfig` 对象。
  - 核心逻辑:
    - Routing Policies: 追加 (Append)。
    - Model Registry: 覆盖 (Overlay)。
    - Endpoints: 过滤 (Filter)。

- **2. 预算控制 (Budget Control)**
  - 模块: Ledger, Interceptor.
  - 逻辑: Pre-check (估算费用) -> Check Cap (是否超额) -> Execute -> Post-update (异步写入 WAL SQLite)。

- **3. 诊断模块 (Doctor)**
  - 功能: `sdk.doctor()`。
  - 逻辑: 对配置的 Endpoints 进行 Ping 或 Soft Validation（不消耗余额）。

## 五、技术方向与关键决策 (Technical Direction & Decisions)
- **语言**: Python。
- **数据持久化**: SQLite (开启 WAL 模式)。
- **配置格式**: YAML.
- **并发策略**: 关键写入路径采用非阻塞或加锁机制，确保线程安全。
- **优先级策略**: 显式参数 > 环境变量 > 配置文件。

## 六、交互、风格与输出约定 (Interaction & Style Conventions)
- **代码风格**: 遵循 Python PEP8，使用 Type Hints。
- **异常处理**: 定义明确的 `ConfigurationError`, `QuotaExceeded` 等自定义异常。

## 七、当前进展总结 (Current Status)
- **已确认**: 需求 SPEC 已定稿，目录结构已创建。
- **待执行**: 生成实施计划，开始编码。
