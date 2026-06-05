"""CV generation: produce a polished, ATS-friendly CV in Markdown."""

from __future__ import annotations

from . import prompts


def generate_cv(
    client, background: str, *, target_role: str | None = None, style: str = "standard"
) -> str:
    """Generate a CV in Markdown from free-form background information.

    ``background`` can be anything the user has — an old resume, a LinkedIn
    export, or bullet notes about their experience.
    """
    user = prompts.build_cv_prompt(background, target_role=target_role, style=style)
    return client.complete(system=prompts.CV_SYSTEM, user=user, max_tokens=6000)
