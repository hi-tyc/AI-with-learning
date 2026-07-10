#!/usr/bin/env python3
"""
StudyBuddy AI 停止脚本
跨平台，支持 Windows / macOS / Linux
"""

import os
import sys
import json
import time
import socket
import subprocess
import signal
import platform
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PID_FILE = BASE_DIR / "studybuddy_pids.json"

BACKEND_PORT_RANGE = range(6003, 6011)
FRONTEND_PORTS = [5173, 5174]

IS_WINDOWS = platform.system() == "Windows"


def log(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] {msg}")


def warn(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] [WARN] {msg}")


def error(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] [ERROR] {msg}")


def kill_process(pid):
    """跨平台进程终止。先礼貌终止，失败后强制杀。"""
    if not pid:
        return False
    try:
        if IS_WINDOWS:
            r = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, text=True, timeout=5
            )
            return r.returncode == 0
        else:
            try:
                os.kill(pid, signal.SIGTERM)
                # 等待进程退出
                for _ in range(10):
                    try:
                        os.kill(pid, 0)
                        time.sleep(0.3)
                    except ProcessLookupError:
                        return True
                # 超时后强制杀
                os.kill(pid, signal.SIGKILL)
                return True
            except ProcessLookupError:
                return True
            except Exception:
                return False
    except Exception:
        return False


def get_pid_by_port(port):
    """通过端口查找 PID（跨平台）。"""
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
                            return int(pid)
        except Exception:
            pass
    else:
        try:
            r = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5
            )
            if r.stdout.strip():
                pids = r.stdout.strip().splitlines()
                if pids:
                    return int(pids[0].strip())
        except Exception:
            pass
    return None


def kill_by_port(port):
    pid = get_pid_by_port(port)
    if pid:
        log(f"端口 {port} 被 PID {pid} 占用，正在停止...")
        return kill_process(pid)
    return False


def main():
    print()
    print("  ==========================================")
    print("     StudyBuddy AI  -  stopping services")
    print("  ==========================================")
    print()

    stopped = []
    pid_data = {}

    # ---------- 1. 优先使用 PID 文件 ----------
    if PID_FILE.exists():
        try:
            pid_data = json.loads(PID_FILE.read_text(encoding="utf-8"))
        except Exception:
            warn("PID 文件损坏，将回退到端口扫描")

    if pid_data:
        log("从 PID 文件读取进程信息...")
        for key, label in [("backend_pid", "后端"), ("frontend_pid", "前端")]:
            pid = pid_data.get(key)
            if pid:
                if kill_process(pid):
                    log(f"{label}(PID {pid}) 已停止")
                    stopped.append(key)
                else:
                    warn(f"{label}(PID {pid}) 停止失败，将回退到端口扫描")
        PID_FILE.unlink(missing_ok=True)
    else:
        warn("未找到 PID 文件，将通过端口扫描清理")

    # ---------- 2. 回退：通过端口清理 ----------
    log("检查端口占用...")
    for port in list(BACKEND_PORT_RANGE) + FRONTEND_PORTS:
        if kill_by_port(port):
            stopped.append(f"port_{port}")

    time.sleep(0.5)

    # ---------- 3. 验证 ----------
    still_live = []
    for port in [5173, 5174] + list(range(6003, 6006)):
        if get_pid_by_port(port):
            still_live.append(port)

    print()
    if still_live:
        warn(f"以下端口仍有进程占用: {still_live}")
        warn("可能属于其他应用程序，请手动检查")
    else:
        log("所有 StudyBuddy 服务已停止")
    print()
    time.sleep(3)


if __name__ == "__main__":
    main()
