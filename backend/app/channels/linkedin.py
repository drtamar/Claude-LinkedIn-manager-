"""LinkedIn adapter using the official Posts API (plan B5.2).

This replaces the browser-automation path in `app/automation/post_publisher.py`,
which drove linkedin.com with stored session cookies, typed character by
character with randomised delays and watched for CAPTCHAs. That is automated
access under LinkedIn's User Agreement, and the usual outcome is a permanent
restriction on the account. Nothing here touches a browser or a cookie.

**Endpoint note.** The code this was ported from used `/v2/ugcPosts`. LinkedIn
has replaced that with the versioned Posts API at `/rest/posts`, which is what
is used below. The Posts API requires a monthly `LinkedIn-Version` header; it
is configurable because it needs bumping periodically, and an unsupported
value is one of the few errors here that is not self-explanatory.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from app.channels.base import ChannelAdapter, Piece, PublishResult, ValidationIssue
from app.config import get_settings
from app.subjects import Channel

POSTS_ENDPOINT = "https://api.linkedin.com/rest/posts"

# LinkedIn versions its REST API by month and rejects versions it has sunset.
# Override with LINKEDIN_API_VERSION when this stops being accepted — the
# error message below says so explicitly.
DEFAULT_API_VERSION = "202506"

# LinkedIn's own ceiling for post text. Exceeding it is a 422, so we catch it
# in validate() and explain it rather than letting the API refuse.
MAX_POST_CHARS = 3000

AI_DISCLOSURE_SUFFIX = "\n\n— Drafted with AI assistance, reviewed before posting."


def api_version() -> str:
    return os.environ.get("LINKEDIN_API_VERSION", "").strip() or DEFAULT_API_VERSION


class LinkedInAdapter(ChannelAdapter):
    channel = Channel.LINKEDIN
    max_body_chars = MAX_POST_CHARS
    requires_ai_disclosure = True

    def __init__(
        self,
        access_token: str | None = None,
        author_urn: str | None = None,
        *,
        timeout: float = 15.0,
    ):
        settings = get_settings()
        self.access_token = access_token or (settings.linkedin_access_token or "").strip()
        self.author_urn = author_urn or (settings.linkedin_author_urn or "").strip()
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.access_token and self.author_urn)

    def validate(self, piece: Piece) -> list[ValidationIssue]:
        issues = super().validate(piece)
        # The disclosure suffix is appended at publish time, so its length has
        # to fit too — otherwise a piece that validates here fails at the API.
        if len(self._body_with_disclosure(piece)) > MAX_POST_CHARS:
            issues.append(ValidationIssue(
                "body",
                f"with the AI-disclosure line appended this reaches "
                f"{len(self._body_with_disclosure(piece))} characters, over "
                f"LinkedIn's {MAX_POST_CHARS} limit",
            ))
        return issues

    def _body_with_disclosure(self, piece: Piece) -> str:
        """Append the disclosure here rather than relying on the writer.

        Set at the point of the API call, never left to memory (plan G3.3).
        """
        if not piece.ai_assisted:
            return piece.body
        return piece.body.rstrip() + AI_DISCLOSURE_SUFFIX

    def build_payload(self, piece: Piece) -> dict:
        """Posts API body. Note this is not the UGC shape — `commentary` and a
        flat `visibility`, where UGC nested text under `specificContent`."""
        return {
            "author": self.author_urn,
            "commentary": self._body_with_disclosure(piece),
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

    def _headers(self, piece: Piece) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": api_version(),
            # Content-derived, so a retry after a timeout cannot double-post
            # (plan G3.1).
            "X-RestLi-Request-Id": piece.idempotency_key,
        }

    def publish(self, piece: Piece) -> PublishResult:
        request = urllib.request.Request(
            POSTS_ENDPOINT,
            data=json.dumps(self.build_payload(piece)).encode("utf-8"),
            method="POST",
            headers=self._headers(piece),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                post_id = (
                    response.headers.get("x-restli-id")
                    or response.headers.get("x-linkedin-id")
                )
                return PublishResult(
                    published=True,
                    detail="Posted to LinkedIn.",
                    external_id=post_id,
                    location=(
                        f"https://www.linkedin.com/feed/update/{post_id}/"
                        if post_id else None
                    ),
                )
        except urllib.error.HTTPError as exc:
            return PublishResult(published=False, detail=self._explain(exc))
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return PublishResult(
                published=False,
                detail=f"Could not reach LinkedIn: {exc}. Nothing was posted.",
            )

    def _explain(self, exc: urllib.error.HTTPError) -> str:
        """Turn an HTTP error into something that says what to do next."""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            body = ""

        if exc.code == 401:
            return (
                "LinkedIn rejected the access token. Member tokens expire after "
                "about 60 days and cannot be refreshed on the self-serve "
                "product — run `python -m app.cli connect-linkedin` again."
            )
        if exc.code == 403:
            return (
                "LinkedIn refused the request as not permitted. The app needs "
                "the 'Share on LinkedIn' product enabled and the "
                "w_member_social scope granted. "
                f"Response: {body}"
            )
        if exc.code == 426 or "version" in body.lower():
            return (
                f"LinkedIn rejected API version {api_version()}, which it "
                "sunsets periodically. Set LINKEDIN_API_VERSION in .env to a "
                f"current YYYYMM value. Response: {body}"
            )
        if exc.code == 429:
            return (
                "LinkedIn rate-limited the request. Nothing was posted; try "
                f"again later. Response: {body}"
            )
        return f"LinkedIn API error {exc.code}: {body}"
