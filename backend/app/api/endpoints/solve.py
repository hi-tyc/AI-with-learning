from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from openai import APITimeoutError, APIConnectionError, APIStatusError, RateLimitError
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, AsyncGenerator
import json
from datetime import datetime
import os

import uuid

from app.api.endpoints.auth import get_current_user
from app.core.user_data import (
    get_user_config_path,
    get_user_subject,
    get_problems_path,
    get_solve_sessions_path,
    get_user_path,
    get_materials_path,
    get_answers_path,
    get_words_path,
)
from app.api.endpoints.settings_api import _get_deepseek_model_name
from app.core.paths import UPLOAD_DIR
from app.utils.file_lock import read_json, write_json
from app.core.pricing import extract_usage, compute_cost, get_pricing, _pricing_key
from app.core.daily_cost import check_daily_limit, add_daily_cost
from app.utils.ai_client import create_client, DEEPSEEK_BASE_URL, KIMI_BASE_URL, extract_reasoning, extract_usage_sdk

router = APIRouter()


class SolveRequest(BaseModel):
    strategy: Literal["auto", "geometry", "no_geometry"] = "auto"
    message: Optional[str] = None
    engine: Literal["auto", "kimi", "deepseek"] = "auto"
    reasoning: bool = True
    reasoning_depth: int = Field(default=5, ge=1, le=10)
    materials_path: Optional[str] = None


class FreeSolveRequest(BaseModel):
    strategy: Literal["auto", "geometry", "no_geometry"] = "auto"
    message: str
    engine: Literal["auto", "kimi", "deepseek"] = "auto"
    reasoning: bool = True
    reasoning_depth: int = Field(default=5, ge=1, le=10)
    materials_path: Optional[str] = None


async def _build_system_prompt(username: str, subject: str = "") -> str:
    user = await read_json(get_user_path(username)) or {}
    grade = user.get('grade', '八年级')
    pref = user.get('preferences', '')
    is_english = subject == "英语"

    parts = [f"你是初中{grade}学习辅导老师。分步讲解，清晰易懂。"]
    if pref:
        parts.append(f"用户偏好：{pref}")
    if is_english:
        parts.append("若用户提供了标准答案，以此答案为基准讲解，不评价用户水平。")

    return "\n".join(parts)


async def _build_user_content(
    problem: Optional[dict],
    message: Optional[str],
    username: str,
    model: str,
    materials_path: Optional[str] = None,
    subject: str = "",
) -> list:
    content = []

    if problem:
        problem_text = problem.get("content", "")
        if problem_text:
            content.append({"type": "text", "text": problem_text})

        # 对所有模型（DeepSeek）也发送图片，DeepSeek Vision 支持图片输入
        if problem.get("image_file_id"):
            img_path = os.path.join(UPLOAD_DIR, f"{problem['image_file_id']}_compressed.jpg")
            if os.path.exists(img_path):
                import base64
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })

        if problem.get("pdf_file_id"):
            text_path = os.path.join(UPLOAD_DIR, f"{problem['pdf_file_id']}_text.txt")
            if os.path.exists(text_path):
                with open(text_path, "r", encoding="utf-8") as f:
                    pdf_text = f.read().strip()
                if pdf_text:
                    content.append({"type": "text", "text": f"[PDF内容]\n{pdf_text}"})

    # 加载指定资料路径的内容
    if materials_path:
        try:
            material_ids = [x.strip() for x in materials_path.split(",") if x.strip()]
            subject_for_materials = subject if subject else await get_user_subject(username)
            materials = await read_json(get_materials_path(username, subject_for_materials)) or []
            words_data = await read_json(get_words_path(username, subject_for_materials)) or []
            for mid in material_ids:
                found = False
                for m in materials:
                    if m["id"] == mid or m.get("filename", "") == mid:
                        text_path = os.path.join(UPLOAD_DIR, f"{m['id']}_text.txt")
                        if os.path.exists(text_path):
                            with open(text_path, "r", encoding="utf-8") as f:
                                mat_text = f.read().strip()
                            if mat_text:
                                content.append({"type": "text", "text": f"[参考资料：{m.get('filename','')}]\n{mat_text}"})
                        found = True
                        break
                if not found:
                    for wl in words_data:
                        if wl["id"] == mid:
                            words = wl.get("words", [])
                            word_lines = [f"{w.get('english', '')} — {w.get('chinese', '')}" for w in words if w.get('english')]
                            if word_lines:
                                content.append({"type": "text", "text": f"[词单：{wl.get('filename','')}]\n" + "\n".join(word_lines)})
                            break
        except Exception:
            pass

    if message and message.strip():
        if content:
            content.append({"type": "text", "text": f"\n\n追问：{message}"})
        else:
            content.append({"type": "text", "text": message})

    return content


def _make_sse(event: str, data_str: str) -> str:
    import json as _json
    return "data: " + _json.dumps({"type": event, "text": data_str}, ensure_ascii=False) + "\n\n"


def _error_sse(msg: str) -> str:
    return _make_sse("error", msg)


def _done_sse() -> str:
    return "data: [DONE]\n\n"


async def _call_deepseek(
    api_key: str,
    model: str,
    messages: list,
    timeout: int,
    provider: str = "deepseek",
    show_reasoning: bool = True,
) -> AsyncGenerator[str, None]:
    client = create_client(api_key, DEEPSEEK_BASE_URL if provider == "deepseek" else KIMI_BASE_URL, timeout)
    model_name = _get_deepseek_model_name(model) if provider == "deepseek" else model

    create_kwargs = dict(
        model=model_name,
        messages=messages,
        stream=True,
    )
    if provider == "kimi":
        if show_reasoning:
            create_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    else:
        create_kwargs["temperature"] = 0.7

    try:
        stream = await client.chat.completions.create(**create_kwargs)
    except APITimeoutError:
        raise HTTPException(status_code=504, detail=f"{'Kimi' if provider == 'kimi' else 'DeepSeek'} 请求超时")
    except RateLimitError:
        raise HTTPException(status_code=503, detail=f"{'Kimi' if provider == 'kimi' else 'DeepSeek'} 服务暂不可用，请稍后重试")
    except (APIConnectionError, APIStatusError) as e:
        detail = getattr(e, "message", str(e))[:100] if hasattr(e, "message") else str(e)[:100]
        status = getattr(e, "status_code", 502)
        raise HTTPException(status_code=status, detail=f"{'Kimi' if provider == 'kimi' else 'DeepSeek'} 错误: {detail}")

    async for chunk in stream:
        if chunk.usage:
            hit, miss, out = extract_usage_sdk(chunk.usage)
            yield _make_sse("usage", json.dumps({"hit": hit, "miss": miss, "out": out}))
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta is None:
            continue
        if show_reasoning:
            reasoning = extract_reasoning(delta)
            if reasoning:
                yield _make_sse("reasoning", reasoning)
        if delta.content:
            yield _make_sse("content", delta.content)
    yield "[DONE]"


async def _select_model(problem: Optional[dict], strategy: str, config: dict, subject: str = "数学") -> str:
    if strategy == "kimi":
        return "kimi"
    if strategy == "deepseek":
        return "deepseek"
    if problem and problem.get("has_figure"):
        return "kimi"
    return "deepseek"


async def _do_solve(
    problem_id: Optional[str],
    strategy: str,
    message: Optional[str],
    username: str,
    engine: str = "auto",
    reasoning: bool = True,
    reasoning_depth: int = 5,
    materials_path: Optional[str] = None,
):
    config = await read_json(get_user_config_path(username)) or {}
    subject = await get_user_subject(username)

    daily_limit = config.get("daily_cost_limit", 10.0)
    if not await check_daily_limit(username, daily_limit):
        raise HTTPException(status_code=429, detail="今日 API 花费已达上限，请明天再试")

    problem = None
    if problem_id:
        problems = await read_json(get_problems_path(username, subject)) or []
        for p in problems:
            if p["id"] == problem_id:
                problem = p
                break
        if not problem:
            raise HTTPException(status_code=404, detail="题目不存在")

    use_engine = engine if engine != "auto" else await _select_model(problem, strategy, config, subject)
    provider = "kimi" if use_engine == "kimi" else "deepseek"

    system_prompt = await _build_system_prompt(username, subject)
    depth_desc = {1:"极其简略", 3:"简略", 5:"适中", 7:"详细", 10:"非常详细"}
    depth_text = next((v for k,v in sorted(depth_desc.items(), reverse=True) if reasoning_depth >= k), "适中")
    system_prompt += f"\n\n【推理深度：{depth_text}。请根据此深度调整解答的详细程度。】"
    user_content = await _build_user_content(problem, message, username, provider, materials_path=materials_path, subject=subject)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    async def event_generator():
        full_text = ""
        reasoning_text = ""
        usage_from_api = None
        try:
            if provider == "kimi":
                api_key = config.get("kimi_api_key", "")
                if not api_key:
                    yield _error_sse("Kimi API Key 未配置")
                    yield _done_sse()
                    return
                model_name = config.get("kimi_model", "kimi-k2.6")
            else:
                api_key = config.get("deepseek_api_key", "")
                if not api_key:
                    yield _error_sse("DeepSeek API Key 未配置")
                    yield _done_sse()
                    return
                model_name = config.get("deepseek_model", "flash")
            timeout_key = "kimi_timeout" if provider == "kimi" else "deepseek_timeout"
            timeout = config.get(timeout_key, 120)
            gen = _call_deepseek(api_key, model_name, messages, timeout, provider, reasoning)

            # Pre-calc input tokens for real-time progress
            est_sys = max(1, int(len(system_prompt) * 0.35) + 1)
            est_prob = max(1, int(len(problem.get("content", "") if problem else "") * 0.35) + 1) if problem else 0
            est_msg = max(1, int(len(message or "") * 0.35) + 1)
            est_in = est_sys + est_prob + est_msg
            pk_progress = _pricing_key(provider, model_name)
            config_pricing = get_pricing(config or {})
            progress_count = 0

            async for chunk in gen:
                if chunk == "[DONE]":
                    yield _done_sse()
                    break
                if chunk.startswith("data: "):
                    yield chunk
                    try:
                        p = json.loads(chunk[6:])
                        tp = p.get("type")
                        if tp == "content":
                            full_text += p.get("text", "")
                            progress_count += 1
                            if progress_count % 5 == 0:
                                est_out = max(1, int(len(full_text) * 0.35) + 1)
                                c = compute_cost(pk_progress, 0, est_in, est_out, config_pricing) or 0
                                yield "data: " + json.dumps({"type": "progress", "output_tokens": est_out, "input_tokens": est_in, "cost": round(c, 8)}, ensure_ascii=False) + "\n\n"
                        elif tp == "reasoning":
                            reasoning_text += p.get("text", "")
                        elif tp == "usage":
                            usage_data = p.get("text", "")
                            if isinstance(usage_data, str):
                                usage_data = json.loads(usage_data)
                            usage_from_api = (usage_data.get("hit", 0), usage_data.get("miss", 0), usage_data.get("out", 0))
                    except Exception:
                        pass
                    continue
                full_text += chunk
                yield "data: " + json.dumps({"type": "content", "text": chunk}, ensure_ascii=False) + "\n\n"

            # If Kimi thinking mode didn't return visible content, fallback to reasoning_text
            if not full_text and reasoning_text:
                full_text = reasoning_text
                reasoning_text = ""

            if problem:
                problems = await read_json(get_problems_path(username, subject)) or []
                for p in problems:
                    if p["id"] == problem.get("id"):
                        p["solution"] = full_text
                        p["solved_at"] = datetime.now().isoformat()
                        p["solved_by"] = model_name
                        break
                await write_json(get_problems_path(username, subject), problems)

            config_pricing = get_pricing(config or {})
            pk = _pricing_key(provider, model_name)

            if usage_from_api:
                hit, miss, out = usage_from_api
                cost = compute_cost(pk, hit, miss, out, config_pricing)
            else:
                # Estimate: Chinese text ~0.5 token/char, English/mixed ~0.35
                est_sys = max(1, int(len(system_prompt) * 0.35) + 1)
                est_prob = max(1, int(len(problem.get("content", "") if problem else "") * 0.35) + 1) if problem else 0
                est_msg = max(1, int(len(message or "") * 0.35) + 1)
                est_in = est_sys + est_prob + est_msg
                est_out = max(1, int(len(full_text) * 0.35) + 1)
                hit, miss, out = 0, est_in, est_out
                cost = compute_cost(pk, hit, miss, out, config_pricing)

            # For daily limit tracking, treat None (non-metered) as 0 cost.
            await add_daily_cost(username, cost or 0.0)

            try:
                solve_sessions = await read_json(get_solve_sessions_path(username, subject)) or []
                problem_content = problem.get("content", "") if problem else ""
                question_text = message or ""
                title = problem_content[:30] + ("..." if len(problem_content) > 30 else "") if problem_content else (question_text[:30] + "..." if len(question_text) > 30 else question_text) or "自由解题"
                has_figure = problem.get("has_figure", False) if problem else False
                solve_sessions.append({
                    "id": str(uuid.uuid4())[:8],
                    "title": title,
                    "problem_id": problem.get("id", "") if problem else "",
                    "problem_content": problem_content,
                    "has_figure": has_figure,
                    "image_file_id": problem.get("image_file_id", "") if problem else "",
                    "model": model_name,
                    "engine": provider,
                    "question": question_text,
                    "answer": full_text,
                    "reasoning": reasoning_text,
                    "input_cache_hit": hit,
                    "input_cache_miss": miss,
                    "output": out,
                    "cost_yuan": cost,
                    "created_at": datetime.now().isoformat(),
                })
                await write_json(get_solve_sessions_path(username, subject), solve_sessions)
            except Exception as e:
                print(f"保存解题会话失败: {e}")

            # 将最终用量和费用回传给前端
            yield _make_sse("usage", json.dumps({
                "hit": hit,
                "miss": miss,
                "out": out,
                "cost": round(cost, 8) if cost is not None else None,
            }, ensure_ascii=False))

        except HTTPException as e:
            yield _error_sse(e.detail)
            yield _done_sse()
        except Exception as e:
            yield _error_sse(str(e))
            yield _done_sse()

    return event_generator()


async def _migrate_old_sessions(username: str, subject: str) -> None:
    path = get_solve_sessions_path(username, subject)
    sessions = await read_json(path) or []
    changed = False
    for s in sessions:
        if s.get("cost_yuan") is None and s.get("answer"):
            est = max(1, len(s.get("answer", "")) // 2)
            s["input_cache_hit"] = s.get("input_cache_hit", 0) or 0
            s["input_cache_miss"] = s.get("input_cache_miss", 0) or est * 2 or est
            s["output"] = s.get("output", 0) or est
            config = {}
            try:
                config = await read_json(get_user_config_path(username)) or {}
            except:
                pass
            pricing = get_pricing(config)
            engine = s.get("engine", "deepseek")
            model = s.get("model", engine)
            pk = _pricing_key(engine, model)
            # Preserve non-metered (subscription) sessions as None.
            if pk in ("kimi_code",):
                s["cost_yuan"] = None
            else:
                s["cost_yuan"] = compute_cost(pk, s["input_cache_hit"], s["input_cache_miss"], s["output"], pricing)
                if s["cost_yuan"] is None:
                    s["cost_yuan"] = 0.0
            changed = True
        if "has_figure" not in s:
            s["has_figure"] = False
            s["image_file_id"] = ""
            changed = True
    if changed:
        await write_json(path, sessions)


@router.post("/{problem_id}/solve")
async def solve_problem(
    problem_id: str,
    req: SolveRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    gen = await _do_solve(problem_id, req.strategy, req.message, username, req.engine, req.reasoning, req.reasoning_depth, req.materials_path)
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/solve")
async def solve_free(
    req: FreeSolveRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    gen = await _do_solve(None, req.strategy, req.message, username, req.engine, req.reasoning, req.reasoning_depth, req.materials_path)
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
