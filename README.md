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
| **报表与趋势** | `llm budget` 命令查看消耗趋势、排行和今日状态 |
| **自动重试** | 429/超时退避重试，可配置 `max_retries` / `max_delay_s` |
| **双层配置** | 项目规则 vs API Key 分离，防止误提交 |

---

## 💰 定价与成本参考

SDK 的计费逻辑以 `llm.project.yaml` 中的配置为准。默认模板已对齐以下官方公开价：

- **Google Gemini**: [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- **Alibaba Qwen**: [Alibaba Cloud Model Pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing?spm=a2c63.p38356.help-menu-2400256.d_0_0_3.5b933fd9UZWrpM)

| 平台/区域 | 计费口径 | 核心差异 |
| :--- | :--- | :--- |
| **Qwen (Mainland)** | 约 $0.345/1M (Max) | 🚀 价格极低，适合国内备案业务，安全过滤较严 |
| **Qwen (International)** | 约 $1.6/1M (Max) | 🌍 新加坡/全球节点，对标 GPT-4 逻辑，过滤较松 |
| **Gemini (Standard)** | $0.075 - $1.25 / 1M | ⚡ 阶梯计费，>128k/200k 上下文价格翻倍 |

> **提示**：请根据部署环境在 `llm.project.yaml` 中微调价格。目前 SDK 默认采用保守的国际版/基础档定价。

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

## 📊 CLI 预算与报表 (V0.5+)

SDK 内置了强大的用量统计与预算管理工具。

### 1. 今日消耗状态
```bash
python -m my_llm_sdk.cli budget status
```
展示今日已用金额、请求数、Token 数以及预算进度条。

### 2. 消耗趋势图
```bash
python -m my_llm_sdk.cli budget report --days 7
```
使用柱状图展示最近 N 天的费用支出趋势。

### 3. 消耗大户排行
```bash
python -m my_llm_sdk.cli budget top --by model
```
按模型或厂商对支出进行排序，找出“最贵”的调用来源。

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

- [x] 核心管控与预算拦截 (V0.1)
- [x] 结构化响应与 Streaming (V0.2)
- [x] Async 全链路支持 (V0.3)
- [x] 运维报表与 CLI 工具 (V0.5.0)
- [x] V0.5.x: 精准计费与流水重计算 (V0.5.1)
- [x] V0.5.x: 预算比例预警与硬性熔断 (V0.5.2)
- [x] V0.5.x: 自动化测试套件 (Pytest Integration, V0.5.3)
- [x] V0.5.4: Gemini 官方 SDK 升级 (`google-genai`)
- [ ] V0.4.0+: 多模态支持 (Vision / Audio)
- [ ] 发布到 PyPI (`pip install my-llm-sdk`)

---

## 🤝 贡献

1. Fork 本仓库
2. 在 `src/my_llm_sdk/providers/` 添加新 Provider（继承 `BaseProvider`）
3. 在 `src/my_llm_sdk/client.py` 的 `self.providers` 中注册
4. 提交 PR

---

## 📄 License

[Apache 2.0](LICENSE)
