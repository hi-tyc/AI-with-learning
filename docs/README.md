# StudyBuddy AI 伴学系统

> **智能解题 · 知识管理 · 多模态学习** — 面向初中生的私有化 AI 学习辅助平台

---

## 项目简介

StudyBuddy 是一款面向初中学生的智能学习辅助系统，支持 **数学**、**英语**、**对话** 三种模式。系统深度融合 DeepSeek 和 Kimi 双 AI 模型，提供拍照/PDF 上传识别、智能分步解题、资料自动分类归档、错题管理等完整学习闭环。所有数据以 JSON 文件存储，支持完全私有化部署。

本项目由朵朵独立开发，作为初中学习阶段的全栈知识管理实践项目。

---

## 核心功能

### 三种模式

| 模式 | 登录入口 | AI 引擎 | 核心能力 |
|------|----------|---------|---------|
| **数学** | 登录选「数学」 | DeepSeek + Kimi 自动分流 | 试卷拍照/PDF 上传识别，代数/几何分类，智能解题，题库管理 |
| **英语** | 登录选「英语」 | 强制 DeepSeek | 统一上传入口，AI 自动分类（题目/答案/资料），标签归档，答案匹配 |
| **对话** | 登录选「对话」 | DeepSeek + Kimi | 通用 AI 对话，支持图片/PDF/Word 上传，多轮会话管理 |

### 数学模式

- **题目录入** — 上传 JPG/PNG/PDF 试卷，AI 识别文字并结构化入库。支持代数（文字识别）与几何（原图保存）两种模式
- **PDF 智能分流** — 文本页直接提取文字，扫描页转为截图；几何模式 PDF 由 Kimi 分析分类
- **智能解题** — 支持「解大题」「解小题」「自由输入」三种方式，流式 SSE 实时输出解题过程
- **模型自动选择** — 含图/PDF → Kimi，纯文字 → DeepSeek（flash/pro）
- **题库管理** — 树形目录，支持新建/重命名/移动/删除，大题-子题层级

### 英语模式

- **统一上传入口** — 一个「上传资料」按钮，支持 PDF / Word（docx）/ 图片，可多选
- **AI 自动分类** — DeepSeek 自动分析文档内容，判断为 **题目** / **答案** / **资料**，分别存入独立库
- **答案匹配** — AI 自动将题目文件与答案文件配对，建立映射关系
- **标签归档** — 按 `月考1 / 期中 / 月考2 / 期末 / 其他` 标签分类，解题时可一键调用
- **复习资料调用** — 解题时输入框上方选择资料标签，AI 自动将资料内容注入 prompt

### 对话模式

- 通用 AI 对话，支持上传图片/PDF/Word 文档
- 多轮会话管理（创建、重命名、删除）
- 支持 DeepSeek 和 Kimi 双模型切换

### 通用功能

| 功能 | 说明 |
|------|------|
| **流式输出** | 上传识别、解题过程均通过 SSE 实时推送，前端深色终端面板滚动展示 |
| **用量统计** | 每次会话精确记录缓内/缓外 input/output tokens 与花费，历史可查 |
| **费用管控** | 基于 API 官方定价实时计算，支持设置每日花费上限，超限自动熔断 |
| **图片压缩** | 可配置压缩质量与长边上限，显著降低 token 消耗 |
| **系统设置** | 前端配置 API Key、模型版本、压缩参数、超时、重试、每日上限，实时测试连接 |
| **个人资料** | 设置年级、学校，AI 据此调整讲解深度 |
| **数据隔离** | 不同学科数据完全分离（`用户_学科_*.json`），互不干扰 |

---

## 技术架构

### 后端

| 层级 | 技术 | 说明 |
|------|------|------|
| 框架 | FastAPI + Uvicorn | Python 3.13，异步全栈 |
| AI SDK | `openai` (AsyncOpenAI) | 统一封装 DeepSeek / Kimi API |
| 图片/PDF | Pillow / PyMuPDF (fitz) | 压缩、格式转换、PDF 文本提取 |
| Word 解析 | zipfile + xml.etree.ElementTree | 内置提取 docx 文本，零额外依赖 |
| 数据存储 | JSON 文件 | 按用户+学科隔离，`asyncio.Lock` 并发安全，原子写入 |
| 流式传输 | StreamingResponse (SSE) | 上传进度 + 解题结果实时推送 |

**后端模块**（18 个 API 端点文件）：

```
app/api/endpoints/
├── auth.py              # 登录/注册/学科选择（Cookie Session）
├── settings_api.py      # 系统配置 CRUD + 测试连接
├── upload.py            # 数学上传（图片/PDF + Kimi 识别）
├── english_upload.py    # 英语上传（AI 分类 + 三库存储）
├── solve.py             # 智能解题（SSE 流式 + 模型分流）
├── solve_sessions.py    # 解题记录管理
├── problems.py              # 题库 CRUD + 错题管理
├── sessions.py          # 上传会话管理
├── paths.py             # 路径重命名/创建/删除
├── materials.py         # 复习资料管理（标签分组）
├── match_answers.py     # 英语答案匹配（AI 配对）
├── memory.py            # 记忆系统（画像/摘要/每日记忆）
├── usage.py             # 用量统计与查询
├── chat.py              # 对话模式（多轮会话）
├── admin.py             # 状态监控/诊断
├── library_trash.py     # 回收站（删除/恢复）
└── ...
```

**关键服务层**：

- `app/core/pricing.py` — 基于官方定价的 token 计费引擎，支持 DeepSeek 和 Kimi 全系模型
- `app/core/user_data.py` — 用户数据路径管理，按 `{username}_{subject}_{suffix}.json` 隔离
- `app/utils/ai_client.py` — AI 客户端工厂，统一超时/重试/错误处理
- `app/utils/file_lock.py` — 异步文件锁 + 原子写入（`.tmp` → `os.replace`）+ 崩溃恢复（`.bak`）

### 前端

| 层级 | 技术 |
|------|------|
| 框架 | Vue 3 (Composition API, `<script setup>`) |
| 构建 | Vite 5 |
| UI | Element Plus + Element Plus Icons |
| 状态管理 | Pinia |
| 路由 | Vue Router (Hash History) |
| HTTP | Axios（拦截器：全局 Loading / 错误处理 / 401 跳转） |
| 公式渲染 | KaTeX + markdown-it（LaTeX 与 Markdown 混排） |
| 样式 | 液态玻璃（Liquid Glass）UI，深色/浅色自适应 |

**前端页面**：

```
src/views/
├── Login.vue               # 登录 + 学科选择（数学/英语/对话）
├── Upload.vue               # 数学上传（流式进度 + 日志面板）
├── Solve.vue                # 数学解题（自由输入/目录/题目选择）
├── EnglishUpload.vue        # 英语上传（多文件 + 标签 + 流式日志）
├── english/
│   ├── Solve.vue            # 英语解题（固定 DeepSeek）
│   ├── Library.vue          # 英语资料库（标签/学期/关键词检索）
│   ├── DocDetail.vue        # 文档详情
│   └── Usage.vue            # 英语用量统计
├── Usage.vue                # 数学用量统计
├── Library.vue              # 数学题库（已合并至 Manage）
├── Manage.vue               # 数学管理模式（路径树 + 题目编辑）
├── ProblemDetail.vue        # 题目详情
├── Materials.vue            # 复习资料管理（批量上传 + tag 分组）
├── Chat.vue                 # 对话模式
├── SystemSettings.vue       # 系统设置（API Key/模型/压缩/超时）
└── Profile.vue              # 个人资料（年级/学校）
```

---

## 项目结构

```
AI伴学/
├── start.bat              # 一键启动（端口探测 + 健康检查 + 自动打开浏览器）
├── stop.bat               # 一键停止所有服务
├── 使用指南.md              # 用户使用文档
├── 开发指南.md              # 原始需求/开发任务书

├── backend/
│   ├── main.py             # FastAPI 入口 + CORS + 静态文件
│   ├── requirements.txt    # Python 依赖
│   ├── .env                # 环境变量（默认配置 fallback）
│   ├── run_srv.bat         # 后端单独启动脚本
│   ├── start_server.bat    # 服务器启动脚本
│   ├── start.vbs           # VBS 启动方式
│   ├── app/
│   │   ├── api/
│   │   │   ├── router.py   # 路由汇总
│   │   │   └── endpoints/  # 18 个 API 端点模块
│   │   ├── core/           # 配置、路径、定价、用户数据
│   │   └── utils/          # AI 客户端、文件锁
│   ├── data/               # 运行时数据（用户/题库/用量/上传文件）
│   └── venv/               # Python 虚拟环境

├── frontend/
│   ├── package.json
│   ├── vite.config.js      # Vite 配置（代理 /api → 后端）
│   ├── index.html
│   └── src/
│       ├── views/          # 12 个页面 + 4 个英语子页面
│       ├── components/     # AppLayout, SidebarLeft, SidebarRight, NavBar
│       ├── stores/         # auth.js, app.js
│       ├── router/         # 路由配置（含学科守卫）
│       └── api/            # API 适配层

├── tests/                   # 测试文件
│   ├── test_upload.py
│   ├── test_upload2.py
│   ├── test_image.jpg
│   ├── test_2pages.pdf
│   └── test_10pages.pdf

└── temp/                    # 临时文件目录
```

---

## 启动方式

### 一键启动

双击项目根目录的 **`start.bat`**：

- 自动探测空闲后端端口（6003–6010）
- 检测虚拟环境与依赖
- 启动后端（Uvicorn）并等待健康检查通过
- 启动前端（Vite dev server）
- 自动打开浏览器

### 手动启动

```bash
# 终端 1：后端
cd backend
venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 6003 --reload

# 终端 2：前端
cd frontend
npm run dev
```

访问 **`http://localhost:5173`**

### 首次使用

1. 登录时选择 **数学** / **英语** / **对话** 模式
2. 进入「设置 → 系统设置」配置 API Key 并测试连接
3. 数学模式 → 点击「录入题目」上传试卷
4. 英语模式 → 点击「上传资料」选择文件与标签
5. 在「解题」页面开始学习

---

## 数据存储

所有数据以 JSON 文件存储在 `backend/data/`，按 `{username}_{subject}_{type}.json` 命名。核心数据文件：

| 文件 | 内容 |
|------|------|
| `{username}.json` | 用户资料（年级、学校、偏好） |
| `{username}_config.json` | 系统配置（API Key、模型、压缩参数等） |
| `{username}_{subject}_problems.json` | 题库 |
| `{username}_{subject}_wrong.json` | 错题 ID 列表 |
| `{username}_{subject}_sessions.json` | 上传会话记录 |
| `{username}_{subject}_usage.json` | API 用量与花费 |
| `{username}_{subject}_solve_sessions.json` | 解题记录 |
| `{username}_{subject}_materials.json` | 复习资料（英语） |
| `{username}_{subject}_answers.json` | 答案库（英语） |
| `{username}_{subject}_words.json` | 单词/词汇（英语） |
| `{username}_{subject}_trash.json` | 回收站 |
| `{username}_{subject}_library_trash.json` | 资料回收站 |
| `{username}_{subject}_problem_answer_map.json` | 题目-答案映射 |
| `{username}_对话_chat_sessions.json` | 对话会话 |
| `{username}_对话_chat_{id}.json` | 对话消息 |

---

## 开发亮点

- **端口自适应** — `start.bat` 自动检测 6003–6010 空闲端口，避免残留进程冲突
- **学科完全隔离** — 登录时选择的学科决定数据存储前缀，题库/用量/资料互不干扰
- **英语 AI 三库分类** — 上传时 DeepSeek 自动判断文档类型（题目/答案/资料），分别存储
- **英语答案匹配** — AI 根据文件名智能配对题目文件与答案文件，支持批量处理
- **PDF 智能分流** — 文本页直接提取文字（零 token 消耗），扫描页自动转截图
- **Word 零依赖解析** — `zipfile + ElementTree` 提取 docx 文本，无需安装额外的库
- **模型自动分流** — 数学含图/PDF → Kimi，纯文字 → DeepSeek，英语强制 DeepSeek
- **实时定价** — 基于 DeepSeek 和 Kimi 官方定价精确计算每次会话花费
- **原子写入** — JSON 文件先写 `.tmp` 再 `os.replace`，崩溃时保留 `.bak` 备份
- **文件锁** — `asyncio.Lock` 防并发覆盖，读写操作线程安全
- **流式实时反馈** — SSE 推送上传进度和解题过程，前端深色终端面板滚动展示
- **LaTeX 渲染** — KaTeX + markdown-it 完整支持公式与 Markdown 混排
- **液态玻璃 UI** — 统一视觉风格，动态粒子效果，深色/浅色自适应
- **导航自适应** — 左侧导航栏根据学科动态显示/隐藏对应入口
- **全局 Loading** — Axios 拦截器自动管理请求加载状态

---

## 适用场景

- **初中生日常学习**：数学错题整理、英语试卷归档、AI 辅助解题与知识梳理
- **期末/期中备考**：系统性上传试卷，AI 智能分类归档，高效复习
- **英语专项训练**：按标签（月考1/期中/月考2/期末）管理资料，解题时一键调用
- **个人知识库**：长期积累跨学科学习材料，形成可检索、可调用的智能学习档案

---

*开发者：朵朵 | 南京外国语学校 2025 级 2 班*
