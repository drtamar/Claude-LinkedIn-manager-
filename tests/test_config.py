"""Tests for configuration loading."""

from __future__ import annotations

import pytest

from linkedin_manager.config import DEFAULT_MODEL, Config


def test_from_env_defaults(monkeypatch):
    for key in (
        "ANTHROPIC_API_KEY",
        "LINKEDIN_MANAGER_MODEL",
        "LINKEDIN_MANAGER_OUTPUT_DIR",
        "LINKEDIN_ACCESS_TOKEN",
        "LINKEDIN_AUTHOR_URN",
    ):
        monkeypatch.delenv(key, raising=False)

    config = Config.from_env()
    assert config.model == DEFAULT_MODEL
    assert config.api_key is None
    assert config.can_post_to_linkedin is False


def test_from_env_reads_values(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("LINKEDIN_MANAGER_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("LINKEDIN_AUTHOR_URN", "urn:li:person:123")

    config = Config.from_env()
    assert config.api_key == "sk-test"
    assert config.model == "claude-sonnet-4-6"
    assert config.can_post_to_linkedin is True


def test_require_api_key_raises_when_missing():
    config = Config(api_key=None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        config.require_api_key()


def test_require_api_key_returns_key():
    config = Config(api_key="sk-test")
    assert config.require_api_key() == "sk-test"
