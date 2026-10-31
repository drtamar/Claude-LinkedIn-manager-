"""LinkedIn OAuth 2.0, ported from PR #3 (plan B5.1).

Ported rather than rewritten: the version on branch
`claude/linkedin-oauth-helper` is stdlib-only, keeps the pure helpers separate
from network I/O so they can be tested offline, and already verifies the CSRF
state. All of that is kept. What changed in the port is the module it lives in
and the error messages, which now name the CLI command that fixes them.

Flow: open the browser to LinkedIn's consent page, catch the redirect on a
short-lived local server, exchange the code for a token, then read the member
URN from the OpenID Connect userinfo endpoint.
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

# w_member_social is the permission to post on behalf of the authenticated
# member; openid + profile are what make the userinfo endpoint return the
# member id we need as the author URN.
DEFAULT_SCOPES = ("openid", "profile", "w_member_social")


class LinkedInAuthError(RuntimeError):
    """Any failure in the OAuth flow."""


@dataclass(frozen=True)
class TokenResult:
    access_token: str
    author_urn: str
    expires_in: int | None = None

    @property
    def expires_in_days(self) -> int | None:
        """LinkedIn member tokens last about 60 days, and there is no refresh
        token on the self-serve product — so this gets re-run periodically."""
        return round(self.expires_in / 86400) if self.expires_in else None


def new_state() -> str:
    """Opaque CSRF state for the authorization request."""
    return secrets.token_urlsafe(16)


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
) -> str:
    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "state": state,
    })
    return f"{AUTHORIZE_URL}?{query}"


def encode_token_request(
    *, code: str, client_id: str, client_secret: str, redirect_uri: str
) -> bytes:
    return urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }).encode("utf-8")


def author_urn_from_userinfo(userinfo: dict) -> str:
    """Derive `urn:li:person:<id>` from a userinfo payload."""
    sub = userinfo.get("sub")
    if not sub:
        raise LinkedInAuthError(
            "LinkedIn's userinfo response had no 'sub' (member id). The "
            "'openid' and 'profile' scopes have to be granted — check the "
            "products enabled on your app at developer.linkedin.com."
        )
    return f"urn:li:person:{sub}"


def verify_state(expected: str, received: str | None) -> None:
    """Reject a redirect whose state does not match the one we sent."""
    if not received or not secrets.compare_digest(expected, received):
        raise LinkedInAuthError(
            "The state parameter did not match, which can mean the redirect "
            "was forged. Nothing was saved; run the command again."
        )


def exchange_code_for_token(
    *, code: str, client_id: str, client_secret: str, redirect_uri: str,
    timeout: float = 15.0,
) -> dict:  # pragma: no cover - network path
    body = encode_token_request(
        code=code, client_id=client_id, client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    request = urllib.request.Request(
        TOKEN_URL, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LinkedInAuthError(
            f"Token exchange failed ({exc.code}): {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise LinkedInAuthError(f"Network error during token exchange: {exc.reason}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise LinkedInAuthError(f"Token response was not valid JSON: {exc}") from exc


def fetch_userinfo(
    access_token: str, *, timeout: float = 15.0
) -> dict:  # pragma: no cover - network path
    request = urllib.request.Request(
        USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LinkedInAuthError(f"userinfo request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise LinkedInAuthError(f"Network error during userinfo: {exc.reason}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise LinkedInAuthError(f"userinfo response was not valid JSON: {exc}") from exc


def run_flow(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
    open_browser: bool = True,
    timeout_seconds: int = 300,
) -> TokenResult:  # pragma: no cover - browser + network path
    """Run the interactive flow once and return the token and author URN."""
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
        def do_GET(self) -> None:  # noqa: N802 - stdlib naming
            request = urllib.parse.urlparse(self.path)
            if request.path != expected_path:
                self.send_response(404)
                self.end_headers()
                return
            params = urllib.parse.parse_qs(request.query)
            captured["code"] = params.get("code", [""])[0]
            captured["state"] = params.get("state", [""])[0]
            captured["error"] = params.get("error", [""])[0]
            captured["error_description"] = params.get("error_description", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body style='font-family:sans-serif;padding:3rem'>"
                b"<h2>Connected.</h2><p>You can close this tab and go back to "
                b"the terminal.</p></body></html>"
            )
            done.set()

        def log_message(self, *args) -> None:
            pass  # the default logger writes to stderr on every request

    try:
        server = http.server.HTTPServer((host, port), Handler)
    except OSError as exc:
        raise LinkedInAuthError(
            f"Could not start the local callback server on {host}:{port}: {exc}. "
            f"Something else may be using port {port}. The redirect URI in your "
            "LinkedIn app settings has to match this address exactly."
        ) from exc

    threading.Thread(target=server.serve_forever, daemon=True).start()

    auth_url = build_authorization_url(
        client_id=client_id, redirect_uri=redirect_uri, state=state, scopes=scopes)
    print("Opening LinkedIn in your browser to ask for permission...")
    print(f"If it does not open, paste this into your browser:\n\n{auth_url}\n")
    if open_browser:
        webbrowser.open(auth_url)

    try:
        if not done.wait(timeout=timeout_seconds):
            raise LinkedInAuthError(
                f"Gave up after {timeout_seconds // 60} minutes with no reply "
                "from LinkedIn. Nothing was saved; run the command again."
            )
    finally:
        server.shutdown()
        server.server_close()

    if captured.get("error"):
        raise LinkedInAuthError(
            f"LinkedIn declined: {captured['error']}"
            + (f" — {captured['error_description']}"
               if captured.get("error_description") else "")
        )
    verify_state(state, captured.get("state"))

    code = captured.get("code")
    if not code:
        raise LinkedInAuthError("LinkedIn returned no authorization code.")

    token = exchange_code_for_token(
        code=code, client_id=client_id, client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    access_token = token.get("access_token")
    if not access_token:
        raise LinkedInAuthError(f"No access_token in the token response: {token}")

    return TokenResult(
        access_token=access_token,
        author_urn=author_urn_from_userinfo(fetch_userinfo(access_token)),
        expires_in=token.get("expires_in"),
    )
