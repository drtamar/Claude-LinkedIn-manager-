import anthropic
from typing import AsyncIterator
from app.config import get_settings

settings = get_settings()
_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


async def stream_response(
    prompt: str,
    system: str = "",
    model: str = "claude-opus-4-8",
    max_tokens: int = 4096,
) -> AsyncIterator[str]:
    client = get_client()
    messages = [{"role": "user", "content": prompt}]
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system

    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            yield text


async def complete(
    prompt: str,
    system: str = "",
    model: str = "claude-opus-4-8",
    max_tokens: int = 4096,
) -> str:
    client = get_client()
    messages = [{"role": "user", "content": prompt}]
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    return response.content[0].text
