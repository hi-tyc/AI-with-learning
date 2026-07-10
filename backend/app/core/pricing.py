"""Pricing & usage extraction helpers.

DEFAULT_PRICING below are the providers' real published rates, expressed in
¥ (RMB) per 1,000,000 tokens, matching the endpoints this app uses
(Kimi platform api.moonshot.cn / kimi-k2.6, DeepSeek api.deepseek.com).

These defaults can be overridden per-user via the user config under the
``config["pricing"]`` key (same nested shape: provider -> {input_cache_hit,
input_cache_miss, output}). Any keys present in the user config are deep-merged
over these defaults; missing providers/keys fall back to the defaults here.

Note: the ``kimi_code`` provider (Kimi Code 包月订阅, model kimi-for-coding) is
NOT billed per token — it is a monthly subscription. Sessions using Kimi Code
are recorded with cost_yuan = None (UI shows 不计费/包月) and ``compute_cost``
returns None for them.
"""

# Providers whose usage is a flat monthly subscription, not metered per token.
# Their sessions are recorded with cost_yuan = None ("不计费/包月").
NON_METERED_PROVIDERS = {"kimi_code"}

DEFAULT_PRICING = {
    # Kimi 开放平台 (api.moonshot.cn) 各模型实际价格 (¥/1M tokens)
    # 来源: https://platform.kimi.com/docs/pricing/chat
    "kimi_k25":       {"input_cache_hit": 0.70, "input_cache_miss": 4.00, "output": 21.0},
    "kimi_k26":       {"input_cache_hit": 1.10, "input_cache_miss": 6.50, "output": 27.0},
    "kimi_k27_code":  {"input_cache_hit": 1.30, "input_cache_miss": 6.50, "output": 27.0},
    "kimi_k27_code_highspeed": {"input_cache_hit": 2.60, "input_cache_miss": 13.00, "output": 54.0},
    # 兼容旧配置 / 未知 Kimi 模型：回退到 K2.6 价格
    "kimi":           {"input_cache_hit": 1.10, "input_cache_miss": 6.50, "output": 27.0},
    # Kimi K2 Thinking 系列（已下线，保留用于历史账单兼容）
    "kimi_thinking":  {"input_cache_hit": 4.0, "input_cache_miss": 4.0, "output": 32.0},
    # DeepSeek (¥/1M tokens)
    "deepseek_flash": {"input_cache_hit": 0.02,  "input_cache_miss": 1.0, "output": 2.0},
    "deepseek_pro":   {"input_cache_hit": 0.025, "input_cache_miss": 3.0, "output": 6.0},
    # 兼容旧配置
    "deepseek":       {"input_cache_hit": 0.025, "input_cache_miss": 3.0, "output": 6.0},
    # Kimi Code 包月订阅，不按 token 计费。
    "kimi_code": None,
}


def _pricing_key(provider: str, model_name: str) -> str:
    """Map provider + actual model name to the correct pricing table key."""
    if provider == "deepseek":
        lower = model_name.lower()
        if "pro" in lower:
            return "deepseek_pro"
        return "deepseek_flash"
    if provider == "kimi":
        lower = model_name.lower()
        if "kimi-k2.5" in lower or "k25" in lower:
            return "kimi_k25"
        if "kimi-k2.6" in lower or "k26" in lower:
            return "kimi_k26"
        # Non-metered Kimi Code subscription must be checked before other code variants.
        if "kimi-for-coding" in lower or lower == "kimi_code":
            return "kimi_code"
        # Highspeed variant must be checked before standard k2.7-code.
        if "kimi-k2.7-code-highspeed" in lower or "highspeed" in lower:
            return "kimi_k27_code_highspeed"
        if "kimi-k2.7-code" in lower or "k27_code" in lower:
            return "kimi_k27_code"
        return "kimi"
    return provider


def get_pricing(config: dict) -> dict:
    """Deep-merge ``config["pricing"]`` over DEFAULT_PRICING (per provider,
    per key) and return the resulting pricing table."""
    override = (config or {}).get("pricing", {}) or {}
    merged: dict = {}
    # start from defaults (a None entry means a non-metered / subscription provider)
    for provider, rates in DEFAULT_PRICING.items():
        merged[provider] = dict(rates) if isinstance(rates, dict) else rates
    # apply overrides (including any extra providers the user defines)
    for provider, rates in override.items():
        if rates is None:
            merged[provider] = None
            continue
        if not isinstance(rates, dict):
            continue
        base = merged.get(provider) or {}
        base = dict(base)
        for key, val in rates.items():
            base[key] = val
        merged[provider] = base
    return merged


def extract_usage(usage: dict) -> tuple[int, int, int]:
    """Normalize a provider ``usage`` object into (hit, miss, out) token counts.

    - DeepSeek shape: has ``prompt_cache_hit_tokens`` →
        hit = prompt_cache_hit_tokens
        miss = prompt_cache_miss_tokens (fallback prompt_tokens - hit)
        out = completion_tokens
    - Kimi (Moonshot) shape: no ``prompt_cache_hit_tokens`` →
        hit = cached_tokens (or prompt_tokens_details.cached_tokens)
        miss = max(0, prompt_tokens - hit)
        out = completion_tokens
    All values guarded with ``or 0``.
    """
    usage = usage or {}
    if "prompt_cache_hit_tokens" in usage:
        # DeepSeek
        hit = usage.get("prompt_cache_hit_tokens") or 0
        miss = usage.get("prompt_cache_miss_tokens")
        if miss is None:
            miss = (usage.get("prompt_tokens") or 0) - hit
        miss = miss or 0
        out = usage.get("completion_tokens") or 0
        return int(hit), int(max(0, miss)), int(out)

    # Kimi (Moonshot)
    prompt_tokens = usage.get("prompt_tokens") or 0
    hit = usage.get("cached_tokens")
    if not hit:
        details = usage.get("prompt_tokens_details", {}) or {}
        hit = details.get("cached_tokens", 0)
    hit = hit or 0
    miss = max(0, (prompt_tokens or 0) - hit)
    out = usage.get("completion_tokens") or 0
    return int(hit), int(miss), int(out)


def compute_cost(provider: str, hit: int, miss: int, out: int, pricing: dict):
    """Compute the ¥ cost for a session given token counts and a pricing table.

    Returns ``None`` for non-metered providers (e.g. Kimi Code 包月订阅) or when
    the provider's pricing entry is explicitly ``None`` — the caller should then
    treat the session as 不计费/包月 rather than ¥0.
    """
    if provider in NON_METERED_PROVIDERS:
        return None
    p = pricing.get(provider, DEFAULT_PRICING.get(provider, {}))
    if not p:  # None or empty -> non-metered / unknown
        return None
    cost = (
        hit * p.get("input_cache_hit", 0)
        + miss * p.get("input_cache_miss", 0)
        + out * p.get("output", 0)
    ) / 1_000_000
    return round(cost, 6)
