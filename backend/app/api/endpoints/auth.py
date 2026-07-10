from datetime import datetime
import hashlib
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.admin_auth import get_admin_config, verify_admin_password
from app.core.paths import REGISTRATION_DIR, USERS_DIR
from app.core.user_data import get_user_config_path, get_user_path, user_data_path
from app.utils.file_lock import read_json, write_json

router = APIRouter()

sessions: dict[str, str] = {}
PASSWORD_SALT = "studybuddy-auth-v2"
DEFAULT_SUBJECT = "英语"
LEGACY_SUFFIXES = ["problems", "sessions", "usage", "wrong", "solve_sessions", "materials"]
FACE_CONSENT_VERSION = "face-consent-v1"
FACE_CONSENT_TEXT = [
    "本人知悉本系统会在注册阶段采集一段现场人脸视频，仅用于身份核验、人工审核和防止冒用注册。",
    "采集内容仅限注册时主动录制并上传的视频文件，不会在未授权的情况下持续开启摄像头或进行其他用途分析。",
    "该视频仅限管理员或经授权的审核人员查看，未经额外授权不会对外公开、转让或挪作教学无关用途。",
    "若注册申请被拒绝、撤回或超过内部保留期限，学校或机构应按管理规则删除或停用该视频资料。",
    "本人确认提交前已获得监护人或本人合法授权，并同意系统保存本次授权版本与确认时间作为审计记录。",
]


class LoginRequest(BaseModel):
    username: str
    password: str = ""


async def get_current_user(request: Request) -> str:
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="未登录")
    return sessions[session_id]


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"{PASSWORD_SALT}:{password}".encode("utf-8")).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    return bool(password_hash) and _hash_password(password) == password_hash


def _is_strong_password(password: str) -> bool:
    if len(password) < 8:
        return False
    return any(ch.isalpha() for ch in password) and any(ch.isdigit() for ch in password)


def _default_registration() -> dict:
    return {
        "captcha_verified": False,
        "human_check_value": "",
        "face_video_name": "",
        "face_video_path": "",
        "face_video_deleted_at": None,
        "face_video_delete_reason": "",
        "face_detection_supported": False,
        "face_aligned": False,
        "face_consent_accepted": False,
        "face_consent_version": "",
        "face_consent_at": None,
        "submitted_at": None,
        "review_notes": "",
        "reviewed_at": None,
    }


def _default_user(username: str, role: str = "teacher", real_name: Optional[str] = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "username": username,
        "real_name": real_name or username,
        "role": role,
        "status": "active" if role in ("admin", "teacher") else "pending",
        "approval_status": "approved" if role in ("admin", "teacher") else "pending",
        "class_type_ids": [],
        "class_ids": [],
        "expires_at": None,
        "password_hash": "",
        "registration": _default_registration(),
        "school": "",
        "preferences": "",
        "created_at": datetime.now().isoformat(),
    }


def _default_config(username: str) -> dict:
    return {
        "username": username,
        "subject": DEFAULT_SUBJECT,
        "kimi_api_type": "platform",
        "kimi_api_key": "",
        "kimi_model": "kimi-k2.7-code",
        "daily_cost_limit": 10.0,
        "image_max_size_mb": 10,
        "image_compress_quality": 40,
        "image_max_long_edge": 800,
        "kimi_timeout": 120,
        "retry_count": 2,
        "retry_interval": 3,
    }


def _normalize_user(user: dict | None, username: str) -> dict:
    base = _default_user(username, role="admin" if username == "root" else "teacher")
    if isinstance(user, dict):
        base.update(user)
    base["username"] = username
    base["real_name"] = base.get("real_name") or username
    base["role"] = base.get("role") or ("admin" if username == "root" else "teacher")
    base["status"] = base.get("status") or "active"
    base["approval_status"] = base.get("approval_status") or ("approved" if base["status"] == "active" else "pending")
    base["class_type_ids"] = list(dict.fromkeys(base.get("class_type_ids") or []))
    base["class_ids"] = list(dict.fromkeys(base.get("class_ids") or []))
    registration = _default_registration()
    if isinstance(base.get("registration"), dict):
        registration.update(base["registration"])
    base["registration"] = registration
    return base


async def _load_user_record(username: str) -> dict | None:
    user = await read_json(get_user_path(username))
    if user is None:
        return None
    normalized = _normalize_user(user, username)
    if normalized != user:
        await write_json(get_user_path(username), normalized)
    return normalized


async def _migrate_legacy_data(username: str) -> None:
    for suffix in LEGACY_SUFFIXES:
        old_path = os.path.join(USERS_DIR, f"{username}_{suffix}.json")
        new_path = user_data_path(username, DEFAULT_SUBJECT, suffix)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            data = await read_json(old_path)
            if data:
                await write_json(new_path, data)


async def get_current_user_profile(
    request: Request,
    username: str = Depends(get_current_user),
) -> dict:
    user = await _load_user_record(username)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.get("status") != "active":
        raise HTTPException(status_code=403, detail="账号未激活")
    expires_at = user.get("expires_at")
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at) < datetime.now():
                raise HTTPException(status_code=403, detail="账号已过期")
        except ValueError:
            pass
    return user


def require_roles(*roles: str):
    async def _checker(user: dict = Depends(get_current_user_profile)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return user
    return _checker


@router.get("/face-consent")
async def get_face_consent():
    return {
        "version": FACE_CONSENT_VERSION,
        "title": "人脸视频采集授权书",
        "items": FACE_CONSENT_TEXT,
        "checkbox_label": "我已阅读并同意上述人脸视频采集、审核与留存说明",
    }


@router.post("/register")
async def register(
    username: str = Form(...),
    real_name: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(""),
    captcha_token: str = Form(""),
    human_check_value: str = Form(""),
    class_id: str = Form(""),
    face_detection_supported: bool = Form(False),
    face_aligned: bool = Form(False),
    face_consent_accepted: bool = Form(False),
    face_consent_version: str = Form(""),
    face_video: UploadFile | None = File(None),
):
    username = username.strip()
    real_name = real_name.strip()
    if not username or len(username) > 20:
        raise HTTPException(status_code=400, detail="用户名无效")
    if not real_name:
        raise HTTPException(status_code=400, detail="真实姓名不能为空")
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="两次密码不一致")
    if not _is_strong_password(password):
        raise HTTPException(status_code=400, detail="密码至少 8 位，且需包含字母和数字")
    if not captcha_token.strip():
        raise HTTPException(status_code=400, detail="请完成人机验证")
    if not human_check_value.strip():
        raise HTTPException(status_code=400, detail="请填写验证结果")
    if not face_consent_accepted:
        raise HTTPException(status_code=400, detail="请先确认人脸采集授权")
    if face_consent_version.strip() != FACE_CONSENT_VERSION:
        raise HTTPException(status_code=400, detail="授权版本无效，请刷新页面后重试")
    if face_video is None:
        raise HTTPException(status_code=400, detail="请录制人脸视频")
    if await read_json(get_user_path(username)) is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = _default_user(username, role="student", real_name=real_name)
    user["status"] = "pending"
    user["approval_status"] = "pending"
    user["class_ids"] = [class_id] if class_id else []
    user["password_hash"] = _hash_password(password)

    raw_video = await face_video.read()
    if not raw_video:
        raise HTTPException(status_code=400, detail="视频内容为空")
    ext = os.path.splitext(face_video.filename or "")[1].lower() or ".webm"
    saved_name = f"{username}_{uuid.uuid4().hex[:8]}{ext}"
    saved_path = os.path.join(REGISTRATION_DIR, saved_name)
    with open(saved_path, "wb") as f:
        f.write(raw_video)

    user["registration"] = {
        "captcha_verified": bool(captcha_token),
        "human_check_value": human_check_value.strip(),
        "face_video_name": face_video.filename or saved_name,
        "face_video_path": saved_path,
        "face_video_deleted_at": None,
        "face_video_delete_reason": "",
        "face_detection_supported": bool(face_detection_supported),
        "face_aligned": bool(face_aligned),
        "face_consent_accepted": True,
        "face_consent_version": FACE_CONSENT_VERSION,
        "face_consent_at": datetime.now().isoformat(),
        "submitted_at": datetime.now().isoformat(),
        "review_notes": "",
        "reviewed_at": None,
    }
    await write_json(get_user_path(username), user)
    await write_json(get_user_config_path(username), _default_config(username))
    return {"message": "注册申请已提交，等待管理员审核"}


@router.post("/login")
async def login(req: LoginRequest, response: Response):
    username = req.username.strip()
    if not username or len(username) > 20:
        raise HTTPException(status_code=400, detail="用户名无效")

    if username == "root":
        if not await verify_admin_password(req.password or ""):
            raise HTTPException(status_code=401, detail="管理员密码错误")
        await get_admin_config()
        user = await _load_user_record(username)
        if user is None:
            user = _default_user(username, role="admin", real_name="管理员")
            await write_json(get_user_path(username), user)
        if await read_json(get_user_config_path(username)) is None:
            await write_json(get_user_config_path(username), _default_config(username))
    else:
        user = await _load_user_record(username)
        if user is None:
            raise HTTPException(status_code=404, detail="账号不存在，请联系管理员创建")
        if user.get("role") == "student":
            raise HTTPException(status_code=403, detail="学生端尚未开放，请等待管理员通知")
        password_hash = user.get("password_hash", "")
        if password_hash and not _verify_password(req.password or "", password_hash):
            raise HTTPException(status_code=401, detail="密码错误")
        if user.get("approval_status") == "rejected":
            raise HTTPException(status_code=403, detail="账号未通过审核")
        if user.get("status") != "active":
            raise HTTPException(status_code=403, detail="账号未激活")

    if await read_json(get_user_config_path(username)) is None:
        await write_json(get_user_config_path(username), _default_config(username))
    await _migrate_legacy_data(username)

    session_id = str(uuid.uuid4())
    sessions[session_id] = username
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return {
        "username": username,
        "real_name": user.get("real_name") or username,
        "role": user.get("role") or ("admin" if username == "root" else "teacher"),
        "is_admin": (user.get("role") == "admin") or username == "root",
        "message": "登录成功",
    }


@router.get("/me")
async def get_me(request: Request, username: str = Depends(get_current_user)):
    user = await _load_user_record(username)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user["is_admin"] = user.get("role") == "admin" or username == "root"
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
    user = _normalize_user(await read_json(user_path), username)
    user["real_name"] = data.get("real_name", user.get("real_name", username))
    user["school"] = data.get("school", user.get("school", ""))
    user["preferences"] = data.get("preferences", user.get("preferences", ""))
    user["expires_at"] = data.get("expires_at", user.get("expires_at"))
    await write_json(user_path, user)
    return {"message": "资料已更新"}


@router.get("/registration-video/{username}")
async def get_registration_video(
    username: str,
    user: dict = Depends(require_roles("admin")),
):
    target = await _load_user_record(username)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    registration = target.get("registration") or {}
    video_path = registration.get("face_video_path", "")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="视频不存在")
    ext = os.path.splitext(video_path)[1].lower()
    media_type = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
    }.get(ext, "application/octet-stream")
    headers = {
        "Cache-Control": "private, no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }
    return FileResponse(
        video_path,
        media_type=media_type,
        headers=headers,
        content_disposition_type="inline",
    )
