# Google Gemini 使用指南

本文档详细介绍 `my-llm-sdk` 对 Google Gemini 系列模型的支持。

---

## 支持的模型

| 别名 | 模型 ID | 能力 |
|:---|:---|:---|
| `gemini-2.5-flash` | gemini-2.5-flash | 文本 / Vision |
| `gemini-2.5-pro` | gemini-2.5-pro | 文本 / Vision / 深度思考 |
| `gemini-3.0-flash` | gemini-3-flash-preview | 文本 / Vision / TTS |
| `gemini-3.0-pro` | gemini-3-pro-preview | 文本 / Vision |
| `gemini-2.5-flash-image` | gemini-2.5-flash-image | 图片生成 |
| `gemini-3-pro-image-preview` | gemini-3-pro-image-preview | 图片生成 (高质量) |
| `imagen-4.0-generate` | imagen-4.0-generate-001 | 图片生成 (Imagen) |
| `gemini-2.5-flash-preview-tts` | gemini-2.5-flash-preview-tts | 语音合成 |

---

## 文本生成

```python
from my_llm_sdk.client import LLMClient

client = LLMClient()

# 基础调用
response = client.generate("你好", model_alias="gemini-2.5-flash")
print(response)

# 获取详细信息 (含 cost/token)
res = client.generate("你好", model_alias="gemini-2.5-flash", full_response=True)
print(f"Cost: ${res.cost}, Tokens: {res.usage.total_tokens}")

# 流式输出
for event in client.stream("数到10", model_alias="gemini-3.0-flash"):
    print(event.delta, end="", flush=True)
```

---

## 图片生成

### 文生图 (Text-to-Image)

```python
res = client.generate(
    "A cyberpunk city street at night, neon lights, rain, highly detailed",
    model_alias="gemini-3-pro-image-preview",
    config={
        "image_size": "2K",       # 可选: 1K (默认), 2K, 4K (仅 Pro)
        "aspect_ratio": "16:9"    # 可选: 1:1, 16:9, 4:5, 3:4, 21:9 等
    },
    full_response=True
)

if res.media_parts:
    with open("output.png", "wb") as f:
        f.write(res.media_parts[0].inline_data)
```

### 图生图 / 混合输入 (Image-to-Image)

```python
from PIL import Image

res = client.generate(
    model_alias="gemini-3-pro-image-preview",
    contents=[
         "Convert this sketch into a photorealistic portrait.", 
         Image.open("sketch.png") 
    ],
    full_response=True
)
```

### 参数参考

| 比例  | 1K 分辨率   | 2K 分辨率   | 4K 分辨率   |
|:------|:------------|:------------|:------------|
| 1:1   | 1024x1024   | 2048x2048   | 4096x4096   |
| 16:9  | 1376x768    | 2752x1536   | 5504x3072   |
| 4:5   | 928x1152    | 1856x2304   | 3712x4608   |

> 更多详情: [Gemini Image Generation Docs](https://ai.google.dev/gemini-api/docs/image-generation)

### 安全拦截处理

图片生成时，Google 会通过 `finish_reason` 指示是否被安全策略拦截：

```python
if res.finish_reason == "safety_blocked":
    # Case A: 安全拦截 (无图片)
    print(f"🛑 生成被拦截! 原因: {res.content}") 
    # 例如: "I cannot create images of specific real people."
    
elif res.media_parts:
    # Case B: 成功生成
    print(f"✅ 生成成功!")
    
else:
    # Case C: 其他异常
    print(f"⚠️ 生成结束但无图片，请检查 Prompt。模型回复: {res.content}")
```

---

## 语音合成 (TTS)

```python
from my_llm_sdk.schemas import GenConfig, TaskType

res = client.generate(
    "你好，我是语音助手。",
    model_alias="gemini-2.5-flash-preview-tts",
    config=GenConfig(task=TaskType.TTS),
    full_response=True
)

if res.media_parts:
    with open("output.wav", "wb") as f:
        f.write(res.media_parts[0].inline_data)
```

---

## 配置示例

在 `llm.project.d/google.yaml` 中定义模型：

```yaml
model_registry:
  gemini-2.5-flash:
    provider: google
    model_id: gemini-2.5-flash
    rpm: 1000
    pricing:
      input_per_1m_tokens: 0.30
      output_per_1m_tokens: 2.50
```

API Key 配置在 `config.yaml`：

```yaml
api_keys:
  google: "AIzaSy..."
```
