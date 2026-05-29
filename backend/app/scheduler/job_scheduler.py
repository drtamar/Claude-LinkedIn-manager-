from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        jobstores = {
            "default": SQLAlchemyJobStore(url="sqlite:///./data/linkedin_manager.db")
        }
        _scheduler = AsyncIOScheduler(jobstores=jobstores)
    return _scheduler


def start_scheduler():
    scheduler = get_scheduler()
    if not scheduler.running:
        # Weekly learning cycle — Sunday 3 AM
        scheduler.add_job(
            "app.scheduler.jobs.learning_cycle:run_weekly_cycle",
            trigger="cron",
            day_of_week="sun",
            hour=3,
            minute=0,
            id="weekly_learning_cycle",
            replace_existing=True,
        )
        # Daily analytics scrape — 6 AM
        scheduler.add_job(
            "app.scheduler.jobs.scrape_analytics:run_daily_scrape",
            trigger="cron",
            hour=6,
            minute=0,
            id="daily_analytics_scrape",
            replace_existing=True,
        )
        scheduler.start()


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
