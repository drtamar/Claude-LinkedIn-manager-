"""Channel adapters, and the registry that hands out the right one.

Only the channels Stage B built are registered. A channel in the subject
matrix but not here reports itself as not yet implemented, which is the
honest answer and keeps `publish` usable while the rest are built.

Note what is *not* imported here: `app.automation.post_publisher`. That is the
old browser-automation path, kept on disk but called by nothing (decision
0.9). A test enforces that mechanically — see tests/test_channels.py.
"""
from __future__ import annotations

from app.channels.base import (  # noqa: F401
    ChannelAdapter,
    Piece,
    PublishResult,
    ValidationIssue,
)
from app.channels.linkedin import LinkedInAdapter
from app.channels.website import WebsiteAdapter
from app.subjects import Channel

# Channels Stage B implements.
ADAPTERS: dict[Channel, type[ChannelAdapter]] = {
    Channel.WEBSITE: WebsiteAdapter,
    Channel.LINKEDIN: LinkedInAdapter,
}

# Named in the subject matrix, not built yet. Listed rather than omitted so
# the gap is visible in `app.cli channels` instead of looking like an error.
PLANNED: dict[Channel, str] = {
    Channel.INSTAGRAM: "Graph API — needs a business/creator account (G2.1)",
    Channel.YOUTUBE: "Data API v3 — upload quota is the real limit (G2.2)",
    Channel.REDDIT: "official API, participation mode only (G2.3)",
    Channel.TIKTOK: "can only stage drafts until the app passes audit (G2.4)",
}


class ChannelNotImplemented(RuntimeError):
    pass


def get_adapter(channel: Channel, **kwargs) -> ChannelAdapter:
    try:
        return ADAPTERS[channel](**kwargs)
    except KeyError:
        reason = PLANNED.get(channel, "not planned")
        raise ChannelNotImplemented(
            f"No adapter for {channel.value} yet: {reason}."
        ) from None


def available_channels() -> list[Channel]:
    return list(ADAPTERS)


def status() -> list[dict]:
    """Every channel in the matrix and whether it can publish right now."""
    rows = []
    for channel in Channel:
        if channel in ADAPTERS:
            rows.append({**get_adapter(channel).describe(), "implemented": True})
        else:
            rows.append({
                "channel": channel.value,
                "implemented": False,
                "configured": False,
                "note": PLANNED.get(channel, "not planned"),
            })
    return rows
