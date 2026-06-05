"""LinkedIn OAuth 2.0 helper.

Walks the 3-legged OAuth flow so a user can obtain the ``access_token`` and
member URN that :mod:`linkedin_manager.linkedin` needs to publish posts —
without copying values by hand.

The flow:
1. Open the browser to LinkedIn's authorization page.
2. Catch the redirect on a short-lived local HTTP server to grab the ``code``.
3. Exchange the code for an access token.
4. Call the OpenID Connect ``userinfo`` endpoint to derive the member URN.

Pure helpers (URL building, request encoding, URN derivation) are kept
separate from the network/browser I/O so they can be unit-tested offline.
Uses the standard library only.
"""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

# Scopes: w_member_social to post; openid+profile to read the member id via
# the OpenID Connect userinfo endpoint.
DEFAULT_SCOPES = ("openid", "profile", "w_member_social")


@dataclass
class TokenResult:
    """Result of a completed OAuth flow."""

    access_token: str
    author_urn: str
    expires_in: int | None = None


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
    state: str,
) -> str:
    """Build the LinkedIn authorization URL the user visits to grant access."""
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def encode_token_request(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> bytes:
    """Encode the form body for the access-token exchange request."""
    return urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")


def author_urn_from_userinfo(userinfo: dict) -> str:
    """Derive the member URN (``urn:li:person:<id>``) from a userinfo payload.

    The OpenID Connect ``userinfo`` response carries the member id in ``sub``.
    """
    sub = userinfo.get("sub")
    if not sub:
        raise RuntimeError(
            "LinkedIn userinfo response did not include a 'sub' (member id). "
            "Ensure the 'openid' and 'profile' scopes were granted."
        )
    return f"urn:li:person:{sub}"


def new_state() -> str:
    """Generate an opaque CSRF state token for the authorization request."""
    return secrets.token_urlsafe(16)


def exchange_code_for_token(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    timeout: float = 15.0,
) -> dict:  # pragma: no cover - network path
    """POST the authorization code and return the parsed token response."""
    body = encode_token_request(
        code=code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Token exchange failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error during token exchange: {exc.reason}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Invalid JSON in token response: {exc}") from exc


def fetch_userinfo(
    access_token: str, *, timeout: float = 15.0
) -> dict:  # pragma: no cover - network path
    """Call the userinfo endpoint with the bearer token."""
    request = urllib.request.Request(
        USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"userinfo request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error during userinfo: {exc.reason}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Invalid JSON in userinfo response: {exc}") from exc


def run_flow(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
    open_browser: bool = True,
    timeout_seconds: int = 300,
) -> TokenResult:  # pragma: no cover - browser + network path
    """Run the full interactive OAuth flow and return tokens.

    Starts a local HTTP server bound to the host/port of ``redirect_uri`` to
    catch the redirect, opens the browser to the authorization page, then
    exchanges the returned code for a token and derives the member URN.
    """
    import http.server
    import threading
    import webbrowser

    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80
    expected_path = parsed.path or "/"
    state = new_state()

    captured: dict[str, str] = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
            request = urllib.parse.urlparse(self.path)
            if request.path != expected_path:
                self.send_response(404)
                self.end_headers()
                return
            params = urllib.parse.parse_qs(request.query)
            captured["code"] = params.get("code", [""])[0]
            captured["state"] = params.get("state", [""])[0]
            captured["error"] = params.get("error", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>You can close this tab and return to the "
                b"terminal.</h2></body></html>"
            )
            done.set()

        def log_message(self, *args) -> None:  # silence default logging
            pass

    try:
        server = http.server.HTTPServer((host, port), Handler)
    except OSError as exc:
        raise RuntimeError(
            f"Failed to start local callback server on {host}:{port}: {exc}. "
            "Make sure the port is free and you have permission to bind to it."
        ) from exc
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    auth_url = build_authorization_url(
        client_id=client_id, redirect_uri=redirect_uri, scopes=scopes, state=state
    )
    print("Opening LinkedIn authorization in your browser...")
    print(f"If it doesn't open, visit:\n{auth_url}\n")
    if open_browser:
        webbrowser.open(auth_url)

    try:
        if not done.wait(timeout=timeout_seconds):
            raise RuntimeError("Timed out waiting for the LinkedIn redirect.")
    finally:
        server.shutdown()
        server.server_close()

    if captured.get("error"):
        raise RuntimeError(f"Authorization denied: {captured['error']}")
    if captured.get("state") != state:
        raise RuntimeError("State mismatch — possible CSRF; aborting.")
    code = captured.get("code")
    if not code:
        raise RuntimeError("No authorization code returned by LinkedIn.")

    token = exchange_code_for_token(
        code=code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    access_token = token.get("access_token")
    if not access_token:
        raise RuntimeError(f"No access_token in token response: {token}")

    userinfo = fetch_userinfo(access_token)
    return TokenResult(
        access_token=access_token,
        author_urn=author_urn_from_userinfo(userinfo),
        expires_in=token.get("expires_in"),
    )
