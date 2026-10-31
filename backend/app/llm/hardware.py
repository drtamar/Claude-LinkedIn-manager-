"""Hardware probe and local-model tier selection (plan A1).

Stdlib only, and every probe is best-effort: on any failure the field goes
None and the tier falls back to the most conservative option. A wrong answer
here should slow the app down, never stop it from starting.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from enum import Enum

# How long any single probe command gets before we give up on it.
PROBE_TIMEOUT_SECONDS = 5


class ModelTier(str, Enum):
    """What the local model is trusted to do (plan A1.2)."""

    # No usable accelerator. Local model does triage and classification only;
    # everything that gets written for a human goes to the cloud.
    TRIAGE_ONLY = "triage_only"
    # 8-16GB VRAM. Also summarising and first drafts.
    MID = "mid"
    # 24GB+. Genuine drafting, light fine-tuning possible.
    FULL = "full"


# Ollama tags per tier, with the on-disk download size so the UI can warn
# before a multi-GB pull. Override with SOCIAL_DESK_LOCAL_MODEL.
TIER_MODELS: dict[ModelTier, tuple[str, float]] = {
    ModelTier.TRIAGE_ONLY: ("llama3.2:3b", 2.0),
    ModelTier.MID: ("qwen2.5:14b", 9.0),
    ModelTier.FULL: ("qwen2.5:32b", 20.0),
}

# Below this much system RAM, even a 3B model on CPU is painful.
MIN_USABLE_RAM_GB = 8.0


@dataclass(frozen=True)
class Hardware:
    """What we could actually determine about this machine."""

    system: str                      # "Windows" / "Linux" / "Darwin"
    cpu_cores: int | None
    ram_gb: float | None
    gpu_name: str | None
    vram_gb: float | None
    # True when vram_gb came from Apple unified memory rather than a discrete
    # card. Same number, different meaning: it is shared with the OS.
    unified_memory: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def _run(cmd: list[str]) -> str | None:
    """Run a probe command. Returns stdout, or None if anything goes wrong."""
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def detect_cpu_cores() -> int | None:
    # Physical cores would be better than logical, but os.cpu_count is the
    # only answer available everywhere without a dependency.
    try:
        return os.cpu_count()
    except Exception:
        return None


def detect_ram_gb() -> float | None:
    """Total system RAM in GB."""
    system = platform.system()

    if system == "Linux":
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        kb = float(line.split()[1])
                        return round(kb / (1024 * 1024), 1)
        except (OSError, ValueError, IndexError):
            return None
        return None

    if system == "Darwin":
        raw = _run(["sysctl", "-n", "hw.memsize"])
        if raw:
            try:
                return round(float(raw) / (1024**3), 1)
            except ValueError:
                return None
        return None

    if system == "Windows":
        # ctypes first: no subprocess, and it works on every Windows build.
        # wmic is deprecated and already absent on recent Windows 11.
        try:
            import ctypes

            class _MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MemoryStatusEx()
            stat.dwLength = ctypes.sizeof(_MemoryStatusEx)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return round(stat.ullTotalPhys / (1024**3), 1)
        except Exception:
            pass

        raw = _run([
            "powershell", "-NoProfile", "-Command",
            "(Get-CIMInstance Win32_PhysicalMemory | "
            "Measure-Object -Property Capacity -Sum).Sum",
        ])
        if raw:
            try:
                return round(float(raw.strip()) / (1024**3), 1)
            except ValueError:
                return None
    return None


def detect_gpu() -> tuple[str | None, float | None, bool]:
    """Return (gpu_name, vram_gb, unified_memory).

    NVIDIA is checked first because nvidia-smi gives an exact VRAM figure on
    both Windows and Linux. Apple Silicon reports unified memory, which is
    shared with the OS, so we only count part of it as usable.
    """
    raw = _run([
        "nvidia-smi",
        "--query-gpu=name,memory.total",
        "--format=csv,noheader,nounits",
    ])
    if raw:
        # Multiple GPUs produce one line each; take the largest card rather
        # than the first, since inference will be pinned to one of them.
        best_name, best_vram = None, 0.0
        for line in raw.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            try:
                mib = float(parts[1])
            except ValueError:
                continue
            gb = round(mib / 1024, 1)
            if gb > best_vram:
                best_name, best_vram = parts[0], gb
        if best_name:
            return best_name, best_vram, False

    if platform.system() == "Darwin" and platform.machine() == "arm64":
        ram = detect_ram_gb()
        chip = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or "Apple Silicon"
        if ram:
            # Metal will not hand the whole pool to one process. Two thirds is
            # the conventional safe assumption.
            return chip, round(ram * 2 / 3, 1), True
        return chip, None, True

    # AMD on Linux. rocm-smi output format varies between releases, so we
    # scrape loosely and accept failure.
    raw = _run(["rocm-smi", "--showmeminfo", "vram", "--csv"])
    if raw:
        match = re.search(r"(\d{7,})", raw)
        if match:
            try:
                return "AMD GPU (ROCm)", round(float(match.group(1)) / (1024**3), 1), False
            except ValueError:
                pass

    return None, None, False


def probe() -> Hardware:
    """Inspect this machine. Never raises."""
    gpu_name, vram_gb, unified = detect_gpu()
    return Hardware(
        system=platform.system(),
        cpu_cores=detect_cpu_cores(),
        ram_gb=detect_ram_gb(),
        gpu_name=gpu_name,
        vram_gb=vram_gb,
        unified_memory=unified,
    )


def tier_for(hw: Hardware) -> ModelTier:
    """Map hardware to what the local model may be trusted with (plan A1.2).

    Thresholds are on VRAM because that is what bounds a loaded model. With no
    accelerator we stay at TRIAGE_ONLY regardless of how much RAM there is:
    CPU inference is fast enough to classify a feed overnight, not to draft
    text while someone waits.
    """
    if hw.vram_gb is not None:
        if hw.vram_gb >= 24:
            return ModelTier.FULL
        if hw.vram_gb >= 8:
            return ModelTier.MID
    return ModelTier.TRIAGE_ONLY


def recommended_model(tier: ModelTier) -> tuple[str, float]:
    """(ollama_tag, download_size_gb) for a tier, honouring the env override."""
    override = os.environ.get("SOCIAL_DESK_LOCAL_MODEL", "").strip()
    if override:
        return override, 0.0
    return TIER_MODELS[tier]


def describe(hw: Hardware | None = None) -> dict:
    """Probe plus verdict, shaped for the doctor command and the UI."""
    hw = hw or probe()
    tier = tier_for(hw)
    model, size_gb = recommended_model(tier)

    warnings: list[str] = []
    if hw.ram_gb is not None and hw.ram_gb < MIN_USABLE_RAM_GB:
        warnings.append(
            f"Only {hw.ram_gb}GB RAM detected. A local model will be slow; "
            "triage may be better left to the cloud model in small batches."
        )
    if hw.vram_gb is None:
        warnings.append(
            "No GPU detected, so the local model runs on CPU. That is fine for "
            "triage but too slow for drafting — drafting stays in the cloud."
        )
    if hw.unified_memory:
        warnings.append(
            f"Apple unified memory: the {hw.vram_gb}GB figure is shared with "
            "macOS, so treat it as an upper bound."
        )
    if hw.ram_gb is None and hw.vram_gb is None:
        warnings.append(
            "Could not read this machine's memory. Assuming the most "
            "conservative tier; set SOCIAL_DESK_LOCAL_MODEL to override."
        )

    return {
        "hardware": hw.as_dict(),
        "tier": tier.value,
        "local_model": model,
        "download_gb": size_gb,
        "can_draft_locally": tier in (ModelTier.MID, ModelTier.FULL),
        "can_finetune_locally": tier is ModelTier.FULL,
        "warnings": warnings,
    }
