import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.ai_learning import AutomationJob
from app.automation.safety_limiter import get_daily_counts, can_perform, record_action
from app.channels import Piece, get_adapter
from app.subjects import Channel
from app.services import content_service as content_svc

router = APIRouter(prefix="/api/automation", tags=["automation"])


class CookieSessionRequest(BaseModel):
    cookies: list[dict]


class PublishRequest(BaseModel):
    post_id: int


OFFICIAL_API_NOTE = (
    "LinkedIn now publishes through its official API instead of a browser "
    "session. Run `python -m app.cli connect-linkedin` once to authorise it. "
    "Driving linkedin.com with stored cookies is automated access under "
    "LinkedIn's User Agreement and risks a permanent restriction on the "
    "account, which is why this route was retired."
)


@router.post("/linkedin/connect", status_code=410)
def save_linkedin_session(
    req: CookieSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retired (decision 0.9). Cookie sessions are no longer accepted."""
    raise HTTPException(status_code=410, detail=OFFICIAL_API_NOTE)


@router.get("/linkedin/status")
async def check_linkedin_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Whether LinkedIn can be posted to, by the official API.

    Reports on the API credentials now, not on a browser session. A stored
    cookie is reported separately so it is visible that it is still there and
    unused — DELETE /linkedin/disconnect clears it.
    """
    adapter = get_adapter(Channel.LINKEDIN)
    return {
        "connected": adapter.is_configured(),
        "method": "official_api",
        "reason": (
            None if adapter.is_configured()
            else "Not authorised yet — run `python -m app.cli connect-linkedin`."
        ),
        "stale_cookies_stored": bool(current_user.linkedin_cookies),
    }


@router.delete("/linkedin/disconnect")
def disconnect_linkedin(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.linkedin_cookies = None
    current_user.linkedin_connected = False
    db.commit()
    return {"message": "LinkedIn session cleared"}


@router.post("/publish/{post_id}")
async def publish_post_now(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = content_svc.get_post(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    allowed, reason = can_perform(current_user.id, "post_publish")
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    channel = Channel(post.channel or "linkedin")
    adapter = get_adapter(channel)
    if not adapter.is_configured():
        raise HTTPException(status_code=400, detail=OFFICIAL_API_NOTE)

    # Synchronous on purpose: an API call returns in under a second, so the
    # background job and its polling only existed because driving a browser
    # took minutes.
    result = adapter.check_then_publish(Piece(
        title=post.title or "",
        body=post.content,
        subject=(post.idea.subject if post.idea else None) or "vet_news",
        channel=channel,
        idea_id=post.idea_id,
    ))

    if not result.published:
        raise HTTPException(status_code=502, detail=result.detail)

    post.status = "published"
    post.published_at = datetime.utcnow()
    post.external_id = result.external_id
    if channel is Channel.LINKEDIN:
        post.linkedin_post_id = result.external_id
    db.commit()
    record_action(current_user.id, "post_publish")

    return {
        "message": result.detail,
        "external_id": result.external_id,
        "url": result.location,
    }


@router.get("/jobs")
def list_jobs(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import desc
    jobs = db.query(AutomationJob).filter(
        AutomationJob.user_id == current_user.id
    ).order_by(desc(AutomationJob.queued_at)).limit(limit).all()
    return [
        {
            "id": j.id,
            "job_type": j.job_type,
            "status": j.status,
            "payload": json.loads(j.payload or "{}"),
            "result": json.loads(j.result or "{}"),
            "error_message": j.error_message,
            "attempts": j.attempts,
            "queued_at": j.queued_at.isoformat() if j.queued_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]


@router.get("/status")
def get_automation_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    counts = get_daily_counts(current_user.id)
    return {
        "linkedin_connected": current_user.linkedin_connected,
        "daily_limits": {
            "connections_sent": counts.get("connection_send", 0),
            "connections_limit": 15,
            "posts_published": counts.get("post_publish", 0),
            "posts_limit": 3,
        }
    }
