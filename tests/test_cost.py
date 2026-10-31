"""Cost meter: arithmetic, the cap, and the ledger (plan A3)."""
import pytest

from app.llm import cost


class TestArithmetic:
    def test_prices_per_million_tokens(self):
        # 10k input + 2k output on Opus 5.5 at $4/$20 per million.
        spent = cost.cost_of(
            "claude-opus-5-5",
            cost.Usage(input_tokens=10_000, output_tokens=2_000),
        )
        assert spent == pytest.approx(0.04 + 0.04)

    def test_cache_read_is_far_cheaper_than_fresh_input(self):
        """The whole point of caching the profile prefix."""
        fresh = cost.cost_of("claude-opus-5-5", cost.Usage(input_tokens=100_000))
        cached = cost.cost_of("claude-opus-5-5", cost.Usage(cache_read_tokens=100_000))
        assert cached < fresh / 10

    def test_cache_write_costs_more_than_fresh_input(self):
        """Writing the cache carries a premium, so caching a prefix used once
        is a loss. Worth encoding so nobody 'optimises' by caching everything."""
        fresh = cost.cost_of("claude-opus-5-5", cost.Usage(input_tokens=50_000))
        written = cost.cost_of("claude-opus-5-5", cost.Usage(cache_write_tokens=50_000))
        assert written > fresh

    def test_cached_tokens_are_not_double_counted(self):
        """input_tokens excludes cached tokens in the API's own accounting."""
        usage = cost.Usage(input_tokens=1_000, cache_read_tokens=9_000)
        assert usage.billable_input == 1_000

    def test_haiku_crosses_its_long_prompt_threshold(self):
        under = cost.cost_of(
            "claude-haiku-5-5", cost.Usage(input_tokens=90_000, output_tokens=1_000))
        over = cost.cost_of(
            "claude-haiku-5-5", cost.Usage(input_tokens=110_000, output_tokens=1_000))
        # 5x jump above 100k, so a slightly bigger prompt is much pricier.
        assert over > under * 4

    def test_unknown_model_is_costed_pessimistically(self):
        """A model we have no price for must not look free, or an unpriced
        model would silently escape the cap."""
        spent = cost.cost_of(
            "claude-something-unreleased",
            cost.Usage(input_tokens=1_000_000),
        )
        assert spent >= cost.FALLBACK_PRICE.input

    def test_dated_model_id_resolves_to_its_base_price(self):
        assert cost.price_for("claude-opus-5-5-20260401") is cost.PRICES["claude-opus-5-5"]

    def test_triage_on_cheap_model_is_genuinely_cheap(self):
        """Sanity-check the core cost argument: triaging 500 abstracts of
        ~800 tokens each through the cheap model should cost pennies."""
        per_item = cost.cost_of(
            "claude-haiku-5-5", cost.Usage(input_tokens=800, output_tokens=50))
        assert per_item * 500 < 0.10


class TestUsageParsing:
    def test_reads_usage_off_a_response(self):
        from tests.conftest import make_response
        usage = cost.Usage.from_response(
            make_response(input_tokens=11, output_tokens=22, cache_read=33, cache_write=44))
        assert (usage.input_tokens, usage.output_tokens) == (11, 22)
        assert (usage.cache_read_tokens, usage.cache_write_tokens) == (33, 44)

    def test_response_without_usage_is_zeroed_not_an_error(self):
        from types import SimpleNamespace
        assert cost.Usage.from_response(SimpleNamespace()) == cost.Usage()


class TestLedger:
    def test_records_and_totals_by_stage(self):
        cost.record("triage", "claude-haiku-5-5", cost.Usage(input_tokens=5_000))
        cost.record("draft", "claude-opus-5-5", cost.Usage(input_tokens=8_000, output_tokens=1_500))
        cost.record("draft", "claude-opus-5-5", cost.Usage(input_tokens=4_000, output_tokens=900))

        mtd = cost.month_to_date()
        assert mtd["calls"] == 3
        assert mtd["by_stage"]["draft"]["calls"] == 2
        assert mtd["by_stage"]["draft"]["usd"] > mtd["by_stage"]["triage"]["usd"]
        assert mtd["total_usd"] == pytest.approx(
            mtd["by_stage"]["draft"]["usd"] + mtd["by_stage"]["triage"]["usd"], abs=1e-3)

    def test_empty_ledger_reports_zero_not_an_error(self):
        mtd = cost.month_to_date()
        assert mtd["total_usd"] == 0.0 and mtd["ledger_error"] is None

    def test_record_survives_an_unwritable_ledger(self, monkeypatch, tmp_path):
        """The money is already spent by the time we log it, so a failed write
        must return the cost rather than raise and lose the caller's work."""
        monkeypatch.setenv("SOCIAL_DESK_COST_DB", str(tmp_path / "nope" / "x.db"))
        monkeypatch.setattr(
            cost.Path, "mkdir",
            lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")),
        )
        with pytest.raises(OSError):
            cost._connect()
        # record swallows it:
        assert cost.record("draft", "claude-opus-5-5", cost.Usage(input_tokens=1_000)) > 0


class TestCap:
    def test_under_cap_permits_calls(self, monkeypatch):
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "5.00")
        cost.record("draft", "claude-opus-5-5", cost.Usage(input_tokens=10_000))
        cost.check_cap()  # must not raise

    def test_cap_blocks_once_spent(self, monkeypatch):
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "0.05")
        cost.record("draft", "claude-opus-5-5",
                    cost.Usage(input_tokens=100_000, output_tokens=10_000))
        with pytest.raises(cost.CapExceeded) as exc:
            cost.check_cap()
        # The message has to tell a non-developer what to do next.
        assert "SOCIAL_DESK_MONTHLY_CAP_USD" in str(exc.value)

    def test_cap_fails_open_when_the_ledger_is_unreadable(self, monkeypatch):
        """Deliberate: a budget guard must not lock her out of her own tool
        over an unreadable file. The failure surfaces in summary() instead."""
        monkeypatch.setattr(
            cost, "month_to_date",
            lambda month=None: {"month": "2026-10", "total_usd": 0.0, "calls": 0,
                                "by_stage": {}, "ledger_error": "disk I/O error"},
        )
        cost.check_cap()

    def test_summary_reports_percentage_and_capped_state(self, monkeypatch):
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "1.00")
        cost.record("draft", "claude-opus-5-5",
                    cost.Usage(input_tokens=100_000, output_tokens=5_000))
        s = cost.summary()
        assert 0 < s["percent_used"] < 100
        assert s["capped"] is False
        assert s["remaining_usd"] == pytest.approx(1.00 - s["total_usd"])

    def test_default_cap_applies_when_unset(self):
        assert cost.monthly_cap() == cost.DEFAULT_MONTHLY_CAP_USD

    def test_malformed_cap_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "ten dollars")
        assert cost.monthly_cap() == cost.DEFAULT_MONTHLY_CAP_USD


class TestEstimate:
    def test_estimate_spends_nothing(self):
        before = cost.month_to_date()["calls"]
        cost.estimate("claude-opus-5-5", 10_000, 2_000)
        assert cost.month_to_date()["calls"] == before

    def test_estimate_flags_a_call_that_would_breach_the_cap(self, monkeypatch):
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "0.01")
        assert cost.estimate("claude-opus-5-5", 1_000_000, 100_000)["would_exceed_cap"]
