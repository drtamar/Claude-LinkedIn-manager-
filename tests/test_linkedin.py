"""Tests for the LinkedIn adapter's local-only fallback (no network)."""

from __future__ import annotations

from linkedin_manager import linkedin


def test_local_only_when_no_credentials():
    result = linkedin.publish_post("hi", access_token=None, author_urn=None)
    assert result.posted is False
    assert "local-only" in result.detail


def test_local_only_when_partial_credentials():
    result = linkedin.publish_post("hi", access_token="tok", author_urn=None)
    assert result.posted is False
