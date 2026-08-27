"""Fast unit tests for the orchestrator, with all four services faked out —
see tests/services/*_pipeline_integration.py and scripts/smoke_test_full_pipeline.py
for the real, slow, live-service coverage."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from orchestrator import pipeline as orchestrator_pipeline  # noqa: E402
from shared.contracts.discovery_contract import (  # noqa: E402
    DiscoveryRequest, DiscoveryResult, NoveltyAssessment, PaperMetadata, ResearchGap,
)
from shared.contracts.pipeline_contract import ResearchRequest  # noqa: E402
from shared.contracts.qa_contract import QualityAssuranceResult, QualityScores  # noqa: E402
from shared.contracts.verification_contract import VerificationResult  # noqa: E402
from shared.contracts.writing_contract import DraftMetadata, WritingResult  # noqa: E402


def _fake_discovery_result() -> DiscoveryResult:
    return DiscoveryResult(
        research_request=DiscoveryRequest(research_question="Q?", corpus_size=6),
        research_interpretation="interp", search_queries={"keyword": "x"},
        sources_searched=["OpenAlex"],
        selected_papers=[PaperMetadata(id=1, title="Paper One", doi="10.1/x", has_abstract=True, abstract="abstract")],
        field_overview="overview", limitations="none",
        research_gaps=[ResearchGap(
            title="Gap", gap_type="methodological", impact="high",
            description="desc", evidence="evi", supporting_paper_ids=[1], research_questions=["Q1?"],
        )],
        novelty_analysis=NoveltyAssessment(novelty_summary="summary", confidence="medium", caveats="caveat"),
        confidence_notes="notes",
    )


def _fake_writing_result() -> WritingResult:
    return WritingResult(
        research_outline="# Q\n## Introduction", research_draft_markdown="draft body [1].",
        reference_candidates=['[1] A. Author, "Paper One," 2020, doi: 10.1/x.'],
        run_directory="/tmp/writing-run",
        draft_metadata=DraftMetadata(
            model_name="qwen3.5:9b", run_id="writing-run-1", generated_at="2026-08-27T00:00:00Z",
            sections_written=2, papers_cited=1,
        ),
    )


def _fake_verification_result() -> VerificationResult:
    return VerificationResult(
        validated_draft_markdown="draft body [1].",
        verified_references=[], invalid_references=[], unverifiable_references=[],
        validation_report="# Citation Verification Report\n",
    )


def _fake_qa_result() -> QualityAssuranceResult:
    return QualityAssuranceResult(
        final_draft_markdown="draft body [1].",
        final_references=['[1] A. Author, "Paper One," 2020, doi: 10.1/x.'],
        final_validation_report="# Citation Verification Report\n",
        quality_report_markdown="# Quality Assurance Report\n",
        scores=QualityScores(
            citation_integrity=5.0, claim_source_alignment=5.0,
            process_control=5.0, literature_coverage=5.0, overall=5.0,
        ),
    )


async def _fake_run_discovery(request):
    yield {"type": "status", "message": "searching"}
    yield {"type": "result", "result": _fake_discovery_result()}


async def _fake_run_writing(request, output_root=None):
    yield {"type": "status", "stage": "write", "state": "running", "message": "writing"}
    yield {"type": "result", "result": _fake_writing_result()}


async def _fake_run_verification(request):
    yield {"type": "status", "stage": "verify", "state": "running", "message": "verifying"}
    yield {"type": "result", "result": _fake_verification_result()}


async def _fake_run_qa(request):
    yield {"type": "status", "stage": "audit", "state": "running", "message": "auditing"}
    yield {"type": "result", "result": _fake_qa_result()}


@pytest.fixture(autouse=True)
def _patch_services(monkeypatch):
    monkeypatch.setattr(orchestrator_pipeline.discovery_service, "run_discovery", _fake_run_discovery)
    monkeypatch.setattr(orchestrator_pipeline.writing_service, "run_writing", _fake_run_writing)
    monkeypatch.setattr(orchestrator_pipeline.verification_service, "run_verification", _fake_run_verification)
    monkeypatch.setattr(orchestrator_pipeline.qa_service, "run_quality_assurance", _fake_run_qa)


def test_run_pipeline_produces_result_and_persists_artifacts(tmp_path):
    request = ResearchRequest(research_question="What is X?", corpus_size=6)

    async def run():
        events = []
        result = None
        async for event in orchestrator_pipeline.run_pipeline(request, output_root=tmp_path):
            if event["type"] == "result":
                result = event["result"]
            else:
                events.append(event)
        return events, result

    events, result = asyncio.run(run())

    assert result is not None
    assert result.quality_assurance.scores.overall == 5.0
    assert Path(result.run_directory).is_dir()
    assert (Path(result.run_directory) / "00_request.json").exists()
    assert (Path(result.run_directory) / "01_discovery" / "result.json").exists()
    assert (Path(result.run_directory) / "final" / "draft.md").exists()
    assert (Path(result.run_directory) / "final" / "draft.md").read_text(encoding="utf-8") == "draft body [1]."

    metadata = json.loads((Path(result.run_directory) / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["overall_quality_score"] == 5.0

    # Standardized progress events carry the required fields.
    stage_events = [e for e in events if e.get("stage") == "discovery"]
    assert stage_events
    for event in stage_events:
        assert set(event) >= {"run_id", "stage", "service", "status", "emoji", "title", "message", "details", "timestamp"}


def test_research_request_requires_format_other_name_when_format_is_other():
    with pytest.raises(ValueError):
        ResearchRequest(research_question="Q?", target_format="Other")
    # Valid when the name is supplied.
    ResearchRequest(research_question="Q?", target_format="Other", format_other_name="Custom Style")


def test_run_pipeline_raises_if_a_stage_yields_no_result(tmp_path, monkeypatch):
    async def _empty_discovery(request):
        yield {"type": "status", "message": "nothing"}
        return

    monkeypatch.setattr(orchestrator_pipeline.discovery_service, "run_discovery", _empty_discovery)
    request = ResearchRequest(research_question="What is X?", corpus_size=6)

    async def run():
        async for _ in orchestrator_pipeline.run_pipeline(request, output_root=tmp_path):
            pass

    with pytest.raises(orchestrator_pipeline.PipelineError):
        asyncio.run(run())
