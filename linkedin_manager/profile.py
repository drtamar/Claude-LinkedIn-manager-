"""Profile optimization: analyze profile text and return improvements."""

from __future__ import annotations

from . import prompts


def optimize_profile(client, profile_text: str, *, target_role: str | None = None) -> str:
    """Return prioritized, concrete suggestions to improve a LinkedIn profile.

    ``profile_text`` is the raw text the user copies from their profile
    (headline, About, experience). The result is Markdown.
    """
    user = prompts.build_profile_prompt(profile_text, target_role=target_role)
    return client.complete(system=prompts.PROFILE_SYSTEM, user=user, max_tokens=4000)
