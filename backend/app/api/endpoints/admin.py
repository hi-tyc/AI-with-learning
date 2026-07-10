from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import os
import shutil
from datetime import datetime, date
from typing import Optional

from app.api.endpoints.auth import get_current_user_profile
from app.core.admin_auth import change_admin_password, verify_admin_password
from app.core.paths import DATA_DIR, UPLOAD_DIR, USERS_DIR, SHARED_DIR, MEMORY_DIR
from app.utils.file_lock import read_json, write_json

router = APIRouter()


async def get_current_admin(request: Request, user: dict = Depends(get_current_user_profile)) -> str:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user.get("username", "root")


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class DeleteUserRequest(BaseModel):
    username: str


# ─── 系统状态 ───

@router.get("/status")
async def admin_status(request: Request, username: str = Depends(get_current_admin)):
    total_size = 0
    file_count = 0
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total_size += os.path.getsize(fp)
                file_count += 1
            except Exception:
                pass

    disk_usage = shutil.disk_usage(DATA_DIR)
    disk_free = disk_usage.free
    disk_total = disk_usage.total
    disk_used = disk_total - disk_free

    user_count = len([f for f in os.listdir(USERS_DIR) if f.endswith(".json") and not f.endswith("_config.json")])

    return {
        "data_files": file_count,
        "data_size_mb": round(total_size / 1024 / 1024, 2),
        "disk_used_mb": round(disk_used / 1024 / 1024, 2),
        "disk_free_mb": round(disk_free / 1024 / 1024, 2),
        "disk_total_mb": round(disk_total / 1024 / 1024, 2),
        "disk_free_percent": round(disk_free / disk_total * 100, 1),
        "low_space_warning": disk_free < 100 * 1024 * 1024,
        "user_count": user_count,
    }


# ─── 用户管理 ───

def _is_today(iso_str: str) -> bool:
    if not iso_str:
        return False
    try:
        return datetime.fromisoformat(iso_str).strftime("%Y-%m-%d") == date.today().isoformat()
    except Exception:
        return False


@router.get("/users")
async def list_users(request: Request, username: str = Depends(get_current_admin)):
    users = {}
    for f in os.listdir(USERS_DIR):
        if not f.endswith(".json") or f.endswith(".tmp"):
            continue
        if not os.path.isfile(os.path.join(USERS_DIR, f)):
            continue
        path = os.path.join(USERS_DIR, f)
        try:
            user_data = await read_json(path)
            if not user_data or not isinstance(user_data, dict):
                continue
            uname = user_data.get("username")
            if not uname:
                continue
            # Skip data/config files that happen to be JSON dicts but aren't user profiles.
            if f != f"{uname}.json":
                continue
            mtime = os.path.getmtime(path)
            users[uname] = {
                "username": uname,
                "real_name": user_data.get("real_name") or uname,
                "role": user_data.get("role", "teacher"),
                "status": user_data.get("status", "active"),
                "created_at": user_data.get("created_at", ""),
                "school": user_data.get("school", ""),
                "last_modified": datetime.fromtimestamp(mtime).isoformat(),
            }
        except Exception:
            pass

    items = sorted(users.values(), key=lambda u: u.get("created_at", ""), reverse=True)
    return {"items": items, "total": len(items)}


@router.get("/users/{target_username}")
async def get_user_detail(target_username: str, request: Request, username: str = Depends(get_current_admin)):
    user_path = os.path.join(USERS_DIR, f"{target_username}.json")
    config_path = os.path.join(USERS_DIR, f"{target_username}_config.json")

    user_data = await read_json(user_path) or {}
    config = await read_json(config_path) or {}

    # List user's data files
    data_files = []
    for f in os.listdir(USERS_DIR):
        if f.startswith(f"{target_username}_") and f.endswith(".json"):
            fpath = os.path.join(USERS_DIR, f)
            try:
                size = os.path.getsize(fpath)
                mtime = os.path.getmtime(fpath)
                data_files.append({
                    "filename": f,
                    "size_bytes": size,
                    "last_modified": datetime.fromtimestamp(mtime).isoformat(),
                })
            except Exception:
                pass

    return {
        "user": user_data,
        "config": config,
        "data_files": data_files,
    }


@router.delete("/users/{target_username}")
async def delete_user(target_username: str, request: Request, username: str = Depends(get_current_admin)):
    if target_username == "root":
        raise HTTPException(status_code=400, detail="不能删除管理员账户")

    deleted = []
    prefix = f"{target_username}_"
    for f in os.listdir(USERS_DIR):
        if f == f"{target_username}.json" or (f.startswith(prefix) and f.endswith(".json")):
            try:
                os.remove(os.path.join(USERS_DIR, f))
                deleted.append(f)
            except Exception:
                pass

    return {"message": f"用户 {target_username} 已删除", "deleted_files": len(deleted)}


# ─── 修改管理员密码 ───

@router.post("/change-password")
async def change_password(
    req: PasswordChangeRequest,
    request: Request,
    username: str = Depends(get_current_admin),
):
    if not req.old_password or not req.new_password:
        raise HTTPException(status_code=400, detail="请提供旧密码和新密码")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少需要6个字符")
    if not await change_admin_password(req.old_password, req.new_password):
        raise HTTPException(status_code=400, detail="旧密码错误")
    return {"message": "密码已修改"}


# ─── 管理员诊断检查 ───

@router.post("/diagnose")
async def admin_diagnose(request: Request, username: str = Depends(get_current_admin)):
    status = await admin_status(request, username)
    suggestions = []
    if status["low_space_warning"]:
        suggestions.append("磁盘空间不足 100MB，建议清理数据")
    if status["data_size_mb"] > 500:
        suggestions.append("数据文件超过 500MB，建议归档旧数据")
    return {
        "status": status,
        "suggestions": suggestions,
        "warning_level": "high" if status["low_space_warning"] else "normal",
    }


# ─── 系统日志查看 ───

@router.get("/logs")
async def view_logs(
    request: Request,
    username: str = Depends(get_current_admin),
    lines: int = 100,
):
    log_files = []
    from app.core.paths import BASE_DIR
    base_dir = BASE_DIR
    for f in ["backend.log", "server.log", "backend6.log", "frontend.log"]:
        fpath = os.path.join(base_dir, f)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    all_lines = fh.readlines()
                    tail = all_lines[-lines:]
                log_files.append({
                    "filename": f,
                    "size_bytes": os.path.getsize(fpath),
                    "lines": len(all_lines),
                    "tail": "".join(tail),
                })
            except Exception as e:
                log_files.append({"filename": f, "error": str(e)})

    return {"logs": log_files}


# ─── 数据清理 ───

@router.post("/purge-temp")
async def purge_temp_data(request: Request, username: str = Depends(get_current_admin)):
    temp_dir = os.path.join(os.path.dirname(DATA_DIR), "temp")
    count = 0
    if os.path.exists(temp_dir):
        for f in os.listdir(temp_dir):
            fpath = os.path.join(temp_dir, f)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
                    count += 1
                elif os.path.isdir(fpath):
                    shutil.rmtree(fpath)
                    count += 1
            except Exception:
                pass
    return {"message": f"已清理 {count} 个临时文件"}


# ─── 用量统计 (所有用户) ───

@router.get("/usage-summary")
async def admin_usage_summary(request: Request, username: str = Depends(get_current_admin)):
    items = []
    for f in os.listdir(USERS_DIR):
        if not f.endswith("_usage.json") or f.endswith(".tmp"):
            continue
        base = f.replace("_usage.json", "")
        parts = base.rsplit("_", 1)
        uname = parts[0]
        subj = parts[1] if len(parts) > 1 else ""
        fpath = os.path.join(USERS_DIR, f)
        try:
            records = await read_json(fpath)
            if not records or not isinstance(records, list):
                continue
            today_records = [r for r in records if _is_today(r.get("created_at", ""))]
            tokens_in = sum((r.get("input_cache_hit", 0) or 0) + (r.get("input_cache_miss", 0) or 0) for r in today_records)
            tokens_out = sum(r.get("output", 0) or 0 for r in today_records)
            cost = sum(r.get("cost_yuan", 0) or 0 for r in today_records)
            today_count = len(today_records)

            items.append({
                "username": uname,
                "subject": subj,
                "today_tokens_in": int(tokens_in),
                "today_tokens_out": int(tokens_out),
                "today_cost": round(cost, 6),
                "today_count": today_count,
            })
        except Exception:
            pass

    items.sort(key=lambda x: x["today_cost"], reverse=True)
    return {"items": items, "total": len(items)}


# ─── 系统信息 ───

@router.get("/info")
async def system_info(request: Request, username: str = Depends(get_current_admin)):
    import platform
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
        "data_dir": DATA_DIR,
        "users_dir": USERS_DIR,
        "backend_dir": os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    }
