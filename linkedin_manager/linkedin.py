"""LinkedIn publishing adapter.

Posting to LinkedIn uses the official Marketing/UGC API, which requires an
OAuth 2.0 access token with the ``w_member_social`` scope and the author's
member URN. When credentials are not configured, :func:`publish_post` runs in
"local only" mode and simply reports that nothing was sent — so the rest of
the tool is fully usable with zero LinkedIn setup and no ToS risk.

Network calls use the standard library only (``urllib``) to avoid an extra
dependency.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

UGC_ENDPOINT = "https://api.linkedin.com/v2/ugcPosts"


@dataclass
class PublishResult:
    """Outcome of a publish attempt."""

    posted: bool
    detail: str
    post_id: str | None = None


def publish_post(
    text: str,
    *,
    access_token: str | None,
    author_urn: str | None,
    timeout: float = 15.0,
) -> PublishResult:
    """Publish ``text`` as a LinkedIn post, or report local-only mode.

    Returns a :class:`PublishResult` rather than raising for the common
    "not configured" case, so callers can branch cleanly.
    """
    if not access_token or not author_urn:
        return PublishResult(
            posted=False,
            detail=(
                "LinkedIn credentials not configured — running in local-only mode. "
                "Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN to enable posting."
            ),
        )

    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    request = urllib.request.Request(
        UGC_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            post_id = response.headers.get("x-restli-id")
            return PublishResult(
                posted=True, detail="Post published to LinkedIn.", post_id=post_id
            )
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        body = exc.read().decode("utf-8", errors="replace")
        return PublishResult(
            posted=False, detail=f"LinkedIn API error {exc.code}: {body}"
        )
    except urllib.error.URLError as exc:  # pragma: no cover - network path
        return PublishResult(posted=False, detail=f"Network error: {exc.reason}")
