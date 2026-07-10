#!/usr/bin/env python3
"""
StudyBuddy 关闭服务脚本

双击运行即可停止服务（无需打开终端输入命令）。
"""

import sys
import os
import json
import time
import signal
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PID_FILE = BASE_DIR / "studybuddy_pids.json"
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


def kill_process(pid):
    if not pid:
        return False
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, text=True, timeout=5
            )
        else:
            try:
                os.kill(pid, signal.SIGTERM)
                for _ in range(10):
                    try:
                        os.kill(pid, 0)
                        time.sleep(0.3)
                    except ProcessLookupError:
                        return True
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                return True
        return True
    except Exception:
        return False


def get_pid_by_port(port):
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


def main():
    print_box("StudyBuddy 关闭中...", [
        "正在停止服务，请稍候..."
    ])

    stopped = []

    # 1. 通过 PID 文件停止
    pid_data = {}
    if PID_FILE.exists():
        try:
            pid_data = json.loads(PID_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    if pid_data:
        for key, label in [("backend_pid", "后端"), ("frontend_pid", "前端")]:
            pid = pid_data.get(key)
            if pid and kill_process(pid):
                print(f"  已停止 {label}(PID {pid})")
                stopped.append(key)
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    # 2. 通过端口扫描清理残留
    for port in list(range(6003, 6011)) + [5173, 5174]:
        pid = get_pid_by_port(port)
        if pid and kill_process(pid):
            print(f"  已释放端口 {port}")
            stopped.append(f"port_{port}")

    time.sleep(0.5)

    if stopped:
        print()
        print("  所有服务已停止。")
    else:
        print("  未发现运行中的服务。")

    input("\n  按 Enter 键退出...")


if __name__ == "__main__":
    main()
