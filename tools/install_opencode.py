#!/usr/bin/env python3
"""
OpenCode CLI 跨平台安装脚本

检测当前系统，自动下载并安装 OpenCode CLI。
无运行时依赖（仅使用 Python 标准库）。
"""

import os
import sys
import json
import shutil
import platform
import subprocess
import tempfile
import urllib.request
import urllib.error
import zipfile
import tarfile
import io
from pathlib import Path


IS_WINDOWS = platform.system() == "Windows"
INSTALL_DIR_NAME = ".opencode"
BIN_NAME = "opencode.exe" if IS_WINDOWS else "opencode"


def log(msg):
    print(f"  [*] {msg}")


def warn(msg):
    print(f"  [!] {msg}")


def error(msg):
    print(f"  [x] {msg}")


def detect_platform():
    """检测操作系统和架构，返回 OpenCode 下载目标名称。"""
    raw_os = platform.system().lower()
    raw_arch = platform.machine().lower()

    if raw_os == "windows":
        os_name = "windows"
    elif raw_os == "darwin":
        os_name = "darwin"
    elif raw_os == "linux":
        os_name = "linux"
    else:
        error(f"不支持的操作系统: {raw_os}")
        sys.exit(1)

    if raw_arch in ("amd64", "x86_64", "x64"):
        arch_name = "x64"
    elif raw_arch in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        error(f"不支持的架构: {raw_arch}")
        sys.exit(1)

    target = f"{os_name}-{arch_name}"

    # 检测是否需要 -baseline 变体（无 AVX2 支持）
    needs_baseline = False
    if arch_name == "x64":
        if raw_os == "linux":
            try:
                with open("/proc/cpuinfo") as f:
                    if "avx2" not in f.read().lower():
                        needs_baseline = True
            except Exception:
                pass
        elif raw_os == "darwin":
            try:
                r = subprocess.run(
                    ["sysctl", "-n", "hw.optional.avx2_0"],
                    capture_output=True, text=True, timeout=5
                )
                if r.stdout.strip() != "1":
                    needs_baseline = True
            except Exception:
                pass
        elif raw_os == "windows":
            try:
                ps_cmd = (
                    '(Add-Type -MemberDefinition "[DllImport(\\"kernel32.dll\\")] '
                    'public static extern bool IsProcessorFeaturePresent(int ProcessorFeature);" '
                    '-Name Kernel32 -Namespace Win32 -PassThru)::IsProcessorFeaturePresent(40)'
                )
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=5
                )
                out = r.stdout.strip().lower()
                if out not in ("true", "1"):
                    needs_baseline = True
            except Exception:
                pass

        if needs_baseline:
            target += "-baseline"

    return target


def get_install_dir():
    """返回安装目录。"""
    home = Path.home()
    install_dir = home / INSTALL_DIR_NAME / "bin"
    return install_dir


def is_installed():
    """检查 opencode 是否已在 PATH 中。"""
    return shutil.which("opencode") is not None


def download_release_info():
    """获取最新版本号和下载 URL。"""
    api_url = "https://api.github.com/repos/anomalyco/opencode/releases/latest"
    try:
        req = urllib.request.Request(api_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tag = data.get("tag_name", "v0.0.0").lstrip("v")
            return tag
    except Exception as e:
        warn(f"获取版本信息失败: {e}")
        warn("将使用 latest 版本")
        return None


def download_opencode(target, version, dest_dir):
    """下载并解压 OpenCode 二进制文件。"""
    archive_ext = ".tar.gz" if "linux" in target else ".zip"
    filename = f"opencode-{target}{archive_ext}"

    if version:
        url = f"https://github.com/anomalyco/opencode/releases/download/v{version}/{filename}"
    else:
        url = f"https://github.com/anomalyco/opencode/releases/latest/download/{filename}"

    log(f"下载: {url}")
    dest_path = os.path.join(dest_dir, filename)

    try:
        urllib.request.urlretrieve(url, dest_path)
    except Exception as e:
        error(f"下载失败: {e}")
        sys.exit(1)

    log("下载完成，正在解压...")

    if archive_ext == ".tar.gz":
        with tarfile.open(dest_path, "r:gz") as tar:
            tar.extractall(path=dest_dir)
    else:
        with zipfile.ZipFile(dest_path, "r") as zf:
            zf.extractall(path=dest_dir)

    # 查找 opencode 可执行文件
    extracted_bin = None
    for root, dirs, files in os.walk(dest_dir):
        for f in files:
            if f in ("opencode", "opencode.exe"):
                extracted_bin = os.path.join(root, f)
                break
        if extracted_bin:
            break

    if not extracted_bin:
        error("解压后未找到 opencode 可执行文件")
        sys.exit(1)

    return extracted_bin


def add_to_path_windows(install_dir):
    """将目录添加到 Windows 用户 PATH。"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_READ | winreg.KEY_SET_VALUE
        )
        try:
            current_path, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            current_path = ""

        path_str = str(install_dir)
        if path_str in current_path.split(";"):
            log(f"{path_str} 已在 PATH 中")
            winreg.CloseKey(key)
            return

        new_path = f"{path_str};{current_path}" if current_path else path_str
        winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)

        # 广播环境变量变更
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Environment]::SetEnvironmentVariable('PATH', $env:PATH, 'User')"],
            capture_output=True, timeout=5
        )
        log(f"已添加到用户 PATH: {path_str}")
        warn("请重新打开终端使 PATH 生效")
    except Exception as e:
        warn(f"自动添加 PATH 失败: {e}")
        warn(f"请手动将以下目录添加到 PATH: {install_dir}")


def add_to_path_unix(install_dir):
    """将目录添加到 Unix shell 配置文件。"""
    path_str = str(install_dir)
    export_line = f'export PATH="{path_str}:$PATH"'

    shell = os.environ.get("SHELL", "").split("/")[-1] if not IS_WINDOWS else "bash"
    rc_files = {
        "bash": ["~/.bashrc", "~/.bash_profile", "~/.profile"],
        "zsh": ["~/.zshrc", "~/.zshenv"],
        "fish": ["~/.config/fish/config.fish"],
    }

    candidates = rc_files.get(shell, rc_files["bash"])
    written = False

    for rc in candidates:
        rc_path = os.path.expanduser(rc)
        if os.path.isfile(rc_path):
            with open(rc_path, "r") as f:
                content = f.read()
            if export_line in content:
                log(f"{rc_path} 已包含 PATH 配置")
                written = True
                break
            with open(rc_path, "a") as f:
                f.write(f"\n# opencode\n{export_line}\n")
            log(f"已添加到 {rc_path}")
            written = True
            break

    if not written:
        # 尝试创建默认 rc 文件
        default_rc = os.path.expanduser(candidates[0])
        with open(default_rc, "a") as f:
            f.write(f"\n# opencode\n{export_line}\n")
        log(f"已创建并添加到 {default_rc}")

    log("请执行 'source ~/.bashrc' 或重新打开终端使 PATH 生效")


def main():
    print()
    print("  ==========================================")
    print("     OpenCode CLI 安装助手")
    print("  ==========================================")
    print()

    # 1. 检查是否已安装
    if is_installed():
        existing = shutil.which("opencode")
        log(f"OpenCode 已安装: {existing}")
        try:
            r = subprocess.run(["opencode", "--version"], capture_output=True, text=True, timeout=10)
            log(f"版本: {r.stdout.strip() or r.stderr.strip()}")
        except Exception:
            pass
        return

    # 2. 检测平台
    log("检测系统平台...")
    target = detect_platform()
    log(f"目标: {target}")

    # 3. 获取版本信息
    version = download_release_info()
    if version:
        log(f"最新版本: v{version}")

    # 4. 创建临时目录并下载
    install_dir = get_install_dir()
    os.makedirs(str(install_dir), exist_ok=True)

    tmp_dir = tempfile.mkdtemp(prefix="opencode_install_")
    try:
        extracted_bin = download_opencode(target, version, tmp_dir)

        # 5. 安装
        dest_bin = install_dir / BIN_NAME
        shutil.copy2(extracted_bin, str(dest_bin))
        if not IS_WINDOWS:
            os.chmod(str(dest_bin), 0o755)

        log(f"已安装到: {dest_bin}")

        # 6. 添加到 PATH
        if IS_WINDOWS:
            add_to_path_windows(install_dir)
        else:
            add_to_path_unix(install_dir)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    log("安装完成！运行 'opencode' 即可启动")
    print()


if __name__ == "__main__":
    main()
