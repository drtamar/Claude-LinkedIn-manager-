import anthropic
from typing import AsyncIterator
from app.config import get_settings

settings = get_settings()
_client: anthropic.AsyncAnthropic | None = None


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


async def stream_response(
    prompt: str,
    system: str = "",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
) -> AsyncIterator[str]:
    client = get_client()
    messages = [{"role": "user", "content": prompt}]
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system

    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield text


async def complete(
    prompt: str,
    system: str = "",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
) -> str:
    client = get_client()
    messages = [{"role": "user", "content": prompt}]
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system

    response = await client.messages.create(**kwargs)
    return response.content[0].text
