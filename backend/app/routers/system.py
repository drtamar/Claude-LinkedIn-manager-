"""Spend meter, routing picture and self-diagnosis (plan A3.2).

Deliberately unauthenticated. These are the endpoints you need when something
is wrong, and in this app "something is wrong" has repeatedly meant "I cannot
log in" — a diagnostic behind a login is useless exactly when it is needed.
The app binds to localhost for a single user, and nothing here returns a
secret: the API key is reported as present/absent and masked, never echoed.
"""
from fastapi import APIRouter, Query

from app.ai.claude_client import DEFAULT_MODEL
from app.config import get_settings
from app.channels import status as channel_status
from app.llm import cost, hardware, local
from app.llm.router import Router, TaskKind
from app.subjects.definitions import matrix as subject_matrix

router = APIRouter(prefix="/api/system", tags=["system"])
settings = get_settings()

# Probing hardware shells out to nvidia-smi, so do it once per process rather
# than on every poll of the cost panel.
_router_cache: Router | None = None


def get_router() -> Router:
    global _router_cache
    if _router_cache is None:
        _router_cache = Router()
    return _router_cache


def _mask(key: str) -> str:
    """Enough to tell two keys apart, not enough to use one."""
    key = (key or "").strip()
    if not key:
        return ""
    return f"{key[:11]}…{key[-4:]}" if len(key) > 18 else "…"


@router.get("/cost")
def spend(month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$")):
    """Month-to-date spend, broken down by stage.

    `month` accepts YYYY-MM to look at a previous month.
    """
    summary = cost.summary() if month is None else {
        **cost.month_to_date(month),
        "cap_usd": cost.monthly_cap(),
    }
    return {
        **summary,
        "note": (
            "Local-model work is free and does not appear here. A month with a "
            "small total and many calls means routing is working."
        ),
    }


@router.get("/cost/estimate")
def estimate(
    model: str = Query(DEFAULT_MODEL),
    input_tokens: int = Query(..., ge=0),
    output_tokens: int = Query(0, ge=0),
):
    """Price a call without making it (plan A3.4)."""
    return cost.estimate(model, input_tokens, output_tokens)


@router.get("/routes")
def routes():
    """Where each pipeline step would run right now, and why.

    Spends nothing: this reports the decision, it does not execute anything.
    """
    r = get_router()
    plans = [r.plan(t) for t in TaskKind]
    return {
        "local_model": r.local_model,
        "tier": r.tier.value,
        "routes": plans,
        "free_steps": sum(1 for p in plans if p["free"]),
        "paid_steps": sum(1 for p in plans if p["actual_destination"] == "cloud"),
        "fallbacks_active": [
            {"task": p["task"], "reason": p["fallback_reason"]}
            for p in plans if p["fallback_reason"]
        ],
    }


@router.get("/subjects")
def subjects():
    """The four subjects and their channel assignments (plan B1, B2)."""
    from app.subjects import NO_SELF_PROMOTION

    return {
        "subjects": subject_matrix(),
        "no_self_promotion": [c.value for c in NO_SELF_PROMOTION],
    }


@router.get("/channels")
def channels():
    """Which channels are built and which can publish right now."""
    rows = channel_status()
    return {
        "channels": rows,
        "ready": [r["channel"] for r in rows if r.get("configured")],
        "planned": [r["channel"] for r in rows if not r["implemented"]],
    }


@router.get("/doctor")
def doctor():
    """One call that answers "is this thing set up correctly?".

    Each check carries a `fix` string written for someone who is not a
    developer, because that is who reads it.
    """
    hw = hardware.describe(get_router().hardware)
    tier_model = hw["local_model"]
    ollama = local.status(tier_model)
    spend_now = cost.summary()
    key = (settings.anthropic_api_key or "").strip()
    key_ok = bool(key) and key.startswith("sk-ant-") and "PUT-YOUR-KEY" not in key

    checks = [
        {
            "name": "Anthropic API key",
            "ok": key_ok,
            "detail": _mask(key) if key_ok else "not set, or still a placeholder",
            "fix": None if key_ok else (
                "Open the .env file in the project folder and set "
                "ANTHROPIC_API_KEY to your key from console.anthropic.com, "
                "then restart."
            ),
        },
        {
            "name": "Local model (Ollama)",
            "ok": ollama["ready"],
            "detail": ollama["detail"],
            # Not fatal: the router falls back to a cheap cloud model.
            "severity": "warning",
            "fix": None if ollama["ready"] else ollama["detail"],
        },
        {
            "name": "Spending cap",
            "ok": not spend_now["capped"],
            "detail": (
                f"${spend_now['total_usd']:.2f} of ${spend_now['cap_usd']:.2f} "
                f"used this month ({spend_now['percent_used']}%)"
            ),
            "fix": None if not spend_now["capped"] else (
                "The monthly budget is spent, so paid calls are paused. Raise "
                "SOCIAL_DESK_MONTHLY_CAP_USD in .env, or wait for next month."
            ),
        },
        {
            "name": "Cost ledger",
            "ok": spend_now["ledger_error"] is None,
            "detail": spend_now["ledger_error"] or spend_now["ledger_path"],
            "fix": None if spend_now["ledger_error"] is None else (
                "The spending log could not be read, so the cap cannot be "
                "enforced. Check that the data folder is writable."
            ),
        },
    ]

    channels = channel_status()
    ready = [c["channel"] for c in channels if c.get("configured")]
    checks.append({
        "name": "Publishing channels",
        "ok": bool(ready),
        "detail": (
            f"ready: {', '.join(ready)}" if ready
            else "none configured — the website needs no setup, so this "
                 "should not happen"
        ),
        # Not blocking: channels are set up one at a time, and the website
        # works with no credentials at all.
        "severity": "warning",
        "fix": None if len(ready) > 1 else (
            "To post to LinkedIn, run: python -m app.cli connect-linkedin"
        ),
    })

    blocking = [c for c in checks if not c["ok"] and c.get("severity") != "warning"]
    return {
        "ok": not blocking,
        "checks": checks,
        "hardware": hw,
        "cost": spend_now,
        "cloud_model": DEFAULT_MODEL,
        "prices_reviewed": cost.PRICES_REVIEWED,
        "channels": channels,
        "subjects": [
            {"id": s["id"], "name": s["name"], "publishes_to":
             s["primary"] + s["secondary"]}
            for s in subject_matrix()
        ],
    }
