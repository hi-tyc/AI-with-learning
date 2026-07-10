from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel
from typing import Optional, List
from pydantic import Field
from datetime import datetime
import uuid
import os

from app.api.endpoints.auth import get_current_user
from app.api.endpoints.match_answers import cleanup_matches_after_deletion
from app.core.user_data import (
    get_user_subject,
    get_problems_path,
    get_wrong_path,
    get_sessions_path,
    get_trash_path,
    read_user_data,
    migrate_old_user_data,
)
from app.core.paths import UPLOAD_DIR, USERS_DIR, SHARED_DIR, MEMORY_DIR
from app.utils.file_lock import read_json, write_json

router = APIRouter()


def _get_problems_path(username: str, subject: str) -> str:
    return get_problems_path(username, subject)


def _get_wrong_path(username: str, subject: str) -> str:
    return get_wrong_path(username, subject)


_PROBLEM_DEFAULTS = {
    "image_file_id": None,
    "knowledge_point": "",
    "is_wrong": False,
    "is_shared": False,
    "solved_at": None,
    "solution": "",
    "solved_by": None,
    "session_id": "",
    "parent_id": "",
    "is_big_question": False,
    "upload_mode": "algebra",
}


def _is_solved(p: dict) -> bool:
    return bool(p.get("solved_at") or (p.get("solution") or "").strip())


def _session_type(p: dict) -> str:
    return "解题" if _is_solved(p) else "录题"


def _normalize_problem(p: dict) -> bool:
    changed = False
    for key, default in _PROBLEM_DEFAULTS.items():
        if key not in p:
            p[key] = default
            changed = True
    if "created_at" not in p:
        p["created_at"] = datetime.now().isoformat()
        changed = True
    return changed


async def _load_problems_migrated(username: str, subject: str) -> list:
    problems_path = _get_problems_path(username, subject)
    problems = await read_json(problems_path)
    if problems is None:
        problems = await read_user_data(username, subject, "problems")
        if problems:
            await write_json(problems_path, problems)
    problems = problems or []

    sessions_path = get_sessions_path(username, subject)
    sessions = await read_json(sessions_path) or []

    session_renamed = False
    if sessions and problems:
        for s in sessions:
            if s.get("name") in ("数学", "英语", "未分类", subject):
                for p in problems:
                    if p.get("session_id") != s["id"]:
                        continue
                    content = p.get("content", "").strip()
                    kp = p.get("knowledge_point", "").strip()
                    if content:
                        name = content[:25] + ("..." if len(content) > 25 else "")
                        if kp:
                            name += "（" + kp + "）"
                        s["name"] = name[:40]
                        session_renamed = True
                        break

    if session_renamed:
        await write_json(sessions_path, sessions)

    if not sessions and problems:
        seen = {}
        for p in problems:
            sub = p.get("subject", "未分类")
            if sub not in seen:
                seen[sub] = {"id": str(uuid.uuid4())[:8], "first_content": ""}
            if not seen[sub]["first_content"]:
                c = p.get("content", sub)
                kp = p.get("knowledge_point", "").strip()
                name = c[:25] + ("..." if len(c) > 25 else "")
                if kp:
                    name += "（" + kp + "）"
                seen[sub]["first_content"] = name[:40]
        sessions = [
            {
                "id": info["id"],
                "name": info["first_content"] or sub,
                "description": "",
                "created_at": datetime.now().isoformat(),
            }
            for sub, info in seen.items()
        ]
        await write_json(sessions_path, sessions)

    session_map = {s["name"]: s["id"] for s in sessions}
    default_session_id = sessions[0]["id"] if sessions else ""

    changed = False
    for p in problems:
        if _normalize_problem(p):
            changed = True
        if not p.get("session_id"):
            sub = p.get("subject", "未分类")
            p["session_id"] = session_map.get(sub, default_session_id)
            changed = True

    if changed:
        await write_json(problems_path, problems)
    return problems


PATH_MAP = {
    "math": "数学", "physics": "物理", "chemistry": "化学",
    "chinese": "语文", "english": "英语", "history": "历史",
    "geography": "地理", "biology": "生物", "politics": "政治",
}


class ProblemCreate(BaseModel):
    subject: str
    exam: str
    source: str
    school: str
    big_question: str
    small_question: str
    content: str
    image_file_id: Optional[str] = None
    knowledge_point: Optional[str] = None
    is_wrong: bool = False
    is_shared: bool = False
    session_id: Optional[str] = None
    parent_id: Optional[str] = None
    is_big_question: bool = False
    upload_mode: Optional[str] = "algebra"


class ProblemUpdate(BaseModel):
    subject: Optional[str] = None
    exam: Optional[str] = None
    source: Optional[str] = None
    school: Optional[str] = None
    big_question: Optional[str] = None
    small_question: Optional[str] = None
    content: Optional[str] = None
    knowledge_point: Optional[str] = None
    is_wrong: Optional[bool] = None
    is_shared: Optional[bool] = None
    parent_id: Optional[str] = None
    is_big_question: Optional[bool] = None


@router.get("")
async def list_problems(
    request: Request,
    path: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    knowledge_point: Optional[str] = Query(None),
    is_wrong: Optional[bool] = Query(None),
    is_shared: Optional[bool] = Query(None),
    session_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(1000, ge=1, le=5000),
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    problems = await _load_problems_migrated(username, subject)
    wrong_ids_data = await read_user_data(username, subject, "wrong")
    if wrong_ids_data is None:
        await migrate_old_user_data(username, subject, "wrong")
        wrong_ids_data = await read_user_data(username, subject, "wrong") or []
    wrong_ids = set(wrong_ids_data)

    for p in problems:
        p["is_wrong"] = p["id"] in wrong_ids
        p["session_type"] = _session_type(p)

    if path:
        parts = path.split("/")
        for p in problems:
            match = True
            for i, part in enumerate(parts):
                keys = ["subject", "exam", "source", "school", "big_question", "small_question"]
                if i < len(keys) and p.get(keys[i]) != part:
                    match = False
                    break
            if not match:
                p["_filtered"] = True
    else:
        for p in problems:
            p["_filtered"] = False

    filtered = [p for p in problems if not p.get("_filtered", False)]

    if keyword:
        kw = keyword.lower()
        filtered = [p for p in filtered if kw in (p.get("content", "") + p.get("knowledge_point", "")).lower()]

    if knowledge_point:
        filtered = [p for p in filtered if knowledge_point in p.get("knowledge_point", "")]

    if is_wrong is not None:
        filtered = [p for p in filtered if p["is_wrong"] == is_wrong]

    if is_shared is not None:
        filtered = [p for p in filtered if p.get("is_shared", False) == is_shared]

    if session_id:
        filtered = [p for p in filtered if p.get("session_id") == session_id]

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": filtered[start:end],
    }


@router.post("")
async def create_problem(
    req: ProblemCreate,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    problems_path = _get_problems_path(username, subject)
    problems = await read_json(problems_path) or []

    problem = {
        "id": str(uuid.uuid4())[:8],
        "subject": req.subject,
        "exam": req.exam,
        "source": req.source,
        "school": req.school,
        "big_question": req.big_question,
        "small_question": req.small_question,
        "content": req.content,
        "image_file_id": req.image_file_id,
        "knowledge_point": req.knowledge_point or "",
        "is_wrong": req.is_wrong,
        "is_shared": req.is_shared,
        "created_at": datetime.now().isoformat(),
        "solved_at": None,
        "solution": "",
        "session_id": req.session_id or "",
        "parent_id": req.parent_id or "",
        "is_big_question": req.is_big_question,
        "upload_mode": req.upload_mode or "algebra",
    }
    problems.append(problem)
    await write_json(problems_path, problems)

    if not req.session_id:
        await _load_problems_migrated(username, subject)

    if req.is_wrong:
        wrong = await read_json(_get_wrong_path(username, subject)) or []
        wrong.append(problem["id"])
        await write_json(_get_wrong_path(username, subject), wrong)

    return problem


@router.get("/trash")
async def list_trash(
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    trash = await read_json(get_trash_path(username, subject)) or []
    trash.reverse()
    return {"items": trash, "total": len(trash)}


class RestoreRequest(BaseModel):
    ids: List[str] = Field(default_factory=list)


@router.post("/trash/restore")
async def restore_from_trash(
    req: RestoreRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    trash_path = get_trash_path(username, subject)
    trash = await read_json(trash_path) or []
    ids_set = set(req.ids)
    restored = [t for t in trash if t["id"] in ids_set]
    trash = [t for t in trash if t["id"] not in ids_set]
    await write_json(trash_path, trash)
    if restored:
        problems_path = _get_problems_path(username, subject)
        problems = await read_json(problems_path) or []
        for r in restored:
            r.pop("trashed_at", None)
            problems.append(r)
        await write_json(problems_path, problems)
    return {"message": f"已恢复 {len(restored)} 道题"}


@router.post("/trash/empty")
async def empty_trash(
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    trash = await read_json(get_trash_path(username, subject)) or []
    await write_json(get_trash_path(username, subject), [])
    await cleanup_matches_after_deletion(username, subject)
    return {"message": f"已永久删除 {len(trash)} 道题"}


class BatchDeleteRequest(BaseModel):
    ids: List[str] = Field(default_factory=list)


@router.post("/batch-delete")
async def batch_delete_problems(
    req: BatchDeleteRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    problems_path = _get_problems_path(username, subject)
    problems = await read_json(problems_path) or []
    ids_set = set(req.ids)
    kept = []
    trashed = []
    for p in problems:
        if p["id"] in ids_set:
            p["trashed_at"] = datetime.now().isoformat()
            trashed.append(p)
        else:
            kept.append(p)
    await write_json(problems_path, kept)
    wrong = await read_json(_get_wrong_path(username, subject)) or []
    wrong = [wid for wid in wrong if wid not in ids_set]
    await write_json(_get_wrong_path(username, subject), wrong)
    trash = await read_json(get_trash_path(username, subject)) or []
    trash.extend(trashed)
    await write_json(get_trash_path(username, subject), trash)
    await cleanup_matches_after_deletion(username, subject)
    return {"message": f"已移入废纸篓 {len(trashed)} 道题", "deleted": len(trashed)}


@router.get("/{problem_id}")
async def get_problem(
    problem_id: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    problems = await _load_problems_migrated(username, subject)
    for p in problems:
        if p["id"] == problem_id:
            wrong_ids = set(await read_json(_get_wrong_path(username, subject)) or [])
            p["is_wrong"] = p["id"] in wrong_ids
            p["session_type"] = _session_type(p)
            if p.get("is_big_question"):
                p["sub_problems"] = [
                    {k: sp.get(k) for k in ["id", "content", "small_question", "knowledge_point", "solved_at", "solution", "image_file_id"]}
                    for sp in problems if sp.get("parent_id") == p["id"]
                ]
            return p
    raise HTTPException(status_code=404, detail="题目不存在")


@router.put("/{problem_id}")
async def update_problem(
    problem_id: str,
    req: ProblemUpdate,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    problems_path = _get_problems_path(username, subject)
    problems = await read_json(problems_path) or []
    for p in problems:
        if p["id"] == problem_id:
            for field in req.model_fields_set:
                val = getattr(req, field)
                if val is not None:
                    p[field] = val
            await write_json(problems_path, problems)
            return p
    raise HTTPException(status_code=404, detail="题目不存在")


@router.delete("/{problem_id}")
async def delete_problem(
    problem_id: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    problems_path = _get_problems_path(username, subject)
    problems = await read_json(problems_path) or []
    target = None
    new_problems = []
    for p in problems:
        if p["id"] == problem_id:
            target = p
        else:
            new_problems.append(p)
    if target is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    await write_json(problems_path, new_problems)
    wrong = await read_json(_get_wrong_path(username, subject)) or []
    wrong = [wid for wid in wrong if wid != problem_id]
    await write_json(_get_wrong_path(username, subject), wrong)
    trash = await read_json(get_trash_path(username, subject)) or []
    target["trashed_at"] = datetime.now().isoformat()
    trash.append(target)
    await write_json(get_trash_path(username, subject), trash)
    await cleanup_matches_after_deletion(username, subject)
    return {"message": "已移入废纸篓"}


@router.post("/{problem_id}/toggle-wrong")
async def toggle_wrong(
    problem_id: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    wrong_path = _get_wrong_path(username, subject)
    wrong = await read_json(wrong_path) or []
    if problem_id in wrong:
        wrong.remove(problem_id)
        status = False
    else:
        wrong.append(problem_id)
        status = True
    await write_json(wrong_path, wrong)
    return {"is_wrong": status}
