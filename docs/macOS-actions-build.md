# StudyBuddy macOS 交付包

解压后目录中包含：

- `StudyBuddyServer`：后端可执行文件
- `frontend/dist/`：前端静态文件
- `AI伴学数据/`：本地数据目录
- `run_mac.command`：启动脚本
- `stop_mac.command`：停止脚本

使用方式：

1. 双击 `run_mac.command`
2. 首次运行如果被 Gatekeeper 拦截，在“系统设置 -> 隐私与安全性”里允许执行
3. 浏览器会自动打开 `http://127.0.0.1:6003/login`
4. 停止时双击 `stop_mac.command`

说明：

- API Key 不会打进程序，需要用户在系统设置页面重新填写
- `AI伴学数据/` 会保存上传文件、用户配置和本地会话
- Word 转 PDF 依赖 LibreOffice；如果目标 mac 未安装 LibreOffice，该功能会失效
- 本地 OCR 回退依赖 Tesseract；未安装时不影响主流程，只会少一层本地兜底能力
