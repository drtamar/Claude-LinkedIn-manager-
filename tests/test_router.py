"""Model router: where each task runs, and why (plan A2)."""
import pytest

from app.llm import cost, hardware
from app.llm.hardware import Hardware, ModelTier
from app.llm.router import (CLOUD_CHEAP, CLOUD_DEFAULT, ROUTING_TABLE,
                            Destination, Router, TaskKind)


def gpu_box(vram=24.0) -> Hardware:
    return Hardware(system="Windows", cpu_cores=16, ram_gb=64.0,
                    gpu_name="RTX 4090", vram_gb=vram)


def laptop() -> Hardware:
    """Her actual situation until we know otherwise: no discrete GPU."""
    return Hardware(system="Windows", cpu_cores=8, ram_gb=16.0,
                    gpu_name=None, vram_gb=None)


class TestPolicy:
    def test_every_task_kind_has_a_route(self):
        """A task with no row would route by accident."""
        assert set(ROUTING_TABLE) == set(TaskKind)

    def test_every_route_explains_itself(self):
        for task, route in ROUTING_TABLE.items():
            assert len(route.why) > 20, f"{task.value} has no stated reason"

    def test_nothing_published_is_written_locally(self):
        """The rule that protects her name. Drafting, translating and both
        checks must be cloud, whatever the hardware."""
        for task in (TaskKind.DRAFT, TaskKind.TRANSLATE,
                     TaskKind.CRITIC, TaskKind.CLAIM_FIDELITY):
            assert ROUTING_TABLE[task].destination is Destination.CLOUD

    def test_bulk_work_is_local(self):
        """The cost lever: triage reads everything and must not be paid for."""
        for task in (TaskKind.TRIAGE, TaskKind.BIAS_PRESCORE, TaskKind.FIRST_SUMMARY):
            assert ROUTING_TABLE[task].destination is Destination.LOCAL

    def test_deterministic_steps_use_no_model(self):
        for task in (TaskKind.HARVEST, TaskKind.DEDUPE, TaskKind.PARSE):
            assert ROUTING_TABLE[task].destination is Destination.CODE

    def test_the_checks_that_protect_her_run_at_high_effort(self):
        for task in (TaskKind.CRITIC, TaskKind.CLAIM_FIDELITY):
            route = ROUTING_TABLE[task]
            assert route.effort == "high" and route.thinking is True

    def test_local_tasks_fall_back_to_the_cheap_model(self):
        """Falling back to the default model would turn a free bulk path into
        an expensive one — the exact surprise this stage prevents."""
        for task in (TaskKind.TRIAGE, TaskKind.BIAS_PRESCORE, TaskKind.FIRST_SUMMARY):
            assert ROUTING_TABLE[task].fallback_model == CLOUD_CHEAP

    def test_cheap_fallback_is_much_cheaper_than_the_default(self):
        assert cost.PRICES[CLOUD_CHEAP].input < cost.PRICES[CLOUD_DEFAULT].input / 10

    def test_triage_asks_for_json_and_a_short_answer(self):
        route = ROUTING_TABLE[TaskKind.TRIAGE]
        assert route.json_mode is True and route.max_tokens <= 512


class TestPlanning:
    def test_plan_spends_nothing(self):
        router = Router(gpu_box())
        before = cost.month_to_date()["calls"]
        [router.plan(t) for t in TaskKind]
        assert cost.month_to_date()["calls"] == before

    def test_good_gpu_with_ollama_keeps_bulk_work_free(self, working_local_model):
        router = Router(gpu_box())
        assert router.tier is ModelTier.FULL
        for task in (TaskKind.TRIAGE, TaskKind.FIRST_SUMMARY):
            plan = router.plan(task)
            assert plan["actual_destination"] == "local"
            assert plan["free"] is True and plan["fallback_reason"] is None

    def test_missing_ollama_is_reported_not_hidden(self, no_local_model):
        plan = Router(gpu_box()).plan(TaskKind.TRIAGE)
        assert plan["actual_destination"] == "cloud"
        assert "Ollama is not running" in plan["fallback_reason"]
        assert plan["model"] == CLOUD_CHEAP

    def test_weak_hardware_still_triages_locally(self, working_local_model):
        """A 3B model on CPU is slow but perfectly able to classify."""
        plan = Router(laptop()).plan(TaskKind.TRIAGE)
        assert plan["actual_destination"] == "local"

    def test_weak_hardware_does_not_summarise_locally(self, working_local_model):
        plan = Router(laptop()).plan(TaskKind.FIRST_SUMMARY)
        assert plan["actual_destination"] == "cloud"
        assert "below the mid" in plan["fallback_reason"]

    def test_cloud_tasks_are_never_rerouted_to_local(self, working_local_model):
        router = Router(gpu_box())
        for task in (TaskKind.DRAFT, TaskKind.CRITIC):
            assert router.plan(task)["actual_destination"] == "cloud"


class TestExecution:
    async def test_local_run_is_free_and_recorded_as_such(self, working_local_model):
        result = await Router(gpu_box()).run(TaskKind.TRIAGE, "classify this abstract")
        assert result.destination is Destination.LOCAL
        assert result.cost_usd == 0.0
        assert cost.month_to_date()["calls"] == 0, "a local call must not touch the ledger"

    async def test_cloud_run_is_billed_to_its_stage(self, fake_cloud, working_local_model):
        result = await Router(gpu_box()).run(TaskKind.DRAFT, "write the article")
        assert result.destination is Destination.CLOUD
        assert result.cost_usd > 0
        assert cost.month_to_date()["by_stage"]["draft"]["calls"] == 1

    async def test_cloud_run_uses_the_routes_model_and_effort(self, fake_cloud, working_local_model):
        await Router(gpu_box()).run(TaskKind.CRITIC, "check this draft")
        call = fake_cloud[-1]
        assert call["model"] == CLOUD_DEFAULT
        assert call["effort"] == "high" and call["thinking"] is True
        assert call["stage"] == "critic"

    async def test_fallback_records_its_reason_on_the_result(self, fake_cloud, no_local_model):
        """Rule 3: a silent local-to-cloud fallback is the surprise we are
        guarding against, so the reason travels with the result."""
        result = await Router(gpu_box()).run(TaskKind.TRIAGE, "classify")
        assert result.destination is Destination.CLOUD
        assert "Ollama is not running" in (result.fallback_reason or "")

    async def test_local_model_dying_mid_call_falls_back(self, monkeypatch, fake_cloud):
        from app.llm import local
        monkeypatch.setattr(local, "is_available", lambda: True)

        async def boom(prompt, **kwargs):
            raise local.LocalModelUnavailable("connection reset")

        monkeypatch.setattr(local, "acomplete", boom)
        result = await Router(gpu_box()).run(TaskKind.TRIAGE, "classify")
        assert result.destination is Destination.CLOUD
        assert "connection reset" in result.fallback_reason

    async def test_code_only_tasks_refuse_to_run_through_a_model(self):
        with pytest.raises(ValueError, match="plain code"):
            await Router(gpu_box()).run(TaskKind.HARVEST, "fetch feeds")


class TestCapInteraction:
    async def test_spent_cap_blocks_a_cloud_task(self, monkeypatch, working_local_model):
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "0.01")
        cost.record("draft", CLOUD_DEFAULT,
                    cost.Usage(input_tokens=200_000, output_tokens=20_000))
        with pytest.raises(cost.CapExceeded):
            await Router(gpu_box()).run(TaskKind.DRAFT, "write")

    async def test_spent_cap_still_allows_local_work(self, monkeypatch, working_local_model):
        """Plan A3.3: on reaching the cap, cloud stops and work queues
        locally — it does not stop the whole system."""
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "0.01")
        cost.record("draft", CLOUD_DEFAULT,
                    cost.Usage(input_tokens=200_000, output_tokens=20_000))
        result = await Router(gpu_box()).run(TaskKind.TRIAGE, "classify")
        assert result.destination is Destination.LOCAL

    async def test_cap_is_checked_on_the_fallback_path_too(self, monkeypatch, no_local_model):
        """A fallback is still a paid call, so it must not slip past the cap."""
        monkeypatch.setenv("SOCIAL_DESK_MONTHLY_CAP_USD", "0.01")
        cost.record("draft", CLOUD_DEFAULT,
                    cost.Usage(input_tokens=200_000, output_tokens=20_000))
        with pytest.raises(cost.CapExceeded):
            await Router(gpu_box()).run(TaskKind.TRIAGE, "classify")

    async def test_cloud_can_be_switched_off_entirely(self, no_local_model):
        router = Router(gpu_box(), allow_cloud=False)
        with pytest.raises(cost.CapExceeded, match="switched off"):
            await router.run(TaskKind.DRAFT, "write")


class TestReporting:
    def test_describe_covers_hardware_ollama_cost_and_routes(self, no_local_model):
        report = Router(laptop()).describe()
        assert set(report) >= {"hardware", "local_model", "ollama", "cost", "routes"}
        assert len(report["routes"]) == len(TaskKind)
        assert report["cost"]["cap_usd"] == cost.DEFAULT_MONTHLY_CAP_USD
