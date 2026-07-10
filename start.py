#!/usr/bin/env python3
"""
StudyBuddy AI 一键启动脚本
跨平台，支持 Windows / macOS / Linux
"""

import os
import sys
import json
import time
import socket
import subprocess
import webbrowser
import urllib.request
import urllib.error
import shutil
import signal
import platform
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
PID_FILE = BASE_DIR / "studybuddy_pids.json"

BACKEND_PORT_START = 6003
BACKEND_PORT_END = 6010
FRONTEND_PORT = 5173
BACKEND_WAIT_MAX = 30
FRONTEND_WAIT_MAX = 20

IS_WINDOWS = platform.system() == "Windows"


def log(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] {msg}")


def warn(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] [WARN] {msg}")


def error(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] [ERROR] {msg}")


def find_venv_python():
    """查找虚拟环境中的 Python 解释器（跨平台）。"""
    venv_dirs = [BACKEND_DIR / "venv", BACKEND_DIR / ".venv"]

    for venv_dir in venv_dirs:
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

        for p in candidates:
            if p.is_file():
                return p
    return None


def find_system_python():
    """查找系统中可用的 Python（需包含 uvicorn 和 dotenv）。"""
    candidates = []
    if IS_WINDOWS:
        candidates = [
            shutil.which("python"),
            shutil.which("python3"),
            shutil.which("py"),
        ]
    else:
        candidates = [
            shutil.which("python3"),
            shutil.which("python"),
        ]

    for py in candidates:
        if not py:
            continue
        try:
            r = subprocess.run(
                [py, "-c", "import uvicorn, dotenv; print('ok')"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                return Path(py)
        except Exception:
            pass
    return None


def detect_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("114.114.114.114", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def find_free_port(start, end):
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return None


def is_port_open(host, port, timeout=1):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def check_backend_health(port, timeout=2):
    try:
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health", timeout=timeout
        )
        return resp.status == 200
    except Exception:
        return False


def kill_process(pid):
    """跨平台进程终止。"""
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, text=True, timeout=5
            )
        else:
            os.kill(pid, signal.SIGTERM)
            # 等待进程退出
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
    except Exception:
        pass


def kill_by_port(port):
    """通过端口查找并终止进程（跨平台）。"""
    if IS_WINDOWS:
        try:
            r = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        if pid and pid != "0":
                            kill_process(pid)
        except Exception:
            pass
    else:
        # Unix: 使用 lsof 或 fuser
        try:
            r = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5
            )
            if r.stdout.strip():
                for pid in r.stdout.strip().splitlines():
                    kill_process(int(pid.strip()))
        except Exception:
            try:
                r = subprocess.run(
                    ["fuser", "-k", f"{port}/tcp"],
                    capture_output=True, text=True, timeout=5
                )
            except Exception:
                pass


def load_pid_data():
    if PID_FILE.exists():
        try:
            return json.loads(PID_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_pid_data(data):
    PID_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_subprocess(cmd_args, cwd=None, env=None, log_file=None):
    """跨平台子进程启动。"""
    startupinfo = None
    if IS_WINDOWS:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    kwargs = {
        "args": cmd_args,
        "cwd": str(cwd) if cwd else None,
        "env": env,
        "startupinfo": startupinfo,
    }
    if log_file:
        kwargs["stdout"] = open(log_file, "w", encoding="utf-8")
        kwargs["stderr"] = subprocess.STDOUT

    return subprocess.Popen(**kwargs)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="StudyBuddy AI 启动脚本")
    parser.add_argument("--prod", action="store_true", help="生产模式：不启动 Vite，由后端提供前端静态文件")
    parser.add_argument("--build", action="store_true", help="在当前机器上执行 npm run build")
    parser.add_argument("--port", type=int, default=None, help="指定后端端口")
    args = parser.parse_args()

    print()
    print("  ==========================================")
    print("     StudyBuddy AI  -  starting...")
    print("  ==========================================")
    print()

    # ---------- 1. 检测环境 ----------
    log("检测运行环境...")
    venv_python = find_venv_python()
    if not venv_python:
        log("未找到虚拟环境，尝试使用系统 Python...")
        venv_python = find_system_python()

    if not venv_python:
        error("未找到可用的 Python（需要 uvicorn + python-dotenv）")
        error("请先运行: cd backend && python -m venv venv && venv/bin/pip install -r requirements.txt")
        input("\n  按 Enter 键退出...")
        sys.exit(1)
    log(f"Python: {venv_python}")

    # ---------- 检查前端依赖（非 --prod 模式） ----------
    if not args.prod:
        npm_path = shutil.which("npm")
        if npm_path:
            npm_path = Path(npm_path)
            log(f"npm: {npm_path}")
        else:
            if IS_WINDOWS:
                for base in [
                    os.environ.get("LOCALAPPDATA", ""),
                    os.environ.get("ProgramFiles", ""),
                    os.environ.get("ProgramFiles(x86)", ""),
                ]:
                    candidate = Path(base) / "nodejs" / "npm.cmd"
                    if candidate.exists():
                        npm_path = candidate
                        log(f"npm: {npm_path}")
                        break
                    candidate = Path(base) / "Programs" / "nodejs" / "npm.cmd"
                    if candidate.exists():
                        npm_path = candidate
                        log(f"npm: {npm_path}")
                        break

        if not npm_path:
            error("未找到 Node.js/npm")
            if args.build:
                error("--build 模式需要 npm，请先安装 Node.js")
            else:
                error("开发模式需要 npm。请安装 Node.js，或使用 --prod 模式（无需 Node.js）")
            input("\n  按 Enter 键退出...")
            sys.exit(1)

        frontend_modules = FRONTEND_DIR / "node_modules"
        if not frontend_modules.is_dir():
            warn("正在安装前端依赖 (npm install)...")
            r = subprocess.run(
                [str(npm_path), "install"],
                cwd=str(FRONTEND_DIR),
                capture_output=True, text=True, timeout=120
            )
            if r.returncode != 0:
                error("npm install 失败:")
                print(r.stderr[-500:] if r.stderr else r.stdout[-500:])
                input("\n  按 Enter 键退出...")
                sys.exit(1)
            log("前端依赖安装完成")

        # --build 模式：只构建，不启动服务
        if args.build:
            log("正在构建前端 (npm run build)...")
            r = subprocess.run(
                [str(npm_path), "run", "build"],
                cwd=str(FRONTEND_DIR),
                capture_output=True, text=True, timeout=120
            )
            if r.returncode != 0:
                error("npm run build 失败:")
                print(r.stderr[-500:] if r.stderr else r.stdout[-500:])
                sys.exit(1)
            log("前端构建完成")
            dist_size = sum(f.stat().st_size for f in FRONTEND_DIR.glob("dist/**/*") if f.is_file()) / 1024 / 1024
            log(f"dist/ 大小: {dist_size:.1f} MB")
            print()
            log("构建完成！在目标机器上使用 --prod 模式运行即可")
            return

    # ---------- 2. 清理旧进程 ----------
    log("清理旧服务进程...")
    old_data = load_pid_data()
    if old_data:
        for key in ("backend_pid", "frontend_pid"):
            pid = old_data.get(key)
            if pid:
                kill_process(pid)
    for p in range(BACKEND_PORT_START, BACKEND_PORT_END + 1):
        kill_by_port(p)
    kill_by_port(FRONTEND_PORT)
    kill_by_port(FRONTEND_PORT + 1)
    time.sleep(0.5)

    # ---------- 3. 检测可用端口和 IP ----------
    backend_port = args.port or find_free_port(BACKEND_PORT_START, BACKEND_PORT_END)
    if not backend_port:
        error(f"端口 {BACKEND_PORT_START}-{BACKEND_PORT_END} 均被占用，无法启动")
        input("\n  按 Enter 键退出...")
        sys.exit(1)

    if args.prod:
        frontend_port = backend_port
    else:
        frontend_port = FRONTEND_PORT
        if is_port_open("127.0.0.1", frontend_port):
            frontend_port = FRONTEND_PORT + 1
            if is_port_open("127.0.0.1", frontend_port):
                error(f"前端端口 {FRONTEND_PORT}/{FRONTEND_PORT+1} 均被占用")
                input("\n  按 Enter 键退出...")
                sys.exit(1)

    local_ip = detect_local_ip()
    log(f"后端端口: {backend_port}  前端端口: {frontend_port}  IP: {local_ip} 模式: {'prod' if args.prod else 'dev'}")

    # ---------- 4. 构建 CORS 环境变量 ----------
    extra_origins = set()
    if local_ip != "127.0.0.1":
        extra_origins.add(f"http://{local_ip}:{frontend_port}")
    origins_str = ",".join(sorted(extra_origins))

    # ---------- 5. 启动后端 ----------
    log("启动后端服务...")
    backend_log = BACKEND_DIR / "server.log"
    backend_log.write_text("", encoding="utf-8")

    backend_env = os.environ.copy()
    if origins_str:
        backend_env["VITE_ALLOWED_ORIGINS"] = origins_str
        backend_env["VITE_FRONTEND_PORTS"] = str(frontend_port)
    if args.prod:
        backend_env["STUDYBUDDY_PROD"] = "1"
        backend_env["STUDYBUDDY_FRONTEND_PORT"] = str(frontend_port)
    else:
        backend_env["VITE_BACKEND_PORT"] = str(backend_port)

    backend_proc = run_subprocess(
        [str(venv_python), "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0", "--port", str(backend_port),
         "--log-level", "warning"],
        cwd=BACKEND_DIR,
        env=backend_env,
        log_file=backend_log,
    )
    backend_pid = backend_proc.pid

    # ---------- 6. 启动前端（仅 dev 模式） ----------
    frontend_pid = None
    frontend_proc = None
    if not args.prod:
        log("启动前端服务...")
        frontend_log = FRONTEND_DIR / "dev.log"
        frontend_log.write_text("", encoding="utf-8")

        frontend_env = os.environ.copy()
        frontend_env["VITE_BACKEND_PORT"] = str(backend_port)

        frontend_proc = run_subprocess(
            [str(npm_path), "run", "dev", "--", "--port", str(frontend_port)],
            cwd=FRONTEND_DIR,
            env=frontend_env,
            log_file=frontend_log,
        )
        frontend_pid = frontend_proc.pid

    # ---------- 7. 等待后端就绪 ----------
    log("等待后端就绪...")
    backend_ok = False
    for i in range(BACKEND_WAIT_MAX * 2):
        if check_backend_health(backend_port):
            backend_ok = True
            break
        if backend_proc.poll() is not None:
            error("后端进程已提前退出")
            break
        time.sleep(0.5)

    if not backend_ok:
        error("后端启动超时（~30秒），请检查:")
        error(f"  日志: {backend_log}")
        if backend_log.exists():
            lines = backend_log.read_text(encoding="utf-8").strip().splitlines()
            for line in lines[-10:]:
                error(f"  {line}")
        kill_process(backend_pid)
        if frontend_pid:
            kill_process(frontend_pid)
        input("\n  按 Enter 键退出...")
        sys.exit(1)
    log("后端就绪")

    # ---------- 8. 等待前端就绪（仅 dev 模式） ----------
    if not args.prod and frontend_proc:
        log("等待前端就绪...")
        frontend_ok = False
        for i in range(FRONTEND_WAIT_MAX * 2):
            if is_port_open("127.0.0.1", frontend_port, timeout=0.5):
                frontend_ok = True
                break
            if frontend_proc.poll() is not None:
                error("前端进程已提前退出")
                break
            time.sleep(0.5)

        if not frontend_ok:
            warn("前端可能仍在编译（超时 ~20秒），后台继续加载中...")

    # ---------- 9. 保存 PID 信息 ----------
    save_pid_data({
        "backend_pid": backend_pid,
        "frontend_pid": frontend_pid,
        "backend_port": backend_port,
        "frontend_port": frontend_port,
        "local_ip": local_ip,
    })

    # ---------- 10. 打开浏览器并显示信息 ----------
    if not args.prod:
        frontend_url = f"http://localhost:{frontend_port}/"
        webbrowser.open(frontend_url)

    print()
    print("  ==========================================")
    print(f"     StudyBuddy AI  -  started successfully")
    print("  ==========================================")
    print(f"     后端:  http://localhost:{backend_port}/")
    if args.prod:
        print(f"     前端:  http://localhost:{backend_port}/（生产模式，后端直接提供）")
    else:
        print(f"     前端:  http://localhost:{frontend_port}/")
    if local_ip != "127.0.0.1":
        print(f"     LAN:   http://{local_ip}:{frontend_port if not args.prod else backend_port}/")
    print()
    print(f"  停止: python stop.py  |  日志: server.log, dev.log")
    print()

    if args.prod:
        time.sleep(3)
    else:
        time.sleep(5)


if __name__ == "__main__":
    main()
