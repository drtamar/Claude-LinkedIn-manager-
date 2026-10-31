import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import engine, Base

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    Base.metadata.create_all(bind=engine)
    # Safe column migrations for existing databases
    _run_column_migrations()
    # Seed default prompt versions
    from app.database import SessionLocal
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


# Columns added after the first release. Each runs once; re-running is a
# no-op because the column already exists. SQLite can only ADD COLUMN, which
# is why every one of these is additive and nullable (or carries a default).
COLUMN_MIGRATIONS = [
    # 2026-05 — skills categorisation
    "ALTER TABLE linkedin_profiles ADD COLUMN skills_categorized_json TEXT",

    # Stage B3 — posts become channel-aware. Existing rows were all LinkedIn,
    # so the default backfills them correctly.
    "ALTER TABLE posts ADD COLUMN channel TEXT DEFAULT 'linkedin'",
    "ALTER TABLE posts ADD COLUMN external_id TEXT",
    "ALTER TABLE posts ADD COLUMN idea_id INTEGER REFERENCES content_ideas(id)",
    "ALTER TABLE posts ADD COLUMN approved_at DATETIME",
    "ALTER TABLE posts ADD COLUMN review_tier TEXT",

    # Stage B3 — ideas gain a subject and research provenance.
    "ALTER TABLE content_ideas ADD COLUMN subject TEXT",
    "ALTER TABLE content_ideas ADD COLUMN research_ref TEXT",
    "ALTER TABLE content_ideas ADD COLUMN bias_score REAL",
    "ALTER TABLE content_ideas ADD COLUMN bias_rationale TEXT",
    "ALTER TABLE content_ideas ADD COLUMN approved_at DATETIME",
    "ALTER TABLE content_ideas ADD COLUMN expires_at DATETIME",

    # Indexes the new columns are queried by. IF NOT EXISTS makes these
    # idempotent on their own.
    "CREATE INDEX IF NOT EXISTS ix_posts_channel ON posts(channel)",
    "CREATE INDEX IF NOT EXISTS ix_posts_idea_id ON posts(idea_id)",
    "CREATE INDEX IF NOT EXISTS ix_content_ideas_subject ON content_ideas(subject)",
    "CREATE INDEX IF NOT EXISTS ix_content_ideas_research_ref ON content_ideas(research_ref)",
]


def _already_applied(error: Exception) -> bool:
    """Is this error just "that column is already there"?

    The previous version of this loop swallowed every exception, so a
    genuinely broken statement would fail silently on every startup forever.
    We still ignore the already-applied case — that is the whole point of a
    re-runnable list — but anything else gets logged.
    """
    message = str(error).lower()
    return (
        "duplicate column name" in message
        or "already exists" in message
    )


def _run_column_migrations() -> None:
    from sqlalchemy import text

    applied, skipped = 0, 0
    with engine.connect() as conn:
        for statement in COLUMN_MIGRATIONS:
            try:
                conn.execute(text(statement))
                conn.commit()
                applied += 1
            except Exception as exc:  # noqa: BLE001 - classified below
                conn.rollback()
                if _already_applied(exc):
                    skipped += 1
                    continue
                logger.error("Migration failed: %s -> %s", statement, exc)
    if applied:
        logger.info("Applied %s column migration(s), %s already present.",
                    applied, skipped)


def _seed_default_prompts(db):
    """Seed initial prompt versions if none exist."""
    from app.models.ai_learning import PromptVersion
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
from app.routers import auth, questionnaire, profile, content, network, analytics, automation, learning, schedule, system

app.include_router(auth.router)
app.include_router(questionnaire.router)
app.include_router(profile.router)
app.include_router(content.router)
app.include_router(network.router)
app.include_router(schedule.router)
app.include_router(analytics.router)
app.include_router(automation.router)
app.include_router(learning.router)
app.include_router(system.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
