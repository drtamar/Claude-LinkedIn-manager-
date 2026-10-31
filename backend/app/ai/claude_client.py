import logging
from typing import AsyncIterator

import anthropic

from app.config import get_settings
from app.llm import cost

logger = logging.getLogger(__name__)

settings = get_settings()
_client: anthropic.AsyncAnthropic | None = None

# Model that writes anything a person will read.
DEFAULT_MODEL = "claude-opus-5-5"

# Above this many max_tokens, or whenever thinking is on, use streaming so a
# slow generation cannot hit the SDK's HTTP timeout.
STREAM_THRESHOLD_TOKENS = 4096


class MissingAPIKeyError(Exception):
    """Raised when the Anthropic API key is not configured."""
    pass


def _validate_key() -> str:
    key = (settings.anthropic_api_key or "").strip()
    if not key or not key.startswith("sk-ant-") or "PUT-YOUR-KEY" in key or key == "sk-ant-api03-...":
        raise MissingAPIKeyError(
            "Anthropic API key is not set. Open the .env file in the project root, "
            "set ANTHROPIC_API_KEY to your real key from https://console.anthropic.com, "
            "then restart the backend."
        )
    return key


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        key = _validate_key()
        _client = anthropic.AsyncAnthropic(api_key=key)
    return _client


def _system_blocks(system: str) -> list[dict]:
    """System prompt as a cacheable block (plan A3.5).

    The profile and subject brief repeat on every single call, so they are the
    obvious caching target. Note the API silently declines to cache a prefix
    below its minimum (512-4096 tokens depending on model) — so this is free
    when the prompt is short and pays off as the profile grows. Check
    `usage.cache_read_input_tokens` to see whether it actually cached.
    """
    return [{
        "type": "text",
        "text": system,
        "cache_control": {"type": "ephemeral"},
    }]


def _text_from(response) -> str:
    """Join the text blocks of a response.

    Must not be `response.content[0].text`: with thinking enabled the first
    block is a thinking block, and indexing position 0 would return the wrong
    thing or raise.
    """
    parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]
    return "".join(parts).strip()


def _build_kwargs(
    prompt: str,
    system: str,
    model: str,
    max_tokens: int,
    effort: str | None,
    thinking: bool,
) -> dict:
    """Assemble a request body.

    Deliberately omitted: `budget_tokens` (removed — a 400 on current models),
    `temperature`/`top_p`/`top_k` (rejected from API version 2026-10-21), and
    assistant prefill (a 400 on current models).
    """
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = _system_blocks(system)
    if thinking:
        # Adaptive is the only on-mode on current models; the model decides
        # how much to think rather than us setting a token budget.
        kwargs["thinking"] = {"type": "adaptive"}
    if effort:
        # Inside output_config, not top-level. Set explicitly because Opus 5.5
        # defaults to "medium".
        kwargs["output_config"] = {"effort": effort}
    return kwargs


async def complete_metered(
    prompt: str,
    *,
    system: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    effort: str | None = None,
    thinking: bool = False,
    stage: str = "unattributed",
    note: str | None = None,
) -> tuple[str, float]:
    """One paid call: cap checked before, cost recorded after.

    Returns (text, dollars_spent). This is the only function in the app that
    talks to the Messages API; `complete` and `stream_response` go through it
    so no call can bypass the meter.
    """
    cost.check_cap()
    client = get_client()
    kwargs = _build_kwargs(prompt, system, model, max_tokens, effort, thinking)

    use_stream = thinking or max_tokens > STREAM_THRESHOLD_TOKENS
    if use_stream:
        async with client.messages.stream(**kwargs) as stream:
            response = await stream.get_final_message()
    else:
        response = await client.messages.create(**kwargs)

    # Record before parsing: the money is spent either way, and a parse
    # failure must not also lose the ledger entry.
    spent = cost.record(stage, model, cost.Usage.from_response(response), note=note)

    stop = getattr(response, "stop_reason", None)
    if stop == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        raise RuntimeError(
            f"The model declined this request (category: {category or 'unspecified'}). "
            "Rephrasing usually resolves it."
        )
    if stop == "max_tokens":
        logger.warning(
            "Stage %s hit the %s token ceiling; output is truncated.",
            stage, max_tokens,
        )

    return _text_from(response), spent


async def complete(
    prompt: str,
    system: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    stage: str = "unattributed",
) -> str:
    """Backwards-compatible single call. Metered and capped."""
    text, _ = await complete_metered(
        prompt, system=system, model=model, max_tokens=max_tokens, stage=stage
    )
    return text


async def stream_response(
    prompt: str,
    system: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    stage: str = "unattributed",
) -> AsyncIterator[str]:
    """Stream text to the UI, then record what the call cost.

    The cap is checked up front; the ledger entry is written in `finally` so a
    reader that disconnects mid-stream still gets billed correctly.
    """
    cost.check_cap()
    client = get_client()
    kwargs = _build_kwargs(prompt, system, model, max_tokens, None, False)

    response = None
    try:
        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
            response = await stream.get_final_message()
    finally:
        if response is not None:
            cost.record(stage, model, cost.Usage.from_response(response))
