"""Every existing AI feature actually invokes, and bills to a named stage.

This file exists because "the module imports" proved nothing: Python does not
check call arity at import time, so a call missing its prompt argument imports
cleanly and fails only when a user clicks the button. These tests call each
function for real against a fake client.
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.llm import cost

MODULES_DIR = Path(__file__).resolve().parents[1] / "backend/app/ai/modules"

# Minimal arguments per function. Values only have to be the right shape — the
# model is faked, so nothing is actually reasoned about.
PROFILE = {
    "name": "Dr Tamar Savtchenko", "role": "Veterinarian",
    "industry": "Veterinary medicine", "target_audience": ["pet owners"],
    "achievements": ["16 years in practice"], "keywords": ["pet health"],
}
LINKEDIN = {"headline": "Vet", "about_section": "...", "experience": [], "skills": []}

# algorithm_ai returns industry defaults below a data threshold rather than
# calling the model, so these need enough rows to reach the paid path.
POSTS = [
    {"date": f"2026-0{m}-15", "time": "08:00", "impressions": 100 * m,
     "engagement_rate": m / 100}
    for m in range(1, 7)
]

CASES: dict[str, dict] = {
    "algorithm_ai.get_optimal_times": {
        "user_profile": PROFILE, "historical_data": POSTS},
    "algorithm_ai.generate_insights": {
        "user_profile": PROFILE, "posts_with_metrics": POSTS},
    "content_ai.generate_hooks": {"topic": "ticks", "user_profile": PROFILE},
    "content_ai.stream_post": {
        "topic": "ticks", "post_type": "educational", "hook": "Ticks are early this year.",
        "user_profile": PROFILE},
    "content_ai.generate_hashtags": {"topic": "ticks", "industry": "vet"},
    "content_ai.score_post": {
        "content": "A post about ticks.", "post_type": "educational",
        "user_profile": PROFILE},
    "content_ai.stream_content_ideas": {"user_profile": PROFILE},
    "cv_ai.stream_cv": {"user_profile": PROFILE, "linkedin_profile": LINKEDIN},
    "import_ai.extract_profile_from_text": {"raw_text": "CV text. " * 40},
    "learning_ai.analyze_performance": {
        "user_profile": PROFILE, "posts_with_metrics": [],
        "current_prompt_versions": []},
    "learning_ai.refine_prompt": {
        "module": "content", "current_prompt": "p", "current_system": "s",
        "performance_findings": {}, "high_performing_examples": []},
    "network_ai.stream_icp": {"user_profile": PROFILE},
    "network_ai.generate_connection_note": {
        "prospect_name": "A", "prospect_title": "DVM", "prospect_company": "Clinic",
        "prospect_bio_snippet": "...", "user_profile": PROFILE},
    "network_ai.stream_sequence": {
        "user_profile": PROFILE, "icp_name": "Vets", "icp_description": "..."},
    "profile_ai.generate_headline": {"user_profile": PROFILE},
    "profile_ai.stream_about": {"user_profile": PROFILE, "headline": "Vet"},
    "profile_ai.generate_experience": {"user_profile": PROFILE},
    "profile_ai.generate_skills": {"user_profile": PROFILE},
    "profile_ai.categorize_skills": {"skills": ["surgery", "dentistry"]},
    "profile_ai.score_profile": {
        "headline": "Vet", "about": "...", "skills": [], "experience": []},
    "questionnaire_ai.get_next_question": {
        "user_type": "founder", "answers": {}, "step_number": 0},
    "questionnaire_ai.synthesize_profile": {"user_type": "founder", "answers": {}},
}


def tagged_calls() -> dict[str, str]:
    """Map 'module.function' -> expected stage, read from the source.

    Derived from the code rather than hardcoded, so a new paid call that
    forgets its stage tag shows up as a missing case instead of passing.
    """
    found: dict[str, str] = {}
    for path in sorted(MODULES_DIR.glob("*_ai.py")):
        current = None
        for line in path.read_text().splitlines():
            m = re.match(r"\s*(?:async )?def (\w+)\(", line)
            if m:
                current = m.group(1)
            stage = re.search(r'stage="([^"]+)"', line)
            if stage and current:
                found.setdefault(f"{path.stem}.{current}", stage.group(1))
    return found


# A reply that satisfies the JSON parsing the modules do on their results.
FAKE_JSON = json.dumps({
    "hooks": [{"text": "h", "angle": "a"}], "hashtags": ["#vet"],
    "score": 80, "headline": "Vet", "about": "...", "skills": ["surgery"],
    "experience": [], "insights": [], "findings": {}, "times": [],
    "question": "What do you do?", "categories": {"Clinical": ["surgery"]},
    "user_profile": {}, "linkedin_profile": {},
})


@pytest.fixture
def fake_sdk(monkeypatch):
    """Fake the Anthropic client and report which stages got billed."""
    from app.ai import claude_client

    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=FAKE_JSON)],
        stop_reason="end_turn",
        stop_details=None,
        usage=SimpleNamespace(
            input_tokens=500, output_tokens=100,
            cache_read_input_tokens=0, cache_creation_input_tokens=0),
    )

    class Stream:
        async def __aenter__(self): return self
        async def __aexit__(self, *e): return False
        async def get_final_message(self): return response
        @property
        def text_stream(self):
            async def gen():
                yield FAKE_JSON
            return gen()

    class Messages:
        async def create(self, **kw): return response
        def stream(self, **kw): return Stream()

    monkeypatch.setattr(
        claude_client, "get_client", lambda: SimpleNamespace(messages=Messages()))
    return response


def test_every_paid_call_has_a_test_case():
    """Guards the guard: a new paid call must be added to CASES."""
    missing = set(tagged_calls()) - set(CASES)
    assert not missing, f"paid calls with no invocation test: {sorted(missing)}"


def test_no_paid_call_is_left_untagged():
    source = "\n".join(p.read_text() for p in MODULES_DIR.glob("*_ai.py"))
    calls = re.findall(r"(?:await complete|stream_response)\((.*?)\)\s*:?\s*$",
                       source, re.MULTILINE)
    untagged = [c for c in calls if "stage=" not in c]
    assert not untagged, f"paid calls without a stage tag: {untagged}"


def test_no_date_suffixed_model_ids():
    """Date-suffixed ids are not valid model strings on current models."""
    source = "\n".join(p.read_text() for p in MODULES_DIR.glob("*_ai.py"))
    assert not re.findall(r"claude-[a-z0-9.-]*-20\d{6}", source)


def test_all_referenced_models_are_priced():
    """An unpriced model would be costed at the pessimistic fallback rate, so
    the ledger would be wrong rather than absent."""
    source = "\n".join(p.read_text() for p in MODULES_DIR.glob("*_ai.py"))
    for model in set(re.findall(r'model="(claude-[^"]+)"', source)):
        assert cost.price_for(model) is not cost.FALLBACK_PRICE, \
            f"{model} has no entry in cost.PRICES"


@pytest.mark.parametrize("target", sorted(CASES))
async def test_function_invokes_and_bills_its_stage(target, fake_sdk):
    """Calls the real function. Catches a dropped or renamed argument, which
    is invisible to an import check."""
    import importlib
    module_name, func_name = target.split(".")
    module = importlib.import_module(f"app.ai.modules.{module_name}")
    fn = getattr(module, func_name)

    result = fn(**CASES[target])
    if inspect.isasyncgen(result):
        chunks = [c async for c in result]
        assert chunks, f"{target} streamed nothing"
    else:
        await result

    expected_stage = tagged_calls()[target]
    billed = cost.month_to_date()["by_stage"]
    assert expected_stage in billed, (
        f"{target} did not bill to '{expected_stage}'; billed: {sorted(billed)}")
    assert billed[expected_stage]["usd"] > 0


class TestThinDataShortCircuits:
    """These paths return industry defaults instead of calling the model.

    Worth locking in as a cost property: analysing three data points is not
    worth a paid call, and a future refactor that "simplifies" the guard away
    would start spending money on every dashboard load.
    """

    async def test_optimal_times_spends_nothing_without_enough_history(self, fake_sdk):
        from app.ai.modules import algorithm_ai
        result = await algorithm_ai.get_optimal_times(PROFILE, historical_data=[])
        assert result["based_on"] == "industry defaults"
        assert cost.month_to_date()["calls"] == 0

    async def test_insights_spends_nothing_with_under_three_posts(self, fake_sdk):
        from app.ai.modules import algorithm_ai
        result = await algorithm_ai.generate_insights(PROFILE, posts_with_metrics=[])
        assert result and cost.month_to_date()["calls"] == 0
