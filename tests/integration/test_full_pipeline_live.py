"""Full end-to-end regression test: runs the real orchestrator through all
four services against live Ollama + live external APIs, exactly the path
scripts/smoke_test_full_pipeline.py exercises manually.

This is deliberately NOT part of the default fast test run. A full-corpus
Discovery pass (search + full-text mining across 6-9 papers) plus Writing
with a real outline can take well beyond the ~8 minutes the rest of the
suite already takes on this hardware (see DECISIONS.md D-009/D-010/D-011).
Gated behind an opt-in env var so `pytest` stays fast for routine commits,
while still giving the project a real automated (not just manual) check of
the full chained pipeline.

Run explicitly with:
    AI_RESEARCH_RUN_FULL_PIPELINE=1 pytest tests/integration/test_full_pipeline_live.py -v -s

Recommended cadence: before any Review milestone, and after any change to
orchestrator/pipeline.py or a service's public contract (shared/contracts/*).
"""

import os
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.utilities.llm_provider import DEFAULT_MODEL, OLLAMA_HOST  # noqa: E402


def _ollama_available() -> bool:
    try:
        resp = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        resp.raise_for_status()
        names = {m["name"] for m in resp.json().get("models", [])}
        return DEFAULT_MODEL in names or f"{DEFAULT_MODEL}:latest" in names
    except httpx.HTTPError:
        return False


pytestmark = [
    pytest.mark.skipif(
        os.environ.get("AI_RESEARCH_RUN_FULL_PIPELINE") != "1",
        reason="Opt-in only: set AI_RESEARCH_RUN_FULL_PIPELINE=1 to run the "
               "full live pipeline regression test (can take 15+ minutes).",
    ),
    pytest.mark.skipif(
        not _ollama_available(),
        reason=f"Ollama not reachable at {OLLAMA_HOST} with model {DEFAULT_MODEL} installed",
    ),
]


def test_full_pipeline_produces_all_final_artifacts(tmp_path):
    import asyncio

    from orchestrator.pipeline import run_pipeline
    from shared.contracts.pipeline_contract import ResearchRequest

    request = ResearchRequest(
        research_question="What are the effects of intermittent fasting on cognitive performance?",
        corpus_size=6,
    )

    async def run():
        result = None
        async for event in run_pipeline(request, output_root=tmp_path):
            assert "type" in event
            if event["type"] == "result":
                result = event["result"]
        return result

    result = asyncio.run(run())

    assert result is not None
    run_dir = Path(result.run_directory)
    assert run_dir.exists()

    # Every stage persisted its own artifact.
    assert (run_dir / "00_request.json").exists()
    assert (run_dir / "01_discovery" / "result.json").exists()
    assert (run_dir / "02_writing" / "result.json").exists()
    assert (run_dir / "03_verification" / "result.json").exists()
    assert (run_dir / "04_quality_assurance" / "result.json").exists()

    # Final consolidated artifacts.
    final_dir = run_dir / "final"
    assert (final_dir / "draft.md").exists()
    assert (final_dir / "quality_report.md").exists()
    assert (final_dir / "validation_report.md").exists()
    assert (final_dir / "references.md").exists()
    assert (run_dir / "metadata.json").exists()

    # Sanity on the actual content, not just that files exist.
    assert 1 <= len(result.discovery.selected_papers) <= 9
    assert result.writing.draft_metadata.model_name == DEFAULT_MODEL
    assert 0.0 <= result.quality_assurance.scores.overall <= 5.0
    assert result.timings.discovery_seconds > 0
    assert result.timings.writing_seconds > 0
    assert result.timings.verification_seconds >= 0
    assert result.timings.quality_assurance_seconds >= 0
