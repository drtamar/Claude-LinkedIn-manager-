from app.database import SessionLocal
from app.models.user import User
from app.models.ai_learning import AutomationJob
import json


async def run_daily_scrape():
    db = SessionLocal()
    try:
        users = db.query(User).filter(
            User.is_active == True,
            User.linkedin_connected == True,
        ).all()
        for user in users:
            job = AutomationJob(
                user_id=user.id,
                job_type="analytics_scrape",
                payload=json.dumps({"scheduled": True}),
            )
            db.add(job)
        db.commit()
    finally:
        db.close()
