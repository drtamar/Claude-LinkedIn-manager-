import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.ai_learning import LearningCycle, PromptVersion
from app.services.learning_service import run_learning_cycle, get_prompt_history, rollback_prompt

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/cycles")
def list_cycles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cycles = db.query(LearningCycle).filter(
        LearningCycle.user_id == current_user.id
    ).order_by(desc(LearningCycle.cycle_date)).limit(20).all()
    return [
        {
            "id": c.id,
            "cycle_date": c.cycle_date.isoformat(),
            "status": c.status,
            "improvements_made": c.improvements_made,
            "modules_analyzed": json.loads(c.modules_analyzed or "[]"),
            "avg_before_score": c.avg_before_score,
        }
        for c in cycles
    ]


@router.get("/cycles/{cycle_id}")
def get_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cycle = db.query(LearningCycle).filter(
        LearningCycle.id == cycle_id,
        LearningCycle.user_id == current_user.id,
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return {
        "id": cycle.id,
        "cycle_date": cycle.cycle_date.isoformat(),
        "status": cycle.status,
        "improvements_made": cycle.improvements_made,
        "insights": json.loads(cycle.insights or "{}"),
        "full_report": cycle.full_report,
    }


@router.post("/cycles/run")
async def trigger_cycle(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cycle = await run_learning_cycle(db, current_user.id)
    return {
        "cycle_id": cycle.id,
        "status": cycle.status,
        "improvements_made": cycle.improvements_made,
    }


@router.get("/prompts")
def list_all_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active = db.query(PromptVersion).filter(PromptVersion.is_active == True).all()
    return [
        {
            "module": pv.module,
            "version": pv.version,
            "model": pv.model,
            "performance_score": pv.performance_score,
            "sample_count": pv.sample_count,
            "created_at": pv.created_at.isoformat() if pv.created_at else None,
        }
        for pv in active
    ]


@router.get("/prompts/{module}")
def get_prompt_versions(
    module: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    history = get_prompt_history(db, module)
    return [
        {
            "id": pv.id,
            "version": pv.version,
            "is_active": pv.is_active,
            "performance_score": pv.performance_score,
            "sample_count": pv.sample_count,
            "change_reason": pv.change_reason,
            "created_at": pv.created_at.isoformat() if pv.created_at else None,
            "retired_at": pv.retired_at.isoformat() if pv.retired_at else None,
        }
        for pv in history
    ]


@router.post("/prompts/{module}/rollback/{version_id}")
def rollback(
    module: str,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pv = rollback_prompt(db, module, version_id)
    return {"message": f"Rolled back {module} to version {pv.version}"}
