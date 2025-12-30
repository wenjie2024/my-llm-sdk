# LLM SDK Requirements & Specification

## 1. 核心需求
实现一个自用的 LLM SDK 工具，解决灵活性与管控的矛盾。

## 2. 关键架构设计
### 2.1 双层配置 (Project + User)
- **Project Configuration (`llm.project.yaml`)**:
  - 位于项目仓库根目录
  - 定义团队规则（如：必须用国产模型、禁止日志落盘）
  - 类似于 `.gitignore`，随代码提交

- **User Configuration (`~/.config/llm-sdk/config.yaml`)**:
  - 位于用户本地
  - 管理个人连接凭证（API Keys）、本地网络代理配置
  - 类似于 SSH Config，不随代码提交

- **MergedConfig (运行时)**:
  - 在内存中将 Project 和 User 配置合并。
  - **合并逻辑**:
    - **Routing Policies**: 追加策略 (Project Policies + User Policies)。
    - **Model Registry**: 覆盖策略 (Overlay)。项目级定义优于用户级。
    - **Endpoints**: 过滤策略。根据项目级 `data_residency` 过滤用户提供的 endpoints。

### 2.2 预算控制 (Ledger & Budget)
- **Pre-check**: 每次调用前进行估算拦截。
- **SQLite Ledger**: 本地数据库记录消耗。
- **Daily Cap**: 设置每日限额（如 $1.0），超标抛出 `QuotaExceeded`。
- **性能优化**: 强制开启 WAL 模式，非阻塞写入。

### 2.3 诊断模块 (Doctor)
- 支持网络连通性检查（Ping/Soft Validation）。
- 在发起请求前确认链路通畅。

## 3. 环境与合规要求
- **数据合规**: 支持 Global Residency 要求。
- **网络环境**: 支持通过本地代理访问。
- **配置优先级**: 显式参数 > 环境变量 (LLM_PROVIDER_OPENAI_API_KEY) > 配置文件。

## 4. 技术栈
- 语言: Python
