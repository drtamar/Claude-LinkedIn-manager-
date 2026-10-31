"""Shared fixtures. Every test here is offline: no API calls, no Ollama."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """Point the cost ledger at a throwaway file.

    Autouse and unconditional: a test that accidentally wrote to the real
    ledger would corrupt actual spending records.
    """
    monkeypatch.setenv("SOCIAL_DESK_COST_DB", str(tmp_path / "costs.db"))
    monkeypatch.delenv("SOCIAL_DESK_MONTHLY_CAP_USD", raising=False)
    monkeypatch.delenv("SOCIAL_DESK_LOCAL_MODEL", raising=False)
    yield


@pytest.fixture
def no_local_model(monkeypatch):
    """Ollama absent — the state on a machine that has not installed it."""
    from app.llm import local
    monkeypatch.setattr(local, "is_available", lambda: False)
    monkeypatch.setattr(local, "list_models", lambda: [])


@pytest.fixture
def working_local_model(monkeypatch):
    """Ollama present and answering."""
    from app.llm import local

    monkeypatch.setattr(local, "is_available", lambda: True)
    monkeypatch.setattr(local, "list_models", lambda: ["qwen2.5:14b", "llama3.2:3b"])

    async def fake_acomplete(prompt, **kwargs):
        return local.LocalResult(
            text='{"subject": "pet_health", "relevance": 0.81}',
            model=kwargs.get("model", "llama3.2:3b"),
            prompt_tokens=120,
            output_tokens=18,
            duration_seconds=1.4,
        )

    monkeypatch.setattr(local, "acomplete", fake_acomplete)


def make_response(
    text: str = "drafted text",
    *,
    input_tokens: int = 1_000,
    output_tokens: int = 200,
    cache_read: int = 0,
    cache_write: int = 0,
    stop_reason: str = "end_turn",
    with_thinking_block: bool = False,
    stop_details=None,
):
    """A stand-in for an Anthropic Message.

    `with_thinking_block` puts a thinking block at content[0], which is what
    the real API returns when thinking is on — the case that breaks naive
    `content[0].text` extraction.
    """
    content = []
    if with_thinking_block:
        content.append(SimpleNamespace(type="thinking", thinking="reasoning..."))
    content.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        stop_details=stop_details,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
        ),
    )


@pytest.fixture
def fake_cloud(monkeypatch):
    """Replace the paid call with a recorder.

    Returns the list of calls made, so a test can assert on model, effort and
    stage without spending anything.
    """
    from app.ai import claude_client
    calls: list[dict] = []

    async def fake_complete_metered(prompt, **kwargs):
        from app.llm import cost
        calls.append({"prompt": prompt, **kwargs})
        model = kwargs.get("model", "claude-opus-5-5")
        spent = cost.record(
            kwargs.get("stage", "unattributed"),
            model,
            cost.Usage(input_tokens=1_000, output_tokens=200),
        )
        return f"cloud reply for {kwargs.get('stage')}", spent

    monkeypatch.setattr(claude_client, "complete_metered", fake_complete_metered)
    return calls
