[English](README_en.md) | **中文**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)

# My LLM SDK

**一套代码，调用多家模型。**

> 用同一套 `client.generate()` / `stream()` 调用 Gemini / Qwen / OpenAI-compatible。  
> 内置预算控制、429 自动等待重试、Ledger 记账与用量统计。  
> 适合：团队共享模型策略 + 个人本地 Key 隔离 + 需要稳定跑批/高并发/成本可追踪的场景。

---

## 🚀 快速上手

### 在你的项目中使用

```bash
# 1. 安装（从本地路径，未来支持 pip install my-llm-sdk）
pip install -e <SDK路径>/my-llm-sdk
# 例: pip install -e ~/projects/my-llm-sdk      (macOS/Linux)
#     pip install -e C:\Users\你\my-llm-sdk     (Windows)

# 2. 在你的项目目录下初始化配置
python -m my_llm_sdk.cli init

# 3. 编辑 config.yaml，填入 API Key

# 4. 调用
python -m my_llm_sdk.cli generate --model gemini-2.5-flash --prompt "你好"
```

### 参与 SDK 开发

```bash
git clone https://github.com/NoneSeniorEngineer/my-llm-sdk.git
cd my-llm-sdk
pip install -e .
python -m my_llm_sdk.cli doctor
```

---

## 💡 为什么用它

| 需求 | My LLM SDK 的解决方案 |
| :--- | :--- |
| **一次接入，多家切换** | 不改代码，只换 `model_alias` |
| **怕账单失控** | 请求前预算检查 + 统一 Ledger 记账 |
| **怕 429 / 超时** | 自动退避重试，可配置最大等待 |
| **团队协作** | `llm.project.yaml` (Git) + `config.yaml` (本地) 彻底分离 |
| **跑批 / 并发** | Async + Streaming + 结构化返回（cost/token 统一） |

---

## 🧪 典型用法

### 1. 跑批：预算封顶 + 自动重试
适合 nightly job / 数据标注 / 评测脚本：超预算自动拒绝，429 自动等待重试。

### 2. 在线服务：Streaming + 统一用量统计
`stream=True` 流式返回，同时精确记录 token/cost 到 Ledger。

### 3. 团队协作：策略共享，Key 永不入库
`llm.project.yaml` 提交到 Git；`config.yaml` 只在本地（支持 personal overrides）。

---

## 🎯 核心功能

| 功能 | 说明 |
| :--- | :--- |
| **统一接口** | 一套 `client.generate()` 调用所有厂商 |
| **多模型支持** | Gemini 2.5/3.0, Qwen Max/Plus/Flash, OpenAI Compatible |
| **Async + Streaming** | `generate_async` / `stream_async` 支持高并发 |
| **结构化返回** | `full_response=True` 获取 usage/cost/token |
| **预算控制** | 每次请求前检查消费，超额自动拒绝 |
| **自动重试** | 429/超时退避重试，可配置 `max_retries` / `max_delay_s` |
| **双层配置** | 项目规则 vs API Key 分离，防止误提交 |

---

## ✅ 可靠性

- **自动重试**：429/超时退避（可配置最大次数与最大等待时间）
- **Ledger 记账**：每次请求记录 cost / token / provider / model / latency
- **结构化返回**：`full_response=True` 统一拿到 usage/cost
- **测试覆盖**：`pytest` 单元测试 + 端到端验证脚本

---

## 📦 Python API

```python
from my_llm_sdk.client import LLMClient

client = LLMClient()

# 基础调用
response = client.generate("你好", model_alias="gemini-2.5-flash")
print(response)

# 结构化对象（含 cost/token）
res = client.generate("你好", full_response=True)
print(f"Cost: ${res.cost}, Tokens: {res.usage.total_tokens}")

# 流式输出
for event in client.stream("数到5", model_alias="qwen-max"):
    print(event.delta, end="", flush=True)
```

---

## 🔧 配置参考

### config.yaml（本地，勿提交 Git）
```yaml
api_keys:
  google: "AIzaSy..."
  dashscope: "sk-..."
daily_spend_limit: 5.0
```

### llm.project.yaml（可提交 Git）
```yaml
model_registry:
  gemini-2.5-flash:
    provider: google
    model_id: gemini-2.5-flash
    rpm: 1000
```

### 重试配置
```yaml
resilience:
  max_retries: 3
  wait_on_rate_limit: true
  max_delay_s: 60
```

### 本地模型覆盖（如 Ollama）
```yaml
personal_model_overrides:
  llama-3-local:
    provider: openai
    model_id: llama3
    api_base: "http://localhost:11434/v1"
```

---

## 📊 性能基准 (2025-12)

| 模型 | 简单任务 | 复杂任务 | 回答长度 | 特点 |
| :--- | :--- | :--- | :--- | :--- |
| qwen-flash | **3.70s** | 48.53s | 11414c | 响应最快 |
| gemini-3.0-flash | 4.49s | **14.85s** | 5403c | 复杂任务最快 |
| qwen-plus | 3.95s | 33.15s | 7968c | 简单任务极快 |
| gemini-2.5-pro | 16.47s | 53.80s | 9988c | 深度思考 |
| qwen-max | 9.75s | 31.36s | 3822c | 回答精炼 |

> **复现**：`python benchmark.py` (开发模式下运行)  
> **环境**：macOS + 家用网络，不同地区/网络差异大  
> **任务定义**：Simple = 常识问答；Complex = 多线程爬虫代码生成

---

## 🗺️ Roadmap

- [ ] 发布到 PyPI (`pip install my-llm-sdk`)
- [ ] 增加 OpenTelemetry tracing
- [ ] 更多 OpenAI-compatible provider 支持
- [ ] 多模态支持 (Vision / Audio)
- [ ] 更细粒度的按 provider 错误码重试策略

---

## 🤝 贡献

1. Fork 本仓库
2. 在 `src/my_llm_sdk/providers/` 添加新 Provider（继承 `BaseProvider`）
3. 在 `src/my_llm_sdk/client.py` 的 `self.providers` 中注册
4. 提交 PR

---

## 📄 License

[Apache 2.0](LICENSE)
