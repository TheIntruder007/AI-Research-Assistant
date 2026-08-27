"""Fast unit tests for the FastAPI backend, with the pipeline faked out."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from orchestrator import api as orchestrator_api  # noqa: E402
from shared.contracts.discovery_contract import (  # noqa: E402
    DiscoveryRequest, DiscoveryResult, NoveltyAssessment, PaperMetadata, ResearchGap,
)
from shared.contracts.pipeline_contract import PipelineResult, ResearchRequest, StageTimings  # noqa: E402
from shared.contracts.qa_contract import QualityAssuranceResult, QualityScores  # noqa: E402
from shared.contracts.verification_contract import VerificationResult  # noqa: E402
from shared.contracts.writing_contract import DraftMetadata, WritingResult  # noqa: E402
from orchestrator.pipeline import PipelineError  # noqa: E402


def _fake_pipeline_result() -> PipelineResult:
    discovery = DiscoveryResult(
        research_request=DiscoveryRequest(research_question="Q?", corpus_size=6),
        research_interpretation="interp", search_queries={"keyword": "x"},
        sources_searched=["OpenAlex"],
        selected_papers=[PaperMetadata(id=1, title="Paper One", has_abstract=True, abstract="abstract")],
        field_overview="overview", limitations="none",
        research_gaps=[ResearchGap(
            title="Gap", gap_type="methodological", impact="high",
            description="desc", evidence="evi", supporting_paper_ids=[1], research_questions=["Q1?"],
        )],
        novelty_analysis=NoveltyAssessment(novelty_summary="summary", confidence="medium", caveats="caveat"),
        confidence_notes="notes",
    )
    writing = WritingResult(
        research_outline="# Q\n## Introduction", research_draft_markdown="draft [1].",
        reference_candidates=['[1] A. Author, "Paper One," 2020.'],
        run_directory="/tmp/writing-run",
        draft_metadata=DraftMetadata(
            model_name="qwen3.5:9b", run_id="run1", generated_at="2026-08-27T00:00:00Z",
            sections_written=2, papers_cited=1,
        ),
    )
    verification = VerificationResult(
        validated_draft_markdown="draft [1].",
        validation_report="# Citation Verification Report\n",
    )
    qa = QualityAssuranceResult(
        final_draft_markdown="draft [1].", final_references=['[1] A. Author, "Paper One," 2020.'],
        final_validation_report="# Citation Verification Report\n",
        quality_report_markdown="# Quality Assurance Report\n",
        scores=QualityScores(
            citation_integrity=5.0, claim_source_alignment=5.0,
            process_control=5.0, literature_coverage=5.0, overall=5.0,
        ),
    )
    return PipelineResult(
        run_id="run1", run_directory="/tmp/run1",
        request=ResearchRequest(research_question="Q?"),
        discovery=discovery, writing=writing, verification=verification, quality_assurance=qa,
        timings=StageTimings(
            discovery_seconds=1.0, writing_seconds=1.0,
            verification_seconds=1.0, quality_assurance_seconds=1.0,
        ),
    )


async def _fake_run_pipeline_success(request, output_root=None):
    yield {"type": "progress", "message": "working"}
    yield {"type": "result", "result": _fake_pipeline_result()}


async def _fake_run_pipeline_failure(request, output_root=None):
    yield {"type": "progress", "message": "working"}
    raise PipelineError("Research Discovery Service produced no result.")


@pytest.fixture
def client():
    return TestClient(orchestrator_api.app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_research_endpoint_returns_pipeline_result(client, monkeypatch):
    monkeypatch.setattr(orchestrator_api, "run_pipeline", _fake_run_pipeline_success)
    response = client.post("/research", json={"research_question": "What is X?"})
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run1"
    assert body["quality_assurance"]["scores"]["overall"] == 5.0


def test_research_endpoint_rejects_invalid_request(client):
    response = client.post("/research", json={
        "research_question": "Q?", "target_format": "Other",
    })
    assert response.status_code == 422


def test_research_endpoint_returns_502_on_pipeline_error(client, monkeypatch):
    monkeypatch.setattr(orchestrator_api, "run_pipeline", _fake_run_pipeline_failure)
    response = client.post("/research", json={"research_question": "What is X?"})
    assert response.status_code == 502
