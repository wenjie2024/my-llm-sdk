---
level: 2
file_id: plan_03
parent: plan_01
status: pending
created: 2025-12-29 17:00
children: [plan_03_01, plan_03_02]
estimated_time: 360分钟
---

# 模块：预算控制 (Budget Control)

## 1. 模块概述

### 模块目标
实现基于 SQLite 的本地消耗账本 (Ledger)，提供预算拦截能力。防止 API 滥用或意外循环导致的资金损失。

### 在项目中的位置
安全守卫层。`Client` 在发起请求前必须调用 `BudgetIntercepter.check()`，请求后调用 `Ledger.record_transaction()`。

---

## 2. 依赖关系

### 前置条件
- **输入**: `MergedConfig` (需要获取 `daily_spend_limit` 和 `api_keys` 对应的 masked ID).
- **存储**: `~/.cache/llm-sdk/ledger.db` (或类似持久化路径).

### 后续影响
- **输出**: Boolean (Allow/Deny), Exception `QuotaExceeded`.

---

## 3. 子任务分解

- [ ] plan_03_01 - **数据库设计与基础操作 (Ledger)**
  - 简述: 初始化 MySQLite (WAL Mode), 定义 Table `transactions` (id, timestamp, cost, model, status...).
- [ ] plan_03_02 - **拦截器逻辑 (Interceptor)**
  - 简述: 实现 `check_budget()`: `SUM(cost) WHERE date = today > daily_limit`.

---

## 4. 技术方案

### 数据库 Schema

Table `transactions`:
- `id`: TEXT (UUID) PK
- `timestamp`: REAL (Unix epoch) or DATETIME
- `model`: TEXT
- `provider`: TEXT
- `input_tokens`: INTEGER
- `output_tokens`: INTEGER
- `cost`: REAL (USD)
- `status`: TEXT ('success', 'failed')
- `metadata`: TEXT (JSON)

### 关键配置 (Critical)
- **WAL Mode**: `PRAGMA journal_mode=WAL;` 提高并发写入性能。
- **Synchronous**: `PRAGMA synchronous=NORMAL;` 平衡安全与性能。

### 拦截逻辑
```python
def check_availability(limit: float):
    used = db.execute("SELECT SUM(cost) FROM transactions WHERE timestamp >= start_of_day").fetchone()
    if used > limit:
        raise QuotaExceeded()
```

---

## 5. 交付物清单

### 代码
- `src/budget/ledger.py`: 数据库管理。
- `src/budget/interceptor.py`: 业务逻辑。

### 测试
- `tests/test_budget_ledger.py`: 并发写入测试，额度拦截测试。

---
