import asyncio
import json
import os
import random
import sqlite3
import threading
import time
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings

settings = get_settings()

# Daily counters, persisted to disk (plan B5.4).
#
# These used to live only in a module-level dict, which meant every restart
# reset the day's count to zero — so the "maximum 3 posts a day" limit was
# really "3 posts per process", and a crash loop could publish without bound.
# Stdlib sqlite3 in its own file, for the same reasons as the cost ledger: no
# lock contention with the ORM, and the record survives a database reset.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS action_counts (
    day       TEXT    NOT NULL,
    user_id   INTEGER NOT NULL,
    action    TEXT    NOT NULL,
    count     INTEGER NOT NULL DEFAULT 0,
    last_at   REAL,
    PRIMARY KEY (day, user_id, action)
);
"""

_lock = threading.Lock()
# Still in memory: spacing between actions only matters within a run.
_last_action: dict[int, float] = {}


def limiter_path() -> Path:
    override = os.environ.get("SOCIAL_DESK_LIMITER_DB", "").strip()
    if override:
        return Path(override)
    return _BACKEND_ROOT / "data" / "limits.db"


def _connect() -> sqlite3.Connection:
    path = limiter_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.executescript(_SCHEMA)
    return conn


def daily_limit(action: str) -> int:
    return {
        "connection_send": settings.max_connections_per_day,
        "post_publish": settings.max_posts_per_day,
    }.get(action, 100)


def count_today(user_id: int, action: str) -> int:
    """How many of this action today. Returns 0 if the store is unreadable."""
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT count FROM action_counts WHERE day=? AND user_id=? AND action=?",
                (date.today().isoformat(), user_id, action),
            ).fetchone()
            return row[0] if row else 0
    except (sqlite3.Error, OSError):
        # Fails open, like the cost cap: a rate limiter that locks her out of
        # her own tool over an unreadable file is the worse outcome.
        return 0


def can_perform(user_id: int, action: str) -> tuple[bool, str]:
    counter = count_today(user_id, action)
    limit = daily_limit(action)
    if counter >= limit:
        return False, (
            f"Daily limit reached: {counter} of {limit} allowed {action} actions today. "
            "This resets at midnight."
        )
    return True, "ok"


def record_action(user_id: int, action: str):
    now = time.time()
    try:
        with _lock, _connect() as conn:
            conn.execute(
                "INSERT INTO action_counts (day, user_id, action, count, last_at)"
                " VALUES (?,?,?,1,?)"
                " ON CONFLICT(day, user_id, action) DO UPDATE SET"
                " count = count + 1, last_at = excluded.last_at",
                (date.today().isoformat(), user_id, action, now),
            )
    except (sqlite3.Error, OSError):
        pass  # the action already happened; losing the count must not raise
    _last_action[user_id] = now


def usage_today(user_id: int) -> dict:
    """What has been used against each limit today, for the UI and doctor."""
    return {
        action: {"used": count_today(user_id, action), "limit": daily_limit(action)}
        for action in ("post_publish", "connection_send")
    }


async def wait_between_actions(user_id: int):
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
    """Bare counts per action. Kept for the existing automation router.

    Reads the persistent store; it used to read a module-level dict, which is
    gone along with the per-process counting it implied.
    """
    return {
        action: count_today(user_id, action)
        for action in ("connection_send", "post_publish")
    }


async def human_type_delay():
    """Random delay between keystrokes to mimic human typing."""
    await asyncio.sleep(random.uniform(0.03, 0.08))


async def human_pause():
    """Random human-like pause before clicking."""
    await asyncio.sleep(random.gauss(2.5, 0.8))
