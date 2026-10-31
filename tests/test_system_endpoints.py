"""The endpoints that make spend visible (plan A3.2)."""
import pytest
from fastapi.testclient import TestClient

from app.llm import cost


@pytest.fixture
def client(monkeypatch, tmp_path):
    """A test client over just the system router.

    The full app is not mounted: its lifespan creates database tables and
    starts a scheduler, neither of which these endpoints touch.
    """
    from fastapi import FastAPI
    from app.routers import system

    monkeypatch.setattr(system, "_router_cache", None)
    app = FastAPI()
    app.include_router(system.router)
    return TestClient(app)


class TestCostEndpoint:
    def test_reports_an_empty_month_without_erroring(self, client):
        body = client.get("/api/system/cost").json()
        assert body["total_usd"] == 0 and body["ledger_error"] is None

    def test_breaks_spend_down_by_stage(self, client):
        cost.record("content.post", "claude-opus-4-8",
                    cost.Usage(input_tokens=5_000, output_tokens=800))
        cost.record("triage", "claude-haiku-5-5", cost.Usage(input_tokens=2_000))
        body = client.get("/api/system/cost").json()
        assert set(body["by_stage"]) == {"content.post", "triage"}
        assert body["calls"] == 2

    def test_rejects_a_malformed_month(self, client):
        assert client.get("/api/system/cost?month=October").status_code == 422

    def test_accepts_a_past_month(self, client):
        assert client.get("/api/system/cost?month=2026-01").json()["month"] == "2026-01"

    def test_says_percent_used_and_remaining(self, client, monkeypatch):
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "1.00")
        cost.record("draft", "claude-opus-5-5",
                    cost.Usage(input_tokens=50_000, output_tokens=5_000))
        body = client.get("/api/system/cost").json()
        assert body["percent_used"] > 0
        assert body["remaining_usd"] == pytest.approx(1.0 - body["total_usd"])


class TestEstimateEndpoint:
    def test_prices_a_call_without_making_it(self, client):
        body = client.get(
            "/api/system/cost/estimate",
            params={"input_tokens": 10_000, "output_tokens": 2_000},
        ).json()
        assert body["estimated_usd"] == pytest.approx(0.08)
        assert cost.month_to_date()["calls"] == 0

    def test_flags_a_call_that_would_breach_the_cap(self, client):
        body = client.get(
            "/api/system/cost/estimate",
            params={"input_tokens": 5_000_000, "output_tokens": 500_000},
        ).json()
        assert body["would_exceed_cap"] is True

    def test_requires_input_tokens(self, client):
        assert client.get("/api/system/cost/estimate").status_code == 422

    def test_rejects_negative_tokens(self, client):
        assert client.get(
            "/api/system/cost/estimate", params={"input_tokens": -5}
        ).status_code == 422


class TestRoutesEndpoint:
    def test_lists_every_step_with_its_destination(self, client):
        from app.llm.router import TaskKind
        body = client.get("/api/system/routes").json()
        assert len(body["routes"]) == len(TaskKind)
        assert body["free_steps"] + body["paid_steps"] <= len(TaskKind)

    def test_surfaces_active_fallbacks(self, client, no_local_model):
        """Without Ollama, bulk steps fall back to a paid model, and the
        endpoint has to say so rather than quietly reporting 'cloud'."""
        body = client.get("/api/system/routes").json()
        tasks = {f["task"] for f in body["fallbacks_active"]}
        assert "triage" in tasks

    def test_spends_nothing(self, client):
        client.get("/api/system/routes")
        assert cost.month_to_date()["calls"] == 0


class TestDoctorEndpoint:
    def test_returns_checks_each_with_a_fix_or_none(self, client):
        body = client.get("/api/system/doctor").json()
        names = {c["name"] for c in body["checks"]}
        assert names == {"Anthropic API key", "Local model (Ollama)",
                         "Spending cap", "Cost ledger", "Publishing channels"}
        for check in body["checks"]:
            if not check["ok"] and check.get("severity") != "warning":
                assert check["fix"], f"{check['name']} failed with no fix text"

    def test_a_missing_ollama_is_a_warning_not_a_failure(self, client, no_local_model):
        """The router falls back to a cheap paid model, so it still works."""
        body = client.get("/api/system/doctor").json()
        ollama = next(c for c in body["checks"] if "Ollama" in c["name"])
        assert ollama["ok"] is False and ollama["severity"] == "warning"

    def test_a_missing_api_key_is_blocking(self, client, monkeypatch):
        from app.routers import system
        monkeypatch.setattr(system.settings, "anthropic_api_key", "")
        body = client.get("/api/system/doctor").json()
        assert body["ok"] is False

    def test_the_api_key_is_never_echoed(self, client, monkeypatch):
        """This endpoint is unauthenticated, so the key must not leave it."""
        from app.routers import system
        secret = "sk-ant-api03-SUPERSECRETVALUE12345"
        monkeypatch.setattr(system.settings, "anthropic_api_key", secret)
        raw = client.get("/api/system/doctor").text
        assert secret not in raw
        assert "SUPERSECRET" not in raw

    def test_a_valid_key_reports_ok_masked(self, client, monkeypatch):
        from app.routers import system
        monkeypatch.setattr(
            system.settings, "anthropic_api_key", "sk-ant-api03-abcdefghij1234")
        check = next(c for c in client.get("/api/system/doctor").json()["checks"]
                     if c["name"] == "Anthropic API key")
        assert check["ok"] is True and "…" in check["detail"]

    def test_a_spent_cap_is_reported_as_blocking(self, client, monkeypatch):
        from app.routers import system
        monkeypatch.setattr(
            system.settings, "anthropic_api_key", "sk-ant-api03-abcdefghij1234")
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "0.01")
        cost.record("draft", "claude-opus-5-5",
                    cost.Usage(input_tokens=500_000, output_tokens=50_000))
        body = client.get("/api/system/doctor").json()
        assert body["ok"] is False
        cap = next(c for c in body["checks"] if c["name"] == "Spending cap")
        assert cap["ok"] is False and "SOCIAL_DESK_MONTHLY_CAP_USD" in cap["fix"]


class TestDoctorChannels:
    """Stage B added a channels check: "can I actually publish?" is the
    question the doctor exists to answer."""

    def test_the_website_is_always_ready(self, client):
        """It writes a file, so it needs no credentials — which is why the
        roadmap puts the website first."""
        body = client.get("/api/system/doctor").json()
        check = next(c for c in body["checks"] if c["name"] == "Publishing channels")
        assert check["ok"] is True
        assert "website" in check["detail"]

    def test_an_unconfigured_linkedin_is_a_warning_not_a_failure(self, client):
        body = client.get("/api/system/doctor").json()
        check = next(c for c in body["checks"] if c["name"] == "Publishing channels")
        assert check["severity"] == "warning"
        assert "connect-linkedin" in (check["fix"] or "")

    def test_doctor_lists_the_channels_and_subjects(self, client):
        body = client.get("/api/system/doctor").json()
        assert len(body["channels"]) == 6
        assert len(body["subjects"]) == 4


class TestSubjectsEndpoint:
    def test_returns_the_matrix(self, client):
        body = client.get("/api/system/subjects").json()
        assert len(body["subjects"]) == 4
        assert body["no_self_promotion"] == ["reddit"]

    def test_every_subject_states_its_rationale(self, client):
        for subject in client.get("/api/system/subjects").json()["subjects"]:
            assert subject["rationale"]


class TestChannelsEndpoint:
    def test_separates_ready_from_planned(self, client):
        body = client.get("/api/system/channels").json()
        assert "website" in body["ready"]
        assert set(body["planned"]) == {"instagram", "youtube", "reddit", "tiktok"}

    def test_spends_nothing(self, client):
        client.get("/api/system/channels")
        assert cost.month_to_date()["calls"] == 0
