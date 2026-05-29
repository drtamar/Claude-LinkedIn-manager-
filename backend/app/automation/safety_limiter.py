import json
import random
import asyncio
from datetime import date
from sqlalchemy.orm import Session
from app.config import get_settings

settings = get_settings()

# In-memory daily counters (reset at midnight)
_daily_counters: dict[str, dict] = {}
_last_action: dict[int, float] = {}


def _get_today_key(user_id: int, action: str) -> str:
    return f"{user_id}:{action}:{date.today().isoformat()}"


def can_perform(user_id: int, action: str) -> tuple[bool, str]:
    key = _get_today_key(user_id, action)
    counter = _daily_counters.get(key, 0)

    limits = {
        "connection_send": settings.max_connections_per_day,
        "post_publish": settings.max_posts_per_day,
    }
    limit = limits.get(action, 100)

    if counter >= limit:
        return False, f"Daily limit reached: {counter}/{limit} {action}s today"
    return True, "ok"


def record_action(user_id: int, action: str):
    key = _get_today_key(user_id, action)
    _daily_counters[key] = _daily_counters.get(key, 0) + 1
    import time
    _last_action[user_id] = time.time()


async def wait_between_actions(user_id: int):
    import time
    last = _last_action.get(user_id, 0)
    elapsed = time.time() - last
    min_wait = settings.min_action_interval_seconds
    # Normal distribution around min_wait for human appearance
    wait_time = random.gauss(min_wait, min_wait * 0.2)
    wait_time = max(wait_time * 0.5, wait_time)  # at least 50% of configured value
    remaining = wait_time - elapsed
    if remaining > 0:
        await asyncio.sleep(remaining)


def get_daily_counts(user_id: int) -> dict:
    result = {}
    for action in ["connection_send", "post_publish"]:
        key = _get_today_key(user_id, action)
        result[action] = _daily_counters.get(key, 0)
    return result


async def human_type_delay():
    """Random delay between keystrokes to mimic human typing."""
    await asyncio.sleep(random.uniform(0.03, 0.08))


async def human_pause():
    """Random human-like pause before clicking."""
    await asyncio.sleep(random.gauss(2.5, 0.8))
