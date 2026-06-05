"""Configuration loading for the LinkedIn manager.

Reads settings from environment variables (and a local ``.env`` file when
``python-dotenv`` is installed). Keeping all environment access in one place
makes the rest of the package easy to test and reason about.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Default Claude model. Opus 4.8 is the most capable model; override via
# LINKEDIN_MANAGER_MODEL if you want a cheaper/faster option (e.g.
# claude-sonnet-4-6 or claude-haiku-4-5).
DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_OUTPUT_DIR = "./output"


def _load_dotenv() -> None:
    """Load a local .env file if python-dotenv is available.

    The dependency is optional so the package still imports in minimal
    environments (e.g. CI running unit tests with env vars set directly).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


@dataclass
class Config:
    """Resolved runtime configuration.

    Use :meth:`from_env` to build one from the environment rather than
    constructing directly, so a ``.env`` file is honored.
    """

    api_key: str | None
    model: str = DEFAULT_MODEL
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    linkedin_access_token: str | None = None
    linkedin_author_urn: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        """Build a Config from environment variables (loading .env first)."""
        _load_dotenv()
        output_dir = os.environ.get("LINKEDIN_MANAGER_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)
        return cls(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            model=os.environ.get("LINKEDIN_MANAGER_MODEL", DEFAULT_MODEL),
            output_dir=Path(output_dir),
            linkedin_access_token=os.environ.get("LINKEDIN_ACCESS_TOKEN") or None,
            linkedin_author_urn=os.environ.get("LINKEDIN_AUTHOR_URN") or None,
        )

    def require_api_key(self) -> str:
        """Return the API key or raise a clear error if it is missing."""
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add "
                "your key, or export ANTHROPIC_API_KEY in your shell."
            )
        return self.api_key

    @property
    def can_post_to_linkedin(self) -> bool:
        """True when credentials for the LinkedIn API are configured."""
        return bool(self.linkedin_access_token and self.linkedin_author_urn)
