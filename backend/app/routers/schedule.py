from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.schedule import ContentCalendar
from app.ai.modules.algorithm_ai import get_optimal_times, OPTIMAL_TIMES
from app.services.profile_service import get_user_profile, user_profile_to_dict

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("/calendar")
def get_calendar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entries = db.query(ContentCalendar).filter(
        ContentCalendar.user_id == current_user.id
    ).all()
    return [
        {
            "id": e.id,
            "post_id": e.post_id,
            "scheduled_date": e.scheduled_date.isoformat() if e.scheduled_date else None,
            "scheduled_time": e.scheduled_time.isoformat() if e.scheduled_time else None,
            "slot_type": e.slot_type,
            "status": e.status,
            "notes": e.notes,
        }
        for e in entries
    ]


@router.get("/optimal-times")
async def get_optimal(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_profile_obj = get_user_profile(db, current_user.id)
    profile_dict = user_profile_to_dict(user_profile_obj) if user_profile_obj else {}
    result = await get_optimal_times(profile_dict, [])
    return result


@router.post("/auto-plan")
async def auto_plan_calendar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import timedelta
    today = date.today()
    created = 0
    for i in range(30):
        day = today + timedelta(days=i)
        # Skip weekends
        if day.weekday() >= 5:
            continue
        # Post 3x/week: Mon, Wed, Thu
        if day.weekday() in [0, 2, 3] and i % 1 == 0:
            existing = db.query(ContentCalendar).filter(
                ContentCalendar.user_id == current_user.id,
                ContentCalendar.scheduled_date == day,
            ).first()
            if not existing:
                entry = ContentCalendar(
                    user_id=current_user.id,
                    scheduled_date=day,
                    slot_type="morning",
                    status="planned",
                    notes="AI-planned slot",
                )
                db.add(entry)
                created += 1
    db.commit()
    return {"message": f"Created {created} planned slots for the next 30 days"}
