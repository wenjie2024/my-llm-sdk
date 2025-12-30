# My LLM SDK (生产级)
一个健壮的、企业级的 Python LLM 交互 SDK。设计时严格遵循 **预算控制**、**双层配置** 和 **自我诊断** 原则。
> **状态**: 活跃开发中
> **特性**: 多供应商支持 (OpenAI, Gemini, Qwen), SQLite 预算账本, 网络医生, 动态节点切换。
## 🚀 核心特性
*   **🛡️ 预算控制**:
    *   **预检 (Pre-check)**: 如果超出每日限额，会在请求发生*之前*进行拦截。
    *   **账本 (Ledger)**: 本地 `sqlite3` (WAL 模式) 记录每一笔交易，支持高并发。
    *   **动态定价**: 实时估算 Qwen-Max, Gemini 3.0 等模型的费用。
*   **⚙️ 双层配置架构**:
    *   `llm.project.yaml`: 提交到 Git。定义合法的模型列表和路由策略。
    *   `config.yaml`: **仅本地** (Git-ignored)。存储 API Key 和个人端点。
    *   **智能合并**: 支持 追加 (Policies) / 覆盖 (Models) / 过滤 (Endpoints) 策略。
    *   `python -m my_llm_sdk.cli doctor`: 自动诊断与美国/中国/新加坡节点的连通性。
    *   **智能路由**: Qwen 提供商会根据是否能连通 Google，自动在 CN (国内) 和 SG (新加坡) 节点间切换。
*   **🔌 多引擎支持**:
    *   **Google Gemini**: 支持 1.5, 2.5, 和 3.0 (Preview) 系列。
    *   **Alibaba Qwen**: 支持 Max, Plus, 和 Flash (通义千问 DashScope)。
    *   **OpenAI/Compatible**: 支持通用接口。
*   **⏳ 异步与流式 (New in V0.2/0.3)**:
    *   **Async API**: `client.generate_async` 和 `client.stream_async` 支持高并发（每秒 50+ 请求）。
    *   **Streaming**: 完整支持流式输出 (`stream=True`)，且能精准记录 Ledger。
    *   **Structured Output**: 统一返回对象，包含 Cost 和 Token Usage。
    *   **Resilience**: 自动重试与速率限制等待 (`resilience.wait_on_rate_limit`)。
## 🛠️ 安装指南
```bash
# 1. 开发模式安装 (推荐)
# 如果你在本项目根目录下:
pip install -e .

# 2. 在其他项目中引用 (Local Path)
# 如果你想在另一个项目中使用本 SDK:
pip install -e /path/to/documents/my-llm-sdk

# 3. 打包安装 (Production)
# 生成 .whl 文件并安装
pip install build
python -m build
pip install dist/my_llm_sdk-0.1.0-py3-none-any.whl
```
## ⚡ 快速上手
### 1. 初始化配置 (Initialize Config)
在你的项目根目录下运行：
```bash
python -m my_llm_sdk.cli init
```
这将自动生成：
*   `llm.project.yaml`: 项目级模型规则 (建议提交到 Git)。
*   `config.yaml`: 包含 API Key 的模板 (请编辑并**加入 .gitignore**)。

### 2. 填入密钥 (Setup Keys)
编辑 `config.yaml`，填入 API Key：
```yaml
api_keys:
  google: "AIzaSy..."
  dashscope: "sk-..."
  openai: "sk-..."
daily_spend_limit: 5.0
```

### 3. 运行诊断 (Doctor)
检查网络和 Key 是否配置正确：
```bash
python -m src.cli doctor
```

## 🔧 进阶配置 (Advanced Config)
`config.yaml` 不仅仅用于存储密钥，还支持**本地覆盖**（不会影响团队共享配置）：

### 1. 本地模型定义 (personal_model_overrides)
定义仅本地可见的模型（如 Ollama 或临时测试模型）：
```yaml
personal_model_overrides:
  llama-3-local:
    provider: "openai" # 兼容协议
    model_id: "llama3"
    api_base: "http://localhost:11434/v1"
    rpm: 9999
```

### 2. 本地路由策略 (personal_routing_policies)
定义本地优先的路由规则：
```yaml
personal_routing_policies:
  - name: "debug-local-first"
    strategy: "priority"
    params:
      priority_list: "llama-3-local,gpt-4"
```
这样你就可以在不修改 `llm.project.yaml` 的情况下，强制 SDK 优先使用本地模型进行调试。
### 3. 生成文本 (CLI)
**使用 Gemini 2.5:**
```bash
python -m my_llm_sdk.cli generate --prompt "解释量子力学" --model gemini-2.5-flash
```
**使用 Qwen Max:**
```bash
python -m my_llm_sdk.cli generate --prompt "你好，写首诗" --model qwen-max
```
## 📦 Python API 调用
```python
from my_llm_sdk.client import LLMClient
import asyncio

# 初始化 (自动加载配置)
client = LLMClient()

async def main():
    try:
        # 1. 基础生成 (Blocking)
        print("--- Sync Generate ---")
        response = client.generate(
            prompt="为银行账户设计一个 Python 类", 
            model_alias="gemini-2.5-flash"
        )
        print(response) # 直接打印内容

        # 2. 结构化对象 (Rich Object)
        print("\n--- Structured Response ---")
        res_obj = client.generate("Hello", full_response=True)
        print(f"Cost: ${res_obj.cost}, Tokens: {res_obj.usage.total_tokens}")

        # 3. 异步流式 (Async Streaming - High Concurrency)
        print("\n--- Async Stream ---")
        stream = client.stream_async("数到3", model_alias="gemini-2.5-flash")
        async for event in stream:
            if event.delta:
                print(event.delta, end="", flush=True)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 🧩 核心功能配置
在 `llm.project.yaml` 或 `config.yaml` 中配置 Resilience：
```yaml
resilience:
  max_retries: 3           # 失败重试次数
  wait_on_rate_limit: true # 遇到 429 是否自动等待
  max_delay_s: 60          # 最大等待时间
```

## 📂 项目结构
```
my-llm-sdk/
│   └── my_llm_sdk/     # Python Package
│       ├── budget/     # ...
│       ├── client.py   # ...
│       └── ...
├── tests/              # Pytest 测试套件
├── config.yaml         # 本地密钥 (已忽略)
├── llm.project.yaml    # 项目规则 (已提交)
└── ledger.db           # 本地交易日志
```
## 📝 配置参考
### llm.project.yaml
定义 **模型注册表 (Model Registry)** (别名映射到真实 Model ID) 和 **允许的区域 (Allowed Regions)**。
### config.yaml
定义 **API Keys** 和 **Endpoints**。默认情况下，Qwen 端点连接到 CN，但支持灵活路由。

## 📊 性能基准测试 (2025-12)

基于 `tests/benchmark.py` 的实测数据（Simple:常识问答, Complex:多线程爬虫代码生成）：

| 模型 (Model) | 简单任务耗时 | 复杂任务耗时 | 复杂回答长度 | 特点 |
| :--- | :--- | :--- | :--- | :--- |
| **qwen-flash** | **3.70s** | 48.53s | **11414 c** | **响应最快且内容最丰富** |
| **qwen-plus** | 3.95s | 33.15s | 7968 c | 简单任务极快 (3.9s) |
| **gemini-3.0-flash** | 4.49s | **14.85s** | 5403 c | **复杂任务处理速度最快** |
| **gemini-2.5-pro** | 16.47s | 53.80s | 9988 c | 深度思考，内容详实 |
| **qwen-max** | 9.75s | 31.36s | 3822 c | 回答精炼 |

> *注：测试环境取决于本地网络状况，数据仅供参考。*

## 🤝 贡献
1.  Fork 本仓库。
2.  在 `src/my_llm_sdk/providers/` 中添加新的 Provider。
3.  在 `src/my_llm_sdk/client.py` 中注册它。
4.  提交 PR!
