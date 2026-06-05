"""Tests for the feature modules using a fake client."""

from __future__ import annotations

from linkedin_manager import content, cv, engagement, profile, prompts


def test_draft_post_uses_post_system_and_returns_text(fake_client):
    fake_client.response = "My great post"
    out = content.draft_post(fake_client, "shipping faster", tone="conversational")
    assert out == "My great post"
    call = fake_client.calls[0]
    assert call["system"] == prompts.POST_SYSTEM
    assert "shipping faster" in call["user"]
    assert "conversational" in call["user"]


def test_draft_comment(fake_client):
    out = engagement.draft_comment(fake_client, "Some interesting post", intent="ask")
    assert out == fake_client.response
    assert fake_client.calls[0]["system"] == prompts.ENGAGEMENT_SYSTEM
    assert "Some interesting post" in fake_client.calls[0]["user"]


def test_draft_connection_note(fake_client):
    engagement.draft_connection_note(
        fake_client, "Alex", reason="shared interest in MLOps"
    )
    assert "Alex" in fake_client.calls[0]["user"]
    assert "MLOps" in fake_client.calls[0]["user"]


def test_optimize_profile(fake_client):
    profile.optimize_profile(fake_client, "My headline", target_role="PM")
    assert fake_client.calls[0]["system"] == prompts.PROFILE_SYSTEM
    assert "PM" in fake_client.calls[0]["user"]


def test_generate_cv(fake_client):
    cv.generate_cv(fake_client, "10 years of backend work", target_role="Staff Engineer")
    assert fake_client.calls[0]["system"] == prompts.CV_SYSTEM
    assert "Staff Engineer" in fake_client.calls[0]["user"]
