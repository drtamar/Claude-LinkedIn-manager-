"""Hardware probe and tier selection (plan A1)."""
from app.llm import hardware
from app.llm.hardware import Hardware, ModelTier


def hw(**kw) -> Hardware:
    base = dict(system="Windows", cpu_cores=8, ram_gb=16.0,
                gpu_name=None, vram_gb=None)
    base.update(kw)
    return Hardware(**base)


class TestTierSelection:
    def test_no_gpu_is_triage_only(self):
        assert hardware.tier_for(hw()) is ModelTier.TRIAGE_ONLY

    def test_plenty_of_ram_does_not_promote_a_cpu_only_machine(self):
        """Deliberate: CPU inference can classify a feed overnight but cannot
        draft while someone waits, however much RAM there is."""
        assert hardware.tier_for(hw(ram_gb=128.0)) is ModelTier.TRIAGE_ONLY

    def test_small_gpu_stays_triage_only(self):
        assert hardware.tier_for(hw(gpu_name="GTX 1650", vram_gb=4.0)) is ModelTier.TRIAGE_ONLY

    def test_mid_range_gpu_can_summarise(self):
        for vram in (8.0, 12.0, 16.0, 23.9):
            assert hardware.tier_for(hw(gpu_name="RTX", vram_gb=vram)) is ModelTier.MID

    def test_large_gpu_unlocks_full_tier(self):
        assert hardware.tier_for(hw(gpu_name="RTX 4090", vram_gb=24.0)) is ModelTier.FULL

    def test_boundaries_are_inclusive(self):
        assert hardware.tier_for(hw(vram_gb=7.9)) is ModelTier.TRIAGE_ONLY
        assert hardware.tier_for(hw(vram_gb=8.0)) is ModelTier.MID
        assert hardware.tier_for(hw(vram_gb=24.0)) is ModelTier.FULL


class TestDegradation:
    def test_unknown_hardware_falls_back_to_the_safest_tier(self):
        """A probe that returns nothing must not optimistically assume a GPU."""
        blind = hw(cpu_cores=None, ram_gb=None)
        assert hardware.tier_for(blind) is ModelTier.TRIAGE_ONLY
        assert "conservative" in " ".join(hardware.describe(blind)["warnings"])

    def test_probe_never_raises_on_this_machine(self):
        result = hardware.probe()
        assert isinstance(result, Hardware)
        assert result.system  # platform.system always answers

    def test_failing_probe_command_returns_none(self, monkeypatch):
        monkeypatch.setattr(hardware.shutil, "which", lambda _: None)
        assert hardware._run(["nvidia-smi", "--version"]) is None

    def test_low_ram_is_warned_about(self):
        warnings = hardware.describe(hw(ram_gb=4.0))["warnings"]
        assert any("4.0GB RAM" in w for w in warnings)

    def test_unified_memory_is_flagged_as_shared(self):
        mac = hw(system="Darwin", gpu_name="Apple M2", vram_gb=16.0)
        described = hardware.describe(Hardware(**{**mac.as_dict(), "unified_memory": True}))
        assert any("shared with" in w for w in described["warnings"])


class TestMultiGpuParsing:
    def test_picks_the_largest_card_not_the_first(self, monkeypatch):
        """Inference pins to one GPU, so the biggest one is the useful answer."""
        monkeypatch.setattr(
            hardware, "_run",
            lambda cmd: "Quadro P400, 2048\nRTX 4090, 24564" if cmd[0] == "nvidia-smi" else None,
        )
        name, vram, unified = hardware.detect_gpu()
        assert name == "RTX 4090"
        assert vram > 23 and unified is False

    def test_garbled_nvidia_smi_output_is_ignored(self, monkeypatch):
        monkeypatch.setattr(
            hardware, "_run",
            lambda cmd: "error: driver/library version mismatch" if cmd[0] == "nvidia-smi" else None,
        )
        assert hardware.detect_gpu() == (None, None, False)


class TestModelRecommendation:
    def test_each_tier_maps_to_a_model_and_a_download_size(self):
        for tier in ModelTier:
            tag, size = hardware.recommended_model(tier)
            assert ":" in tag and size > 0

    def test_bigger_tier_means_bigger_model(self):
        _, small = hardware.recommended_model(ModelTier.TRIAGE_ONLY)
        _, large = hardware.recommended_model(ModelTier.FULL)
        assert large > small

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("SOCIAL_DESK_LOCAL_MODEL", "mistral:7b")
        assert hardware.recommended_model(ModelTier.FULL)[0] == "mistral:7b"

    def test_describe_reports_what_the_tier_may_be_trusted_with(self):
        assert hardware.describe(hw())["can_draft_locally"] is False
        big = hardware.describe(hw(gpu_name="RTX 4090", vram_gb=24.0))
        assert big["can_draft_locally"] and big["can_finetune_locally"]
