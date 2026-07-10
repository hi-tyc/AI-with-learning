from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from fastapi import Query
import uuid
from datetime import datetime

from app.api.endpoints.auth import get_current_user
from app.core.user_data import get_user_subject, get_solve_sessions_path, get_user_config_path
from app.utils.file_lock import read_json, write_json
from app.core.pricing import extract_usage, compute_cost, get_pricing
from app.api.endpoints.solve import _migrate_old_sessions, _pricing_key

router = APIRouter()


class SolveSessionCreate(BaseModel):
    problem_id: Optional[str] = None
    problem_content: Optional[str] = None
    model: str
    engine: str
    question: str
    answer: str
    reasoning: Optional[str] = None
    has_figure: Optional[bool] = None
    image_file_id: Optional[str] = None
    usage: Optional[dict] = None


def _resolve_pricing_key(engine: str, model: str, config: dict) -> str:
    """Resolve the correct pricing key, handling 'auto' engine."""
    if engine != "auto":
        return _pricing_key(engine, model)
    # engine is "auto" — infer actual provider from model hint
    provider = "kimi" if model.lower() == "kimi" else "deepseek"
    return _pricing_key(provider, model)


@router.get("")
async def list_solve_sessions(
    request: Request,
    page_size: int = Query(50, alias="page_size"),
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    await _migrate_old_sessions(username, subject)
    sessions = await read_json(get_solve_sessions_path(username, subject)) or []
    sessions_desc = sorted(sessions, key=lambda s: s.get("created_at", ""), reverse=True)
    limited = sessions_desc[:page_size]
    return {
        "items": [
            {
                "id": s["id"],
                "title": s.get("title", ""),
                "problem_id": s.get("problem_id", ""),
                "has_figure": s.get("has_figure", False),
                "image_file_id": s.get("image_file_id", ""),
                "model": s.get("model", ""),
                "engine": s.get("engine", ""),
                "created_at": s.get("created_at", ""),
                "input_cache_hit": s.get("input_cache_hit", 0),
                "input_cache_miss": s.get("input_cache_miss", 0),
                "output": s.get("output", 0),
                "cost_yuan": s.get("cost_yuan"),
                "message_count": 1 if s.get("answer") else 0,
            }
            for s in limited
        ]
    }


@router.post("")
async def create_solve_session(
    req: SolveSessionCreate,
    request: Request,
    username: str = Depends(get_current_user),
):
    config = await read_json(get_user_config_path(username)) or {}
    pricing = get_pricing(config)
    hit, miss, out = 0, 0, 0
    cost = None
    if req.usage:
        hit, miss, out = extract_usage(req.usage)
    else:
        # No real usage data — estimate from text length
        est_answer = max(1, int(len(req.answer or "") * 0.35) + 1)
        est_question = max(1, int(len(req.question or "") * 0.35) + 1)
        hit, miss, out = 0, est_question, est_answer
    pk = _resolve_pricing_key(req.engine, req.model, config)
    cost = compute_cost(pk, hit, miss, out, pricing)
    title = ""
    if req.problem_content:
        title = req.problem_content[:30] + ("..." if len(req.problem_content) > 30 else "")
    elif req.question:
        title = req.question[:30] + ("..." if len(req.question) > 30 else "")
    else:
        title = f"{req.engine} 解题"
    session = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "problem_id": req.problem_id or "",
        "problem_content": req.problem_content or "",
        "has_figure": req.has_figure if req.has_figure is not None else False,
        "image_file_id": req.image_file_id or "",
        "model": req.model,
        "engine": req.engine,
        "question": req.question,
        "answer": req.answer,
        "reasoning": req.reasoning or "",
        "input_cache_hit": hit,
        "input_cache_miss": miss,
        "output": out,
        "cost_yuan": cost,
        "created_at": datetime.now().isoformat(),
    }
    subject = await get_user_subject(username)
    path = get_solve_sessions_path(username, subject)
    sessions = await read_json(path) or []
    sessions.append(session)
    await write_json(path, sessions)
    return session


@router.get("/{session_id}")
async def get_solve_session(
    session_id: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    await _migrate_old_sessions(username, subject)
    sessions = await read_json(get_solve_sessions_path(username, subject)) or []
    for s in sessions:
        if s["id"] == session_id:
            return s
    raise HTTPException(status_code=404, detail="解题会话不存在")


@router.delete("/{session_id}")
async def delete_solve_session(
    session_id: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    path = get_solve_sessions_path(username, subject)
    sessions = await read_json(path) or []
    new_sessions = [s for s in sessions if s["id"] != session_id]
    if len(new_sessions) == len(sessions):
        raise HTTPException(status_code=404, detail="解题会话不存在")
    await write_json(path, new_sessions)
    return {"message": "已删除"}
