from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import StreamingResponse
from openai import APITimeoutError, APIConnectionError, APIStatusError, RateLimitError
from typing import Optional
import json
import io
import uuid
import base64
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
import os

from app.api.endpoints.auth import get_current_user
from app.api.endpoints.settings_api import _get_deepseek_model_name
from app.core.user_data import user_data_path, get_user_config_path
from app.utils.file_lock import read_json, write_json
from app.utils.ai_client import (
    create_client, DEEPSEEK_BASE_URL, KIMI_BASE_URL,
    extract_reasoning, extract_usage_sdk,
)
from app.core.pricing import compute_cost, get_pricing, _pricing_key
from app.core.daily_cost import check_daily_limit, add_daily_cost

router = APIRouter()

MAGIC_PDF = b"%PDF"
MAGIC_ZIP = b"PK\x03\x04"
MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_PNG = b"\x89\x50\x4e\x47"


def _session_path(username: str) -> str:
    return user_data_path(username, "对话", "chat_sessions")


def _session_messages_path(username: str, session_id: str) -> str:
    from app.core.paths import USERS_DIR
    return os.path.join(USERS_DIR, f"{username}_对话_chat_{session_id}.json")


async def _create_session(username: str) -> dict:
    sessions = await read_json(_session_path(username)) or []
    session = {
        "id": str(uuid.uuid4())[:8],
        "title": "新对话",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "message_count": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
    }
    sessions.insert(0, session)
    await write_json(_session_path(username), sessions)
    return session


def _is_pdf(data: bytes) -> bool:
    return data.startswith(MAGIC_PDF)


def _is_docx(data: bytes) -> bool:
    if not data.startswith(MAGIC_ZIP):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            return "word/document.xml" in z.namelist()
    except Exception:
        return False


def _is_image(data: bytes) -> bool:
    return data.startswith(MAGIC_JPEG) or data.startswith(MAGIC_PNG)


def _is_scanned_pdf(data: bytes) -> bool:
    try:
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        text_len = sum(len(page.get_text().strip()) for page in doc)
        doc.close()
        return text_len < 200
    except Exception:
        return True


async def _compress_image(data: bytes, max_long: int = 600, quality: int = 40) -> bytes:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_long:
            ratio = max_long / max(w, h)
            w, h = int(w * ratio), int(h * ratio)
            img = img.resize((w, h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()
    except Exception:
        return data


async def _extract_docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            if "word/document.xml" not in z.namelist():
                return ""
            xml_content = z.read("word/document.xml")
        root = ET.fromstring(xml_content)
        texts = []
        for elem in root.iter():
            if elem.tag.endswith("}t") and elem.text:
                texts.append(elem.text)
        return " ".join(texts).strip()
    except Exception:
        return ""


async def _extract_pdf_text(data: bytes) -> str:
    try:
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text.strip()
    except Exception:
        return ""


@router.post("/send")
async def chat_send(
    message: str = Form(...),
    file: Optional[UploadFile] = File(None),
    engine: str = Form("auto"),
    reasoning: str = Form("true"),
    session_id: str = Form(""),
    username: str = Depends(get_current_user),
):
    config = await read_json(get_user_config_path(username)) or {}

    daily_limit = config.get("daily_cost_limit", 10.0)
    if not await check_daily_limit(username, daily_limit):
        raise HTTPException(status_code=429, detail="今日 API 花费已达上限，请明天再试")

    show_reasoning = reasoning.lower() == "true"
    file_text = ""
    is_vision = False

    if file:
        data = await file.read()
        if _is_image(data):
            data = await _compress_image(data)
            b64 = base64.b64encode(data).decode("utf-8")
            if engine == "auto":
                engine = "kimi"
            is_vision = True
        elif _is_pdf(data):
            if _is_scanned_pdf(data):
                pass
            else:
                file_text = await _extract_pdf_text(data)
        elif _is_docx(data):
            file_text = await _extract_docx_text(data)

    if engine == "auto":
        engine = "deepseek"

    if engine == "kimi":
        api_key = config.get("kimi_api_key", "")
        if not api_key:
            raise HTTPException(status_code=400, detail="Kimi API Key 未配置")
        model_name = config.get("kimi_model", "kimi-k2.6")
        base_url = KIMI_BASE_URL
        provider = "kimi"
    else:
        api_key = config.get("deepseek_api_key", "")
        if not api_key:
            raise HTTPException(status_code=400, detail="DeepSeek API Key 未配置")
        model_choice = config.get("deepseek_model", "flash")
        model_name = _get_deepseek_model_name(model_choice)
        base_url = DEEPSEEK_BASE_URL
        provider = "deepseek"
        if is_vision:
            raise HTTPException(status_code=400, detail="DeepSeek 不支持图片输入，请切换到 Kimi")

    timeout_key = "kimi_timeout" if provider == "kimi" else "deepseek_timeout"
    timeout = config.get(timeout_key, 120) or 120
    client = create_client(api_key, base_url, timeout)

    if session_id:
        sessions = await read_json(_session_path(username)) or []
        session = next((s for s in sessions if s["id"] == session_id), None)
        if not session:
            session = await _create_session(username)
    else:
        session = await _create_session(username)
    session_id = session["id"]

    if is_vision:
        content = [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": message},
        ]
    elif file_text:
        content = f"{message}\n\n--- 文件内容 ---\n\n{file_text[:15000]}"
    else:
        content = message

    system_prompt = "你是一个智能学习助手。请回答用户的问题，分步讲解，清晰易懂。如果需要使用数学公式，请使用LaTeX格式（行内公式用$...$，行间公式用$$...$$）。"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]

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

    async def event_generator():
        full_content = ""
        reasoning_text = ""
        usage_from_api = None
        token_counter = 0
        token_interval = 50
        est_sys = max(1, int(len(system_prompt) * 0.35) + 1)
        est_input = max(1, int((len(message) + len(file_text)) * 0.35) + 1)
        est_in = est_sys + est_input
        try:
            stream = await client.chat.completions.create(**create_kwargs)

            async for chunk in stream:
                if chunk.usage:
                    hit, miss, out = extract_usage_sdk(chunk.usage)
                    usage_from_api = (hit, miss, out)
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue
                if show_reasoning:
                    reasoning = extract_reasoning(delta)
                    if reasoning:
                        reasoning_text += reasoning
                        yield "data: " + json.dumps({"type": "reasoning", "text": reasoning}, ensure_ascii=False) + "\n\n"
                if delta.content:
                    full_content += delta.content
                    token_counter += 1
                    yield "data: " + json.dumps({"type": "content", "text": delta.content}, ensure_ascii=False) + "\n\n"
                    if token_counter % token_interval == 0:
                        est = max(1, int(len(full_content) * 0.35) + 1)
                        pk = _pricing_key(provider, model_name)
                        p = get_pricing(config).get(pk, {}) or {}
                        out_rate = p.get("output", 2.0)
                        miss_rate = p.get("input_cache_miss", 3.0)
                        hit_rate = p.get("input_cache_hit", miss_rate)
                        # Progress estimate: assume 30% cache hit for live cost estimate.
                        est_hit = int(est_in * 0.3)
                        est_miss = est_in - est_hit
                        cost_est = (est_hit * hit_rate + est_miss * miss_rate + est * out_rate) / 1_000_000
                        yield "data: " + json.dumps({
                            "type": "progress",
                            "input_tokens": est_in,
                            "hit_tokens": est_hit,
                            "miss_tokens": est_miss,
                            "output_tokens": est,
                            "cost": round(cost_est, 8),
                        }, ensure_ascii=False) + "\n\n"

            pk = _pricing_key(provider, model_name)
            if usage_from_api:
                hit, miss, out = usage_from_api
                cost = compute_cost(pk, hit, miss, out, get_pricing(config))
            else:
                est_tokens = max(1, int(len(full_content) * 0.35) + 1)
                est_sys = max(1, int(len(system_prompt) * 0.35) + 1)
                est_input = max(1, int((len(message) + len(file_text)) * 0.35) + 1)
                hit, miss, out = 0, est_sys + est_input, est_tokens
                cost = compute_cost(pk, hit, miss, out, get_pricing(config))

            # For daily limit tracking, treat None (non-metered) as 0 cost.
            await add_daily_cost(username, cost or 0.0)

            msgs = await read_json(_session_messages_path(username, session_id)) or []
            user_content = message
            if file_text:
                user_content += f"\n[文件内容已提取，共 {len(file_text)} 字]"
            msgs.append({"role": "user", "content": user_content, "timestamp": datetime.now().isoformat()})
            msgs.append({
                "role": "assistant", "content": full_content,
                "reasoning": reasoning_text,
                "usage": {"hit": hit, "miss": miss, "out": out, "cost": cost},
                "timestamp": datetime.now().isoformat(),
            })
            await write_json(_session_messages_path(username, session_id), msgs)

            sessions = await read_json(_session_path(username)) or []
            for s in sessions:
                if s["id"] == session_id:
                    title = message[:30] + "..." if len(message) > 30 else message
                    s["title"] = title
                    s["engine"] = engine
                    s["message_count"] = len(msgs) // 2
                    s["total_tokens"] = (s.get("total_tokens", 0) or 0) + hit + miss + out
                    s["total_cost"] = round((s.get("total_cost", 0) or 0) + (cost or 0.0), 6)
                    s["last_usage"] = {"hit": hit, "miss": miss, "out": out, "cost": cost}
                    break
            await write_json(_session_path(username), sessions)

            yield "data: " + json.dumps({
                "type": "done",
                "usage": {"hit": hit, "miss": miss, "out": out, "cost": cost},
            }, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"

        except APITimeoutError:
            yield "data: " + json.dumps({"type": "error", "text": "AI 请求超时，请稍后重试"}, ensure_ascii=False) + "\n\n"
        except RateLimitError:
            yield "data: " + json.dumps({"type": "error", "text": "请求过于频繁，请稍后重试"}, ensure_ascii=False) + "\n\n"
        except (APIConnectionError, APIStatusError) as e:
            yield "data: " + json.dumps({"type": "error", "text": f"AI 服务错误: {type(e).__name__}"}, ensure_ascii=False) + "\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"type": "error", "text": str(e)}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/sessions")
async def create_session(
    username: str = Depends(get_current_user),
):
    session = await _create_session(username)
    return session


@router.get("/sessions")
async def list_sessions(
    username: str = Depends(get_current_user),
):
    sessions = await read_json(_session_path(username)) or []
    return {"items": sessions}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    username: str = Depends(get_current_user),
):
    msgs = await read_json(_session_messages_path(username, session_id)) or []
    return {"messages": msgs}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    username: str = Depends(get_current_user),
):
    sessions = await read_json(_session_path(username)) or []
    sessions = [s for s in sessions if s["id"] != session_id]
    await write_json(_session_path(username), sessions)
    path = _session_messages_path(username, session_id)
    if os.path.exists(path):
        os.unlink(path)
    return {"message": "已删除"}


@router.get("/sessions/{session_id}/usage")
async def get_session_usage(
    session_id: str,
    username: str = Depends(get_current_user),
):
    sessions = await read_json(_session_path(username)) or []
    for s in sessions:
        if s["id"] == session_id:
            return {
                "total_tokens": s.get("total_tokens", 0),
                "total_cost": s.get("total_cost", 0),
                "last_usage": s.get("last_usage", {}),
            }
    return {"total_tokens": 0, "total_cost": 0, "last_usage": {}}
