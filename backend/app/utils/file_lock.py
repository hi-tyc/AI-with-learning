import asyncio
import json
import os
from typing import Optional, Any

_locks: dict[str, asyncio.Lock] = {}


def _get_lock(path: str) -> asyncio.Lock:
    if path not in _locks:
        _locks[path] = asyncio.Lock()
    return _locks[path]


async def read_json(path: str) -> Optional[Any]:
    lock = _get_lock(path)
    async with lock:
        return await _read_json(path)


async def write_json(path: str, data: Any):
    lock = _get_lock(path)
    async with lock:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


async def update_json(path: str, updater):
    """原子性地读取、修改、写入JSON文件。整个读-改-写过程持有锁。"""
    lock = _get_lock(path)
    async with lock:
        data = await _read_json(path)
        if data is None:
            data = []
        result = updater(data)
        if result is not None:
            data = result
        await _write_json_direct(path, data)
        return data


async def _read_json(path: str) -> Optional[Any]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        bak = path + ".bak"
        try:
            os.replace(path, bak)
        except Exception:
            pass
        return None


async def _write_json_direct(path: str, data: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
