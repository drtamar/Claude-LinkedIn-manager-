"""The paid-call wrapper: text extraction, metering, and request shape."""
from types import SimpleNamespace

import pytest

from app.ai import claude_client
from app.llm import cost
from tests.conftest import make_response


class FakeStream:
    """Stands in for client.messages.stream(...) — an async context manager."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_final_message(self):
        return self._response

    @property
    def text_stream(self):
        async def gen():
            for block in self._response.content:
                if getattr(block, "type", None) == "text":
                    for word in block.text.split():
                        yield word + " "
        return gen()


class FakeMessages:
    def __init__(self, response):
        self._response = response
        self.create_calls: list[dict] = []
        self.stream_calls: list[dict] = []

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._response

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        return FakeStream(self._response)


@pytest.fixture
def fake_api(monkeypatch):
    """Install a fake Anthropic client; return a setter for the response."""
    holder = {}

    def install(response):
        messages = FakeMessages(response)
        monkeypatch.setattr(
            claude_client, "get_client",
            lambda: SimpleNamespace(messages=messages),
        )
        holder["messages"] = messages
        return messages

    install(make_response())
    return SimpleNamespace(install=install, current=lambda: holder["messages"])


class TestTextExtraction:
    async def test_skips_the_thinking_block(self, fake_api):
        """With thinking on, content[0] is a thinking block. Indexing position
        zero — as the previous version did — returns reasoning or raises."""
        fake_api.install(make_response("the real answer", with_thinking_block=True))
        text, _ = await claude_client.complete_metered("hi", thinking=True)
        assert text == "the real answer"

    async def test_joins_multiple_text_blocks(self, fake_api):
        """Citations split a reply across several text blocks."""
        response = make_response()
        response.content = [
            SimpleNamespace(type="text", text="first half. "),
            SimpleNamespace(type="text", text="second half."),
        ]
        fake_api.install(response)
        text, _ = await claude_client.complete_metered("hi")
        assert text == "first half. second half."

    async def test_a_reply_with_no_text_block_is_empty_not_an_error(self, fake_api):
        response = make_response()
        response.content = [SimpleNamespace(type="thinking", thinking="...")]
        fake_api.install(response)
        text, _ = await claude_client.complete_metered("hi", thinking=True)
        assert text == ""


class TestRequestShape:
    async def test_system_prompt_is_sent_as_a_cacheable_block(self, fake_api):
        messages = fake_api.install(make_response())
        await claude_client.complete_metered("hi", system="you are a vet")
        sent = messages.create_calls[0]["system"]
        assert sent[0]["cache_control"] == {"type": "ephemeral"}
        assert sent[0]["text"] == "you are a vet"

    async def test_effort_goes_inside_output_config(self, fake_api):
        messages = fake_api.install(make_response())
        await claude_client.complete_metered("hi", effort="high")
        assert messages.create_calls[0]["output_config"] == {"effort": "high"}

    async def test_thinking_is_adaptive_with_no_token_budget(self, fake_api):
        """budget_tokens is rejected on current models."""
        messages = fake_api.install(make_response(with_thinking_block=True))
        await claude_client.complete_metered("hi", thinking=True)
        sent = messages.stream_calls[0]
        assert sent["thinking"] == {"type": "adaptive"}
        assert "budget_tokens" not in sent

    async def test_no_sampling_parameters_are_sent(self, fake_api):
        """temperature / top_p / top_k are rejected from API version 2026-10-21."""
        messages = fake_api.install(make_response())
        await claude_client.complete_metered("hi")
        sent = messages.create_calls[0]
        assert not {"temperature", "top_p", "top_k"} & set(sent)

    async def test_thinking_requests_stream(self, fake_api):
        """A thinking call can run long enough to hit the HTTP timeout."""
        messages = fake_api.install(make_response(with_thinking_block=True))
        await claude_client.complete_metered("hi", thinking=True)
        assert messages.stream_calls and not messages.create_calls

    async def test_large_max_tokens_streams(self, fake_api):
        messages = fake_api.install(make_response())
        await claude_client.complete_metered("hi", max_tokens=8192)
        assert messages.stream_calls and not messages.create_calls

    async def test_small_plain_request_does_not_stream(self, fake_api):
        messages = fake_api.install(make_response())
        await claude_client.complete_metered("hi", max_tokens=256)
        assert messages.create_calls and not messages.stream_calls


class TestMetering:
    async def test_every_call_lands_in_the_ledger(self, fake_api):
        fake_api.install(make_response(input_tokens=10_000, output_tokens=2_000))
        _, spent = await claude_client.complete_metered(
            "hi", model="claude-opus-5-5", stage="draft")
        assert spent == pytest.approx(0.08)
        assert cost.month_to_date()["by_stage"]["draft"]["calls"] == 1

    async def test_the_legacy_complete_helper_is_also_metered(self, fake_api):
        """Seven existing AI modules call complete(); none may bypass the meter."""
        fake_api.install(make_response())
        await claude_client.complete("hi", stage="content")
        assert cost.month_to_date()["by_stage"]["content"]["calls"] == 1

    async def test_cap_is_checked_before_the_request_is_made(self, fake_api, monkeypatch):
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "0.01")
        cost.record("draft", "claude-opus-5-5",
                    cost.Usage(input_tokens=500_000, output_tokens=50_000))
        messages = fake_api.install(make_response())
        with pytest.raises(cost.CapExceeded):
            await claude_client.complete_metered("hi")
        assert not messages.create_calls, "no request may be sent once capped"

    async def test_streaming_records_cost_after_the_stream_closes(self, fake_api):
        fake_api.install(make_response("alpha beta gamma", input_tokens=4_000))
        chunks = [c async for c in claude_client.stream_response("hi", stage="post")]
        assert "".join(chunks).strip() == "alpha beta gamma"
        assert cost.month_to_date()["by_stage"]["post"]["calls"] == 1

    async def test_cost_is_recorded_even_when_a_reader_disconnects(self, fake_api):
        """The call is billed by the API whether or not the UI stayed open."""
        fake_api.install(make_response("alpha beta gamma"))
        stream = claude_client.stream_response("hi", stage="post")
        await stream.__anext__()
        await stream.aclose()
        # Generator closed early: the finally block must still have run if the
        # final message was reached, and must not raise either way.
        assert cost.month_to_date()["ledger_error"] is None

    async def test_unattributed_is_the_default_stage(self, fake_api):
        """So an un-tagged call shows up in the breakdown rather than hiding."""
        fake_api.install(make_response())
        await claude_client.complete_metered("hi")
        assert "unattributed" in cost.month_to_date()["by_stage"]


class TestStopReasons:
    async def test_a_refusal_raises_with_its_category(self, fake_api):
        fake_api.install(make_response(
            stop_reason="refusal",
            stop_details=SimpleNamespace(type="refusal", category="bio"),
        ))
        with pytest.raises(RuntimeError, match="bio"):
            await claude_client.complete_metered("hi")

    async def test_a_refusal_is_still_billed(self, fake_api):
        """A refusal is an HTTP 200 and is charged for, so it must be logged."""
        fake_api.install(make_response(
            stop_reason="refusal",
            stop_details=SimpleNamespace(type="refusal", category="bio"),
        ))
        with pytest.raises(RuntimeError):
            await claude_client.complete_metered("hi", stage="critic")
        assert cost.month_to_date()["by_stage"]["critic"]["calls"] == 1

    async def test_truncation_warns_but_returns_what_there_is(self, fake_api, caplog):
        fake_api.install(make_response("cut off mid-", stop_reason="max_tokens"))
        text, _ = await claude_client.complete_metered("hi", stage="draft")
        assert text == "cut off mid-"
        assert "truncated" in caplog.text


class TestApiKeyValidation:
    @pytest.mark.parametrize("key", ["", "   ", "sk-ant-api03-...", "sk-ant-PUT-YOUR-KEY", "nope"])
    def test_placeholder_and_empty_keys_are_rejected(self, key, monkeypatch):
        monkeypatch.setattr(claude_client.settings, "anthropic_api_key", key)
        with pytest.raises(claude_client.MissingAPIKeyError, match=r"\.env"):
            claude_client._validate_key()

    def test_a_real_looking_key_passes(self, monkeypatch):
        monkeypatch.setattr(
            claude_client.settings, "anthropic_api_key", "sk-ant-api03-realkey123")
        assert claude_client._validate_key() == "sk-ant-api03-realkey123"
