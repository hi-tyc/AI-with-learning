from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from openai import (
    APITimeoutError, APIConnectionError, APIStatusError, RateLimitError, BadRequestError, APIError,
)
import io
import asyncio
import base64
import uuid
import json
from datetime import datetime
import os

from app.api.endpoints.auth import get_current_user
from app.api.endpoints.settings_api import _get_deepseek_model_name
from app.core.user_data import get_user_config_path, get_user_subject, get_usage_path
from app.core.paths import UPLOAD_DIR
from app.utils.file_lock import read_json, write_json
from app.core.pricing import extract_usage, compute_cost, get_pricing, _pricing_key
from app.core.daily_cost import check_daily_limit, add_daily_cost
from app.utils.ai_client import create_client, DEEPSEEK_BASE_URL, KIMI_BASE_URL, extract_usage_sdk

router = APIRouter()

MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_PNG = b"\x89\x50\x4e\x47"
MAGIC_PDF = b"%PDF"


def _is_image(data: bytes) -> bool:
    return data.startswith(MAGIC_JPEG) or data.startswith(MAGIC_PNG)


def _is_pdf(data: bytes) -> bool:
    return data.startswith(MAGIC_PDF)


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
        pass
    return data


async def _pdf_to_pages(data: bytes, max_size_mb: int, quality: int, max_long: int):
    import fitz
    file_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(data)
    doc = fitz.open(pdf_path)
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(1.5, 1.5)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("jpeg")
        compressed = await _compress_image(img_data, max_long, quality)
        pages.append((page_num + 1, compressed))
    doc.close()
    return pages, file_id


async def _pdf_to_images(data: bytes, quality: int = 40, max_long: int = 600) -> tuple[list[bytes], str]:
    pages, file_id = await _pdf_to_pages(data, 99, quality, max_long)
    return [img for _, img in pages], file_id


def _build_kimi_prompt(mode: str, page_count: int) -> str:
    return f"""你是数学试卷识别助手。逐页识别题目和答案解析。

输出JSON格式：{{"p":[...], "aps":[...], "gps":[...]}}
字段说明：sj=subject学科("数学"), t=type题型(选择题/填空题/解答题), c=content完整题目内容(含图写"[几何题，图片见配图]"), a=answer自带答案, ap=answer_page答案页码(无则null), af=answer_has_figure答案含几何图, kp=knowledge_point知识点, hf=has_figure题目含几何图, pg=page页码(从1), bq=is_big_question是否大题含子题, sp=sub_problems子题列表
aps=answer_pages答案页码列表, gps=geometry_answer_pages几何答案页码列表
只输出JSON。"""


def _map_problem_fields(raw: dict) -> dict:
    """将AI返回的短字段名映射为标准字段名，兼容旧格式。"""
    if not isinstance(raw, dict):
        return raw
    m = {
        "sj": "subject", "t": "type", "c": "content", "a": "answer",
        "ap": "answer_page", "af": "answer_has_figure", "kp": "knowledge_point",
        "hf": "has_figure", "pg": "page", "bq": "is_big_question", "sp": "sub_problems",
    }
    out = dict(raw)
    for short, long in m.items():
        if short in out:
            out[long] = out.pop(short)
    if "sub_problems" in out and isinstance(out["sub_problems"], list):
        out["sub_problems"] = [_map_problem_fields(sp) for sp in out["sub_problems"] if isinstance(sp, dict)]
    return out


async def _recognize_with_kimi(
    api_key: str,
    model_name: str,
    images: list[bytes],
    mode: str,
    timeout: int = 180,
) -> tuple[list, dict, list, list]:
    client = create_client(api_key, KIMI_BASE_URL, timeout)
    content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(img).decode()}"}} for img in images]
    content.append({"type": "text", "text": _build_kimi_prompt(mode, len(images))})

    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是一个精准的数学题目识别助手。仅输出JSON。"},
                {"role": "user", "content": content},
            ],
            max_tokens=16384,
            extra_body={"thinking": {"type": "disabled"}},
        )
    except APITimeoutError:
        raise HTTPException(status_code=504, detail="Kimi识别超时")
    except BadRequestError as e:
        body = str(getattr(e, "body", str(e)))[:200]
        raise HTTPException(status_code=400, detail=f"Kimi请求参数错误: {body}")
    except RateLimitError:
        raise HTTPException(status_code=429, detail="请求过于频繁")
    except (APIConnectionError, APIStatusError) as e:
        raise HTTPException(status_code=502, detail=f"Kimi识别失败: {type(e).__name__}")
    except APIError as e:
        raise HTTPException(status_code=502, detail=f"Kimi服务错误: {type(e).__name__}")

    text_output = response.choices[0].message.content or ""
    hit, miss, out = extract_usage_sdk(response.usage)
    agg = {"hit": hit, "miss": miss, "out": out}

    for attempt in range(2):
        try:
            parsed = json.loads(text_output)
            problems = [_map_problem_fields(p) for p in parsed.get("p", []) or parsed.get("problems", [])]
            answer_pages = parsed.get("aps", []) or parsed.get("answer_pages", [])
            geometry_answer_pages = parsed.get("gps", []) or parsed.get("geometry_answer_pages", [])
            return problems, agg, answer_pages, geometry_answer_pages
        except json.JSONDecodeError:
            if attempt == 0:
                cleaned = text_output.strip()
                if cleaned.startswith("```"):
                    parts = cleaned.split("\n", 1)
                    cleaned = parts[1] if len(parts) > 1 else cleaned
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("\n", 1)[0] if "\n" in cleaned else cleaned.replace("```", "")
                text_output = cleaned.strip()
            else:
                raise HTTPException(status_code=502, detail="Kimi返回格式无法解析")


def _build_usage_payload(agg: dict, config: dict, provider: str = "kimi", model_name: str = "") -> dict:
    pk = _pricing_key(provider, model_name or provider)
    return {
        "input_cache_hit": agg["hit"],
        "input_cache_miss": agg["miss"],
        "output": agg["out"],
        "cost_yuan": compute_cost(pk, agg["hit"], agg["miss"], agg["out"], get_pricing(config)),
    }


async def _save_usage_session(username: str, record: dict) -> None:
    subject = await get_user_subject(username)
    path = get_usage_path(username, subject)
    sessions = await read_json(path) or []
    sessions.append(record)
    await write_json(path, sessions)


@router.post("")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user),
):
    config = await read_json(get_user_config_path(username)) or {}
    max_size_mb = config.get("image_max_size_mb", 10)
    quality = config.get("image_compress_quality", 40)
    max_long = config.get("image_max_long_edge", 800)

    data = await file.read()
    if len(data) > max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件超过 {max_size_mb}MB 限制")

    if _is_image(data):
        compressed = await _compress_image(data, max_long, quality)
        file_id = str(uuid.uuid4())
        with open(os.path.join(UPLOAD_DIR, f"{file_id}_compressed.jpg"), "wb") as f:
            f.write(compressed)
        b64 = base64.b64encode(compressed).decode("utf-8")
        return {"type": "image", "file_id": file_id, "base64": b64}

    if _is_pdf(data):
        pages, pdf_id = await _pdf_to_pages(data, max_size_mb, quality, max_long)
        page_list = []
        for num, img_bytes in pages:
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            page_list.append({"page": num, "base64": b64})
        return {"type": "pdf", "file_id": pdf_id, "pages": page_list}

    raise HTTPException(status_code=400, detail="仅支持 JPG/PNG 图片或 PDF 文件")


@router.post("/recognize")
async def recognize_file(
    request: Request,
    file: UploadFile = File(...),
    mode: str = Form("algebra"),
    username: str = Depends(get_current_user),
):
    config = await read_json(get_user_config_path(username)) or {}

    daily_limit = config.get("daily_cost_limit", 10.0)
    if not await check_daily_limit(username, daily_limit):
        raise HTTPException(status_code=429, detail="今日 API 花费已达上限，请明天再试")

    quality = config.get("image_compress_quality", 40)
    max_long = config.get("image_max_long_edge", 800)

    kimi_key = config.get("kimi_api_key", "")
    if not kimi_key:
        raise HTTPException(status_code=400, detail="Kimi API Key 未配置，数学识别需要 Kimi")
    kimi_model = config.get("kimi_model", "kimi-k2.6")
    timeout = max(int(config.get("kimi_timeout", 120) or 120), 180)

    data = await file.read()
    max_size_mb = config.get("image_max_size_mb", 10)
    if len(data) > max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件超过 {max_size_mb}MB 限制")

    if mode == "pdf":
        if not _is_pdf(data):
            raise HTTPException(status_code=400, detail="PDF 模式仅支持 PDF 文件")
    elif mode == "geometry" and _is_image(data):
        compressed = await _compress_image(data, max_long, quality)
        img_id = str(uuid.uuid4())
        with open(os.path.join(UPLOAD_DIR, f"{img_id}_compressed.jpg"), "wb") as f:
            f.write(compressed)
        problem = {
            "subject": "数学", "type": "几何题",
            "content": "[几何题，图片见配图]", "answer": "",
            "knowledge_point": "几何", "has_figure": True,
            "page": 1, "is_big_question": False,
            "sub_problems": [], "image_file_id": img_id,
            "upload_mode": "geometry",
        }
        return {
            "type": "recognized", "count": 1, "problems": [problem],
            "total_pages": 1, "recognized_pages": 0,
            "batches": 0, "failed_batches": 0, "warning": "",
            "usage": {"hit": 0, "miss": 0, "out": 0, "cost_yuan": None},
        }

    images = []
    if _is_pdf(data):
        images, pdf_id = await _pdf_to_images(data, quality, max_long)
    elif _is_image(data):
        compressed = await _compress_image(data, max_long, quality)
        images.append(compressed)
    else:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG 图片或 PDF 文件")

    if not images:
        raise HTTPException(status_code=400, detail="未能从文件中提取到任何内容")

    max_pages = int(config.get("recognize_max_pages", 20) or 20)
    page_cap_warning = ""
    total_uploaded = len(images)
    if total_uploaded > max_pages:
        page_cap_warning = f"该文件共 {total_uploaded} 页，本次仅识别前 {max_pages} 页"
        images = images[:max_pages]

    problems, agg, answer_pages, geometry_answer_pages = await _recognize_with_kimi(kimi_key, kimi_model, images, mode, timeout)

    def _save_page_image(page_num: int) -> str:
        idx = page_num - 1
        if 0 <= idx < len(images):
            img_id = str(uuid.uuid4())
            with open(os.path.join(UPLOAD_DIR, f"{img_id}_compressed.jpg"), "wb") as f:
                f.write(images[idx])
            return img_id
        return ""

    for i, p in enumerate(problems):
        page = p.get("page", 0)
        if p.get("has_figure") and page:
            p["image_file_id"] = _save_page_image(page)
        ans_page = p.get("answer_page")
        if ans_page and p.get("answer_has_figure"):
            p["answer_image_file_id"] = _save_page_image(ans_page)

    usage = _build_usage_payload(agg, config, "kimi", kimi_model)
    record = {
        "id": str(uuid.uuid4())[:8],
        "created_at": datetime.now().isoformat(),
        "filename": file.filename or "",
        "provider": "kimi",
        "model": kimi_model,
        "total_pages": total_uploaded,
        "recognized_pages": len(images),
        "batches": 1,
        "failed_batches": 0,
        "input_cache_hit": agg["hit"],
        "input_cache_miss": agg["miss"],
        "output": agg["out"],
        "cost_yuan": usage["cost_yuan"],
    }
    await _save_usage_session(username, record)

    for p in problems:
        p["upload_mode"] = mode

    return {
        "type": "recognized",
        "count": len(problems),
        "problems": problems,
        "total_pages": total_uploaded,
        "recognized_pages": len(images),
        "batches": 1,
        "failed_batches": 0,
        "warning": page_cap_warning,
        "usage": usage,
        "session_id": record["id"],
    }


@router.post("/recognize_stream")
async def recognize_file_stream(
    request: Request,
    file: UploadFile = File(...),
    mode: str = Form("algebra"),
    username: str = Depends(get_current_user),
):
    config = await read_json(get_user_config_path(username)) or {}

    daily_limit = config.get("daily_cost_limit", 10.0)
    if not await check_daily_limit(username, daily_limit):
        raise HTTPException(status_code=429, detail="今日 API 花费已达上限，请明天再试")

    quality = config.get("image_compress_quality", 40)
    max_long = config.get("image_max_long_edge", 800)

    kimi_key = config.get("kimi_api_key", "")
    if not kimi_key:
        raise HTTPException(status_code=400, detail="Kimi API Key 未配置，数学识别需要 Kimi")
    kimi_model = config.get("kimi_model", "kimi-k2.6")
    timeout = max(int(config.get("kimi_timeout", 120) or 120), 180)

    data = await file.read()
    max_size_mb = config.get("image_max_size_mb", 10)
    if len(data) > max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件超过 {max_size_mb}MB 限制")

    if mode == "pdf":
        if not _is_pdf(data):
            raise HTTPException(status_code=400, detail="PDF 模式仅支持 PDF 文件")
        usage = {"hit": 0, "miss": 0, "out": 0, "cost_yuan": None}
        record = {
            "id": str(uuid.uuid4())[:8],
            "created_at": datetime.now().isoformat(),
            "filename": file.filename or "", "provider": "kimi",
            "model": "pdf-mode", "total_pages": 0,
            "recognized_pages": 0, "batches": 0, "failed_batches": 0,
            "input_cache_hit": 0, "input_cache_miss": 0, "output": 0, "cost_yuan": None,
        }
        await _save_usage_session(username, record)
    elif mode == "geometry" and _is_image(data):
        compressed = await _compress_image(data, max_long, quality)
        img_id = str(uuid.uuid4())
        with open(os.path.join(UPLOAD_DIR, f"{img_id}_compressed.jpg"), "wb") as f:
            f.write(compressed)
        problem = {
            "subject": "数学", "type": "几何题",
            "content": "[几何题，图片见配图]", "answer": "",
            "knowledge_point": "几何", "has_figure": True,
            "page": 1, "is_big_question": False,
            "sub_problems": [], "image_file_id": img_id,
            "upload_mode": "geometry",
        }
        usage = {"hit": 0, "miss": 0, "out": 0, "cost_yuan": None}
        record = {
            "id": str(uuid.uuid4())[:8],
            "created_at": datetime.now().isoformat(),
            "filename": file.filename or "", "provider": "kimi",
            "model": "geometry-direct", "total_pages": 1,
            "recognized_pages": 0, "batches": 0, "failed_batches": 0,
            "input_cache_hit": 0, "input_cache_miss": 0, "output": 0, "cost_yuan": None,
        }
        await add_daily_cost(username, 0.0)
        await _save_usage_session(username, record)

        async def event_gen():
            yield "data: " + json.dumps({"type": "progress", "done": 1, "total": 1, "recognized": 1}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"type": "result", "problems": [problem],
                "total_pages": 1, "recognized_pages": 0, "batches": 0,
                "failed_batches": 0, "warning": "", "usage": usage, "session_id": record["id"]}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    images = []
    if _is_pdf(data):
        images, pdf_id = await _pdf_to_images(data, quality, max_long)
    elif _is_image(data):
        compressed = await _compress_image(data, max_long, quality)
        images.append(compressed)
    else:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG 图片或 PDF 文件")

    if not images:
        raise HTTPException(status_code=400, detail="未能从文件中提取到任何内容")

    max_pages = int(config.get("recognize_max_pages", 20) or 20)
    page_cap_warning = ""
    total_uploaded = len(images)
    if total_uploaded > max_pages:
        page_cap_warning = f"该文件共 {total_uploaded} 页，本次仅识别前 {max_pages} 页"
        images = images[:max_pages]

    filename = file.filename or ""

    async def worker(q: asyncio.Queue):
        try:
            file_type = "图片" if len(images) == 1 else "PDF"
            await q.put({"type": "text", "text": f"📂 文件类型: {file_type}\n"})
            await q.put({"type": "text", "text": f"🖼 共 {len(images)} 页，正在压缩...\n"})

            await q.put({"type": "text", "text": f"🤖 正在发送给 Kimi ({kimi_model}) 识别...\n"})
            await q.put({"type": "text", "text": f"⏳ Kimi 正在分析中（可能需要30秒~2分钟）...\n"})

            problems, agg, answer_pages, geometry_answer_pages = await _recognize_with_kimi(kimi_key, kimi_model, images, mode, timeout)

            await q.put({"type": "text", "text": f"✅ Kimi 识别完成，共 {len(problems)} 道题\n"})

            def _save_page_image(page_num: int) -> str:
                idx = page_num - 1
                if 0 <= idx < len(images):
                    img_id = str(uuid.uuid4())
                    with open(os.path.join(UPLOAD_DIR, f"{img_id}_compressed.jpg"), "wb") as f:
                        f.write(images[idx])
                    return img_id
                return ""

            for i, p in enumerate(problems):
                page = p.get("page", 0)
                if p.get("has_figure") and page:
                    p["image_file_id"] = _save_page_image(page)
                ans_page = p.get("answer_page")
                if ans_page and p.get("answer_has_figure"):
                    p["answer_image_file_id"] = _save_page_image(ans_page)

            await q.put({"type": "text", "text": f"💾 正在保存图片和用量数据...\n"})

            usage = _build_usage_payload(agg, config, "kimi", kimi_model)
            cost = usage["cost_yuan"]
            await add_daily_cost(username, cost or 0.0)
            record = {
                "id": str(uuid.uuid4())[:8],
                "created_at": datetime.now().isoformat(),
                "filename": filename, "provider": "kimi",
                "model": kimi_model, "total_pages": total_uploaded,
                "recognized_pages": len(images), "batches": 1,
                "failed_batches": 0,
                "input_cache_hit": agg["hit"],
                "input_cache_miss": agg["miss"],
                "output": agg["out"],
                "cost_yuan": cost,
            }
            await _save_usage_session(username, record)

            for p in problems:
                p["upload_mode"] = mode

            await q.put({"type": "text", "text": f"共识别 {len(problems)} 道题\n"})
            await q.put({
                "type": "result",
                "problems": problems, "total_pages": total_uploaded,
                "recognized_pages": len(images), "batches": 1,
                "failed_batches": 0, "warning": page_cap_warning,
                "usage": usage, "session_id": record["id"],
            })
        except HTTPException as e:
            await q.put({"type": "error", "detail": e.detail})
        except Exception as e:
            await q.put({"type": "error", "detail": f"识别失败: {type(e).__name__}"})
        finally:
            await q.put(None)

    q: asyncio.Queue = asyncio.Queue()

    async def event_gen():
        task = asyncio.create_task(worker(q))
        try:
            while True:
                item = await q.get()
                if item is None:
                    break
                yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                if item.get("type") in ("result", "error"):
                    yield "data: [DONE]\n\n"
                    break
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(event_gen(), media_type="text/event-stream")
