"""Tests for OAuth pure helpers (no network, no browser)."""

from __future__ import annotations

import urllib.parse

import pytest

from linkedin_manager import oauth


def test_build_authorization_url_contains_params():
    url = oauth.build_authorization_url(
        client_id="cid",
        redirect_uri="http://localhost:8000/callback",
        state="xyz",
    )
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    assert parsed.netloc == "www.linkedin.com"
    assert params["client_id"] == ["cid"]
    assert params["response_type"] == ["code"]
    assert params["state"] == ["xyz"]
    assert "w_member_social" in params["scope"][0]


def test_encode_token_request_includes_grant_type():
    body = oauth.encode_token_request(
        code="abc", client_id="cid", client_secret="sec", redirect_uri="http://x/cb"
    )
    decoded = urllib.parse.parse_qs(body.decode("utf-8"))
    assert decoded["grant_type"] == ["authorization_code"]
    assert decoded["code"] == ["abc"]
    assert decoded["client_secret"] == ["sec"]


def test_author_urn_from_userinfo():
    assert oauth.author_urn_from_userinfo({"sub": "AbC123"}) == "urn:li:person:AbC123"


def test_author_urn_from_userinfo_missing_sub_raises():
    with pytest.raises(RuntimeError, match="member id"):
        oauth.author_urn_from_userinfo({})


def test_new_state_is_unique():
    assert oauth.new_state() != oauth.new_state()
