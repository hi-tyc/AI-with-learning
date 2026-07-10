from openai import AsyncOpenAI
from openai.types.completion_usage import CompletionUsage
import httpx

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
KIMI_BASE_URL = "https://api.moonshot.cn/v1"

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15.0, read=300.0, write=60.0, pool=15.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _http_client


def create_client(
    api_key: str,
    base_url: str = DEEPSEEK_BASE_URL,
    timeout: int = 120,
) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        max_retries=2,
        http_client=_get_http_client(),
    )


def extract_reasoning(delta) -> str:
    if delta is None:
        return ""
    extra = getattr(delta, "model_extra", None) or {}
    return extra.get("reasoning_content", "") or ""


def extract_usage_sdk(usage: CompletionUsage | None) -> tuple[int, int, int]:
    if usage is None:
        return 0, 0, 0
    prompt = usage.prompt_tokens or 0
    completion = usage.completion_tokens or 0

    # DeepSeek: typed attributes on CompletionUsage
    if hasattr(usage, "prompt_cache_hit_tokens"):
        hit = getattr(usage, "prompt_cache_hit_tokens") or 0
        miss = getattr(usage, "prompt_cache_miss_tokens", None)
        if miss is None:
            miss = max(0, prompt - hit)
        return int(hit), int(max(0, miss or 0)), int(completion)

    # Kimi (Moonshot): typed attributes
    hit = 0
    if hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
        details = usage.prompt_tokens_details
        hit = getattr(details, "cached_tokens", 0) or 0
    if not hit and hasattr(usage, "cached_tokens"):
        hit = getattr(usage, "cached_tokens") or 0

    # Fallback to model_extra for SDK versions that keep them there
    if not hit:
        extra = getattr(usage, "model_extra", None) or {}
        if "prompt_cache_hit_tokens" in extra:
            hit = extra.get("prompt_cache_hit_tokens") or 0
            miss = extra.get("prompt_cache_miss_tokens")
            if miss is None:
                miss = max(0, prompt - hit)
            return int(hit), int(max(0, miss or 0)), int(completion)
        hit = extra.get("cached_tokens") or 0
        if not hit:
            details = extra.get("prompt_tokens_details", {}) or {}
            hit = details.get("cached_tokens", 0) if isinstance(details, dict) else getattr(details, "cached_tokens", 0)

    hit = hit or 0
    miss = max(0, prompt - hit)
    return int(hit), int(miss), int(completion)
