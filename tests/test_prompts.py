"""Tests for prompt builders (pure string construction, no API)."""

from __future__ import annotations

from linkedin_manager import prompts


def test_build_post_prompt_includes_topic_and_tone():
    out = prompts.build_post_prompt("AI in healthcare", tone="bold")
    assert "AI in healthcare" in out
    assert "Tone: bold" in out


def test_build_post_prompt_optional_fields():
    out = prompts.build_post_prompt(
        "remote work", audience="engineering managers", notes="cite the 2024 study"
    )
    assert "engineering managers" in out
    assert "cite the 2024 study" in out


def test_build_connection_note_prompt_mentions_limit():
    out = prompts.build_connection_note_prompt("Jane", reason="we met at PyCon")
    assert "Jane" in out
    assert "300 characters" in out


def test_build_profile_prompt_includes_role():
    out = prompts.build_profile_prompt("headline text", target_role="Data Scientist")
    assert "Data Scientist" in out
    assert "headline text" in out


def test_tones_nonempty():
    assert "professional" in prompts.TONES
