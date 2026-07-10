#!/usr/bin/env python3
"""
StudyBuddy 首次部署脚本

在新电脑上第一次使用时，双击运行这个文件。
它会自动完成：
  1. 检查 Python 版本
  2. 创建虚拟环境并安装依赖
  3. 检查前端文件（如果没有则提示）
  4. 启动服务
"""

import sys
import os
import subprocess
import time
import socket
import urllib.request
import webbrowser
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
BACKEND_PORT_START = 6003
BACKEND_PORT_END = 6010
IS_WINDOWS = os.name == "nt"


def print_box(title, lines):
    print()
    print("  " + "=" * 50)
    print(f"     {title}")
    print("  " + "=" * 50)
    for line in lines:
        print(f"     {line}")
    print("  " + "=" * 50)
    print()


def log(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] {msg}")


def warn(msg):
    print(f"  [!] {msg}")


def error(msg):
    print(f"  [x] {msg}")


def get_venv_dir():
    return BACKEND_DIR / ("venv" if IS_WINDOWS else ".venv")


def check_python():
    """检查 Python 版本。"""
    log("检查 Python 版本...")
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 11):
        error(f"Python 版本过低: {v.major}.{v.minor}（需要 3.11 或更高）")
        error("请去 https://www.python.org/downloads/ 下载最新版")
        return False
    log(f"Python {v.major}.{v.minor}.{v.micro} ✓")
    return True


def setup_venv():
    """创建虚拟环境并安装依赖。"""
    venv_dir = get_venv_dir()

    if venv_dir.is_dir():
        log("虚拟环境已存在 ✓")
    else:
        log("正在创建虚拟环境...")
        r = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode != 0:
            error(f"创建虚拟环境失败: {r.stderr}")
            return False
        log("虚拟环境创建完成 ✓")

    # 确定 pip 路径
    if IS_WINDOWS:
        pip_path = venv_dir / "Scripts" / "pip.exe"
        python_path = venv_dir / "Scripts" / "python.exe"
    else:
        pip_path = venv_dir / "bin" / "pip"
        python_path = venv_dir / "bin" / "python3"
        if not python_path.is_file():
            python_path = venv_dir / "bin" / "python"

    if not pip_path.is_file():
        # 尝试用 python -m pip
        pip_path = None

    log("正在安装 Python 依赖（可能需要几分钟）...")
    if pip_path:
        r = subprocess.run(
            [str(pip_path), "install", "-r", "requirements.txt"],
            cwd=str(BACKEND_DIR),
            capture_output=True, text=True, timeout=300
        )
    else:
        r = subprocess.run(
            [str(python_path), "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=str(BACKEND_DIR),
            capture_output=True, text=True, timeout=300
        )

    if r.returncode != 0:
        error("安装依赖失败:")
        print(r.stderr[-500:] if r.stderr else r.stdout[-500:])
        return False

    log("依赖安装完成 ✓")
    return True


def check_frontend():
    """检查前端文件是否存在（dist/）。"""
    dist_dir = FRONTEND_DIR / "dist"
    index_html = dist_dir / "index.html"

    if index_html.is_file():
        log("前端文件已就绪 ✓")
        return True

    warn("未找到前端文件 (frontend/dist/)。")

    # 检查有没有 npm
    npm = None
    try:
        r = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            npm = "npm"
    except Exception:
        pass

    if npm:
        log("检测到 Node.js，正在构建前端...")
        r = subprocess.run(
            [npm, "run", "build"],
            cwd=str(FRONTEND_DIR),
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0 and index_html.is_file():
            log("前端构建完成 ✓")
            return True
        error("前端构建失败")

    error("需要前端文件才能运行。请选择一种方式：")
    error("  1. 在已有 Node.js 的电脑上运行「python start.py --build」，")
    error("     然后把 frontend/dist/ 文件夹复制过来")
    error("  2. 在本机装好 Node.js 后重新运行本脚本")
    return False


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


def start_server():
    """启动生产模式服务。"""
    port = find_free_port(BACKEND_PORT_START, BACKEND_PORT_END)
    if not port:
        error(f"端口 {BACKEND_PORT_START}-{BACKEND_PORT_END} 全部被占用")
        return False

    # 确定 Python 路径
    venv_dir = get_venv_dir()
    if IS_WINDOWS:
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python3"
        if not venv_python.is_file():
            venv_python = venv_dir / "bin" / "python"

    log(f"正在启动服务（端口 {port}）...")

    backend_env = os.environ.copy()
    backend_env["STUDYBUDDY_PROD"] = "1"

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

    log("等待就绪...")
    ready = False
    for i in range(60):
        if check_backend_health(port):
            ready = True
            break
        if proc.poll() is not None:
            error("后端进程意外退出")
            break
        time.sleep(0.5)

    if not ready:
        error("启动超时，请查看 backend/server.log")
        return False

    # 保存 PID
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

    url = f"http://localhost:{port}/"
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print_box("部署成功！🎉", [
        f"网页地址: {url}",
        "",
        "  以后双击「run.py」即可启动",
        "  双击「关闭服务.py」即可停止",
    ])

    input("  按 Enter 键停止服务并退出...")
    return True


def main():
    print_box("StudyBuddy 首次部署", [
        "本脚本会自动完成以下操作：",
        "  1. 检查 Python 版本",
        "  2. 创建虚拟环境并安装依赖",
        "  3. 准备前端文件",
        "  4. 启动服务",
        "",
        "整个流程大约需要 3~5 分钟。",
    ])
    input("  按 Enter 键开始...")

    # 第 1 步：检查 Python
    print()
    if not check_python():
        input("\n  按 Enter 键退出...")
        sys.exit(1)

    # 第 2 步：创建虚拟环境 + 安装依赖
    print()
    if not setup_venv():
        input("\n  按 Enter 键退出...")
        sys.exit(1)

    # 第 3 步：检查前端文件
    print()
    if not check_frontend():
        input("\n  按 Enter 键退出...")
        sys.exit(1)

    # 第 4 步：启动服务
    print()
    start_server()


if __name__ == "__main__":
    main()
