from fastapi import APIRouter, Depends, Request
from datetime import datetime
import os

from app.api.endpoints.auth import get_current_user
from app.core.user_data import (
    get_user_subject, get_usage_path, get_solve_sessions_path,
    get_user_config_path,
)
from app.core.paths import USERS_DIR
from app.utils.file_lock import read_json, write_json
from app.core.pricing import get_pricing

router = APIRouter()


def _is_today(iso_str: str) -> bool:
    if not iso_str:
        return False
    try:
        return datetime.fromisoformat(iso_str).strftime("%Y-%m-%d") == datetime.now().strftime("%Y-%m-%d")
    except Exception:
        return False


@router.get("")
async def list_usage(
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    sessions = await read_json(get_usage_path(username, subject)) or []
    config = await read_json(get_user_config_path(username)) or {}

    # Include solve sessions cost
    solve_sessions = await read_json(get_solve_sessions_path(username, subject)) or []

    # Include chat sessions cost
    chat_sessions_path = os.path.join(USERS_DIR, f"{username}_对话_chat_sessions.json")
    chat_sessions = await read_json(chat_sessions_path) or []

    deepseek_cost = 0.0
    kimi_cost = 0.0

    def _add_cost(cost: float, provider: str):
        nonlocal deepseek_cost, kimi_cost
        p = (provider or "").lower()
        if p == "deepseek":
            deepseek_cost += cost
        elif p == "kimi":
            kimi_cost += cost

    for s in sessions:
        _add_cost(s.get("cost_yuan") or 0, s.get("provider"))
    for s in solve_sessions:
        _add_cost(s.get("cost_yuan") or 0, s.get("engine"))
    for s in chat_sessions:
        _add_cost(s.get("total_cost") or 0, s.get("engine") or "deepseek")

    total = round(
        sum((s.get("cost_yuan") or 0) for s in sessions)
        + sum((s.get("cost_yuan") or 0) for s in solve_sessions)
        + sum((s.get("total_cost") or 0) for s in chat_sessions),
        6,
    )
    sessions_desc = list(reversed(sessions))
    return {
        "sessions": sessions_desc,
        "total_cost_yuan": total,
        "deepseek_cost_yuan": round(deepseek_cost, 6),
        "kimi_cost_yuan": round(kimi_cost, 6),
        "pricing": get_pricing(config),
    }


@router.get("/today")
async def today_usage(
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    config = await read_json(get_user_config_path(username)) or {}

    def _empty_stats():
        return {"tokens_in": 0, "tokens_out": 0, "cost": 0.0, "count": 0}

    def _add(stats: dict, tokens_in: int, tokens_out: int, cost: float):
        stats["tokens_in"] += tokens_in
        stats["tokens_out"] += tokens_out
        stats["cost"] += cost
        stats["count"] += 1

    total = _empty_stats()
    deepseek = _empty_stats()
    kimi = _empty_stats()

    # Aggregate from usage.json (recognition/upload)
    sessions_usage = await read_json(get_usage_path(username, subject)) or []
    for s in sessions_usage:
        if not _is_today(s.get("created_at", "")):
            continue
        tokens_in = (s.get("input_cache_hit", 0) or 0) + (s.get("input_cache_miss", 0) or 0)
        tokens_out = s.get("output", 0) or 0
        cost = s.get("cost_yuan", 0) or 0
        provider = (s.get("provider") or "").lower()
        _add(total, tokens_in, tokens_out, cost)
        if provider == "deepseek":
            _add(deepseek, tokens_in, tokens_out, cost)
        elif provider == "kimi":
            _add(kimi, tokens_in, tokens_out, cost)

    # Aggregate from solve_sessions.json (solve)
    sessions_solve = await read_json(get_solve_sessions_path(username, subject)) or []
    for s in sessions_solve:
        if not _is_today(s.get("created_at", "")):
            continue
        tokens_in = (s.get("input_cache_hit", 0) or 0) + (s.get("input_cache_miss", 0) or 0)
        tokens_out = s.get("output", 0) or 0
        cost = s.get("cost_yuan", 0) or 0
        provider = (s.get("engine") or "").lower()
        _add(total, tokens_in, tokens_out, cost)
        if provider == "deepseek":
            _add(deepseek, tokens_in, tokens_out, cost)
        elif provider == "kimi":
            _add(kimi, tokens_in, tokens_out, cost)

    # Aggregate from chat_sessions.json (chat)
    chat_sessions_path = os.path.join(USERS_DIR, f"{username}_对话_chat_sessions.json")
    chat_sessions = await read_json(chat_sessions_path) or []
    for s in chat_sessions:
        if not _is_today(s.get("created_at", "")):
            continue
        last = s.get("last_usage") or {}
        tokens_in = (last.get("hit") or 0) + (last.get("miss") or 0)
        tokens_out = last.get("out") or 0
        cost = last.get("cost") or 0
        provider = (s.get("engine") or "deepseek").lower()
        _add(total, tokens_in, tokens_out, cost)
        if provider == "deepseek":
            _add(deepseek, tokens_in, tokens_out, cost)
        elif provider == "kimi":
            _add(kimi, tokens_in, tokens_out, cost)

    return {
        "total_tokens_in": total["tokens_in"],
        "total_tokens_out": total["tokens_out"],
        "total_cost": round(total["cost"], 6),
        "session_count": total["count"],
        "pricing": get_pricing(config),
        "deepseek": deepseek,
        "kimi": kimi,
    }


@router.delete("/{session_id}")
async def delete_usage(
    session_id: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    path = get_usage_path(username, subject)
    sessions = await read_json(path) or []
    sessions = [s for s in sessions if s.get("id") != session_id]
    await write_json(path, sessions)
    return {"ok": True}
