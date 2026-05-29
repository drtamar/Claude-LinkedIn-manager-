from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services import analytics_service as svc
from app.ai.modules.algorithm_ai import generate_insights
from app.services.profile_service import get_user_profile, user_profile_to_dict

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return svc.get_dashboard_stats(db, current_user.id)


@router.get("/posts")
def get_post_performance(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return svc.get_post_metrics(db, current_user.id, days)


@router.get("/ssi")
def get_ssi_history(
    weeks: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return svc.get_ssi_history(db, current_user.id, weeks)


@router.get("/heatmap")
def get_heatmap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return svc.get_engagement_heatmap(db, current_user.id)


@router.get("/insights")
async def get_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stored = svc.get_active_insights(db, current_user.id)
    if stored:
        return stored

    # Generate fresh insights if none exist
    user_profile_obj = get_user_profile(db, current_user.id)
    profile_dict = user_profile_to_dict(user_profile_obj) if user_profile_obj else {}
    metrics = svc.get_post_metrics(db, current_user.id, 30)
    return await generate_insights(profile_dict, metrics)


@router.post("/refresh")
def trigger_scrape(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.ai_learning import AutomationJob
    import json
    job = AutomationJob(
        user_id=current_user.id,
        job_type="analytics_scrape",
        payload=json.dumps({}),
    )
    db.add(job)
    db.commit()
    return {"message": "Analytics scrape queued", "job_id": job.id}
