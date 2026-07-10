from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
import os
import uuid
from datetime import datetime

from app.api.endpoints.auth import get_current_user
from app.core.user_data import get_user_subject, get_problems_path
from app.core.paths import DATA_DIR, UPLOAD_DIR
from app.utils.file_lock import read_json, write_json

router = APIRouter()


class PathRenameRequest(BaseModel):
    old_path: str
    new_path: str


class PathCreateRequest(BaseModel):
    path: str


@router.post("/rename")
async def rename_path(
    req: PathRenameRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    from app.api.endpoints.problems import PATH_MAP
    subject = await get_user_subject(username)
    problems = await read_json(get_problems_path(username, subject)) or []
    old_parts = req.old_path.strip("/").split("/")
    new_parts = req.new_path.strip("/").split("/")
    updated = 0
    for p in problems:
        match = True
        keys = ["subject", "exam", "source", "school", "big_question", "small_question"]
        for i, op in enumerate(old_parts):
            if i < len(keys) and p.get(keys[i]) != op:
                match = False
                break
        if match:
            for i, np in enumerate(new_parts):
                if i < len(keys):
                    p[keys[i]] = np
            updated += 1
    await write_json(get_problems_path(username, subject), problems)
    return {"message": f"已重命名 {updated} 道题的路径"}


@router.post("/create")
async def create_path(
    req: PathCreateRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    path = req.path.strip("/")
    if not path:
        raise HTTPException(status_code=400, detail="路径不能为空")
    safe = "".join(c if c.isalnum() or c in "_-/" else "_" for c in path)
    parts = safe.split("/")

    subject = await get_user_subject(username)
    problems = await read_json(get_problems_path(username, subject)) or []
    keys = ["subject", "exam", "source", "school", "big_question", "small_question"]

    # Create a placeholder problem so the folder becomes visible in the tree.
    problem = {
        "id": str(uuid.uuid4())[:8],
        "content": "[空文件夹占位，可删除或替换为真实题目]",
        "is_placeholder": True,
        "created_at": datetime.now().isoformat(),
        "solved_at": None,
        "solution": "",
        "solved_by": None,
        "session_id": "",
        "parent_id": "",
        "is_big_question": False,
        "upload_mode": "algebra",
        "image_file_id": None,
        "knowledge_point": "",
        "is_wrong": False,
        "is_shared": False,
    }
    for i, part in enumerate(parts):
        if i < len(keys):
            problem[keys[i]] = part
    for key in keys:
        if key not in problem:
            problem[key] = ""

    problems.append(problem)
    await write_json(get_problems_path(username, subject), problems)
    return {"path": safe, "message": "路径已创建"}


@router.delete("/{path:path}")
async def delete_path(
    path: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    problems = await read_json(get_problems_path(username, subject)) or []
    path_parts = path.strip("/").split("/")
    keys = ["subject", "exam", "source", "school", "big_question", "small_question"]
    matching = []
    for p in problems:
        match = True
        for i, pp in enumerate(path_parts):
            if i < len(keys) and p.get(keys[i]) != pp:
                match = False
                break
        if match:
            matching.append(p)
    if matching:
        raise HTTPException(
            status_code=400,
            detail=f"该路径下还有 {len(matching)} 道题，请先删除题目"
        )
    return {"message": "路径已删除"}
