"""Model router: one entry point, decides local vs cloud per task (plan A2).

The routing table below is the single biggest cost lever in the system. Triage
reads everything the harvester collects and discards the large majority; doing
that on a local model means the paid model only ever sees what survived.

Three rules hold everywhere in here:

1. Nothing published under her name is written by a local model. Drafting and
   the critic are cloud, always.
2. Nothing reaches a paid model without passing the cap check first.
3. Every fallback is recorded on the result. A silent fallback from local to
   cloud is exactly the kind of surprise this stage exists to prevent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from app.llm import cost, hardware, local

logger = logging.getLogger(__name__)

# The model that writes anything a human will read. Current default per the
# Anthropic model guidance.
CLOUD_DEFAULT = "claude-opus-5-5"
# Bulk/cheap cloud model. This is what local tasks fall back to when Ollama is
# unavailable: at $0.10 per million input tokens, triaging a feed through it
# costs cents, where falling back to the default model would not.
CLOUD_CHEAP = "claude-haiku-5-5"


class Destination(str, Enum):
    CODE = "code"    # deterministic, no model at all
    LOCAL = "local"  # Ollama, free
    CLOUD = "cloud"  # paid


class TaskKind(str, Enum):
    """Pipeline steps that need a decision about where they run."""

    # Plain code — listed so the table documents them as deliberately
    # model-free rather than merely unimplemented.
    HARVEST = "harvest"
    DEDUPE = "dedupe"
    PARSE = "parse"

    # Local: bulk work whose output she never reads directly.
    TRIAGE = "triage"
    BIAS_PRESCORE = "bias_prescore"
    FIRST_SUMMARY = "first_summary"

    # Cloud: anything that gets published, and the checks that protect her.
    TRANSLATE = "translate"
    DRAFT = "draft"
    CRITIC = "critic"
    CLAIM_FIDELITY = "claim_fidelity"


@dataclass(frozen=True)
class Route:
    """How one task kind runs. Data, so the policy is readable in one place."""

    destination: Destination
    why: str
    # Cloud settings. Effort is set explicitly because Opus 5.5 defaults to
    # "medium", which is not what we want for the checks that protect her.
    cloud_model: str = CLOUD_DEFAULT
    effort: str = "medium"
    max_tokens: int = 4096
    thinking: bool = False
    # Minimum local tier that may run this task. A 3B model on CPU can
    # classify; it cannot write a summary worth keeping.
    min_tier: hardware.ModelTier = hardware.ModelTier.TRIAGE_ONLY
    # Where a LOCAL task goes when the local model cannot serve it.
    fallback_model: str = CLOUD_CHEAP
    # Ask the local model for strict JSON. Removes the "Sure! Here is the
    # JSON:" preamble that makes small models awkward to parse.
    json_mode: bool = False


ROUTING_TABLE: dict[TaskKind, Route] = {
    TaskKind.HARVEST: Route(
        Destination.CODE, "Fetching feeds is deterministic — no model needed."),
    TaskKind.DEDUPE: Route(
        Destination.CODE, "DOI and URL matching is exact, not a judgement."),
    TaskKind.PARSE: Route(
        Destination.CODE, "Structured metadata parses with code."),

    TaskKind.TRIAGE: Route(
        Destination.LOCAL,
        "Reads everything harvested and discards most of it. The one change "
        "that decides whether this system costs cents or dollars.",
        max_tokens=256,
        json_mode=True,
        effort="low",
        fallback_model=CLOUD_CHEAP,
    ),
    TaskKind.BIAS_PRESCORE: Route(
        Destination.LOCAL,
        "Mostly structured signals — study design, funding, retraction state.",
        max_tokens=1024,
        json_mode=True,
        effort="low",
        fallback_model=CLOUD_CHEAP,
    ),
    TaskKind.FIRST_SUMMARY: Route(
        Destination.LOCAL,
        "An internal summary she never reads directly; draft quality is fine.",
        max_tokens=1024,
        min_tier=hardware.ModelTier.MID,
        fallback_model=CLOUD_CHEAP,
    ),

    TaskKind.TRANSLATE: Route(
        Destination.CLOUD,
        "Plain-language rewriting that will be published under her name.",
        effort="high",
        max_tokens=4096,
        thinking=True,
    ),
    TaskKind.DRAFT: Route(
        Destination.CLOUD,
        "Published under her name. Never a local model.",
        effort="high",
        max_tokens=8192,
        thinking=True,
    ),
    TaskKind.CRITIC: Route(
        Destination.CLOUD,
        "Clinical-advice risk and confidentiality. This is the check that "
        "protects her licence, so it gets the strongest model available.",
        effort="high",
        max_tokens=4096,
        thinking=True,
    ),
    TaskKind.CLAIM_FIDELITY: Route(
        Destination.CLOUD,
        "Does the simplification claim more than the paper supports? A "
        "separate pass from the rewrite, deliberately.",
        effort="high",
        max_tokens=2048,
        thinking=True,
    ),
}


@dataclass
class RouteResult:
    """What ran, where, and what it cost."""

    text: str
    task: TaskKind
    destination: Destination
    model: str
    cost_usd: float = 0.0
    # Set when the task did not run where the table said it should.
    fallback_reason: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def was_free(self) -> bool:
        return self.destination is not Destination.LOCAL or self.cost_usd == 0.0


class Router:
    """Decides where a task runs, then runs it.

    Hardware is probed once per instance rather than per call: it does not
    change while the app is running, and probing shells out.
    """

    def __init__(
        self,
        hw: hardware.Hardware | None = None,
        *,
        local_model: str | None = None,
        allow_cloud: bool = True,
    ):
        self.hardware = hw or hardware.probe()
        self.tier = hardware.tier_for(self.hardware)
        self.local_model = local_model or hardware.recommended_model(self.tier)[0]
        # Off switch for an offline or zero-spend run.
        self.allow_cloud = allow_cloud

    # -- planning ---------------------------------------------------------

    def plan(self, task: TaskKind) -> dict:
        """Where this task would run, and why. Makes --dry-run honest and the
        routing decision inspectable without spending anything."""
        route = ROUTING_TABLE[task]
        dest = route.destination
        reason = None

        if dest is Destination.LOCAL:
            if self.tier_too_low(route):
                dest, reason = Destination.CLOUD, (
                    f"local tier {self.tier.value} is below the {route.min_tier.value} "
                    f"this task needs"
                )
            elif not local.is_available():
                dest, reason = Destination.CLOUD, "Ollama is not running"

        model = (
            self.local_model if dest is Destination.LOCAL
            else (route.fallback_model if reason else route.cloud_model)
        )
        return {
            "task": task.value,
            "planned_destination": route.destination.value,
            "actual_destination": dest.value,
            "model": model if dest is not Destination.CODE else None,
            "why": route.why,
            "fallback_reason": reason,
            "free": dest is Destination.LOCAL,
        }

    def tier_too_low(self, route: Route) -> bool:
        order = [
            hardware.ModelTier.TRIAGE_ONLY,
            hardware.ModelTier.MID,
            hardware.ModelTier.FULL,
        ]
        return order.index(self.tier) < order.index(route.min_tier)

    # -- execution --------------------------------------------------------

    async def run(
        self,
        task: TaskKind,
        prompt: str,
        *,
        system: str = "",
        note: str | None = None,
    ) -> RouteResult:
        route = ROUTING_TABLE[task]

        if route.destination is Destination.CODE:
            raise ValueError(
                f"{task.value} is handled by plain code, not a model. "
                "Call the relevant function in app/research/ instead."
            )

        if route.destination is Destination.LOCAL:
            return await self._run_local(task, route, prompt, system, note)
        return await self._run_cloud(
            task, route, prompt, system, route.cloud_model, note, None
        )

    async def _run_local(
        self, task, route, prompt, system, note
    ) -> RouteResult:
        if self.tier_too_low(route):
            return await self._run_cloud(
                task, route, prompt, system, route.fallback_model, note,
                f"local tier {self.tier.value} cannot run {task.value} "
                f"(needs {route.min_tier.value})",
            )

        try:
            result = await local.acomplete(
                prompt,
                system=system,
                model=self.local_model,
                max_tokens=route.max_tokens,
                json_mode=route.json_mode,
            )
        except local.LocalModelUnavailable as exc:
            logger.warning(
                "Local model unavailable for %s, falling back to %s: %s",
                task.value, route.fallback_model, exc,
            )
            return await self._run_cloud(
                task, route, prompt, system, route.fallback_model, note,
                f"local model unavailable ({exc})",
            )

        return RouteResult(
            text=result.text,
            task=task,
            destination=Destination.LOCAL,
            model=result.model,
            cost_usd=0.0,
            notes=(
                [f"local run took {result.duration_seconds}s"]
                if result.duration_seconds else []
            ),
        )

    async def _run_cloud(
        self, task, route, prompt, system, model, note, fallback_reason
    ) -> RouteResult:
        if not self.allow_cloud:
            raise cost.CapExceeded(
                f"Cloud calls are switched off for this run, and {task.value} "
                "cannot be served locally."
            )

        # Rule 2: the cap is checked before any paid call, including fallbacks.
        cost.check_cap()

        from app.ai import claude_client  # imported here to keep this module
                                          # importable without the SDK present

        text, spent = await claude_client.complete_metered(
            prompt,
            system=system,
            model=model,
            max_tokens=route.max_tokens,
            effort=route.effort,
            thinking=route.thinking,
            stage=task.value,
            note=note,
        )
        return RouteResult(
            text=text,
            task=task,
            destination=Destination.CLOUD,
            model=model,
            cost_usd=spent,
            fallback_reason=fallback_reason,
            notes=[f"${spent:.4f}"],
        )

    # -- reporting --------------------------------------------------------

    def describe(self) -> dict:
        """Full routing picture for the doctor command and the cost panel."""
        return {
            "hardware": hardware.describe(self.hardware),
            "local_model": self.local_model,
            "ollama": local.status(self.local_model),
            "cloud_allowed": self.allow_cloud,
            "cost": cost.summary(),
            "routes": [self.plan(t) for t in TaskKind],
        }
