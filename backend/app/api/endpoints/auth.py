from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel
import uuid
from datetime import datetime
import os

from app.core.paths import USERS_DIR
from app.core.user_data import (
    get_user_path, get_user_config_path, get_user_subject, set_user_subject,
    user_data_path
)
from app.core.admin_auth import verify_admin_password, get_admin_config
from app.utils.file_lock import read_json, write_json

router = APIRouter()

sessions: dict[str, str] = {}


class LoginRequest(BaseModel):
    username: str
    password: str = ""
    subject: str = "数学"


async def get_current_user(request: Request) -> str:
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="未登录")
    return sessions[session_id]


def _default_user(username: str) -> dict:
    return {
        "username": username,
        "grade": "八年级",
        "school": "",
        "created_at": datetime.now().isoformat(),
    }


def _default_config(username: str, subject: str = "数学") -> dict:
    return {
        "username": username,
        "subject": subject,
        "deepseek_api_key": "",
        "deepseek_model": "flash",
        "kimi_api_type": "platform",
        "kimi_api_key": "",
        "kimi_model": "kimi-k2.6",
        "daily_cost_limit": 10.0,
        "image_max_size_mb": 10,
        "image_compress_quality": 40,
        "image_max_long_edge": 800,
        "kimi_timeout": 120,
        "deepseek_timeout": 120,
        "retry_count": 2,
        "retry_interval": 3,
    }


_LEGACY_SUFFIXES = ["problems", "sessions", "usage", "wrong", "solve_sessions", "materials"]


async def _migrate_legacy_data(username: str, subject: str) -> None:
    for suffix in _LEGACY_SUFFIXES:
        old_path = os.path.join(USERS_DIR, f"{username}_{suffix}.json")
        new_path = user_data_path(username, subject, suffix)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            data = await read_json(old_path)
            if data:
                await write_json(new_path, data)


@router.post("/login")
async def login(req: LoginRequest, response: Response):
    username = req.username.strip()
    if not username or len(username) > 20:
        raise HTTPException(status_code=400, detail="用户名无效")

    subject = req.subject.strip() if req.subject.strip() else "数学"
    if subject not in ("数学", "英语", "对话"):
        raise HTTPException(status_code=400, detail="学科只能是数学、英语或对话")

    # 管理员 (root) 需要密码验证
    if username == "root":
        password = req.password or ""
        if not await verify_admin_password(password):
            raise HTTPException(status_code=401, detail="管理员密码错误")
        await get_admin_config()

    user_path = get_user_path(username)
    user = await read_json(user_path)
    if user is None:
        user = _default_user(username)
        await write_json(user_path, user)
        config = _default_config(username, subject)
        await write_json(get_user_config_path(username), config)
    else:
        config = await read_json(get_user_config_path(username)) or {}
        config["subject"] = subject
        await write_json(get_user_config_path(username), config)

    await _migrate_legacy_data(username, subject)

    session_id = str(uuid.uuid4())
    sessions[session_id] = username
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return {"username": username, "subject": subject, "is_admin": username == "root", "message": "登录成功"}


@router.get("/me")
async def get_me(request: Request, username: str = Depends(get_current_user)):
    user = await read_json(get_user_path(username))
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    subject = await get_user_subject(username)
    user["subject"] = subject
    user["is_admin"] = (username == "root")
    return user


@router.post("/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]
    response.delete_cookie("session_id")
    return {"message": "已退出"}


@router.put("/me")
async def update_me(
    request: Request,
    data: dict,
    username: str = Depends(get_current_user),
):
    user_path = get_user_path(username)
    user = await read_json(user_path) or {}
    user["grade"] = data.get("grade", user.get("grade", "八年级"))
    user["school"] = data.get("school", user.get("school", ""))
    user["preferences"] = data.get("preferences", user.get("preferences", ""))
    await write_json(user_path, user)
    return {"message": "资料已更新"}


@router.get("/subject")
async def get_subject(
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    return {"subject": subject}


@router.put("/subject")
async def switch_subject(
    request: Request,
    data: dict,
    username: str = Depends(get_current_user),
):
    subject = data.get("subject", "数学")
    if subject not in ("数学", "英语", "对话"):
        raise HTTPException(status_code=400, detail="学科只能是数学、英语或对话")
    await set_user_subject(username, subject)
    return {"subject": subject, "message": "学科已切换"}
