"""Engagement helpers: comments, replies, and connection-request notes."""

from __future__ import annotations

from . import prompts


def draft_comment(client, post_text: str, *, intent: str = "add insight") -> str:
    """Write a comment in reply to someone else's post."""
    user = prompts.build_comment_prompt(post_text, intent=intent)
    return client.complete(system=prompts.ENGAGEMENT_SYSTEM, user=user, max_tokens=600)


def draft_connection_note(
    client, recipient: str, *, reason: str, sender_context: str | None = None
) -> str:
    """Write a short connection-request note (kept under 300 characters)."""
    user = prompts.build_connection_note_prompt(
        recipient, reason=reason, sender_context=sender_context
    )
    return client.complete(system=prompts.ENGAGEMENT_SYSTEM, user=user, max_tokens=400)
