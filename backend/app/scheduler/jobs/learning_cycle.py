import asyncio
from app.database import SessionLocal
from app.models.user import User
from app.services.learning_service import run_learning_cycle


async def run_weekly_cycle():
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_active == True).all()
        for user in users:
            try:
                await run_learning_cycle(db, user.id)
            except Exception as e:
                print(f"Learning cycle failed for user {user.id}: {e}")
    finally:
        db.close()
