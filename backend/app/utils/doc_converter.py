import asyncio
import os
import subprocess
import tempfile
import shutil
import logging

logger = logging.getLogger("doc_converter")

# LibreOffice 路径解析：环境变量 > which/where 自动检测 > Windows 默认路径
_SOFFICE_CACHE = None


def _find_soffice() -> str | None:
    """查找 LibreOffice 可执行文件路径。"""
    global _SOFFICE_CACHE
    if _SOFFICE_CACHE is not None:
        return _SOFFICE_CACHE

    # 1. 环境变量
    env_path = os.environ.get("LIBREOFFICE_PATH")
    if env_path:
        if os.path.exists(env_path):
            _SOFFICE_CACHE = env_path
            return _SOFFICE_CACHE
        logger.warning(f"LIBREOFFICE_PATH 环境变量指向的文件不存在: {env_path}")

    # 2. 系统 PATH 自动检测
    soffice_cmd = "soffice.exe" if os.name == "nt" else "soffice"
    which = shutil.which(soffice_cmd)
    if which:
        _SOFFICE_CACHE = which
        return _SOFFICE_CACHE

    # 3. Windows 常见安装路径 fallback
    if os.name == "nt":
        win_candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\LibreOffice\program\soffice.exe"),
        ]
        for p in win_candidates:
            if os.path.exists(p):
                _SOFFICE_CACHE = p
                return _SOFFICE_CACHE

    _SOFFICE_CACHE = None
    return None


def _soffice_exists() -> bool:
    return _find_soffice() is not None


def _convert_sync(docx_path: str, output_dir: str) -> str | None:
    """Synchronous fallback using subprocess.run."""
    soffice = _find_soffice()
    if not soffice:
        logger.error("LibreOffice not found")
        return None

    base = os.path.splitext(os.path.basename(docx_path))[0]
    pdf_path = os.path.join(output_dir, f"{base}.pdf")
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        return pdf_path

    user_dir = os.path.join(tempfile.gettempdir(), f"lo_{base}")
    os.makedirs(user_dir, exist_ok=True)
    try:
        result = subprocess.run(
            [
                soffice,
                "--headless",
                f"-env:UserInstallation=file:///{user_dir.replace(os.sep, '/')}",
                "--convert-to", "pdf:writer_pdf_Export",
                "--outdir", output_dir,
                docx_path,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error(f"LibreOffice sync failed (returncode={result.returncode}): "
                         f"stdout={result.stdout[:200]} stderr={result.stderr[:200]}")
            return None
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return pdf_path
        logger.error(f"LibreOffice sync: PDF not found at {pdf_path}")
        return None
    except subprocess.TimeoutExpired:
        logger.error("LibreOffice sync timed out after 120s")
        return None
    except Exception as e:
        logger.error(f"LibreOffice sync exception: {e}")
        return None
    finally:
        shutil.rmtree(user_dir, ignore_errors=True)


async def convert_docx_to_pdf(docx_path: str, output_dir: str) -> str | None:
    if not os.path.exists(docx_path):
        logger.error(f"docx not found: {docx_path}")
        return None

    soffice = _find_soffice()
    if not soffice:
        logger.error("LibreOffice not found")
        return None

    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(docx_path))[0]
    pdf_path = os.path.join(output_dir, f"{base}.pdf")

    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        return pdf_path

    user_dir = os.path.join(tempfile.gettempdir(), f"lo_{base}")
    os.makedirs(user_dir, exist_ok=True)
    try:
        proc = await asyncio.create_subprocess_exec(
            soffice,
            "--headless",
            f"-env:UserInstallation=file:///{user_dir.replace(os.sep, '/')}",
            "--convert-to", "pdf:writer_pdf_Export",
            "--outdir", output_dir,
            docx_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            logger.error("LibreOffice async timed out after 120s")
            try:
                proc.kill()
            except Exception:
                pass
            return None

        if proc.returncode != 0:
            err_text = stderr.decode("utf-8", errors="replace")[:500] if stderr else ""
            logger.error(
                f"LibreOffice async failed (returncode={proc.returncode}): {err_text}"
            )
            return None

        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return pdf_path

        logger.error(f"LibreOffice async: PDF not found at {pdf_path}")
        return None
    except Exception as e:
        logger.error(f"LibreOffice async exception: {e}")
        return None
    finally:
        shutil.rmtree(user_dir, ignore_errors=True)
