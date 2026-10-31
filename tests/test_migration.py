"""Schema migration and the persistent rate limiter (plan B3.3, B5.4)."""
import sqlite3

import pytest

# The schema as it was before Stage B, so the test proves a real upgrade
# rather than just that CREATE TABLE works.
PRE_STAGE_B = """
CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);
CREATE TABLE posts (
    id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, content TEXT NOT NULL,
    post_type TEXT DEFAULT 'text', hook TEXT, hashtags TEXT, call_to_action TEXT,
    status TEXT DEFAULT 'draft', ai_score INTEGER DEFAULT 0, score_breakdown TEXT,
    generation_prompt_id INTEGER, word_count INTEGER DEFAULT 0,
    estimated_read_time INTEGER DEFAULT 0, scheduled_at DATETIME,
    published_at DATETIME, linkedin_post_id TEXT,
    created_at DATETIME, updated_at DATETIME);
CREATE TABLE content_ideas (
    id INTEGER PRIMARY KEY, user_id INTEGER, topic TEXT, angle TEXT,
    post_type TEXT DEFAULT 'text', hook_options TEXT, content_pillars TEXT,
    status TEXT DEFAULT 'idea', source TEXT DEFAULT 'ai_generated',
    created_at DATETIME);
CREATE TABLE linkedin_profiles (id INTEGER PRIMARY KEY, user_id INTEGER);
"""


@pytest.fixture
def old_database(tmp_path):
    """A pre-Stage-B database holding real rows."""
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(PRE_STAGE_B)
    conn.execute(
        "INSERT INTO posts (id,user_id,content,status,linkedin_post_id)"
        " VALUES (1,1,'A post from before Stage B','published','urn:li:share:999')")
    conn.execute(
        "INSERT INTO content_ideas (id,user_id,topic,status)"
        " VALUES (1,1,'Ticks are early this year','used')")
    conn.commit()
    conn.close()
    return path


def migrate(path) -> None:
    """Run the app's migration list against a specific database file."""
    from sqlalchemy import create_engine, text
    from app.main import COLUMN_MIGRATIONS, _already_applied

    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as conn:
        for statement in COLUMN_MIGRATIONS:
            try:
                conn.execute(text(statement))
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                if not _already_applied(exc):
                    raise
    engine.dispose()


def columns(path, table) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


class TestMigration:
    def test_adds_the_stage_b_columns(self, old_database):
        migrate(old_database)
        assert {"channel", "external_id", "idea_id", "approved_at", "review_tier"} <= \
            columns(old_database, "posts")
        assert {"subject", "research_ref", "bias_score", "bias_rationale",
                "approved_at", "expires_at"} <= columns(old_database, "content_ideas")

    def test_running_twice_is_a_no_op(self, old_database):
        """It runs on every startup, so a second pass must be silent."""
        migrate(old_database)
        migrate(old_database)  # must not raise

    def test_existing_rows_survive(self, old_database):
        migrate(old_database)
        conn = sqlite3.connect(old_database)
        conn.row_factory = sqlite3.Row
        post = conn.execute("SELECT * FROM posts WHERE id=1").fetchone()
        idea = conn.execute("SELECT * FROM content_ideas WHERE id=1").fetchone()
        conn.close()
        assert post["content"] == "A post from before Stage B"
        assert post["status"] == "published"
        assert idea["topic"] == "Ticks are early this year"

    def test_old_posts_are_backfilled_as_linkedin(self, old_database):
        """Everything before Stage B was a LinkedIn post, so the default has
        to say so — otherwise old rows have no channel at all."""
        migrate(old_database)
        conn = sqlite3.connect(old_database)
        channel = conn.execute("SELECT channel FROM posts WHERE id=1").fetchone()[0]
        conn.close()
        assert channel == "linkedin"

    def test_the_linkedin_urn_is_preserved(self, old_database):
        migrate(old_database)
        conn = sqlite3.connect(old_database)
        urn = conn.execute(
            "SELECT linkedin_post_id FROM posts WHERE id=1").fetchone()[0]
        conn.close()
        assert urn == "urn:li:share:999"

    def test_indexes_are_created(self, old_database):
        migrate(old_database)
        conn = sqlite3.connect(old_database)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        conn.close()
        assert {"ix_posts_channel", "ix_posts_idea_id",
                "ix_content_ideas_subject"} <= names

    def test_a_genuinely_broken_statement_is_not_swallowed(self):
        """The old loop caught every exception, so a typo failed silently on
        every startup forever. Only already-applied is ignored now."""
        from app.main import _already_applied
        assert _already_applied(Exception("duplicate column name: channel"))
        assert _already_applied(Exception("index ix_x already exists"))
        assert not _already_applied(Exception("no such table: psots"))
        assert not _already_applied(Exception('near "ALTR": syntax error'))


class TestPersistentRateLimiter:
    """Plan B5.4: these counts used to live in a module-level dict, so the
    "3 posts a day" limit was really "3 per process"."""

    @pytest.fixture(autouse=True)
    def isolated_limiter(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SOCIAL_DESK_LIMITER_DB", str(tmp_path / "limits.db"))

    def test_counts_up_to_the_limit(self):
        from app.automation import safety_limiter as sl
        limit = sl.daily_limit("post_publish")
        for _ in range(limit):
            allowed, _reason = sl.can_perform(1, "post_publish")
            assert allowed
            sl.record_action(1, "post_publish")
        allowed, reason = sl.can_perform(1, "post_publish")
        assert not allowed and "Daily limit reached" in reason

    def test_the_count_survives_a_restart(self):
        import importlib
        from app.automation import safety_limiter as sl

        sl.record_action(1, "post_publish")
        importlib.reload(sl)  # stands in for restarting the app
        assert sl.count_today(1, "post_publish") == 1

    def test_limits_are_per_user_and_per_action(self):
        from app.automation import safety_limiter as sl
        sl.record_action(1, "post_publish")
        assert sl.count_today(2, "post_publish") == 0
        assert sl.count_today(1, "connection_send") == 0

    def test_usage_today_reports_used_against_limit(self):
        from app.automation import safety_limiter as sl
        sl.record_action(1, "post_publish")
        usage = sl.usage_today(1)
        assert usage["post_publish"]["used"] == 1
        assert usage["post_publish"]["limit"] == sl.daily_limit("post_publish")

    def test_get_daily_counts_still_works(self):
        """Kept for the existing automation router. It read the dict that is
        now gone, so it imported fine and raised NameError when called."""
        from app.automation import safety_limiter as sl
        sl.record_action(1, "connection_send")
        counts = sl.get_daily_counts(1)
        assert counts == {"connection_send": 1, "post_publish": 0}

    def test_an_unreadable_store_fails_open(self, monkeypatch):
        """Same tradeoff as the cost cap: locking her out of her own tool over
        an unreadable file is worse than briefly missing a limit."""
        from app.automation import safety_limiter as sl
        monkeypatch.setattr(
            sl, "_connect",
            lambda: (_ for _ in ()).throw(sqlite3.Error("disk I/O error")))
        assert sl.count_today(1, "post_publish") == 0
        allowed, _ = sl.can_perform(1, "post_publish")
        assert allowed
        sl.record_action(1, "post_publish")  # must not raise
