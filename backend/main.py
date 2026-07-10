from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi import Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import os
import socket
from pathlib import Path

from app.core.config import settings
from app.core.paths import ensure_dirs, UPLOAD_DIR, DATA_DIR, BASE_DIR, PROJECT_ROOT
from app.api.router import api_router


def _get_local_ips():
    """获取本机所有 IPv4 地址，用于内网访问时的 CORS 许可。"""
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    return ips


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 先创建目录，再挂载数据目录（SafeStaticFiles 要求目录已存在）
    ensure_dirs()
    app.mount("/data", SafeStaticFiles(directory=DATA_DIR), name="data")
    yield
    # Shutdown


app = FastAPI(
    title="StudyBuddy AI",
    description="AI伴学系统 - 初中学习辅助",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 来源允许列表构建
# 优先级：VITE_ALLOWED_ORIGINS 环境变量 > 自动检测本地 IP + 默认端口
_origins = set()

# 从环境变量读取明确的允许来源列表（由 start.py 等启动脚本传入）
_extra_origins = os.getenv("VITE_ALLOWED_ORIGINS", "")
if _extra_origins:
    for origin in _extra_origins.split(","):
        origin = origin.strip()
        if origin:
            _origins.add(origin)

# 自动添加本机所有内网 IP（覆盖可能的前后端端口）
_frontend_ports = os.getenv("VITE_FRONTEND_PORTS", "5173,5174")
for ip in _get_local_ips():
    for port in _frontend_ports.split(","):
        port = port.strip()
        if port:
            _origins.add(f"http://{ip}:{port}")

# 默认回退：localhost + 127.0.0.1 的常用端口
if not _origins:
    for port in _frontend_ports.split(","):
        port = port.strip()
        if port:
            _origins.add(f"http://localhost:{port}")
            _origins.add(f"http://127.0.0.1:{port}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


class SafeStaticFiles(StaticFiles):
    """Static files handler that blocks access to JSON user data files."""

    async def get_response(self, path: str, scope):
        if path.lower().endswith(".json"):
            return PlainTextResponse("Forbidden", status_code=403)
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return PlainTextResponse("Not found", status_code=404)
            raise


# 数据目录 mount 移至 lifespan 中（需要其在 ensure_dirs 之后执行）

# ---------- 生产模式：前端静态文件服务 ----------
_STUDYBUDDY_PROD = os.getenv("STUDYBUDDY_PROD", "") == "1"
if _STUDYBUDDY_PROD:
    _DIST_DIR = os.path.join(PROJECT_ROOT, "frontend", "dist")
    _DIST_ASSETS = os.path.join(_DIST_DIR, "assets")
    _INDEX_HTML = os.path.join(_DIST_DIR, "index.html")

    if os.path.isdir(_DIST_ASSETS):
        app.mount("/assets", StaticFiles(directory=_DIST_ASSETS), name="assets")

    if os.path.isfile(_INDEX_HTML):
        # SPA fallback: 对非 API/Data 路径的 404 返回 index.html
        @app.exception_handler(404)
        async def spa_fallback(request: Request, exc):
            path = request.url.path
            if path.startswith("/api/") or path.startswith("/data/"):
                return PlainTextResponse("Not found", status_code=404)
            return FileResponse(_INDEX_HTML)


@app.get("/")
async def root():
    return {"message": "StudyBuddy API is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
