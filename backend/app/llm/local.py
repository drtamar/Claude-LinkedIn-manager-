"""Local model access via Ollama (plan A1.3).

Deliberately stdlib-only: urllib rather than httpx, so this module adds
nothing to install. Ollama exposes a plain HTTP API on localhost, which needs
no client library.

Calls here are free and offline. Everything that routes through this module
instead of the cloud is money not spent (plan A2.2).
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_HOST = "http://127.0.0.1:11434"

# Ollama has to load the model into memory on the first call after a pull or a
# restart, which on CPU can take a while. The health check stays snappy.
HEALTH_TIMEOUT_SECONDS = 2
GENERATE_TIMEOUT_SECONDS = 300

INSTALL_HINT = (
    "Ollama is not running. Install it from https://ollama.com/download "
    "(Windows installer, no admin rights needed), then run "
    "`ollama pull {model}` once. The app works without it, but every triage "
    "call then costs money instead of being free."
)


class LocalModelUnavailable(RuntimeError):
    """Ollama is not installed, not running, or lacks the requested model."""


def _unreachable(exc: Exception) -> "LocalModelUnavailable":
    """Turn a transport failure into something actionable.

    A bare `<urlopen error [Errno 111] Connection refused>` tells a
    non-developer nothing, and this message ends up in the UI as the reason a
    task fell back to a paid model. The wording matches Router.plan() so the
    predicted and actual reasons read the same.
    """
    return LocalModelUnavailable(
        f"Ollama is not running at {host()} ({exc}). "
        "Start it, or install it from https://ollama.com/download."
    )


@dataclass(frozen=True)
class LocalResult:
    text: str
    model: str
    # Ollama reports these; useful for spotting a model that is swapping to
    # disk, which is the usual reason local triage feels broken.
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    duration_seconds: float | None = None


def host() -> str:
    return os.environ.get("OLLAMA_HOST", DEFAULT_HOST).rstrip("/")


def _post(path: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        f"{host()}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise LocalModelUnavailable(
            f"Ollama returned HTTP {exc.code}. {detail}".strip()
        ) from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise _unreachable(exc) from exc
    except json.JSONDecodeError as exc:
        raise LocalModelUnavailable(f"Ollama sent a malformed reply: {exc}") from exc


def _get(path: str, timeout: int) -> dict:
    try:
        with urllib.request.urlopen(f"{host()}{path}", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise LocalModelUnavailable(f"Ollama sent a malformed reply: {exc}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise _unreachable(exc) from exc


def is_available() -> bool:
    """Is Ollama reachable right now? Never raises."""
    try:
        _get("/api/tags", HEALTH_TIMEOUT_SECONDS)
        return True
    except LocalModelUnavailable:
        return False


def list_models() -> list[str]:
    """Model tags already pulled on this machine. Empty if Ollama is down."""
    try:
        data = _get("/api/tags", HEALTH_TIMEOUT_SECONDS)
    except LocalModelUnavailable:
        return []
    out = []
    for entry in data.get("models") or []:
        name = entry.get("name") or entry.get("model")
        if name:
            out.append(name)
    return out


def has_model(model: str) -> bool:
    """True if `model` is pulled. Matches `qwen2.5:14b` against `qwen2.5` too,
    because Ollama reports the full tag but people type the bare name."""
    available = list_models()
    if model in available:
        return True
    bare = model.split(":")[0]
    return any(tag.split(":")[0] == bare for tag in available)


def complete(
    prompt: str,
    *,
    system: str = "",
    model: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
    json_mode: bool = False,
) -> LocalResult:
    """One blocking local generation.

    `json_mode` asks Ollama to constrain output to valid JSON, which is what
    makes a small model usable for triage and scoring: it removes the "sure!
    here is the JSON:" preamble that otherwise has to be stripped.
    """
    options: dict = {}
    if max_tokens is not None:
        options["num_predict"] = max_tokens
    if temperature is not None:
        options["temperature"] = temperature

    payload: dict = {"model": model, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    if options:
        payload["options"] = options
    if json_mode:
        payload["format"] = "json"

    data = _post("/api/generate", payload, GENERATE_TIMEOUT_SECONDS)

    text = (data.get("response") or "").strip()
    if not text:
        raise LocalModelUnavailable(
            f"Local model {model} returned nothing. If it was just pulled, the "
            "first call can time out while it loads — try again."
        )

    nanos = data.get("total_duration")
    return LocalResult(
        text=text,
        model=model,
        prompt_tokens=data.get("prompt_eval_count"),
        output_tokens=data.get("eval_count"),
        duration_seconds=round(nanos / 1e9, 2) if nanos else None,
    )


async def acomplete(prompt: str, **kwargs) -> LocalResult:
    """Async wrapper. Ollama's API is synchronous and a CPU generation can run
    for minutes, so it goes to a thread rather than blocking the event loop."""
    return await asyncio.to_thread(complete, prompt, **kwargs)


def status(expected_model: str | None = None) -> dict:
    """Shaped for the doctor command."""
    running = is_available()
    models = list_models() if running else []
    ready = bool(running and expected_model and has_model(expected_model))

    detail: str
    if not running:
        detail = INSTALL_HINT.format(model=expected_model or "llama3.2:3b")
    elif expected_model and not ready:
        detail = (
            f"Ollama is running but {expected_model} is not pulled. "
            f"Run: ollama pull {expected_model}"
        )
    else:
        detail = f"Ollama running at {host()} with {len(models)} model(s)."

    return {
        "running": running,
        "host": host(),
        "models": models,
        "expected_model": expected_model,
        "ready": ready,
        "detail": detail,
    }
