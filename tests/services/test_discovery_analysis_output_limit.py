"""Regression tests for the Discovery gap-analysis output-limit failure.

Root cause investigation (see PAPER_OUTPUT_FINAL_DIAGNOSTIC.md / a follow-up
reliability pass): `analyze_gaps()`'s `REPORT_SCHEMA` requires one full,
multi-field write-up per author-flagged candidate (up to
`MAX_CANDIDATES_FOR_ANALYSIS = 5`, already deliberately capped per D-009)
plus up to 4 gaps (each with 7 fields, including free-text "evidence"/
"description"). Unlike `gaps`/`themes`, which already explicitly instruct
"fewer, well-evidenced entries over padding," `author_flagged_gaps` had NO
brevity guidance at all — so with a full 5 candidates and several gaps in
one report, the model had no signal to write concisely, and cumulative
verbosity could exceed the fixed `max_tokens=8000` ceiling, truncating the
response (`Completion.stop == "length"`) and failing the whole Discovery
stage. This is a genuine prompt-design gap, not a raw token-limit problem —
fixed by adding explicit per-entry brevity guidance and an overall
output-budget instruction to `ANALYSIS_SYSTEM`, without touching
`max_tokens` or `MAX_CANDIDATES_FOR_ANALYSIS`.

This module has no prior test coverage at all — these are the first tests
for `analyze_gaps()`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-discovery"))
sys.path.insert(0, str(ROOT))

import discovery.analysis as analysis  # noqa: E402
from discovery.models import PipelineError  # noqa: E402
from shared.utilities.llm_provider import Completion  # noqa: E402


def test_analysis_system_prompt_instructs_brevity_for_author_flagged_gaps():
    assert "1-3 sentences" in analysis.ANALYSIS_SYSTEM
    assert "author_flagged_gaps" in analysis.ANALYSIS_SYSTEM


def test_analysis_system_prompt_states_an_overall_output_budget():
    prompt = analysis.ANALYSIS_SYSTEM.casefold()
    assert "output budget" in prompt or "fixed maximum output size" in prompt
    assert "truncat" in prompt  # warns about the actual failure mode


def test_max_candidates_cap_is_unchanged_by_this_fix():
    """This fix is prompt-level only — the existing, deliberate candidate cap
    (D-009) must not have been touched as a side effect."""
    import discovery.pipeline as pipeline
    assert pipeline.MAX_CANDIDATES_FOR_ANALYSIS == 5


async def _fake_stream_json(stop: str, *, system, user, schema, model, max_tokens, think):
    yield {"type": "delta", "text": "x"}
    completion = Completion(text='{"field_overview": "x"}', stop=stop)
    yield {"type": "done", "completion": completion}


def test_truncated_output_still_raises_a_clear_actionable_error(monkeypatch):
    """The truncation-handling path itself (unchanged by this fix) must keep
    failing loudly and clearly rather than parsing a truncated document."""
    import asyncio

    async def fake(*, system, user, schema, model, max_tokens, think):
        async for event in _fake_stream_json("length", system=system, user=user,
                                             schema=schema, model=model,
                                             max_tokens=max_tokens, think=think):
            yield event

    monkeypatch.setattr(analysis.llm, "stream_json", fake)

    async def run():
        events = []
        try:
            async for event in analysis.analyze_gaps("Q?", []):
                events.append(event)
        except PipelineError as error:
            return error
        raise AssertionError("expected a PipelineError")

    error = asyncio.run(run())
    assert "output limit" in str(error)
    assert "fewer papers" in str(error)


def test_a_complete_response_is_not_treated_as_truncated(monkeypatch):
    import asyncio
    import json

    complete_report = {
        "field_overview": "x", "themes": [], "gaps": [], "author_flagged_gaps": [],
        "limitations": "x", "novelty_analysis": {
            "novelty_summary": "x", "supporting_gap_titles": [],
            "confidence": "low", "caveats": "x",
        },
        "confidence_notes": "x",
    }

    async def fake(*, system, user, schema, model, max_tokens, think):
        yield {"type": "delta", "text": "x"}
        yield {"type": "done", "completion": Completion(text=json.dumps(complete_report), stop="end")}

    monkeypatch.setattr(analysis.llm, "stream_json", fake)

    async def run():
        result = None
        async for event in analysis.analyze_gaps("Q?", []):
            if event["type"] == "report":
                result = event
        return result

    result = asyncio.run(run())
    assert result is not None
