from pathlib import Path
from app.core.config import settings
import os

# Path 在 Windows 上对中文字符路径有编码 bug，所有路径拼接都使用 os.path.join


def _resolve_base() -> str:
    """返回项目根目录的绝对路径字符串。"""
    env_backend_dir = os.environ.get("STUDYBUDDY_BACKEND_DIR")
    if env_backend_dir:
        return os.path.abspath(env_backend_dir)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve_project_root() -> str:
    env_project_root = os.environ.get("STUDYBUDDY_PROJECT_ROOT")
    if env_project_root:
        return os.path.abspath(env_project_root)
    return os.path.dirname(BASE_DIR)


BASE_DIR = _resolve_base()  # backend/ 目录
PROJECT_ROOT = _resolve_project_root()  # 项目根目录


def _resolve_data_dir() -> str:
    """
    解析数据目录，优先级：
    1. STUDYBUDDY_DATA_DIR 环境变量
    2. settings.DATA_DIR（来自 .env 文件，路径相对于项目根目录）
    3. 默认值：项目同级的 AI伴学数据
    """
    env_dir = os.environ.get("STUDYBUDDY_DATA_DIR")
    if env_dir:
        if os.path.isabs(env_dir):
            return env_dir
        return os.path.abspath(os.path.join(PROJECT_ROOT, env_dir))

    if settings.DATA_DIR:
        if os.path.isabs(settings.DATA_DIR):
            return settings.DATA_DIR
        return os.path.abspath(os.path.join(PROJECT_ROOT, settings.DATA_DIR))

    return os.path.abspath(os.path.join(PROJECT_ROOT, "..", "AI伴学数据"))


def _resolve_upload_dir() -> str:
    """解析上传目录。"""
    if settings.UPLOAD_DIR:
        if os.path.isabs(settings.UPLOAD_DIR):
            return settings.UPLOAD_DIR
        return os.path.abspath(os.path.join(DATA_DIR, settings.UPLOAD_DIR))
    return os.path.join(DATA_DIR, "uploads")


# 别名（兼容旧代码中引用 BASE_DIR 表示 project root 的场景）
BACKEND_DIR = BASE_DIR


DATA_DIR = _resolve_data_dir()
UPLOAD_DIR = _resolve_upload_dir()
USERS_DIR = os.path.join(DATA_DIR, "users")
SHARED_DIR = os.path.join(DATA_DIR, "shared")
MEMORY_DIR = os.path.join(DATA_DIR, "memory")


def ensure_dirs():
    for d in [UPLOAD_DIR, DATA_DIR, USERS_DIR, SHARED_DIR, MEMORY_DIR]:
        os.makedirs(d, exist_ok=True)
