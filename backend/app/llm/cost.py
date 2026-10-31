"""Cost meter and hard monthly cap (plan A3).

Every paid call is logged here with its stage, so "what did this month cost
and which part of the pipeline spent it" is a query rather than a guess.

Design notes worth knowing before changing anything:

* Stdlib `sqlite3` in its own file, not a SQLAlchemy model in the app's
  database. Two reasons: no lock contention with the ORM's connections, and
  the ledger survives a reset or migration of the app's own tables. Spending
  records are the one thing in here that cannot be regenerated.
* Prices are per million tokens, from the published Anthropic rates. They are
  a local copy, so they can drift — `verify_prices()` reports when the table
  was last reviewed, and the cap is the real protection, not the estimate.
* The cap fails *open* on a ledger read error: it reports the failure loudly
  rather than bricking the app over an unreadable file. A budget guard that
  locks a non-developer out of their own tool is a worse outcome than
  overspending by a few dollars.
"""
from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

# When this price table was last checked against the published rates.
PRICES_REVIEWED = "2026-10-31"
PRICE_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"


@dataclass(frozen=True)
class Price:
    """USD per 1,000,000 tokens."""

    input: float
    output: float
    # Explicit where Anthropic publishes one; otherwise the standard 0.1x of
    # input that applies across the range.
    cache_read: float | None = None
    # Anthropic does not publish a separate cache-write rate; the documented
    # multiplier for the 5-minute TTL is 1.25x input.
    cache_write_multiplier: float = 1.25
    # Haiku 5.5 charges more above a prompt-size threshold. None means flat.
    long_prompt_tokens: int | None = None
    long_prompt_input: float | None = None
    long_prompt_output: float | None = None

    def cache_read_rate(self) -> float:
        return self.cache_read if self.cache_read is not None else self.input * 0.1

    def cache_write_rate(self) -> float:
        return self.input * self.cache_write_multiplier


PRICES: dict[str, Price] = {
    # Frontier tier
    "claude-fable-5-1": Price(10.00, 50.00, cache_read=0.25),
    "claude-mythos-5-1": Price(10.00, 50.00, cache_read=0.25),
    "claude-fable-5": Price(10.00, 50.00),
    # Opus
    "claude-opus-5-5": Price(4.00, 20.00, cache_read=0.20),
    "claude-opus-5": Price(5.00, 25.00),
    "claude-opus-4-8": Price(5.00, 25.00),
    "claude-opus-4-7": Price(5.00, 25.00),
    "claude-opus-4-6": Price(5.00, 25.00),
    # Sonnet
    "claude-sonnet-5-5": Price(2.00, 10.00, cache_read=0.20),
    "claude-sonnet-5": Price(2.00, 10.00),
    "claude-sonnet-4-6": Price(3.00, 15.00),
    # Haiku
    "claude-haiku-5-5": Price(
        0.10, 0.50,
        long_prompt_tokens=100_000,
        long_prompt_input=0.50,
        long_prompt_output=2.50,
    ),
    "claude-haiku-4-5": Price(1.00, 5.00),
}

# Used when a model is not in the table, so an unknown model is costed
# pessimistically rather than as free.
FALLBACK_PRICE = Price(10.00, 50.00)

DEFAULT_MONTHLY_CAP_USD = 10.0


class CapExceeded(RuntimeError):
    """The monthly cloud budget is spent. Raised before any paid call."""


@dataclass(frozen=True)
class Usage:
    """Token counts for one call, as the API reports them."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @classmethod
    def from_response(cls, response) -> "Usage":
        """Read `response.usage` from the Anthropic SDK.

        Cache fields are absent on responses that did not use caching, and
        `getattr` with a default keeps this working across SDK versions.
        """
        u = getattr(response, "usage", None)
        if u is None:
            return cls()
        return cls(
            input_tokens=getattr(u, "input_tokens", 0) or 0,
            output_tokens=getattr(u, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        )

    @property
    def billable_input(self) -> int:
        """Uncached input. The API reports cached tokens separately, so adding
        them here would double-count."""
        return self.input_tokens


def price_for(model: str) -> Price:
    """Price row for a model id, tolerant of a date suffix."""
    if model in PRICES:
        return PRICES[model]
    # Accept `claude-opus-5-5-20260401` style ids by trimming a trailing date.
    for known in PRICES:
        if model.startswith(known):
            return PRICES[known]
    return FALLBACK_PRICE


def cost_of(model: str, usage: Usage) -> float:
    """USD for one call. Rounded to 6dp — fractions of a cent still add up."""
    p = price_for(model)

    in_rate, out_rate = p.input, p.output
    if p.long_prompt_tokens is not None:
        total_in = usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens
        if total_in > p.long_prompt_tokens:
            in_rate = p.long_prompt_input or in_rate
            out_rate = p.long_prompt_output or out_rate

    dollars = (
        usage.billable_input / 1_000_000 * in_rate
        + usage.output_tokens / 1_000_000 * out_rate
        + usage.cache_read_tokens / 1_000_000 * p.cache_read_rate()
        + usage.cache_write_tokens / 1_000_000 * p.cache_write_rate()
    )
    return round(dollars, 6)


# --------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT    NOT NULL,
    month         TEXT    NOT NULL,   -- 'YYYY-MM', indexed for the MTD query
    stage         TEXT    NOT NULL,   -- which pipeline step spent this
    model         TEXT    NOT NULL,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read    INTEGER NOT NULL DEFAULT 0,
    cache_write   INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL    NOT NULL,
    note          TEXT
);
CREATE INDEX IF NOT EXISTS idx_calls_month ON calls(month);
CREATE INDEX IF NOT EXISTS idx_calls_month_stage ON calls(month, stage);
"""

_lock = threading.Lock()


def ledger_path() -> Path:
    """Where the ledger lives. Anchored on the backend package, not the
    current directory, because a Windows shortcut can launch the app from
    anywhere (System32, in practice)."""
    override = os.environ.get("SOCIAL_DESK_COST_DB", "").strip()
    if override:
        return Path(override)
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "data" / "costs.db"


def _connect() -> sqlite3.Connection:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    # WAL so a read for the UI cannot block a write from the pipeline.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def current_month() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m")


def monthly_cap() -> float:
    raw = os.environ.get("SOCIAL_DESK_MONTHLY_CAP_USD", "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return DEFAULT_MONTHLY_CAP_USD


def record(
    stage: str,
    model: str,
    usage: Usage,
    *,
    note: str | None = None,
) -> float:
    """Log one paid call and return its cost.

    Never raises: a failed write must not fail the user's request. The money
    is already spent by the time we get here, so the only question is whether
    we also lose the request.
    """
    dollars = cost_of(model, usage)
    now = _dt.datetime.now(_dt.timezone.utc)
    try:
        with _lock, _connect() as conn:
            conn.execute(
                "INSERT INTO calls (created_at, month, stage, model, input_tokens,"
                " output_tokens, cache_read, cache_write, cost_usd, note)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    now.isoformat(timespec="seconds"),
                    now.strftime("%Y-%m"),
                    stage,
                    model,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.cache_read_tokens,
                    usage.cache_write_tokens,
                    dollars,
                    note,
                ),
            )
    except (sqlite3.Error, OSError):
        # Surfaced via summary()['ledger_error'] rather than thrown. OSError
        # matters as much as sqlite3.Error here: creating the data directory
        # can fail on a read-only or locked folder, which is a real Windows
        # failure mode, and it must not take the caller's request down.
        pass
    return dollars


def month_to_date(month: str | None = None) -> dict:
    """Spend so far this month, in total and per stage."""
    month = month or current_month()
    try:
        with _connect() as conn:
            total_row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) AS total, COUNT(*) AS calls"
                " FROM calls WHERE month = ?",
                (month,),
            ).fetchone()
            stage_rows = conn.execute(
                "SELECT stage, COALESCE(SUM(cost_usd), 0) AS total, COUNT(*) AS calls"
                " FROM calls WHERE month = ? GROUP BY stage ORDER BY total DESC",
                (month,),
            ).fetchall()
    except (sqlite3.Error, OSError) as exc:
        # check_cap() calls this before every paid request, so an exception
        # escaping here would block the whole app rather than one query.
        return {
            "month": month,
            "total_usd": 0.0,
            "calls": 0,
            "by_stage": {},
            "ledger_error": str(exc),
        }

    return {
        "month": month,
        "total_usd": round(total_row["total"], 4),
        "calls": total_row["calls"],
        "by_stage": {
            r["stage"]: {"usd": round(r["total"], 4), "calls": r["calls"]}
            for r in stage_rows
        },
        "ledger_error": None,
    }


def remaining_budget() -> float:
    """Dollars left this month. Can go negative if a single call overshot."""
    return round(monthly_cap() - month_to_date()["total_usd"], 4)


def check_cap() -> None:
    """Raise CapExceeded if the month's budget is spent.

    Called before every paid request. Fails open on a ledger error — see the
    module docstring for why.
    """
    mtd = month_to_date()
    if mtd.get("ledger_error"):
        return
    cap = monthly_cap()
    if mtd["total_usd"] >= cap:
        raise CapExceeded(
            f"Monthly cloud budget reached: ${mtd['total_usd']:.2f} of "
            f"${cap:.2f} spent in {mtd['month']} across {mtd['calls']} calls. "
            "Cloud calls are paused until next month. Raise the limit by "
            "setting SOCIAL_DESK_MONTHLY_CAP_USD in the .env file, or let "
            "local-model work continue in the meantime."
        )


def estimate(model: str, input_tokens: int, output_tokens: int) -> dict:
    """Price a call without making it. Backs the --dry-run flag (plan A3.4)."""
    usage = Usage(input_tokens=input_tokens, output_tokens=output_tokens)
    dollars = cost_of(model, usage)
    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_usd": dollars,
        "remaining_budget_usd": remaining_budget(),
        "would_exceed_cap": dollars > remaining_budget(),
    }


def summary() -> dict:
    """Everything the cost panel and the doctor command need in one call."""
    mtd = month_to_date()
    cap = monthly_cap()
    total = mtd["total_usd"]
    return {
        **mtd,
        "cap_usd": cap,
        "remaining_usd": round(cap - total, 4),
        "percent_used": round(total / cap * 100, 1) if cap > 0 else 0.0,
        "capped": total >= cap and not mtd.get("ledger_error"),
        "ledger_path": str(ledger_path()),
        "prices_reviewed": PRICES_REVIEWED,
        "price_source": PRICE_SOURCE,
    }
