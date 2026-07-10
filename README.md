# StudyBuddy AI伴学

面向英语课外班的本地化教师工作台。系统聚焦班型、班级、资料、作业分发、错题统计与 Kimi Code AI 批改，不包含数学、通用对话或学生解题入口。

## 功能

- 管理员创建班型、班级、教师账号，并审核学生注册申请。
- 教师进入自己所属班级，直接拍照上传 PDF、Word、JPG 或 PNG 资料。
- 资料支持教师自定义的多层标签、资料类型、原文件查看、单份打印和批量打印。
- 可按班级或班型批量分发资料，自动带入对应学生名单。
- 记录学生已完成部分和错题，展示题目正确率与错误学生，并导出个人或整合错题本、Word 包和正确率总表。
- AI 自动批改支持分别上传或选择标准答案与学生作答；Kimi Code 只将高置信度错误写入错题本，低置信度结果保留为待人工确认。
- 学生可提交注册申请和现场人脸审核视频；通过后由管理员安排班级。学生学习端当前不开放。

## 技术栈

- 前端：Vue 3、Vite、Element Plus、Pinia、Vue Router
- 后端：FastAPI、Uvicorn、Pydantic、PyMuPDF、python-docx
- AI：Kimi Code API（OpenAI 兼容接口）
- 数据：本地 JSON 与文件目录，API Key 不进入代码仓库

## 本地开发

前置条件：Python 3.11+、Node.js 22+。

```bash
cd frontend
npm ci
npm run dev
```

另开一个终端：

```bash
cd backend
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 6003
```

访问 `http://127.0.0.1:5173`。Windows 下将 `.venv/bin/python` 替换为 `.venv\Scripts\python.exe`。

管理员默认账户为 `root`，默认密码为 `admin123`。首次登录后应立即修改管理员密码，并在“系统设置”中配置 Kimi API Key。

## 验证

```bash
python -m pip install -r backend/requirements.txt pytest
python -m pytest -q
npm ci --prefix frontend
npm run build --prefix frontend
```

`tests/test_upload.py` 与 `tests/test_upload2.py` 是历史人工联调脚本，依赖一台旧 Windows 电脑上的文件路径，已从自动 pytest 收集中排除。

## GitHub Actions

- `.github/workflows/ci.yml`：每次推送到 `main`、Pull Request 或手动触发时，构建前端、编译并测试后端，并上传源码 ZIP Artifact。
- `.github/workflows/build-macos.yml`：手动触发或推送 `v*` 标签时构建 macOS Intel/Apple Silicon 分发包；标签构建会将 ZIP 附加到 GitHub Release。

## 源码分发包

提交完成后，在项目根目录执行：

```bash
python tools/package_source.py
```

压缩包会生成在 `build/source/`，只包含当前提交中的源代码，不包含本地用户数据、上传文件、虚拟环境或 API Key。需要在未提交状态下临时打包时可使用 `--allow-dirty`，但该包仍以当前 `HEAD` 为准。

## 数据与隐私

运行数据默认保存在代码仓库外或被 `.gitignore` 排除的本地目录中。不要将 `users/`、`uploads/`、`backend/.env`、`backend/data/`、人脸审核视频或 API Key 提交到 GitHub。
