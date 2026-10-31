"""One interface every channel implements (plan B4.1).

Publishing is mechanical and has exactly one correct outcome, so adapters are
plain code — no model calls, no judgement (plan G3). An adapter's job is to
take an already-approved piece, check it fits the channel, and send it.

Two conventions hold across every adapter:

* **Return, don't raise, for the expected cases.** "Not configured yet" and
  "too long for this channel" are normal states in a system that is set up one
  channel at a time, and a caller publishing to five channels should not lose
  four of them to one exception.
* **Idempotency is the adapter's problem** (G3.1). Each publish carries a key
  derived from the content, so a retry after a timeout cannot double-post.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.subjects import Channel, self_promotion_allowed


@dataclass(frozen=True)
class Piece:
    """What gets published: one rendition of one approved idea.

    Deliberately not the `Post` ORM object. Adapters take a plain value so
    they can be tested without a database, and so a dry run can build one
    without writing a row.
    """

    title: str
    body: str
    subject: str
    channel: Channel
    # DOI or canonical URL of what this is based on. The critic requires at
    # least one for anything making a research claim.
    sources: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    # Set when the piece was AI-drafted, which is almost always. Adapters put
    # it in the payload rather than trusting anyone to remember (G3.3).
    ai_assisted: bool = True
    # Links back to ContentIdea.id once persisted; None during a dry run.
    idea_id: int | None = None

    @property
    def idempotency_key(self) -> str:
        """Stable key for this exact content on this exact channel.

        Content-derived rather than random, so a retry of the same publish
        produces the same key and the channel (or our own records) can reject
        the duplicate. Editing the text intentionally produces a new key.
        """
        digest = hashlib.sha256(
            f"{self.channel.value}\x00{self.subject}\x00{self.title}\x00{self.body}"
            .encode("utf-8")
        ).hexdigest()
        return digest[:32]


@dataclass
class PublishResult:
    """Outcome of one publish attempt."""

    published: bool
    detail: str
    # The channel's own id for the published item, when it gave one.
    external_id: str | None = None
    # Where it landed, for channels that produce a file or a URL.
    location: str | None = None
    # True when nothing was sent because the channel is not set up. Distinct
    # from a failure: it needs configuration, not a retry.
    not_configured: bool = False
    # True when the adapter can only stage a draft, not publish (TikTok).
    draft_only: bool = False


@dataclass
class ValidationIssue:
    field: str
    problem: str
    # blocking issues stop a publish; warnings are reported and allowed.
    blocking: bool = True


class ChannelAdapter(ABC):
    """Base for every channel."""

    channel: Channel
    # Hard limits the channel enforces. None means no limit we need to apply.
    max_body_chars: int | None = None
    max_title_chars: int | None = None
    # False for channels whose API cannot publish for us yet, only stage a
    # draft — TikTok until an app passes audit.
    can_publish: bool = True
    # Whether the channel requires its own disclosure of AI assistance.
    requires_ai_disclosure: bool = False

    @abstractmethod
    def is_configured(self) -> bool:
        """Can this adapter actually send something right now?"""

    @abstractmethod
    def publish(self, piece: Piece) -> PublishResult:
        """Send the piece. Must not raise for an expected failure."""

    def validate(self, piece: Piece) -> list[ValidationIssue]:
        """Channel-independent checks. Subclasses extend rather than replace.

        These are mechanical limits only — register, claim fidelity and
        clinical risk are the critic's job in Stage E, upstream of here.
        """
        issues: list[ValidationIssue] = []

        if piece.channel is not self.channel:
            issues.append(ValidationIssue(
                "channel",
                f"piece is for {piece.channel.value}, this adapter is "
                f"{self.channel.value}",
            ))
        if not piece.body.strip():
            issues.append(ValidationIssue("body", "empty"))
        if self.max_body_chars and len(piece.body) > self.max_body_chars:
            issues.append(ValidationIssue(
                "body",
                f"{len(piece.body)} characters exceeds the "
                f"{self.max_body_chars} this channel allows",
            ))
        if self.max_title_chars and len(piece.title) > self.max_title_chars:
            issues.append(ValidationIssue(
                "title",
                f"{len(piece.title)} characters exceeds "
                f"{self.max_title_chars}",
            ))
        if not self_promotion_allowed(self.channel) and piece.tags:
            # A tag list on Reddit reads as marketing. The real enforcement is
            # the critic's; this catches the mechanical case.
            issues.append(ValidationIssue(
                "tags",
                f"{self.channel.value} treats promotional tagging badly — "
                "post the substance, not the labels",
                blocking=False,
            ))
        return issues

    def check_then_publish(self, piece: Piece) -> PublishResult:
        """The entry point callers should use.

        Validates first and refuses on a blocking issue, so a publish either
        happens cleanly or explains itself.
        """
        if not self.is_configured():
            return PublishResult(
                published=False,
                detail=f"{self.channel.value} is not configured yet.",
                not_configured=True,
            )

        issues = self.validate(piece)
        blocking = [i for i in issues if i.blocking]
        if blocking:
            return PublishResult(
                published=False,
                detail="; ".join(f"{i.field}: {i.problem}" for i in blocking),
            )
        return self.publish(piece)

    def describe(self) -> dict:
        return {
            "channel": self.channel.value,
            "configured": self.is_configured(),
            "can_publish": self.can_publish,
            "max_body_chars": self.max_body_chars,
            "requires_ai_disclosure": self.requires_ai_disclosure,
            "self_promotion_allowed": self_promotion_allowed(self.channel),
        }
