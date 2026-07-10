"""Daily API cost tracking.

Tracks per-user daily spending in memory. The counters reset at midnight local time.
Note: the lock is process-local; multiple Uvicorn workers do not share counters.
For single-process deployments this is sufficient.
"""

import asyncio
from datetime import datetime


daily_costs: dict[str, float] = {}
daily_cost_date: str = ""
_cost_lock = asyncio.Lock()


async def _check_daily_reset() -> None:
    global daily_cost_date
    today = datetime.now().strftime("%Y-%m-%d")
    async with _cost_lock:
        if daily_cost_date != today:
            daily_costs.clear()
            daily_cost_date = today


async def check_daily_limit(username: str, daily_limit: float) -> bool:
    """Return True if the user has not reached the daily cost limit."""
    await _check_daily_reset()
    async with _cost_lock:
        current = daily_costs.get(username, 0.0)
        return current < daily_limit


async def add_daily_cost(username: str, cost: float) -> None:
    """Add cost to the user's daily total."""
    await _check_daily_reset()
    async with _cost_lock:
        daily_costs[username] = daily_costs.get(username, 0.0) + cost
