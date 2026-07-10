#!/usr/bin/env python3
"""
PyInstaller/macOS 打包入口。

用于在编译后的目录中启动 StudyBuddy 后端，并把前端静态文件、
数据目录等路径重定向到可分发包根目录。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def main() -> None:
    bundle_root = _bundle_root()
    data_root = bundle_root / "AI伴学数据"

    os.environ.setdefault("STUDYBUDDY_PROD", "1")
    os.environ.setdefault("STUDYBUDDY_PROJECT_ROOT", str(bundle_root))
    os.environ.setdefault("STUDYBUDDY_BACKEND_DIR", str(bundle_root))
    os.environ.setdefault("STUDYBUDDY_DATA_DIR", str(data_root))

    port = int(os.environ.get("PORT", os.environ.get("STUDYBUDDY_PORT", "6003")))

    from main import app

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
