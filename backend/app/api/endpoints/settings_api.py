from pydantic import BaseModel
from openai import APITimeoutError, APIConnectionError, APIStatusError, RateLimitError, AuthenticationError
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from app.api.endpoints.auth import get_current_user
from app.core.user_data import get_user_config_path
from app.utils.file_lock import read_json, write_json
from app.utils.ai_client import create_client, DEEPSEEK_BASE_URL, KIMI_BASE_URL

router = APIRouter()


class TestRequest(BaseModel):
    deepseek_api_key: Optional[str] = None
    deepseek_model: Optional[str] = None
    deepseek_timeout: Optional[int] = None
    kimi_api_key: Optional[str] = None
    kimi_model: Optional[str] = None
    kimi_timeout: Optional[int] = None


def _pick(body_val, config_val):
    if body_val is None:
        return config_val
    if isinstance(body_val, str):
        v = body_val.strip()
        if not v or "****" in v:
            return config_val
        return v
    return body_val


class SystemSettings(BaseModel):
    deepseek_api_key: str = ""
    deepseek_model: Literal["flash", "pro"] = "flash"
    kimi_api_key: str = ""
    kimi_model: str = "kimi-k2.6"
    kimi_timeout: int = 120
    daily_cost_limit: float = 10.0
    image_max_size_mb: int = 10
    image_compress_quality: int = 40
    image_max_long_edge: int = 800
    deepseek_timeout: int = 120
    retry_count: int = 2
    retry_interval: int = 3


class SettingsResponse(BaseModel):
    deepseek_api_key: str
    deepseek_model: str
    kimi_api_key: str
    kimi_model: str
    kimi_timeout: int
    daily_cost_limit: float
    image_max_size_mb: int
    image_compress_quality: int
    image_max_long_edge: int
    deepseek_timeout: int
    retry_count: int
    retry_interval: int


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def _is_masked_or_invalid(key: str) -> bool:
    if not key:
        return True
    if "****" in key:
        return True
    return False


def _get_deepseek_model_name(model: str) -> str:
    return "deepseek-v4-flash" if model == "flash" else "deepseek-v4-pro"


KIMI_MODELS = ["kimi-k2.6", "kimi-k2.5", "kimi-k2.7-code", "kimi-k2.7-code-highspeed", "kimi-for-coding"]


@router.get("", response_model=SettingsResponse)
async def get_settings(request: Request, username: str = Depends(get_current_user)):
    config = await read_json(get_user_config_path(username))
    if config is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    ds_key = config.get("deepseek_api_key", "")
    kimi_key = config.get("kimi_api_key", "")
    return SettingsResponse(
        deepseek_api_key="" if _is_masked_or_invalid(ds_key) else _mask_key(ds_key),
        deepseek_model=config.get("deepseek_model", "flash"),
        kimi_api_key="" if _is_masked_or_invalid(kimi_key) else _mask_key(kimi_key),
        kimi_model=config.get("kimi_model", "kimi-k2.6"),
        kimi_timeout=config.get("kimi_timeout", 120),
        daily_cost_limit=config.get("daily_cost_limit", 10.0),
        image_max_size_mb=config.get("image_max_size_mb", 10),
        image_compress_quality=config.get("image_compress_quality", 40),
        image_max_long_edge=config.get("image_max_long_edge", 800),
        deepseek_timeout=config.get("deepseek_timeout", 120),
        retry_count=config.get("retry_count", 2),
        retry_interval=config.get("retry_interval", 3),
    )


@router.put("")
async def update_settings(
    request: Request,
    settings: SystemSettings,
    username: str = Depends(get_current_user),
):
    config_path = get_user_config_path(username)
    existing = await read_json(config_path) or {}
    if settings.deepseek_api_key and ("****" in settings.deepseek_api_key):
        settings.deepseek_api_key = existing.get("deepseek_api_key", "")
    if settings.kimi_api_key and ("****" in settings.kimi_api_key):
        settings.kimi_api_key = existing.get("kimi_api_key", "")
    existing.update(settings.model_dump())
    await write_json(config_path, existing)
    return {"message": "设置已保存"}


@router.post("/test/deepseek")
async def test_deepseek(
    request: Request,
    body: TestRequest = TestRequest(),
    username: str = Depends(get_current_user),
):
    config = await read_json(get_user_config_path(username)) or {}
    api_key = _pick(body.deepseek_api_key, config.get("deepseek_api_key", ""))
    model_choice = _pick(body.deepseek_model, config.get("deepseek_model", "flash"))
    timeout = body.deepseek_timeout or config.get("deepseek_timeout", 60)
    if not api_key:
        raise HTTPException(status_code=400, detail="DeepSeek API Key 未配置")
    model = _get_deepseek_model_name(model_choice)
    client = create_client(api_key, DEEPSEEK_BASE_URL, timeout)
    try:
        await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "你好"}],
            max_tokens=5,
        )
        return {"status": "ok", "message": f"DeepSeek 连接成功 (模型: {model})"}
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="DeepSeek API Key 无效")
    except RateLimitError:
        raise HTTPException(status_code=429, detail="请求过于频繁")
    except APITimeoutError:
        raise HTTPException(status_code=504, detail="DeepSeek 连接超时")
    except (APIConnectionError, APIStatusError) as e:
        status = getattr(e, "status_code", 502)
        raise HTTPException(status_code=status, detail=f"DeepSeek 返回错误: {status}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"连接测试失败: {str(e)}")


@router.post("/test/kimi")
async def test_kimi(
    request: Request,
    body: TestRequest = TestRequest(),
    username: str = Depends(get_current_user),
):
    config = await read_json(get_user_config_path(username)) or {}
    api_key = _pick(body.kimi_api_key, config.get("kimi_api_key", ""))
    model = _pick(body.kimi_model, config.get("kimi_model", "kimi-k2.6"))
    timeout = body.kimi_timeout or config.get("kimi_timeout", 60)
    if not api_key:
        raise HTTPException(status_code=400, detail="Kimi API Key 未配置")
    client = create_client(api_key, KIMI_BASE_URL, timeout)
    try:
        await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "你好"}],
            max_tokens=5,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return {"status": "ok", "message": f"Kimi 连接成功 (模型: {model})"}
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Kimi API Key 无效")
    except RateLimitError:
        raise HTTPException(status_code=429, detail="请求过于频繁")
    except APITimeoutError:
        raise HTTPException(status_code=504, detail="Kimi 连接超时")
    except (APIConnectionError, APIStatusError) as e:
        status = getattr(e, "status_code", 502)
        raise HTTPException(status_code=status, detail=f"Kimi 返回错误: {status}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"连接测试失败: {str(e)}")
