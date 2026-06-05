"""Thin wrapper around the Anthropic Claude API.

Centralizes how every feature talks to Claude so prompt construction,
streaming, and error handling live in one place. The ``anthropic`` import is
lazy so unit tests can run (and the package can import) without the SDK
installed or an API key present.
"""

from __future__ import annotations

from typing import Protocol


class _Completer(Protocol):
    """Minimal interface the feature modules depend on.

    Anything matching this shape (the real client or a test double) can be
    passed to the content/profile/cv/engagement helpers.
    """

    def complete(self, *, system: str, user: str, max_tokens: int = ...) -> str: ...


class ClaudeClient:
    """Generates text completions with Claude.

    Parameters
    ----------
    api_key:
        Anthropic API key.
    model:
        Model id, e.g. ``claude-opus-4-8``.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        # Import lazily: keeps `import linkedin_manager` working without the
        # SDK installed, and avoids constructing a client until it's needed.
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, *, system: str, user: str, max_tokens: int = 4000) -> str:
        """Return Claude's text response to a single user prompt.

        Uses streaming with ``get_final_message`` so large outputs don't hit
        request timeouts, then concatenates the text blocks of the reply.

        Wraps SDK failures (bad key, rate limit, network) in a
        :class:`RuntimeError` so the CLI prints a clean message instead of a
        raw traceback.
        """
        import anthropic

        try:
            with self._client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as stream:
                message = stream.get_final_message()
        except anthropic.AnthropicError as exc:
            raise RuntimeError(f"Anthropic API error: {exc}") from exc

        return "".join(
            block.text for block in message.content if block.type == "text"
        ).strip()

    @classmethod
    def from_config(cls, config) -> "ClaudeClient":
        """Build a client from a :class:`~linkedin_manager.config.Config`."""
        return cls(api_key=config.require_api_key(), model=config.model)
