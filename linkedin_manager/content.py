"""Post drafting: turn a topic and a few options into a LinkedIn post."""

from __future__ import annotations

from . import prompts


def draft_post(
    client,
    topic: str,
    *,
    tone: str = "professional",
    audience: str | None = None,
    length: str = "medium",
    notes: str | None = None,
) -> str:
    """Generate a single LinkedIn post draft.

    Parameters
    ----------
    client:
        Anything implementing ``complete(system=, user=, max_tokens=)``
        (a :class:`~linkedin_manager.claude_client.ClaudeClient` or a test
        double).
    topic:
        What the post should be about.
    tone:
        One of :data:`linkedin_manager.prompts.TONES`.
    audience, length, notes:
        Optional steering for the draft.
    """
    user = prompts.build_post_prompt(
        topic, tone=tone, audience=audience, length=length, notes=notes
    )
    return client.complete(system=prompts.POST_SYSTEM, user=user, max_tokens=1500)
