from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import engine, Base

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    Base.metadata.create_all(bind=engine)
    # Seed default prompt versions
    from app.database import SessionLocal
    from app.models.ai_learning import PromptVersion
    db = SessionLocal()
    try:
        _seed_default_prompts(db)
    finally:
        db.close()
    # Start scheduler
    from app.scheduler.job_scheduler import start_scheduler
    start_scheduler()
    yield
    from app.scheduler.job_scheduler import stop_scheduler
    stop_scheduler()


def _seed_default_prompts(db):
    """Seed initial prompt versions if none exist."""
    from app.ai.modules.content_ai import POST_WRITER_SYSTEM
    from app.ai.modules.profile_ai import HEADLINE_SYSTEM, ABOUT_SYSTEM

    defaults = [
        {
            "module": "content.post_writer",
            "prompt_template": "Topic: {{ topic }}\nHook: {{ hook }}\nUser profile: {{ profile_json }}\n\nWrite a LinkedIn post.",
            "system_message": POST_WRITER_SYSTEM,
            "model": "claude-opus-4-8",
        },
        {
            "module": "profile.headline",
            "prompt_template": "User profile: {{ profile_json }}\n\nGenerate 3 LinkedIn headline variants.",
            "system_message": HEADLINE_SYSTEM,
            "model": "claude-opus-4-8",
        },
        {
            "module": "profile.about",
            "prompt_template": "User profile: {{ profile_json }}\n\nWrite LinkedIn About section.",
            "system_message": ABOUT_SYSTEM,
            "model": "claude-opus-4-8",
        },
    ]
    for d in defaults:
        exists = db.query(PromptVersion).filter(
            PromptVersion.module == d["module"],
            PromptVersion.is_active == True,
        ).first()
        if not exists:
            pv = PromptVersion(**d, version=1, is_active=True)
            db.add(pv)
    db.commit()


app = FastAPI(
    title="LinkedIn Manager",
    description="AI-powered LinkedIn management with self-learning capabilities",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
from app.routers import auth, questionnaire, profile, content, network, analytics, automation, learning, schedule

app.include_router(auth.router)
app.include_router(questionnaire.router)
app.include_router(profile.router)
app.include_router(content.router)
app.include_router(network.router)
app.include_router(schedule.router)
app.include_router(analytics.router)
app.include_router(automation.router)
app.include_router(learning.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
