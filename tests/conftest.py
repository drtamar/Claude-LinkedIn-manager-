"""Shared test fixtures.

These tests never hit the network: a ``FakeClient`` stands in for the real
Claude client so the feature modules can be tested deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest


@dataclass
class FakeClient:
    """Records the prompts it receives and returns a canned response."""

    response: str = "FAKE RESPONSE"
    calls: list[dict] = field(default_factory=list)

    def complete(self, *, system: str, user: str, max_tokens: int = 4000) -> str:
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        return self.response


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()
