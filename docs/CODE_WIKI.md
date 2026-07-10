# StudyBuddy AI 伴学系统 — Code Wiki

> 智能解题 · 知识管理 · 多模态学习
> 面向初中生的私有化 AI 学习辅助平台

---

## 目录

1. [项目概览](#1-项目概览)
2. [技术栈总览](#2-技术栈总览)
3. [项目目录结构](#3-项目目录结构)
4. [后端架构详解](#4-后端架构详解)
5. [前端架构详解](#5-前端架构详解)
6. [核心数据流](#6-核心数据流)
7. [API 接口文档](#7-api-接口文档)
8. [关键类与函数说明](#8-关键类与函数说明)
9. [依赖关系与数据存储](#9-依赖关系与数据存储)
10. [项目运行方式](#10-项目运行方式)
11. [开发亮点](#11-开发亮点)

---

## 1. 项目概览

StudyBuddy 是一款面向初中学生的智能学习辅助系统，支持 **数学**、**英语**、**对话** 三种学习模式。系统深度融合 **DeepSeek** 和 **Kimi** 双 AI 模型，提供拍照/PDF 上传识别、智能分步解题、资料自动分类归档、错题管理等完整学习闭环。所有数据以 JSON 文件存储，支持完全私有化部署。

| 模式 | AI 引擎 | 核心能力 |
|------|---------|---------|
| **数学** | DeepSeek + Kimi 自动分流 | 试卷拍照/PDF 上传识别，代数/几何分类，智能解题，题库管理 |
| **英语** | 强制 DeepSeek | 统一上传入口，AI 自动分类（题目/答案/资料），标签归档，答案匹配 |
| **对话** | DeepSeek + Kimi | 通用 AI 对话，支持图片/PDF/Word 上传，多轮会话管理 |

---

## 2. 技术栈总览

### 后端

| 层级 | 技术 | 说明 |
|------|------|------|
| 框架 | FastAPI + Uvicorn | Python 3.13，异步全栈 |
| AI SDK | `openai` (AsyncOpenAI) | 统一封装 DeepSeek / Kimi API |
| 图片处理 | Pillow (PIL) | 图片压缩、格式转换 |
| PDF 处理 | PyMuPDF (fitz) | PDF 文本提取、页面转图片 |
| Word 解析 | zipfile + xml.etree.ElementTree | 零依赖提取 docx 文本 |
| OCR | pytesseract (可选) | 本地 OCR 后备方案 |
| 数据存储 | JSON 文件 | 按用户+学科隔离，asyncio.Lock 并发安全 |
| 流式传输 | StreamingResponse (SSE) | 上传进度 + 解题结果实时推送 |

### 前端

| 层级 | 技术 |
|------|------|
| 框架 | Vue 3 (Composition API, `<script setup>`) |
| 构建 | Vite 5 |
| UI 组件库 | Element Plus + Element Plus Icons |
| 状态管理 | Pinia |
| 路由 | Vue Router (Hash History) |
| HTTP | Axios（拦截器：全局 Loading / 错误处理 / 401 跳转） |
| 公式渲染 | KaTeX + markdown-it（LaTeX 与 Markdown 混排） |
| 样式 | Liquid Glass UI，深色/浅色自适应 |

---

## 3. 项目目录结构

```
AI伴学/
│
├── start.bat                  # 一键启动脚本（端口探测 + 健康检查 + 自动打开浏览器）
├── stop.bat                   # 一键停止所有服务
├── README.md                  # 项目说明文档
├── 使用指南.md                 # 用户使用文档
├── 开发指南.md                 # 原始需求 / 开发任务书
├── CODE_WIKI.md               # 本文件 — 代码知识库
│
├── backend/                   # Python 后端
│   ├── main.py                # FastAPI 应用入口 + CORS + 静态文件挂载
│   ├── requirements.txt       # Python 依赖声明
│   ├── .env                   # 环境变量（默认配置 fallback）
│   ├── run_srv.bat            # 后端单独启动脚本
│   ├── start_server.bat       # 服务器启动脚本
│   ├── start.vbs              # VBS 启动方式
│   ├── app/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # 路由汇总（集中注册所有端点）
│   │   │   └── endpoints/     # 16 个路由模块（17 个 .py 文件，含空 __init__.py）
│   │   ├── core/              # 核心配置、路径、定价、用户数据、费用熔断
│   │   ├── services/          # 预留服务层（当前为空）
│   │   └── utils/             # AI 客户端、文件锁
│   └── data/                  # 运行时数据（用户 / 题库 / 用量 / 上传文件）
│       ├── users/             # 所有用户数据 JSON 文件
│       ├── admin.json         # 管理员密码哈希
│       ├── shared/            # 共享数据目录
│       └── memory/            # 记忆系统数据
│
├── frontend/                  # Vue 3 前端
│   ├── package.json           # 前端依赖声明
│   ├── vite.config.js         # Vite 配置（代理 /api → 后端）
│   ├── index.html             # HTML 入口
│   └── src/
│       ├── main.js            # Vue 应用入口（注册 Element Plus / Pinia / Router）
│       ├── App.vue            # 根组件（布局切换逻辑）
│       ├── router/index.js    # 路由配置（含学科守卫 + 管理员守卫）
│       ├── stores/            # Pinia 状态管理
│       ├── components/        # 通用组件
│       ├── views/             # 页面视图
│       ├── api/               # 预留 API 适配层（当前为空）
│       └── utils/             # 工具函数
│
├── tests/                     # 测试文件
│
└── temp/                      # 临时文件目录
```

---

## 4. 后端架构详解

### 4.1 应用入口 (`backend/main.py`)

FastAPI 应用初始化流程：

1. **配置加载** — 从 `app.core.config.Settings` 读取环境变量
2. **目录创建** — `ensure_dirs()` 确保 `uploads/`、`data/users/`、`data/shared/`、`data/memory/` 存在
3. **CORS 配置** — 自动检测本地所有 IPv4 地址加入白名单，支持 `VITE_ALLOWED_ORIGINS` 环境变量注入
4. **路由注册** — `app.include_router(api_router, prefix="/api")`
5. **静态文件挂载** — `/data` 映射到 `DATA_DIR`
6. **健康检查** — `GET /health` 端点

```python
# 关键代码结构
app = FastAPI(lifespan=lifespan)  # lifespan 处理启动/关闭
app.add_middleware(CORSMiddleware, ...)
app.include_router(api_router, prefix="/api")
app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")
```

### 4.2 路由注册 (`app/api/router.py`)

所有端点统一在此文件注册。共 **16 个路由模块**，按功能域划分前缀：

| 路由前缀 | 端点文件 | 说明 |
|---------|---------|------|
| `/api/auth` | `auth.py` | 登录/注册/学科选择/用户资料 |
| `/api/settings` | `settings_api.py` | 系统配置 CRUD + 连接测试 |
| `/api/upload` | `upload.py` | 数学上传（图片/PDF + Kimi 识别） |
| `/api/english-upload` | `english_upload.py` | 英语上传（AI 分类 + 三库存储） |
| `/api/problems` | `problems.py` | 题库 CRUD + 错题管理 + 废纸篓 |
| `/api/problems` | `solve.py` | 智能解题（SSE 流式 + 模型分流） |
| `/api/solve-sessions` | `solve_sessions.py` | 解题记录管理 |
| `/api/sessions` | `sessions.py` | 上传会话管理 |
| `/api/paths` | `paths.py` | 路径重命名/创建/删除 |
| `/api/materials` | `materials.py` | 复习资料管理（标签分组） |
| `/api/match-answers` | `match_answers.py` | 英语答案匹配（AI 配对） |
| `/api/memory` | `memory.py` | 记忆系统（画像/摘要） |
| `/api/usage` | `usage.py` | 用量统计与查询 |
| `/api/chat` | `chat.py` | 对话模式（多轮会话） |
| `/api/admin` | `admin.py` | 状态监控/用户管理/日志 |
| `/api/library-trash` | `library_trash.py` | 资料回收站 |
| `/api/english-wrong` | `english_wrong.py` | 英语错题本 |

### 4.3 核心层 (`app/core/`)

#### 4.3.1 `config.py` — 系统配置

```python
class Settings(BaseSettings):
    SECRET_KEY: str = "study-buddy-secret-key-2024"
    BACKEND_PORT: int = 6003
    UPLOAD_DIR: str = "./data/uploads"
    DATA_DIR: str = "./data"
```

使用 `pydantic-settings` 从 `.env` 文件读取环境变量。

#### 4.3.2 `paths.py` — 路径管理

定义所有关键目录路径，使用 `os.path.join` 而非 `pathlib.Path` 以兼容 Windows 中文路径。

```python
BASE_DIR = _resolve_base()      # 项目根目录
UPLOAD_DIR = ...                 # 上传文件存储
DATA_DIR = ...                   # 数据根目录
USERS_DIR = ...                  # 用户数据目录
SHARED_DIR = ...                 # 共享数据目录
MEMORY_DIR = ...                 # 记忆数据目录
```

#### 4.3.3 `user_data.py` — 用户数据路径

按 `{username}_{subject}_{suffix}.json` 模式生成文件路径，确保学科隔离。核心函数：

| 函数 | 返回路径 |
|------|---------|
| `get_user_path(username)` | `{username}.json`（用户资料） |
| `get_user_config_path(username)` | `{username}_config.json`（系统配置） |
| `get_problems_path(username, subject)` | `{username}_{subject}_problems.json`（题库） |
| `get_wrong_path(username, subject)` | `{username}_{subject}_wrong.json`（错题） |
| `get_sessions_path(username, subject)` | `{username}_{subject}_sessions.json`（会话） |
| `get_usage_path(username, subject)` | `{username}_{subject}_usage.json`（用量） |
| `get_solve_sessions_path(username, subject)` | `{username}_{subject}_solve_sessions.json`（解题记录） |
| `get_materials_path(username, subject)` | `{username}_{subject}_materials.json`（资料） |
| `get_answers_path(username, subject)` | `{username}_{subject}_answers.json`（答案库） |
| `get_words_path(username, subject)` | `{username}_{subject}_words.json`（词单） |
| `get_trash_path(username, subject)` | `{username}_{subject}_trash.json`（废纸篓） |

#### 4.3.4 `pricing.py` — 计费引擎

基于 OpenAI SDK 返回的 usage 对象计算 API 调用费用。支持 DeepSeek 和 Kimi 全系模型，价格基于官方定价。

```python
DEFAULT_PRICING = {
    "kimi_k25":       {"input_cache_hit": 0.70, "input_cache_miss": 4.00, "output": 21.0},
    "kimi_k26":       {"input_cache_hit": 1.10, "input_cache_miss": 6.50, "output": 27.0},
    "deepseek_flash": {"input_cache_hit": 0.02,  "input_cache_miss": 1.0, "output": 2.0},
    "deepseek_pro":   {"input_cache_hit": 0.025, "input_cache_miss": 3.0, "output": 6.0},
    "kimi_code": None,  # 包月计费，不按 token
}
```

关键函数：
- `get_pricing(config)` — 深度合并用户自定义定价覆盖
- `extract_usage(usage)` — 规范化不同提供商的 usage 对象为 `(hit, miss, out)` 三元组
- `compute_cost(provider, hit, miss, out, pricing)` — 计算人民币花费

#### 4.3.5 `admin_auth.py` — 管理员认证

管理员密码以 SHA-256 哈希存储在 `data/admin.json` 中。支持修改密码功能。初始密码为 `admin123`。

#### 4.3.6 `daily_cost.py` — 每日费用熔断

内存中按用户累计当日 API 花费，达到每日上限后自动拒绝新请求。

```python
daily_costs: dict[str, float] = {}      # username -> 当日累计花费
daily_cost_date: str = ""                # 当前计数日期
_cost_lock = asyncio.Lock()              # 并发安全
```

关键函数：
- `check_daily_limit(username, daily_limit)` — 检查用户是否未达每日上限
- `add_daily_cost(username, cost)` — 将本次花费累加到用户当日总额
- `_check_daily_reset()` — 跨天时清空计数器

> 注：计数器为进程内存，单进程部署时足够；多 Uvicorn worker 部署时各进程独立计数。

### 4.4 工具层 (`app/utils/`)

#### 4.4.1 `ai_client.py` — AI 客户端工厂

```python
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
KIMI_BASE_URL = "https://api.moonshot.cn/v1"
```

- `create_client(api_key, base_url, timeout)` — 创建 AsyncOpenAI 客户端实例，共享全局 httpx 连接池
- `extract_reasoning(delta)` — 从流式响应 delta 中提取 reasoning_content（推理过程）
- `extract_usage_sdk(usage)` — 从 SDK CompletionUsage 对象提取 token 用量

#### 4.4.2 `file_lock.py` — 异步文件锁

JSON 文件的并发安全读写解决方案：

```python
async def read_json(path)         # 读取 JSON（带文件锁）
async def write_json(path, data)  # 原子写入（.tmp → os.replace）
async def update_json(path, updater)  # 读-改-写原子操作
```

关键特性：
- **asyncio.Lock 互斥** — 每个文件有独立的锁
- **原子写入** — 先写 `.tmp` 临时文件，再 `os.replace` 替换
- **崩溃恢复** — JSON 解析失败时自动将损坏文件重命名为 `.bak`

### 4.5 关键端点详解

#### 4.5.1 `auth.py` — 认证系统

基于 Cookie Session 的轻量认证：

```
POST /api/auth/login    → 登录/注册（root 需要密码验证）
GET  /api/auth/me       → 获取当前用户信息
POST /api/auth/logout   → 退出登录
PUT  /api/auth/me       → 更新用户资料（年级/学校/偏好）
PUT  /api/auth/subject  → 切换学科
```

- 首次登录用户自动创建用户文件和配置
- 管理员（root）密码验证基于 SHA-256 哈希
- Session 存储于服务端内存字典，Cookie 设置 `httponly`

#### 4.5.2 `solve.py` — 智能解题

流式 SSE 输出，核心解题管线：

```
POST /api/problems/{problem_id}/solve  → 解指定题目（支持子题 / 大题）
POST /api/problems/solve               → 自由输入解题
```

**模型自动分流逻辑**（`_select_model`）：
| 条件 | 选择模型 |
|------|---------|
| strategy 指定 `kimi` | Kimi |
| strategy 指定 `deepseek` | DeepSeek |
| 题目含几何图 (`has_figure`) | Kimi（Vision 能力） |
| 其他情况 | DeepSeek（性价比高） |

**解题流程**：
1. 检查每日费用上限（熔断机制）
2. 构建 System Prompt（含年级/偏好）
3. 构建 User Content（题目文本 + 图片 + 资料引用）
4. 调用 AI 流式接口，输出 SSE 事件流
5. 事件类型：`content` / `reasoning` / `usage` / `progress` / `error`
6. 保存解题记录到 `solve_sessions.json`
7. 更新题目 `solution` 字段

#### 4.5.3 `upload.py` — 数学上传识别

```
POST /api/upload                   → 上传文件（返回 file_id）
POST /api/upload/recognize         → 识别（非流式）
POST /api/upload/recognize_stream  → 识别（流式 SSE）
```

**PDF 智能分流**：
- 文本页（`text_len >= 200` 且图片少）→ 直接提取文字，零 token 消耗
- 扫描页（`text_len < 200` 或图片多）→ 转为 JPEG 图片供 Kimi Vision 识别

**几何题模式**：
- 直接保存原图，不上传 Kimi 识别（content 设为 `[几何题，图片见配图]`）

#### 4.5.4 `english_upload.py` — 英语上传

```
POST /api/english-upload/classify  → 上传并 AI 分类（SSE 流式）
POST /api/english-upload/adjust-type  → 调整文档类型（重新 AI 提取）
POST /api/english-upload/extract-known  → 用户指定类型后 AI 提取
```

**AI 分类提示词** — 使用精心设计的 CLASSIFY_PROMPT，按优先级判断：
1. 文件名含「学生版」→ 题目
2. 文件名含「教师版」/「答案版」/「解析版」/「详解版」→ 答案
3. 纯单词对照表 → 词单
4. 知识点归纳/语法讲解/课文注解 → 资料

**文件名规则预分类** — `_classify_by_filename()` 函数在零 API 费用下完成分类

**上传流程**：
1. 文件解析（图片/pdf/docx）
2. OCR 文字提取（优先 Kimi Vision，后备 pytesseract）
3. AI 分类（文件名规则 → 文本规则 → DeepSeek 调用）
4. 内容提取（题目逐题 / 答案逐条 / 词单逐词）
5. 自动存储到对应数据库，去重机制

#### 4.5.5 `chat.py` — 对话模式

```
POST /api/chat/send               → 发送消息（支持文件上传，SSE 流式）
GET  /api/chat/sessions           → 列出所有对话
POST /api/chat/sessions           → 创建新对话
GET  /api/chat/sessions/{id}      → 获取对话消息
DELETE /api/chat/sessions/{id}    → 删除对话
```

- 图片 → Kimi Vision 处理（自动强制 Kimi）
- PDF → 提取文本后注入 Prompt
- Word → zipfile 零依赖提取文本
- 对话消息存储为 `{username}_对话_chat_{id}.json`

#### 4.5.6 `admin.py` — 管理面板

```
GET  /api/admin/status            → 系统状态概览
GET  /api/admin/users             → 用户列表
GET  /api/admin/users/{username}  → 用户详情
DELETE /api/admin/users/{username} → 删除用户
POST /api/admin/change-password   → 修改管理员密码
GET  /api/admin/logs              → 系统日志
GET  /api/admin/usage-summary     → 全量用户用量统计
GET  /api/admin/info              → 系统信息
POST /api/admin/purge-temp        → 清理临时文件
POST /api/admin/diagnose          → 诊断检查
```

#### 4.5.7 `problems.py` — 题库管理

```
GET    /api/problems           → 列表（支持路径/关键词/知识点/错题筛选 + 分页）
POST   /api/problems           → 创建题目
GET    /api/problems/{id}      → 题目详情（大题时含子题列表）
PUT    /api/problems/{id}      → 更新题目
DELETE /api/problems/{id}      → 删除（移入废纸篓）
POST   /api/problems/{id}/toggle-wrong  → 切换错题标记
GET    /api/problems/trash     → 废纸篓列表
POST   /api/problems/trash/restore  → 从废纸篓恢复
POST   /api/problems/trash/empty    → 清空废纸篓
POST   /api/problems/batch-delete   → 批量删除
```

#### 4.5.8 `usage.py` — 用量统计

```
GET /api/usage          → 历史用量汇总（含 DeepSeek/Kimi 分别统计）
GET /api/usage/today    → 今日用量（从 usage + solve_sessions + chat_sessions 聚合）
DELETE /api/usage/{id}  → 删除用量记录
```

---

## 5. 前端架构详解

### 5.1 应用入口 (`src/main.js`)

```javascript
// 注册 Element Plus + Icons + Pinia + Router
app.use(ElementPlus)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

### 5.2 根组件 (`App.vue`)

根据当前路由决定是否显示 `AppLayout`（登录页不显示布局）。

### 5.3 路由系统 (`src/router/index.js`)

使用 **Hash History** 模式，共 **22 个路由条目**（含 redirect）：

| 路由 | 页面 | 学科 | 说明 |
|------|------|------|------|
| `/login` | Login.vue | - | 登录页 |
| `/upload` | Upload.vue | 数学 | 数学上传 |
| `/solve` | Solve.vue | 数学 | 数学解题首页 |
| `/manage` | Manage.vue | 数学 | 数学题库管理 |
| `/library` | Manage.vue | 数学 | 重定向至 `/manage` |
| `/problem/:id` | ProblemDetail.vue | 数学 | 题目详情 |
| `/usage` | Usage.vue | 数学 | 数学用量统计 |
| `/english-upload` | EnglishUpload.vue | 英语 | 英语上传 |
| `/english/solve` | english/Solve.vue | 英语 | 英语解题 |
| `/english/library` | english/Library.vue | 英语 | 英语资料库 |
| `/english/doc/:sourceFile` | english/DocDetail.vue | 英语 | 英语文档详情 |
| `/english/usage` | english/Usage.vue | 英语 | 英语用量统计 |
| `/english/wrong-book` | english/WrongBook.vue | 英语 | 英语错题本 |
| `/english` | - | 英语 | 重定向至 `/english-upload` |
| `/chat` | Chat.vue | 对话 | 通用对话 |
| `/settings/system` | SystemSettings.vue | - | 系统设置 |
| `/settings/profile` | Profile.vue | - | 个人资料 |
| `/settings` | - | - | 重定向至 `/settings/system` |
| `/` | - | - | 重定向至 `/solve` |
| `/admin` | Admin.vue | 管理员 | 管理员面板 |

**路由守卫逻辑**（`beforeEach`）：

1. **认证守卫** — 非登录路径检查登录状态，未登录跳转 `/login`
2. **管理员守卫** — root 用户自动跳转 `/admin`，非管理员禁止访问 admin 路由
3. **学科守卫** — 确保用户在正确的学科前端（如英语用户不能访问 `/solve`）
4. **用量重置** — `afterEach` 切换页面时重置当前会话用量

### 5.4 状态管理 (Pinia)

#### `stores/auth.js` — 认证状态

```javascript
state: { user, isLoggedIn, subject }
actions: login(), logout(), fetchMe(), switchSubject()
```

- Axios 全局配置：`baseURL: '/api'`，`withCredentials: true`
- **全局 Loading** — 请求拦截器延迟 300ms 显示 Element Plus 全屏 Loading
- **错误处理** — 自动处理 401（跳转登录）、429（频率限制）、500（服务器错误）、Network Error

#### `stores/app.js` — 应用状态

```javascript
state: {
  activeTab,           // 当前激活的侧边栏标签
  currentSubject,      // 当前学科
  tabs,                // 动态标签列表（按学科切换）
  sessions,            // 会话列表
  activeSessionId,     // 当前会话
  currentSessionUsage, // 当前操作用量
  todayUsage,          // 今日累计用量
}
```

`tabs` 计算属性根据 `currentSubject` 返回不同的功能标签组：
- 数学：录入 → 解题 → 管理 → 题库 → 用量
- 英语：录入 → 解题 → 资料 → 错题 → 用量
- 对话：对话

#### `api/` 目录说明

`frontend/src/api/` 目录当前为空，项目中未使用独立的 API 适配层。所有 HTTP 请求直接在视图组件或 Pinia Store 中通过 Axios 发起，`baseURL` 统一设置为 `/api`。

### 5.5 组件架构

#### `components/AppLayout.vue` — 主布局

三栏布局：`SidebarLeft`（左导航） → `main`（主内容区） → `SidebarRight`（右面板）

- 支持移动端响应式：侧边栏变为抽屉式菜单
- 移动端顶部导航栏含汉堡菜单按钮

#### `components/SidebarLeft.vue` — 左侧导航

根据角色显示不同内容：
- **管理员**：系统概览 → 用户管理 → 用量统计 → 系统日志 → 修改密码
- **数学用户**：功能标签 + 题目列表（含废纸篓 + 批量操作）
- **英语用户**：功能标签 + 提示文本
- **对话用户**：功能标签 + 提示文本

#### `components/SidebarRight.vue` — 右侧信息面板

显示当前解题会话的用量信息（input tokens / output tokens / 花费）。

#### `components/NavBar.vue` — 顶部导航栏

### 5.6 核心页面

#### `Login.vue` — 登录页

- 学科选择（数学/英语/对话）+ 用户名输入
- root 管理员需要额外密码
- 登录成功后跳转到对应学科的首页

#### `Solve.vue` — 数学解题页

支持三种解题方式：
- **解大题** — 从题库选择一道大题
- **解小题** — 从题库选择一道小题
- **自由输入** — 直接输入题目文本

解题参数：策略（auto/geometry/no_geometry）、引擎（auto/kimi/deepseek）、推理深度（1-10）、资料引用

#### `Manage.vue` — 题库管理页

树形路径浏览 + 题目编辑 + 批量管理。支持按 `subject/exam/source/school/big_question/small_question` 路径层级组织。

#### `Upload.vue` — 数学上传页

支持图片/PDF 上传，流式显示识别进度和结果。深色终端面板实时展示 AI 分析日志。

#### `EnglishUpload.vue` — 英语上传页

多文件上传 + 标签选择 + 流式进度展示。AI 自动分类后展示结果。

#### `Library.vue` — 数学题库浏览页

按路径树/关键词/知识点筛选题目，支持分页、错题筛选、删除操作。当前已重定向至 `/manage` 统一管理。

#### `Materials.vue` — 数学资料管理页（遗留）

资料上传与标签分组管理页面，代码完整但**当前未在路由中注册**，无法通过导航直接访问。

#### `english/Usage.vue` — 英语用量统计页

展示英语模式下的 AI 调用记录与花费，与数学用量页独立统计。

#### `english/WrongBook.vue` — 英语错题本页

集中管理英语错题（题目/答案/单词），支持生成错题卷。

#### `Chat.vue` — 对话页

多轮会话管理，支持 DeepSeek/Kimi 切换，文件上传，推理过程显示。

#### `SystemSettings.vue` — 系统设置页

API Key 配置、模型版本选择、压缩参数、超时设置、每日上限、连接测试。

### 5.7 公式渲染 (`utils/mathRender.js`)

```javascript
import MarkdownIt from 'markdown-it'
import katex from 'katex'

export function renderMath(text) {
  // 1. 提取 LaTeX 数学块（$$..$$ / \[..\] / \(..\) / $..$）
  // 2. 用 KaTeX 渲染为 HTML
  // 3. 用 markdown-it 渲染 Markdown
  // 4. 将 KaTeX HTML 插回
}
```

优先渲染块级公式（`$$...$$`），再渲染行内公式（`$...$`），避免冲突。

---

## 6. 核心数据流

### 6.1 数学解题流程

```
用户上传试卷图片/PDF
        ↓
Kimi Vision 识别题目（SSE 流式推送进度）
        ↓
题目结构化存入题库 (problems.json)
        ↓
用户在解题页选择题目/自由输入
        ↓
模型自动分流（含图→Kimi，纯文本→DeepSeek）
        ↓
AI 流式输出解题过程（SSE: content / reasoning / usage）
        ↓
前端实时渲染 LaTeX 公式 + 思维链
        ↓
解题记录存入 solve_sessions.json
        ↓
题目 solution 字段更新
        ↓
用量统计更新（每日费用熔断检查）
```

### 6.2 英语上传分类流程

```
用户上传 PDF/Word/图片 + 选择标签
        ↓
文件解析（PDF→文本+图片 / Word→Markdown / 图片→OCR）
        ↓
文件名规则分类（零费用）：学生版→题目 / 教师版→答案 / 完整词单→词单 / 知识点→资料
        ↓
未命中则调用 DeepSeek 分类
        ↓
根据分类结果执行不同提取逻辑：
  ├─ 题目 → 逐题提取 → 存入 problems.json（去重）
  ├─ 答案 → 逐条提取 → 存入 answers.json（去重）
  ├─ 词单 → 逐词提取 → 存入 words.json
  └─ 资料 → 直接保存 → 存入 materials.json（去重）
        ↓
AI 调用用量记录到 usage.json
```

### 6.3 费用管控流程

```
每次 API 调用后：
        ↓
extract_usage() 提取 token 用量
        ↓
compute_cost() 计算花费
        ↓
累加至 daily_costs[username]（内存字典）
        ↓
下次调用前检查是否超限
        ↓
超限则返回 429 "今日 API 花费已达上限"
```

---

## 7. API 接口文档

由于代码中没有自动生成 OpenAPI 文档的额外配置，FastAPI 自带的 `/docs` 和 `/redoc` 在启动后可用。以下是主要 API 接口列表：

### 认证 /auth

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| POST | `/api/auth/login` | 登录/注册 | `{username, password?, subject}` |
| GET | `/api/auth/me` | 获取用户信息 | - |
| POST | `/api/auth/logout` | 退出 | - |
| PUT | `/api/auth/me` | 更新资料 | `{grade?, school?, preferences?}` |
| GET | `/api/auth/subject` | 获取当前学科 | - |
| PUT | `/api/auth/subject` | 切换学科 | `{subject}` |

### 设置 /settings

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 获取系统配置 |
| PUT | `/api/settings` | 保存系统配置 |
| POST | `/api/settings/test/deepseek` | 测试 DeepSeek 连接 |
| POST | `/api/settings/test/kimi` | 测试 Kimi 连接 |

### 上传 /upload (数学)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传文件（返回 file_id） |
| POST | `/api/upload/recognize` | Kimi 识别（非流式） |
| POST | `/api/upload/recognize_stream` | Kimi 识别（SSE 流式） |

### 英语上传 /english-upload

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/english-upload/classify` | 上传并 AI 分类（SSE） |
| POST | `/api/english-upload/adjust-type` | 调整文档类型后重新提取 |
| POST | `/api/english-upload/extract-known` | 用户指定类型后提取 |
| GET | `/api/english-upload/answers` | 答案列表 |
| GET | `/api/english-upload/answers/tags` | 答案标签列表 |
| DELETE | `/api/english-upload/answers/{id}` | 删除答案 |
| PUT | `/api/english-upload/answers/{id}` | 更新答案 |
| POST | `/api/english-upload/answers/batch-delete` | 批量删除答案 |
| GET | `/api/english-upload/words` | 词单列表 |
| GET | `/api/english-upload/words/tags` | 词单标签列表 |
| PUT | `/api/english-upload/words/{word_id}` | 更新词单元数据 |
| DELETE | `/api/english-upload/words/{word_id}` | 删除词单 |
| POST | `/api/english-upload/words/{word_id}/words` | 添加单词 |
| PUT | `/api/english-upload/words/{word_id}/words/{word_idx}` | 更新单词 |
| DELETE | `/api/english-upload/words/{word_id}/words/{word_idx}` | 删除单词 |
| PUT | `/api/english-upload/words/{word_id}/words` | 批量更新单词 |

### 解题 /problems (数学)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/problems/{id}/solve` | 解指定题目（SSE） |
| POST | `/api/problems/solve` | 自由解题（SSE） |
| GET | `/api/problems` | 题目列表（筛选+分页） |
| POST | `/api/problems` | 创建题目 |
| GET | `/api/problems/{id}` | 获取题目 |
| PUT | `/api/problems/{id}` | 更新题目 |
| DELETE | `/api/problems/{id}` | 删除题目（移入废纸篓） |
| POST | `/api/problems/{id}/toggle-wrong` | 切换错题标记 |
| POST | `/api/problems/batch-delete` | 批量删除 |
| GET | `/api/problems/trash` | 废纸篓 |
| POST | `/api/problems/trash/restore` | 恢复 |
| POST | `/api/problems/trash/empty` | 清空 |

### 上传会话 /sessions

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sessions` | 会话列表 |
| POST | `/api/sessions` | 创建会话 |
| PUT | `/api/sessions/{id}` | 更新会话 |
| DELETE | `/api/sessions/{id}` | 删除会话 |
| GET | `/api/sessions/{id}/problems` | 会话下的题目 |
| POST | `/api/sessions/{id}/move-problems` | 批量移动题目 |

### 解题记录 /solve-sessions

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/solve-sessions` | 解题历史 |
| POST | `/api/solve-sessions` | 创建解题记录 |
| GET | `/api/solve-sessions/{id}` | 获取详情 |
| DELETE | `/api/solve-sessions/{id}` | 删除 |

### 复习资料 /materials

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/materials` | 上传资料 |
| GET | `/api/materials` | 资料列表 |
| GET | `/api/materials/tree` | 按路径树展示 |
| GET | `/api/materials/tags` | 资料标签列表 |
| GET | `/api/materials/tree_by_time` | 按时间归档树 |
| GET | `/api/materials/subjects` | 学科列表 |
| GET | `/api/materials/{id}` | 资料详情 |
| GET | `/api/materials/{id}/text` | 资料文本内容 |
| DELETE | `/api/materials/{id}` | 删除资料 |

### 记忆 /memory

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/memory` | 获取记忆画像/摘要 |
| POST | `/api/memory/force-summary` | 强制生成会话摘要 |

### 用量 /usage

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/usage` | 历史用量 |
| GET | `/api/usage/today` | 今日用量 |
| DELETE | `/api/usage/{id}` | 删除记录 |

### 英语答案匹配 /match-answers

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/match-answers/run` | 批量运行题目-答案匹配 |
| POST | `/api/match-answers/run-for-pair` | 为指定文件对运行匹配 |
| POST | `/api/match-answers/run-word-match` | 运行词单匹配 |
| GET | `/api/match-answers/for-problem/{problem_id}` | 题目的候选答案 |
| GET | `/api/match-answers/for-answer/{answer_id}` | 答案的候选题目 |
| GET | `/api/match-answers/word-match/{word_id}` | 词单匹配结果 |
| GET | `/api/match-answers/status` | 匹配任务状态 |
| POST | `/api/match-answers/reset` | 重置匹配状态 |
| GET | `/api/match-answers/unmatched` | 未匹配题目/答案 |
| GET | `/api/match-answers/unmatched-files` | 未配对文件 |
| GET | `/api/match-answers/file-pairs` | 文件配对列表 |
| POST | `/api/match-answers/file-pairs` | 添加文件配对 |
| DELETE | `/api/match-answers/file-pairs` | 删除文件配对 |
| POST | `/api/match-answers/manual-match` | 手动建立题目-答案映射 |
| DELETE | `/api/match-answers/manual-match` | 删除手动映射 |

### 英语错题本 /english-wrong

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/english-wrong/list` | 错题列表 |
| GET | `/api/english-wrong/exam-tags` | 考试标签 |
| POST | `/api/english-wrong/add` | 添加题目/答案到错题 |
| POST | `/api/english-wrong/add-words` | 添加单词到错题 |
| POST | `/api/english-wrong/remove` | 移除错题 |
| POST | `/api/english-wrong/toggle-problem/{problem_id}` | 切换题目错题标记 |
| POST | `/api/english-wrong/toggle-answer/{answer_id}` | 切换答案错题标记 |
| POST | `/api/english-wrong/toggle-word/{word_list_id}/{word_index}` | 切换单词错题标记 |
| GET | `/api/english-wrong/check/{problem_id}` | 检查题目是否在错题本 |
| GET | `/api/english-wrong/check-answer/{answer_id}` | 检查答案是否在错题本 |
| GET | `/api/english-wrong/check-word/{word_list_id}/{word_index}` | 检查单词是否在错题本 |
| POST | `/api/english-wrong/generate` | 生成错题卷 |

### 资料回收站 /library-trash

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/library-trash` | 回收站列表 |
| POST | `/api/library-trash/restore` | 恢复项目 |
| POST | `/api/library-trash/empty` | 清空回收站 |
| DELETE | `/api/library-trash/{item_id}` | 删除项目 |

### 对话 /chat

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/send` | 发送消息（SSE） |
| GET | `/api/chat/sessions` | 会话列表 |
| POST | `/api/chat/sessions` | 创建会话 |
| GET | `/api/chat/sessions/{id}` | 获取消息 |
| DELETE | `/api/chat/sessions/{id}` | 删除会话 |
| GET | `/api/chat/sessions/{id}/usage` | 会话用量 |

### 管理员 /admin

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/status` | 系统状态 |
| GET | `/api/admin/users` | 用户列表 |
| GET | `/api/admin/users/{username}` | 用户详情 |
| DELETE | `/api/admin/users/{username}` | 删除用户 |
| POST | `/api/admin/change-password` | 修改密码 |
| GET | `/api/admin/logs` | 系统日志 |
| GET | `/api/admin/usage-summary` | 用量汇总 |
| GET | `/api/admin/info` | 系统信息 |
| POST | `/api/admin/diagnose` | 诊断 |
| POST | `/api/admin/purge-temp` | 清理临时文件 |

### 运维

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | API 根 |
| GET | `/health` | 健康检查 |

---

## 8. 关键类与函数说明

### 8.1 后端关键函数

| 函数 | 所在文件 | 说明 |
|------|---------|------|
| `get_current_user(request)` | `auth.py` | Cookie Session 认证依赖注入 |
| `_do_solve()` | `solve.py` | 核心解题协程（SSE 生成器） |
| `_call_deepseek()` | `solve.py` | AI 流式调用封装（支持 DeepSeek/Kimi） |
| `_select_model()` | `solve.py` | 模型自动分流逻辑 |
| `_build_system_prompt()` | `solve.py` | 构建 System Prompt（含年级/偏好） |
| `_build_user_content()` | `solve.py` | 构建 User Content（含图片/PDF/资料引用） |
| `_pricing_key()` | `solve.py` | 模型名 → 定价键映射 |
| `_compress_image()` | `upload.py` | Pillow 图片压缩（质量/长边控制） |
| `_pdf_to_pages()` | `upload.py` | PDF 每页转 JPEG 图片 |
| `_recognize_with_kimi()` | `upload.py` | Kimi Vision 识别数学试卷 |
| `_classify_by_filename()` | `english_upload.py` | 文件名规则分类（零费用） |
| `_extract_with_ai()` | `english_upload.py` | DeepSeek 提取题目/答案/词单 |
| `_docx_to_markdown()` | `english_upload.py` | Word 文档 → Markdown 转换 |
| `_compress_image()` | `chat.py` | 对话模式的图片压缩 |
| `read_json()` / `write_json()` | `file_lock.py` | 异步安全 JSON 读写 |
| `update_json()` | `file_lock.py` | 原子读-改-写操作 |
| `_mask_key()` | `settings_api.py` | API Key 显示脱敏 |
| `compute_cost()` | `pricing.py` | Token → 人民币计费 |
| `extract_usage()` | `pricing.py` | 标准化 usage 对象 |
| `get_pricing()` | `pricing.py` | 获取完整定价表 |
| `check_daily_limit()` | `daily_cost.py` | 检查用户当日花费是否超限 |
| `add_daily_cost()` | `daily_cost.py` | 累加用户当日花费 |

### 8.2 前端关键组件与函数

| 组件/函数 | 所在文件 | 说明 |
|-----------|---------|------|
| `useAuthStore` | `stores/auth.js` | 认证状态管理（登录/登出/切换学科） |
| `useAppStore` | `stores/app.js` | 应用状态管理（标签/会话/用量） |
| `renderMath(text)` | `utils/mathRender.js` | KaTeX + Markdown 混合渲染 |
| `AppLayout` | `components/AppLayout.vue` | 三栏布局容器 |
| `SidebarLeft` | `components/SidebarLeft.vue` | 左侧导航（角色感知） |
| `SidebarRight` | `components/SidebarRight.vue` | 右侧信息面板 |

---

## 9. 依赖关系与数据存储

### 9.1 后端依赖 (`requirements.txt`)

| 依赖 | 用途 |
|------|------|
| `fastapi` | Web 框架 |
| `uvicorn[standard]` | ASGI 服务器 |
| `gunicorn` | WSGI 服务器（生产环境） |
| `python-multipart` | 文件上传支持 |
| `python-dotenv` | 环境变量加载 |
| `httpx` | HTTP 客户端（OpenAI SDK 底层） |
| `pillow` | 图片处理（压缩/转换） |
| `PyMuPDF==1.27.2.3` | PDF 处理（文本提取/渲染） |
| `pydantic` / `pydantic-settings` | 数据验证与配置管理 |
| `openai>=1.0` | DeepSeek/Kimi API 调用 |
| `python-docx` | Word 文档读取 |
| `pytesseract` | 本地 OCR（后备方案） |

### 9.2 前端依赖 (`package.json`)

| 依赖 | 用途 |
|------|------|
| `vue@^3.4.0` | 前端框架 |
| `vue-router@^4.2.0` | 路由管理 |
| `pinia@^2.1.0` | 状态管理 |
| `element-plus@^2.5.0` | UI 组件库 |
| `@element-plus/icons-vue@^2.3.0` | 图标库 |
| `axios@^1.6.0` | HTTP 客户端 |
| `katex@^0.17.0` | LaTeX 公式渲染 |
| `markdown-it@^14.2.0` | Markdown 渲染 |
| `vite@^5.0.0` | 构建工具 |
| `@vitejs/plugin-vue@^5.0.0` | Vite Vue 插件 |

### 9.3 数据存储结构

所有数据以 JSON 文件存储于 `backend/data/users/`，按 `{username}_{subject}_{type}.json` 命名。

**用户核心数据文件**：

| 文件 | 内容 | 示例 |
|------|------|------|
| `{username}.json` | 用户资料 | 年级、学校、偏好 |
| `{username}_config.json` | 系统配置 | API Key、模型、压缩参数等 |
| `{username}_{subject}_problems.json` | 题库 | 题目数组（含内容/解答/知识点） |
| `{username}_{subject}_wrong.json` | 错题 ID | 错题 ID 列表 |
| `{username}_{subject}_sessions.json` | 上传会话 | 会话名称与 ID |
| `{username}_{subject}_usage.json` | AI 用量 | 每次 API 调用的 token 与花费 |
| `{username}_{subject}_solve_sessions.json` | 解题记录 | 题目+解答+推理过程+用量 |
| `{username}_{subject}_materials.json` | 复习资料 | 英语资料文件元数据 |
| `{username}_{subject}_answers.json` | 答案库 | 英语答案条目 |
| `{username}_{subject}_words.json` | 词单 | 英语单词列表 |
| `{username}_{subject}_trash.json` | 废纸篓 | 已删除题目 |
| `{username}_{subject}_library_trash.json` | 资料回收站 | 已删除的资料/答案/词单 |
| `{username}_{subject}_problem_answer_map.json` | 题目-答案映射 | 英语题目与答案配对关系 |
| `{username}_对话_chat_sessions.json` | 对话会话 | 对话元数据（含用量统计） |
| `{username}_对话_chat_{id}.json` | 对话消息 | 具体对话的消息数组 |

**全局数据文件**：

| 文件 | 内容 |
|------|------|
| `data/admin.json` | 管理员密码哈希 |

**上传文件存储** — `backend/data/uploads/`：
- `{file_id}_compressed.jpg` — 压缩后的图片
- `{file_id}.pdf` — 上传的 PDF（副本）
- `{file_id}_text.txt` — 提取的文本内容

---

## 10. 项目运行方式

### 10.1 一键启动

双击项目根目录的 **`start.bat`**：

1. **环境检测** — 检查 Python 虚拟环境、Node.js 运行时、npm 依赖
2. **清理旧进程** — 按窗口标题和端口号清理残留进程
3. **端口探测** — 自动检测 6003-6010 可用端口作为后端端口
4. **启动后端** — `venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port {port}`
5. **健康检查** — 等待后端健康检查通过（最多 30 秒）
6. **启动前端** — `npm run dev`
7. **自动打开浏览器** — 访问 `http://localhost:5173`

### 10.2 手动启动

```bash
# 终端 1：后端
cd backend
venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 6003 --reload

# 终端 2：前端
cd frontend
npm run dev
```

访问 **`http://localhost:5173`**

**后端快捷启动脚本**：

| 脚本 | 说明 |
|------|------|
| `backend/run_srv.bat` | 单独启动后端（端口 6003，UTF-8 编码） |
| `backend/start_server.bat` | 启动后端并将输出重定向到 `server.log` |
| `backend/start.vbs` | 静默 VBS 启动后端，无窗口，输出到 `server.log` |

### 10.3 首次使用流程

1. 在登录页选择 **数学** / **英语** / **对话** 模式
2. 输入用户名（root 为管理员，需要密码 `admin123`）
3. 进入「设置 → 系统设置」配置 API Key 并测试连接
4. 数学模式 → 点击「录入题目」上传试卷
5. 英语模式 → 点击「上传资料」选择文件与标签
6. 在「解题」页面开始学习

### 10.4 生产构建

```bash
cd frontend
npm run build
# 静态文件输出到 frontend/dist/
# FastAPI 的静态文件挂载可指向该目录
```

---

## 11. 开发亮点

### 11.1 架构设计

- **学科完全隔离** — 数据按 `{username}_{subject}_{type}.json` 隔离，不同学科互不干扰
- **轻量无数据库** — 全部使用 JSON 文件存储，零运维成本，适合个人/小团队私有部署
- **角色感知导航** — 管理员/数学/英语/对话用户看到不同的侧边栏内容

### 11.2 AI 集成

- **双模型支持** — 同时集成 DeepSeek 和 Kimi，根据任务类型自动分流
- **流式输出全覆盖** — 上传识别、解题过程、对话回复均通过 SSE 实时推送
- **智能模型选择** — 含图 → Kimi Vision，纯文字 → DeepSeek（性价比优先）
- **文件名规则预分类** — 零 API 费用完成英语文档分类

### 11.3 文件处理

- **PDF 智能分流** — 文本页直接提取文字（零 token 消耗），扫描页自动转截图
- **Word 零依赖解析** — `zipfile + ElementTree` 提取 docx 文本，无需安装额外库
- **原子写入** — JSON 文件先写 `.tmp` 再 `os.replace`，崩溃时保留 `.bak` 备份
- **并发安全** — `asyncio.Lock` 文件锁，读写操作线程安全

### 11.4 费用管控

- **实时定价** — 基于官方定价精确计算每次会话花费
- **每日上限熔断** — 达到上限后自动拒绝新请求
- **用量统计** — 精确到每次 API 调用的缓内/缓外 token + 花费

### 11.5 前端体验

- **LaTeX 渲染** — KaTeX + markdown-it 完整支持数学公式与 Markdown 混排
- **液态玻璃 UI** — 统一视觉风格，动态粒子效果，深色/浅色自适应
- **移动端适配** — 侧边栏抽屉式导航，响应式布局
- **全局 Loading** — Axios 拦截器自动管理请求加载状态

### 11.6 运维

- **端口自适应** — `start.bat` 自动检测空闲端口，避免残留进程冲突
- **管理员面板** — 状态监控、用户管理、用量统计、日志查看
- **数据迁移** — 自动兼容旧格式数据（无学科后缀 → 有学科后缀）

---

> **开发者**：朵朵 | 南京外国语学校 2025 级 2 班
> **最后更新**：2026-07-07
