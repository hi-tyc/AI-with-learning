# StudyBuddy Tokens & Pricing 修复计划

## 问题总览

通过全面代码审查，发现以下严重问题：

### 1. 【严重】ai_client.py `extract_usage_sdk` — Kimi cache hit 提取失败
- **文件**: `backend/app/utils/ai_client.py`
- **问题**: `extract_usage_sdk()` 只检查 DeepSeek 的 `prompt_cache_hit_tokens` 字段。对于 Kimi (Moonshot)，cache hit 信息存储在 `cached_tokens` 或 `prompt_tokens_details.cached_tokens` 中，但函数完全未检查这些字段。
- **后果**: 所有 Kimi 调用都报告 hit=0，全部输入按 cache miss 计费，导致费用被严重高估。

### 2. 【严重】pricing.py `get_pricing()` — 潜在的 `dict(None)` 崩溃
- **文件**: `backend/app/core/pricing.py`
- **问题**: 当用户 config 中 override 某个 non-metered provider（如 `kimi_code`）的 pricing 为 dict 时，`base = merged.get(provider, {})` 会返回 `None`，然后 `dict(None)` 抛出 `TypeError`。
- **后果**: 特定配置下后端会直接崩溃。

### 3. 【严重】usage.py — 完全缺少 chat sessions 的用量统计
- **文件**: `backend/app/api/endpoints/usage.py`
- **问题**: `today_usage` 和 `list_usage` 只聚合了 upload/recognition (`usage.json`) 和 solve (`solve_sessions.json`) 的数据，完全没有读取 chat sessions (`{username}_对话_chat_sessions.json`)。
- **后果**: 今日用量、累计花费完全不包含聊天对话的费用，统计数据严重偏低。

### 4. 【严重】admin.py — 管理后台用量统计缺少 chat sessions
- **文件**: `backend/app/api/endpoints/admin.py`
- **问题**: `usage-summary` 端点同样只检查了 `_usage.json` 和 `_solve_sessions.json`，没有 chat sessions。
- **后果**: 管理员看到的用户用量数据不完整。

### 5. 【中等】Chat.vue — 不显示 cache hit tokens
- **文件**: `frontend/src/views/Chat.vue`
- **问题**: 实时用量条和消息 usage 只显示 `miss`（cache miss）作为 input，完全不显示 `hit`（cache hit）。
- **后果**: 用户看到的 "in tokens" 实际上只是 cache miss 部分，total input 被低估显示。

### 6. 【中等】Usage.vue — 只显示 upload/recognition sessions
- **文件**: `frontend/src/views/Usage.vue`
- **问题**: 用量表格只展示 `/usage` 返回的 upload sessions，solve sessions 和 chat sessions 完全不显示。
- **后果**: 用户看不到解题和聊天的用量记录。

---

## 修复分工

### Worker A: 核心定价修复
- 修复 `backend/app/core/pricing.py` — 防御 `dict(None)` 崩溃
- 修复 `backend/app/utils/ai_client.py` — 正确提取 Kimi `cached_tokens`

### Worker B: 后端用量聚合修复
- 修复 `backend/app/api/endpoints/usage.py` — 添加 chat sessions 到 today/list
- 修复 `backend/app/api/endpoints/admin.py` — 添加 chat sessions 到 usage-summary

### Worker C: 前端 Chat.vue 修复
- 修复 `frontend/src/views/Chat.vue` — 显示完整 input tokens (hit+miss)

### Worker D: 前端 Usage.vue 修复
- 修复 `frontend/src/views/Usage.vue` — 显示 solve/chat sessions，区分 hit/miss

## 数据流说明

Chat sessions 存储：
- 会话列表: `{USERS_DIR}/{username}_对话_chat_sessions.json`
- 单会话消息: `{USERS_DIR}/{username}_对话_chat_{session_id}.json`
- 会话元数据包含: `total_tokens`, `total_cost`, `last_usage`

Solve sessions 存储：
- `{USERS_DIR}/{username}_{subject}_solve_sessions.json`
- 记录包含: `input_cache_hit`, `input_cache_miss`, `output`, `cost_yuan`

Upload/recognition 存储：
- `{USERS_DIR}/{username}_{subject}_usage.json`
- 记录包含: `input_cache_hit`, `input_cache_miss`, `output`, `cost_yuan`
