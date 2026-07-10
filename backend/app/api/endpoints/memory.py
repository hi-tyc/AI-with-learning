from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime
import os

from app.api.endpoints.auth import get_current_user
from app.core.user_data import get_user_path, get_user_subject, get_problems_path
from app.core.paths import MEMORY_DIR
from app.utils.file_lock import read_json, write_json

router = APIRouter()


def _get_memory_path(username: str) -> str:
    return os.path.join(MEMORY_DIR, f"{username}_daily.json")


@router.get("")
async def get_memory(request: Request, username: str = Depends(get_current_user)):
    memory = await read_json(_get_memory_path(username)) or _default_memory()
    user = await read_json(get_user_path(username)) or {}
    memory["profile"] = {
        "username": user.get("username", ""),
        "grade": user.get("grade", "八年级"),
        "school": user.get("school", ""),
    }
    return memory


def _default_memory():
    return {"summaries": [], "daily": "", "preferences": {}}


@router.post("/force-summary")
async def force_summary(request: Request, username: str = Depends(get_current_user)):
    subject = await get_user_subject(username)
    problems = await read_json(get_problems_path(username, subject)) or []
    recent = problems[-5:]
    summary = "最近学习了 " + str(len(recent)) + " 道题"
    memory_path = _get_memory_path(username)
    memory = await read_json(memory_path) or _default_memory()
    summaries = memory.get("summaries", [])
    summaries.append({"date": datetime.now().isoformat(), "text": summary})
    if len(summaries) > 7:
        summaries = summaries[-7:]
    memory["summaries"] = summaries
    await write_json(memory_path, memory)
    return {"message": "摘要已生成", "summary": summary}
