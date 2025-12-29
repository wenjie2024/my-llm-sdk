---
level: 2
file_id: plan_04
parent: plan_01
status: pending
created: 2025-12-29 17:05
children: [plan_04_01]
estimated_time: 180分钟
---

# 模块：诊断模块 (Doctor)

## 1. 模块概述

### 模块目标
提供类似 `brew doctor` 的自检工具。检查网络连通性、配置有效性以及账号额度状态。

### 在项目中的位置
辅助工具层。虽不参与核心 Generate 流程，但对开发者排查环境问题（代理、DNS、Key失效）至关重要。

---

## 2. 依赖关系

### 前置条件
- **输入**: `MergedConfig` (获取 Endpoints 和 Models).
- **网络**: 需使用 `httpx` 发起实际探测请求。

### 后续影响
- **输出**: 诊断报告 (Console Output / JSON).

---

## 3. 子任务分解

- [ ] plan_04_01 - **实现网络探测与诊断逻辑**
  - 简述: 实现 `Doctor` 类，遍历 `final_endpoints`，发送 HEAD 或轻量级 GET 请求检测延时和状态码。同时检查 `api_keys` 格式是否规范。

---

## 4. 技术方案

### 探测策略
1. **Connectivity Check**: 对 Endpoint 的 Base URL 发起 `HEAD` 请求 (timeout=3s).
   - 成功: 200-499 (哪怕 401 也说明网络是通的，只是 Auth 没过).
   - 失败: ConnectionError, Timeout.
2. **Auth Check (Soft)**: (可选) 尝试发送一个仅消耗极少 token 或完全免费的 `models` list 请求，验证 Key 是否有效。因为涉及费用，默认可能关闭或标记为 "Advanced Probe".
   - 本次仅实现 Connectivity Check。

### 输出格式
```text
[✓] Configuration: Valid (Loaded from ...)
[✓] Socket Connect: google.com (Latency: 50ms)
[!] Endpoint: https://api.openai.com
    Status: Unreachable (Connection refused)
    Suggestion: Check your proxy settings.
[✓] Budget: Healthy (Used 10%)
```

---

## 5. 交付物清单

### 代码
- `src/doctor/checker.py`: 核心诊断逻辑。
- `src/doctor/report.py`: 格式化输出。

### 测试
- `tests/test_doctor.py`: Mock `httpx` 验证诊断逻辑对不同 HTTP 状态的反应。

---
