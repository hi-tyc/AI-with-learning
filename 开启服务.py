#!/usr/bin/env python3
"""
StudyBuddy 生产模式启动脚本

双击运行即可启动（无需打开终端输入命令）。
启动后会自动打开浏览器。
"""

import sys
import os
import subprocess
import webbrowser
import time
import signal
import socket
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
BACKEND_PORT_START = 6003
BACKEND_PORT_END = 6010
IS_WINDOWS = os.name == "nt"


def print_box(title, lines):
    """打印一个带框的信息框。"""
    print()
    print("  " + "=" * 50)
    print(f"     {title}")
    print("  " + "=" * 50)
    for line in lines:
        print(f"     {line}")
    print("  " + "=" * 50)
    print()


def find_venv_python():
    for venv_dir in [BACKEND_DIR / "venv", BACKEND_DIR / ".venv"]:
        if not venv_dir.is_dir():
            continue
        if IS_WINDOWS:
            candidates = [
                venv_dir / "Scripts" / "python.exe",
                venv_dir / "Scripts" / "python3.exe",
            ]
        else:
            candidates = [
                venv_dir / "bin" / "python3",
                venv_dir / "bin" / "python",
            ]

        for py in candidates:
            if py.is_file():
                return py
    return None


def find_free_port(start, end):
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return None


def check_backend_health(port):
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
        return resp.status == 200
    except Exception:
        return False


def main():
    print_box("StudyBuddy 启动中...", [
        "正在启动生产模式服务，请稍候..."
    ])

    # 1. 检查虚拟环境
    venv_python = find_venv_python()
    if not venv_python:
        print("  [错误] 未找到 Python 虚拟环境。")
        print("  请先运行「首次部署.py」完成安装。")
        input("\n  按 Enter 键退出...")
        sys.exit(1)

    # 2. 检查前端构建
    dist_dir = BASE_DIR / "frontend" / "dist"
    if not dist_dir.is_dir() or not (dist_dir / "index.html").is_file():
        print("  [错误] 未找到前端文件 (frontend/dist/)。")
        print("  请先在装好 Node.js 的电脑上运行「首次部署.py」，")
        print("  或者把构建好的 dist 文件夹复制过来。")
        input("\n  按 Enter 键退出...")
        sys.exit(1)

    # 3. 找空闲端口
    port = find_free_port(BACKEND_PORT_START, BACKEND_PORT_END)
    if not port:
        print(f"  [错误] 端口 {BACKEND_PORT_START}-{BACKEND_PORT_END} 全部被占用。")
        print("  请先运行「关闭服务.py」停止已有服务。")
        input("\n  按 Enter 键退出...")
        sys.exit(1)

    # 4. 启动后端
    print(f"  端口: {port}")
    backend_env = os.environ.copy()
    backend_env["STUDYBUDDY_PROD"] = "1"
    backend_env["STUDYBUDDY_FRONTEND_PORT"] = str(port)

    log_file = BACKEND_DIR / "server.log"
    log_file.write_text("", encoding="utf-8")

    proc = subprocess.Popen(
        [str(venv_python), "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0", "--port", str(port),
         "--log-level", "warning"],
        cwd=str(BACKEND_DIR),
        env=backend_env,
        stdout=open(log_file, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )

    # 5. 等待就绪
    ready = False
    for i in range(60):
        if check_backend_health(port):
            ready = True
            break
        if proc.poll() is not None:
            break
        time.sleep(0.5)

    if not ready:
        print("  [错误] 启动超时或失败。")
        print("  请查看日志文件: backend/server.log")
        input("\n  按 Enter 键退出...")
        sys.exit(1)

    # 6. 保存 PID
    try:
        import json
        pid_file = BASE_DIR / "studybuddy_pids.json"
        pid_file.write_text(json.dumps({
            "backend_pid": proc.pid,
            "frontend_pid": None,
            "backend_port": port,
            "frontend_port": port,
            "local_ip": "127.0.0.1",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    # 7. 打开浏览器
    url = f"http://localhost:{port}/"
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print_box("启动成功！", [
        f"网页地址: {url}",
        "",
        "  关闭服务请运行「关闭服务.py」",
        "  或直接关闭此窗口（服务会停止）",
    ])

    # 等待用户按 Enter
    input("  按 Enter 键停止服务并退出...")


if __name__ == "__main__":
    main()
