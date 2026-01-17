# Volcengine (Doubao) 使用指南

本文档详细介绍 `my-llm-sdk` 对字节跳动火山引擎 / 豆包系列模型的支持。

---

## 支持的模型

| 别名 | 模型 ID 示例 | 能力 |
|:---|:---|:---|
| `doubao-thinking` | doubao-seed-1-6-251015 | 深度思考 / Vision |
| `deepseek-v3` | deepseek-v3-2-251201 | 文本 (DeepSeek) |
| `doubao-image` | doubao-seedream-4-5-251128 | 图片生成 |
| `doubao-video` | doubao-seedance-1-0-pro-250528 | 视频生成 |

> 💡 **Model ID 说明**：
> - 上表中的 Model ID 是**公共模型标识符**，可直接使用
> - Model ID 可能随官方更新而变化，请关注 [火山引擎控制台](https://console.volcengine.com/ark) 的最新版本
> - 如需使用私有部署，可将 `model_id` 替换为您创建的接入点 ID（格式如 `ep-xxxxxx`）

---

## 深度思考 (Doubao-Thinking)

```python
from my_llm_sdk.client import LLMClient
from my_llm_sdk.schemas import ContentPart

client = LLMClient()

# 纯文本思考
res = client.generate(
    "分析一下量子计算对密码学的影响",
    model_alias="doubao-thinking",
    config={"thought_mode": "middle"},  # low / middle / high
    full_response=True
)
print(res.content)

# 图文混合输入
res = client.generate(
    model_alias="doubao-thinking",
    contents=[
        ContentPart(type="image", file_uri="diagram.jpg"),
        "这张图里有什么？详细分析。"
    ],
    config={"thought_mode": "high"},
    full_response=True
)
```

---

## DeepSeek V3

```python
res = client.generate(
    "如何实现快速排序？",
    model_alias="deepseek-v3",
    full_response=True
)
print(res.content)
```

---

## 图片生成 (Seedream)

> ⚠️ **重要提示**: Doubao Seedream 模型**强制要求 2K 分辨率**。使用 `1K` 会返回 `InvalidParameter` 错误。

```python
from my_llm_sdk.schemas import TaskType

res = client.generate(
    "一只可爱的小猫在阳光下打盹",
    model_alias="doubao-image",
    config={
        "task": TaskType.IMAGE_GENERATION,
        "image_size": "2K"  # ⚠️ 必须使用 2K
    },
    full_response=True
)

if res.media_parts:
    with open("cat.png", "wb") as f:
        f.write(res.media_parts[0].inline_data)
```

### 高级参数

```python
res = client.generate(
    "...",
    model_alias="doubao-image",
    config={
        "task": TaskType.IMAGE_GENERATION,
        "image_size": "2K",
        "guidance_scale": 7.5,  # CFG Scale
        "watermark": False      # 关闭水印 (默认)
    },
    full_response=True
)
```

---

## 视频生成 (Seedance)

```python
from my_llm_sdk.schemas import TaskType

res = client.generate(
    "无人机以极快速度穿越森林，4K画质",
    model_alias="doubao-video",
    config={
        "task": TaskType.VIDEO_GENERATION,
        "resolution": "1080p",  # 720p / 1080p
        "duration": 5           # 3 / 5 / 10 秒
    },
    full_response=True
)

if res.media_parts:
    print(f"Video URL: {res.media_parts[0].file_uri}")
```

---

## 配置示例

在 `llm.project.d/volcengine.yaml` 中定义模型：

```yaml
# Volcengine (Doubao) Models
# Note: Model IDs may change with official updates.

model_registry:
  doubao-thinking:
    provider: volcengine
    model_id: doubao-seed-1-6-251015  # 公共 Model ID，可能随版本更新
    config:
      thought_mode: "middle"

  doubao-image:
    provider: volcengine
    model_id: doubao-seedream-4-5-251128  # 公共 Model ID
    config:
      image_size: "2K"  # ⚠️ Seedream 强制要求 2K
```

API Key 配置在 `config.yaml`：

```yaml
api_keys:
  volcengine: "your-api-key"

# 可选: 自定义 Endpoint
endpoints:
  - name: "volcengine"
    url: "https://ark.cn-beijing.volces.com/api/v3"
    region: "cn-beijing"
```

---

## 常见问题

### Q: `InvalidParameter` 或 `BadRequest` 错误
A: 常见原因：
1. **图片生成缺少 2K 分辨率**：Seedream 模型必须设置 `image_size: "2K"`
2. **Model ID 过期**：公共 Model ID 可能随官方更新而变化，请检查 [火山引擎控制台](https://console.volcengine.com/ark) 获取最新版本

### Q: 公共 Model ID 和 接入点 ID 有什么区别？
A: 
- **公共 Model ID**（如 `doubao-seed-1-6-251015`）：官方提供的标准模型标识符，所有用户可用
- **接入点 ID**（如 `ep-xxxxxx`）：用户在控制台创建的私有部署端点，仅限本账户使用

