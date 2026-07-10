from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

from app.api.endpoints.auth import get_current_user
from app.core.user_data import get_user_subject, get_sessions_path, get_problems_path, read_user_data, migrate_old_user_data
from app.utils.file_lock import read_json, write_json

router = APIRouter()


class SessionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class SessionMove(BaseModel):
    target_session_id: str


@router.get("")
async def list_sessions(
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    sessions = await read_user_data(username, subject, "sessions") or []
    if not sessions:
        await migrate_old_user_data(username, subject, "sessions")
        sessions = await read_user_data(username, subject, "sessions") or []
    problems = await read_user_data(username, subject, "problems") or []
    counts = {}
    for p in problems:
        sid = p.get("session_id", "")
        if sid:
            counts[sid] = counts.get(sid, 0) + 1
    return {
        "items": [
            {
                "id": s["id"],
                "name": s["name"],
                "description": s.get("description", ""),
                "created_at": s["created_at"],
                "problem_count": counts.get(s["id"], 0),
            }
            for s in sessions
        ]
    }


@router.post("")
async def create_session(
    req: SessionCreate,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    sessions = await read_json(get_sessions_path(username, subject)) or []
    session = {
        "id": str(uuid.uuid4())[:8],
        "name": req.name,
        "description": req.description or "",
        "created_at": datetime.now().isoformat(),
    }
    sessions.append(session)
    await write_json(get_sessions_path(username, subject), sessions)
    return session


@router.put("/{session_id}")
async def update_session(
    session_id: str,
    req: SessionUpdate,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    sessions = await read_json(get_sessions_path(username, subject)) or []
    for s in sessions:
        if s["id"] == session_id:
            if req.name is not None:
                s["name"] = req.name
            if req.description is not None:
                s["description"] = req.description
            await write_json(get_sessions_path(username, subject), sessions)
            return s
    raise HTTPException(status_code=404, detail="会话不存在")


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    sessions = await read_json(get_sessions_path(username, subject)) or []
    default_session = None
    for s in sessions:
        if s["id"] != session_id:
            default_session = s
            break
    new_sessions = [s for s in sessions if s["id"] != session_id]
    if len(new_sessions) == len(sessions):
        raise HTTPException(status_code=404, detail="会话不存在")
    if default_session:
        problems_path = get_problems_path(username, subject)
        problems = await read_json(problems_path) or []
        changed = False
        for p in problems:
            if p.get("session_id") == session_id:
                p["session_id"] = default_session["id"]
                changed = True
        if changed:
            await write_json(problems_path, problems)
    await write_json(get_sessions_path(username, subject), new_sessions)
    return {"message": "已删除"}


@router.get("/{session_id}/problems")
async def get_session_problems(
    session_id: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    problems_path = get_problems_path(username, subject)
    problems = await read_json(problems_path) or []
    result = []
    for p in problems:
        if p.get("session_id") == session_id:
            result.append({
                "id": p["id"],
                "subject": p.get("subject", ""),
                "content": p.get("content", ""),
                "knowledge_point": p.get("knowledge_point", ""),
                "is_wrong": p.get("is_wrong", False),
                "is_shared": p.get("is_shared", False),
                "created_at": p.get("created_at", ""),
                "solved_at": p.get("solved_at"),
                "solution": p.get("solution", ""),
                "image_file_id": p.get("image_file_id"),
            })
    return result


@router.post("/{session_id}/move-problems")
async def move_problems_to_session(
    session_id: str,
    req: SessionMove,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    problems_path = get_problems_path(username, subject)
    problems = await read_json(problems_path) or []
    changed = False
    for p in problems:
        if p.get("session_id") == session_id:
            p["session_id"] = req.target_session_id
            changed = True
    if changed:
        await write_json(problems_path, problems)
    return {"message": "已移动"}
