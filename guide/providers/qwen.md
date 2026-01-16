# Qwen (DashScope) 使用指南

本文档详细介绍 `my-llm-sdk` 对阿里云 DashScope / 通义千问系列模型的支持。

---

## 支持的模型

| 别名 | 模型 ID | 能力 |
|:---|:---|:---|
| `qwen-max` | qwen-max | 文本 (旗舰) |
| `qwen-plus` | qwen-plus | 文本 (均衡) |
| `qwen-flash` | qwen-flash | 文本 (快速) |
| `qwen-vl-max` | qwen-vl-max | 视觉理解 |
| `qwen-audio-turbo` | qwen-audio-turbo | 音频理解 |
| `qwen-image-plus` | qwen-image-plus | 图片生成 |
| `qwen3-tts-flash` | qwen3-tts-flash | 语音合成 |
| `qwen-tts-realtime` | qwen-tts-realtime | 语音合成 (WebSocket) |
| `qwen3-asr-flash` | qwen3-asr-flash | 语音识别 |

---

## 文本生成

```python
from my_llm_sdk.client import LLMClient

client = LLMClient()

# 基础调用
response = client.generate("你好", model_alias="qwen-max")
print(response)

# 流式输出
for event in client.stream("讲一个笑话", model_alias="qwen-plus"):
    print(event.delta, end="", flush=True)
```

---

## 图片生成

```python
res = client.generate(
    "一只可爱的柯基犬在草地上奔跑",
    model_alias="qwen-image-plus",
    config={"image_size": "1K"},  # 支持 1K (1024*1024)
    full_response=True
)

if res.media_parts:
    with open("corgi.png", "wb") as f:
        f.write(res.media_parts[0].inline_data)
```

---

## 语音合成 (TTS)

### REST API 方式

```python
from my_llm_sdk.schemas import GenConfig, TaskType

res = client.generate(
    "你好，我是语音助手。",
    model_alias="qwen3-tts-flash",
    config=GenConfig(
        task=TaskType.TTS,
        voice_config={"voice_name": "sambert-zhichu-v1"}
    ),
    full_response=True
)

if res.media_parts:
    with open("output.mp3", "wb") as f:
        f.write(res.media_parts[0].inline_data)
```

### Realtime WebSocket 方式

用于需要低延迟的场景：

```python
res = client.generate(
    "欢迎使用实时语音合成。",
    model_alias="qwen-tts-realtime",
    config=GenConfig(
        task=TaskType.TTS,
        voice_config={"voice_name": "your-cloned-voice-id"}
    ),
    full_response=True
)

# 返回 WAV 格式音频
if res.media_parts:
    with open("realtime_output.wav", "wb") as f:
        f.write(res.media_parts[0].inline_data)
```

---

## 语音识别 (ASR)

```python
from my_llm_sdk.schemas import GenConfig, TaskType, ContentPart

with open("audio.wav", "rb") as f:
    audio_data = f.read()

res = client.generate(
    model_alias="qwen3-asr-flash",
    contents=[ContentPart(type="audio", inline_data=audio_data, mime_type="audio/wav")],
    config=GenConfig(task=TaskType.ASR),
    full_response=True
)

print(f"转录结果: {res.content}")
```

---

## 视觉理解 (Vision)

```python
from my_llm_sdk.schemas import ContentPart

res = client.generate(
    model_alias="qwen-vl-max",
    contents=[
        ContentPart(type="image", file_uri="https://example.com/image.jpg"),
        ContentPart(type="text", text="这张图片里有什么？")
    ],
    full_response=True
)

print(res.content)
```

---

## 配置示例

在 `llm.project.d/qwen.yaml` 中定义模型：

```yaml
model_registry:
  qwen-max:
    provider: dashscope
    model_id: qwen-max
    pricing:
      input_per_1m_tokens: 1.20
      output_per_1m_tokens: 6.00
```

API Key 配置在 `config.yaml`：

```yaml
api_keys:
  dashscope: "sk-..."
```

---

## 网络环境

SDK 会根据网络环境自动切换 Endpoint：
- **国内**: `https://dashscope.aliyuncs.com/api/v1`
- **国际**: `https://dashscope-intl.aliyuncs.com/api/v1`

如需手动配置，可在 `config.yaml` 中设置 `network.proxy_bypass_enabled: true`。
