[English](README_en.md) | **中文**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)

<p align="center">
  <img src="assets/banner.png" alt="My LLM SDK" width="800">
</p>

# My LLM SDK

**一套代码，调用多家模型。**

> 用同一套 `client.generate()` 调用 Gemini / Qwen / Doubao / DeepSeek。  
> 内置预算控制、429 自动重试、Ledger 记账与用量统计。

---

## 🚀 快速上手

```bash
# 1. 安装
pip install -e <SDK路径>/my-llm-sdk

# 2. 初始化配置
python -m my_llm_sdk.cli init

# 3. 编辑 config.yaml，填入 API Key

# 4. 调用
python -m my_llm_sdk.cli generate --model gemini-2.5-flash --prompt "你好"
```

---

## ✨ 核心功能

| 功能 | 说明 |
|:---|:---|
| **统一接口** | 一套 `client.generate()` 调用所有厂商 |
| **多模型支持** | Gemini, Qwen, Doubao, DeepSeek |
| **多模态** | 图片生成 / TTS / ASR / Vision |
| **预算控制** | 请求前检查消费，超额自动拒绝 |
| **自动重试** | 429/超时退避重试 |
| **Async + Streaming** | `generate_async` / `stream_async` |

---

## 📚 详细用法

| Provider | 支持能力 | 文档 |
|:---|:---|:---|
| **Google Gemini** | 文本 / Vision / 图片生成 / TTS | [guide/providers/google.md](guide/providers/google.md) |
| **Qwen (DashScope)** | 文本 / Vision / 图片 / TTS / ASR | [guide/providers/qwen.md](guide/providers/qwen.md) |
| **Volcengine (Doubao)** | 文本 / DeepSeek / 图片 / 视频 | [guide/providers/volcengine.md](guide/providers/volcengine.md) |

---

## 🔧 配置

### config.yaml（本地，勿提交 Git）

```yaml
api_keys:
  google: "AIzaSy..."
  dashscope: "sk-..."
  volcengine: "your-key"
daily_spend_limit: 5.0
```

### 模块化配置

SDK 自动加载 `llm.project.d/*.yaml` 中的模型定义：

```text
my-project/
├── llm.project.yaml       # 主配置
└── llm.project.d/
    ├── google.yaml        # Gemini 模型
    ├── qwen.yaml          # Qwen 模型
    └── volcengine.yaml    # Doubao 模型
```

---

## 📊 CLI 命令

```bash
# 今日消耗
python -m my_llm_sdk.cli budget status

# 消耗趋势
python -m my_llm_sdk.cli budget report --days 7

# 消耗排行
python -m my_llm_sdk.cli budget top --by model
```

---

## 🧪 测试

```bash
# 回归测试（跳过音频测试）
pytest tests/

# 包含音频测试
pytest tests/ -m "audio"

# E2E 完整测试（图像生成 + Vision + 翻译）
python tests/e2e_full_suite.py

# 统一 Benchmark（文本 + 延迟 + 图像）
python scripts/benchmark_unified.py

# 仅文本 Benchmark
python scripts/benchmark_unified.py --skip-image
```

---

## 🗺️ Roadmap

- [x] 核心管控与预算拦截
- [x] Async + Streaming
- [x] 多模态支持 (Vision / TTS / ASR / Image Gen)
- [x] Volcengine Provider (Doubao / DeepSeek)
- [x] 运维报表与 CLI 工具
- [ ] 发布到 PyPI

---

## 🤝 贡献

1. Fork 本仓库
2. 在 `src/my_llm_sdk/providers/` 添加新 Provider
3. 提交 PR

---

## 📄 License

[Apache 2.0](LICENSE)
