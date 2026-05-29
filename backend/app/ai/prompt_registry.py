from sqlalchemy.orm import Session
from app.models.ai_learning import PromptVersion
from app.database import SessionLocal
import threading

_cache: dict[str, PromptVersion] = {}
_lock = threading.Lock()


def get_active(module: str, db: Session | None = None) -> PromptVersion | None:
    with _lock:
        if module in _cache:
            return _cache[module]

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        pv = db.query(PromptVersion).filter(
            PromptVersion.module == module,
            PromptVersion.is_active == True
        ).order_by(PromptVersion.version.desc()).first()

        if pv:
            with _lock:
                _cache[module] = pv
        return pv
    finally:
        if close_db:
            db.close()


def invalidate_cache(module: str):
    with _lock:
        _cache.pop(module, None)


def invalidate_all():
    with _lock:
        _cache.clear()
