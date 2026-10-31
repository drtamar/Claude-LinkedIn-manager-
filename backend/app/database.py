from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

# Anchor on the backend package, never the current directory. A Windows
# shortcut launches from System32, so a relative "data/" would put the
# database somewhere surprising — or fail to create it at all. This is the
# same anchoring the cost ledger uses, so both land in backend/data/.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def resolve_database_url(url: str) -> str:
    """Make a relative SQLite path absolute, relative to the backend package.

    Non-SQLite URLs and already-absolute paths are returned untouched. For the
    normal case — running from backend/ — this resolves to the same file as
    before, so an existing database is still found.
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    path_part = url[len(prefix) :]
    if not path_part or path_part.startswith("/"):
        return url  # in-memory, or already absolute
    resolved = (BACKEND_ROOT / path_part.lstrip("./")).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{resolved}"


DATABASE_URL = resolve_database_url(settings.database_url)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    # Off unless explicitly asked for. It used to follow ENVIRONMENT, which
    # .env.example sets to "development" — so every ordinary run printed every
    # SQL statement, and a real error scrolled past unnoticed. Set
    # SQL_ECHO=true when you actually want to watch the queries.
    echo=settings.sql_echo,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
