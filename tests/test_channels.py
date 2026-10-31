"""Channel adapters: the base contract, website, LinkedIn (plan B4, B5, B6)."""
import ast
import datetime as _dt
import json
import urllib.error
from pathlib import Path

import pytest

from app.channels import ADAPTERS, ChannelNotImplemented, get_adapter, status
from app.channels.base import ChannelAdapter, Piece, PublishResult
from app.channels.linkedin import MAX_POST_CHARS, LinkedInAdapter
from app.channels.website import WebsiteAdapter, render_article, slugify
from app.subjects import Channel


def piece(**kw) -> Piece:
    base = dict(
        title="Why ticks arrived early this year",
        body="Warm winters shift the season forward.",
        subject="pet_health",
        channel=Channel.WEBSITE,
    )
    base.update(kw)
    return Piece(**base)


# --------------------------------------------------------------------------
# B6.5 — the guard that enforces decision 0.9
# --------------------------------------------------------------------------

class TestBrowserAutomationRetired:
    """Decision 0.9: the browser path stays on disk but nothing calls it.

    This is the test that matters in six months, when nobody remembers why
    those files are there. A comment would not survive a refactor; this does.
    """

    FORBIDDEN = ("post_publisher", "browser_manager", "playwright")

    def _imports_of(self, path: Path) -> set[str]:
        """Module names a file actually imports.

        Parsed rather than grepped: linkedin.py's docstring names the old
        modules in order to explain why it does not use them, and a string
        search cannot tell an explanation from a dependency.
        """
        tree = ast.parse(path.read_text())
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
                names.update(f"{node.module}.{a.name}" for a in node.names)
        return names

    def test_no_channel_adapter_imports_the_browser_path(self):
        channels_dir = Path(__file__).resolve().parents[1] / "backend/app/channels"
        for path in sorted(channels_dir.glob("*.py")):
            imported = " ".join(self._imports_of(path))
            for forbidden in self.FORBIDDEN:
                assert forbidden not in imported, (
                    f"{path.name} imports {forbidden} — LinkedIn publishes "
                    "through the official API now (decision 0.9)"
                )

    def test_nothing_outside_automation_imports_the_browser_path(self):
        """The whole app, not just the channels package. If a router still
        wires it up, the old path is live however good the new one is."""
        app_dir = Path(__file__).resolve().parents[1] / "backend/app"
        offenders = []
        for path in sorted(app_dir.rglob("*.py")):
            if "automation" in path.parts:
                continue  # the old code may refer to itself
            imported = " ".join(self._imports_of(path))
            if any(f in imported for f in self.FORBIDDEN):
                offenders.append(str(path.relative_to(app_dir)))
        assert not offenders, (
            f"these still import the browser-automation path: {offenders}")

    def test_the_linkedin_adapter_passes_no_cookies(self):
        """Checks the executable code, skipping the docstring that explains
        the decision."""
        path = (Path(__file__).resolve().parents[1]
                / "backend/app/channels/linkedin.py")
        tree = ast.parse(path.read_text())
        tree.body = [n for n in tree.body
                     if not (isinstance(n, ast.Expr)
                             and isinstance(n.value, ast.Constant))]
        assert "cookie" not in ast.unparse(tree).lower()

    def test_the_old_code_is_still_on_disk(self):
        """Left in place on purpose, not deleted — so if this fails, someone
        removed it and should check that was intended."""
        automation = Path(__file__).resolve().parents[1] / "backend/app/automation"
        assert (automation / "post_publisher.py").exists()
        assert (automation / "browser_manager.py").exists()


# --------------------------------------------------------------------------
# Base contract
# --------------------------------------------------------------------------

class TestIdempotencyKey:
    def test_identical_content_gives_the_same_key(self):
        assert piece().idempotency_key == piece().idempotency_key

    def test_the_same_text_on_two_channels_differs(self):
        """Otherwise cross-posting would look like a duplicate of itself."""
        assert piece().idempotency_key != piece(channel=Channel.LINKEDIN).idempotency_key

    def test_editing_the_body_gives_a_new_key(self):
        assert piece().idempotency_key != piece(body="Rewritten.").idempotency_key

    def test_the_key_is_not_random(self):
        """A random key would make retries double-post, which is the whole
        thing it exists to prevent."""
        assert len(piece().idempotency_key) == 32
        assert piece().idempotency_key == piece().idempotency_key


class TestBaseValidation:
    def test_a_piece_for_the_wrong_channel_is_blocked(self):
        issues = WebsiteAdapter().validate(piece(channel=Channel.LINKEDIN))
        assert any(i.field == "channel" and i.blocking for i in issues)

    def test_an_empty_body_is_blocked(self):
        issues = WebsiteAdapter().validate(piece(body="   "))
        assert any(i.field == "body" and i.blocking for i in issues)

    def test_check_then_publish_refuses_on_a_blocking_issue(self):
        result = WebsiteAdapter().check_then_publish(piece(body=""))
        assert result.published is False

    def test_an_unconfigured_channel_says_so_rather_than_failing(self):
        result = LinkedInAdapter(access_token="", author_urn="").check_then_publish(
            piece(channel=Channel.LINKEDIN))
        assert result.not_configured is True and result.published is False


# --------------------------------------------------------------------------
# Website adapter
# --------------------------------------------------------------------------

class TestSlugify:
    @pytest.mark.parametrize("raw,expected", [
        ("Why ticks arrived early", "why-ticks-arrived-early"),
        ("Tick-borne disease: what now?", "tick-borne-disease-what-now"),
        ("  spaces   everywhere  ", "spaces-everywhere"),
        ("!!!", "untitled"),
    ])
    def test_slugs(self, raw, expected):
        assert slugify(raw) == expected

    def test_accents_are_transliterated_not_dropped(self):
        """Cyprus means Greek names and accented clinical terms; stripping
        them to nothing would collide filenames."""
        assert slugify("Leishmanióse in Lefkosía") == "leishmaniose-in-lefkosia"


class TestWebsiteFrontMatter:
    def test_subject_becomes_the_magazine_section(self):
        article = render_article(piece(), published=_dt.date(2026, 10, 31))
        assert 'section: "Pet health"' in article
        assert "subject_id: pet_health" in article

    def test_both_section_and_category_are_written(self):
        """Different static-site generators look for different keys."""
        article = render_article(piece())
        assert "section:" in article and "category:" in article

    def test_sources_appear_in_front_matter_and_body(self):
        article = render_article(piece(sources=("https://doi.org/10.1/x",)))
        assert article.count("https://doi.org/10.1/x") == 2
        assert "## Sources" in article

    def test_the_ai_disclosure_is_added_without_being_asked(self):
        assert "AI assistance" in render_article(piece())

    def test_no_disclosure_when_not_ai_assisted(self):
        assert "AI assistance" not in render_article(piece(ai_assisted=False))

    def test_a_quote_in_the_title_does_not_break_the_yaml(self):
        article = render_article(piece(title='The "cure" for ageing'))
        assert 'title: "The \\"cure\\" for ageing"' in article

    def test_the_publish_key_is_recorded(self):
        p = piece()
        assert f"publish_key: {p.idempotency_key}" in render_article(p)


class TestWebsitePublish:
    def test_writes_into_a_folder_per_subject(self, tmp_path):
        adapter = WebsiteAdapter(tmp_path)
        result = adapter.check_then_publish(piece())
        assert result.published
        written = Path(result.location)
        assert written.parent.name == "pet_health"
        assert written.suffix == ".md"

    def test_the_filename_carries_the_date_and_slug(self, tmp_path):
        result = WebsiteAdapter(tmp_path).check_then_publish(piece())
        name = Path(result.location).name
        assert name.startswith(_dt.date.today().isoformat())
        assert "why-ticks-arrived-early-this-year" in name

    def test_republishing_identical_content_is_a_no_op(self, tmp_path):
        """Idempotency (G3.1): a retry must not duplicate or churn the file."""
        adapter = WebsiteAdapter(tmp_path)
        first = adapter.check_then_publish(piece())
        before = Path(first.location).read_text()
        second = adapter.check_then_publish(piece())
        assert second.published and "Already written" in second.detail
        assert Path(first.location).read_text() == before

    def test_it_needs_no_credentials(self):
        """Which is why the website is first: it works before any API setup."""
        assert WebsiteAdapter().is_configured() is True

    def test_missing_sources_warns_but_does_not_block(self):
        issues = WebsiteAdapter().validate(piece(sources=()))
        source_issues = [i for i in issues if i.field == "sources"]
        assert source_issues and not source_issues[0].blocking

    def test_an_unwritable_directory_returns_rather_than_raises(self, tmp_path, monkeypatch):
        """A full disk or a locked folder must not lose the caller's work.

        The failure is injected rather than produced with chmod, because these
        tests may run as root, where file permissions do not apply.
        """
        def no_write(*args, **kwargs):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(Path, "write_text", no_write)
        result = WebsiteAdapter(tmp_path).check_then_publish(piece())
        assert result.published is False
        assert "Could not write" in result.detail
        assert "No space left" in result.detail


# --------------------------------------------------------------------------
# LinkedIn adapter
# --------------------------------------------------------------------------

def li_piece(**kw) -> Piece:
    return piece(channel=Channel.LINKEDIN, subject="vet_news", **kw)


class TestLinkedInPayload:
    def test_it_uses_the_posts_api_shape_not_ugc(self):
        """The ported code targeted /v2/ugcPosts, which LinkedIn replaced with
        the versioned Posts API. The shapes differ: `commentary` and a flat
        `visibility`, where UGC nested text under `specificContent`."""
        payload = LinkedInAdapter("tok", "urn:li:person:A").build_payload(li_piece())
        assert "commentary" in payload
        assert "specificContent" not in payload
        assert payload["visibility"] == "PUBLIC"
        assert payload["distribution"]["feedDistribution"] == "MAIN_FEED"

    def test_the_endpoint_is_the_versioned_one(self):
        from app.channels.linkedin import POSTS_ENDPOINT
        assert POSTS_ENDPOINT.endswith("/rest/posts")
        assert "ugcPosts" not in POSTS_ENDPOINT

    def test_the_author_urn_is_the_configured_one(self):
        payload = LinkedInAdapter("tok", "urn:li:person:XYZ").build_payload(li_piece())
        assert payload["author"] == "urn:li:person:XYZ"

    def test_the_disclosure_is_appended_at_the_api_call(self):
        """Set here, never left to the writer to remember (G3.3)."""
        payload = LinkedInAdapter("tok", "urn:li:person:A").build_payload(li_piece())
        assert "AI assistance" in payload["commentary"]

    def test_headers_carry_the_version_and_the_idempotency_key(self):
        adapter = LinkedInAdapter("tok", "urn:li:person:A")
        p = li_piece()
        headers = adapter._headers(p)
        assert headers["LinkedIn-Version"]
        assert headers["X-RestLi-Request-Id"] == p.idempotency_key
        assert headers["Authorization"] == "Bearer tok"

    def test_the_version_can_be_overridden(self, monkeypatch):
        monkeypatch.setenv("LINKEDIN_API_VERSION", "202999")
        from app.channels import linkedin
        assert linkedin.api_version() == "202999"


class TestLinkedInValidation:
    def test_a_post_over_the_limit_is_blocked(self):
        issues = LinkedInAdapter("t", "u").validate(li_piece(body="x" * (MAX_POST_CHARS + 1)))
        assert any(i.field == "body" and i.blocking for i in issues)

    def test_the_disclosure_length_counts_towards_the_limit(self):
        """A body just under the limit still fails once the disclosure is
        appended — catching it here beats a 422 from the API."""
        body = "x" * (MAX_POST_CHARS - 10)
        issues = LinkedInAdapter("t", "u").validate(li_piece(body=body))
        assert any("AI-disclosure" in i.problem for i in issues)


class TestLinkedInErrors:
    def _fail_with(self, monkeypatch, code: str | int, body: bytes = b"{}"):
        import io
        from app.channels import linkedin

        def boom(*a, **k):
            raise urllib.error.HTTPError(
                linkedin.POSTS_ENDPOINT, code, "err", {}, io.BytesIO(body))

        monkeypatch.setattr(linkedin.urllib.request, "urlopen", boom)
        return LinkedInAdapter("tok", "urn:li:person:A").publish(li_piece())

    def test_401_tells_her_to_reconnect(self, monkeypatch):
        result = self._fail_with(monkeypatch, 401)
        assert not result.published
        assert "connect-linkedin" in result.detail

    def test_403_names_the_missing_permission(self, monkeypatch):
        result = self._fail_with(monkeypatch, 403)
        assert "w_member_social" in result.detail

    def test_a_sunset_version_says_which_setting_to_change(self, monkeypatch):
        result = self._fail_with(monkeypatch, 426)
        assert "LINKEDIN_API_VERSION" in result.detail

    def test_429_says_nothing_was_posted(self, monkeypatch):
        result = self._fail_with(monkeypatch, 429)
        assert "Nothing was posted" in result.detail

    def test_a_network_failure_returns_rather_than_raising(self, monkeypatch):
        from app.channels import linkedin

        def boom(*a, **k):
            raise urllib.error.URLError("no route to host")

        monkeypatch.setattr(linkedin.urllib.request, "urlopen", boom)
        result = LinkedInAdapter("tok", "urn:li:person:A").publish(li_piece())
        assert not result.published and "Nothing was posted" in result.detail


class TestLinkedInSuccess:
    def test_a_successful_post_returns_the_urn_and_a_link(self, monkeypatch):
        from app.channels import linkedin

        class FakeResponse:
            headers = {"x-restli-id": "urn:li:share:12345"}
            def __enter__(self): return self
            def __exit__(self, *a): return False

        captured = {}

        def fake_urlopen(request, timeout=None):
            captured["body"] = json.loads(request.data)
            captured["headers"] = dict(request.headers)
            return FakeResponse()

        monkeypatch.setattr(linkedin.urllib.request, "urlopen", fake_urlopen)
        result = LinkedInAdapter("tok", "urn:li:person:A").check_then_publish(li_piece())

        assert result.published
        assert result.external_id == "urn:li:share:12345"
        assert "urn:li:share:12345" in result.location
        assert captured["body"]["author"] == "urn:li:person:A"


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

class TestRegistry:
    def test_website_and_linkedin_are_built(self):
        assert set(ADAPTERS) == {Channel.WEBSITE, Channel.LINKEDIN}

    def test_an_unbuilt_channel_explains_itself(self):
        with pytest.raises(ChannelNotImplemented, match="quota"):
            get_adapter(Channel.YOUTUBE)

    def test_status_covers_every_channel_in_the_matrix(self):
        rows = status()
        assert {r["channel"] for r in rows} == {c.value for c in Channel}
        assert sum(1 for r in rows if r["implemented"]) == 2

    def test_every_adapter_declares_the_base_contract(self):
        for channel, cls in ADAPTERS.items():
            assert issubclass(cls, ChannelAdapter)
            assert cls.channel is channel


class TestRetiredAutomationEndpoints:
    """The cookie route is gone, but it is gone *loudly* (decision 0.9).

    Tested at the function rather than over HTTP: these endpoints sit behind
    authentication, so a request without a token returns 401 before it ever
    reaches the body under test.
    """

    def test_saving_a_cookie_session_is_refused(self):
        from fastapi import HTTPException
        from app.routers.automation import (OFFICIAL_API_NOTE,
                                            save_linkedin_session)

        with pytest.raises(HTTPException) as exc:
            save_linkedin_session(req=None, db=None, current_user=None)
        assert exc.value.status_code == 410
        assert exc.value.detail == OFFICIAL_API_NOTE

    def test_the_refusal_says_what_to_run_instead(self):
        from app.routers.automation import OFFICIAL_API_NOTE
        assert "connect-linkedin" in OFFICIAL_API_NOTE
        # And why, so the reason outlives this conversation.
        assert "User Agreement" in OFFICIAL_API_NOTE

    async def test_status_reports_on_the_api_not_a_browser_session(self):
        from types import SimpleNamespace
        from app.routers.automation import check_linkedin_status

        user = SimpleNamespace(linkedin_cookies="leftover-encrypted-blob")
        result = await check_linkedin_status(db=None, current_user=user)
        assert result["method"] == "official_api"
        # Surfaces that the old cookies are still stored and unused, so it is
        # visible rather than quietly forgotten.
        assert result["stale_cookies_stored"] is True
