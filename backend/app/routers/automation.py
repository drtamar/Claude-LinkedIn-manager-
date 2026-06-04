import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.ai_learning import AutomationJob
from app.automation.browser_manager import encrypt_cookies, decrypt_cookies, check_session_valid
from app.automation.post_publisher import publish_post, send_connection_request
from app.automation.safety_limiter import get_daily_counts, can_perform
from app.services import content_service as content_svc

router = APIRouter(prefix="/api/automation", tags=["automation"])


class CookieSessionRequest(BaseModel):
    cookies: list[dict]


class PublishRequest(BaseModel):
    post_id: int


@router.post("/linkedin/connect")
def save_linkedin_session(
    req: CookieSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encrypted = encrypt_cookies(req.cookies)
    current_user.linkedin_cookies = encrypted
    current_user.linkedin_connected = True
    db.commit()
    return {"message": "LinkedIn session saved"}


@router.get("/linkedin/status")
async def check_linkedin_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.linkedin_cookies:
        return {"connected": False, "reason": "No session saved"}
    cookies = decrypt_cookies(current_user.linkedin_cookies)
    valid = await check_session_valid(cookies)
    if not valid:
        current_user.linkedin_connected = False
        db.commit()
    return {"connected": valid}


@router.delete("/linkedin/disconnect")
def disconnect_linkedin(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.linkedin_cookies = None
    current_user.linkedin_connected = False
    db.commit()
    return {"message": "LinkedIn session cleared"}


async def _execute_publish_job(job_id: int, post_id: int, user_id: int, cookies_encrypted: str):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if not job:
            return
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        post = content_svc.get_post(db, post_id, user_id)
        if not post:
            job.status = "failed"
            job.error_message = "Post not found"
            job.completed_at = datetime.utcnow()
            db.commit()
            return

        result = await publish_post(
            user_linkedin_cookies_encrypted=cookies_encrypted,
            content=post.content,
            user_id=user_id,
        )

        job.result = json.dumps(result)
        job.status = "completed" if result.get("success") else "failed"
        job.error_message = result.get("error") if not result.get("success") else None
        job.completed_at = datetime.utcnow()
        job.attempts = 1

        if result.get("success"):
            post.status = "published"
            post.published_at = datetime.utcnow()
            if result.get("linkedin_post_id"):
                post.linkedin_post_id = result["linkedin_post_id"]

        db.commit()
    except Exception as e:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@router.post("/publish/{post_id}", status_code=202)
async def publish_post_now(
    post_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.linkedin_cookies:
        raise HTTPException(status_code=400, detail="Connect LinkedIn first")

    post = content_svc.get_post(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    job = AutomationJob(
        user_id=current_user.id,
        job_type="post_publish",
        payload=json.dumps({"post_id": post_id}),
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        _execute_publish_job,
        job.id,
        post_id,
        current_user.id,
        current_user.linkedin_cookies,
    )

    return {"message": "Publishing job queued", "job_id": job.id}


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
