import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.contracts.discovery_contract import (
    DiscoveryRequest, DiscoveryResult, NoveltyAssessment, PaperMetadata, ResearchGap,
)
from shared.contracts.writing_contract import DraftMetadata, WritingResult
from shared.contracts.verification_contract import ReferenceCheck, VerificationResult
from shared.contracts.qa_contract import QualityAssuranceRequest

# A bare `import service` would collide with the other pipeline services'
# own service.py modules — see the same fix in test_writing_pipeline_integration.py.
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "research_qa_service", ROOT / "services" / "quality-assurance" / "service.py",
)
service = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(service)


def _discovery() -> DiscoveryResult:
    return DiscoveryResult(
        research_request=DiscoveryRequest(research_question="Q?", corpus_size=6),
        research_interpretation="interp",
        search_queries={"keyword": "x"},
        sources_searched=["OpenAlex"],
        selected_papers=[
            PaperMetadata(
                id=1, title="Fasting Improves Memory in Adults", doi="10.1/real",
                venue="Journal X", has_abstract=True,
                abstract="A randomized trial found intermittent fasting improved working memory in adults.",
            ),
        ],
        field_overview="overview",
        limitations="Only one study reviewed.",
        research_gaps=[ResearchGap(
            title="Gap", gap_type="methodological", impact="high",
            description="desc", evidence="evi", supporting_paper_ids=[1],
            research_questions=["Q1?"],
        )],
        novelty_analysis=NoveltyAssessment(novelty_summary="summary", confidence="medium", caveats="caveat"),
        confidence_notes="notes",
    )


def _writing(errors=None, warnings=None) -> WritingResult:
    return WritingResult(
        research_outline="# Q\n## Introduction",
        research_draft_markdown="draft",
        reference_candidates=['[1] A. Author, "Fasting Improves Memory," Journal X, 2020, doi: 10.1/real.'],
        run_directory="/tmp/run",
        draft_metadata=DraftMetadata(
            model_name="qwen3.5:9b", run_id="run1", generated_at="2026-08-27T00:00:00Z",
            errors=errors or [], warnings=warnings or [],
        ),
    )


def _verification(markdown: str) -> VerificationResult:
    check = ReferenceCheck(
        reference_entry='[1] A. Author, "Fasting Improves Memory," Journal X, 2020, doi: 10.1/real.',
        doi="10.1/real", verified=True, verification_source="Crossref",
    )
    return VerificationResult(
        validated_draft_markdown=markdown,
        verified_references=[check],
        validation_report="# Citation Verification Report\n",
    )


def test_find_missing_citations_flags_uncited_empirical_claims():
    markdown = "## Introduction\n\nFasting improved memory scores by 20% in the trial.\n\n## References\n"
    missing = service.find_missing_citations(markdown)
    assert len(missing) == 1
    assert "20%" in missing[0].sentence


def test_find_missing_citations_ignores_cited_sentences():
    markdown = "## Introduction\n\nFasting improved memory scores by 20% in the trial [1].\n\n## References\n"
    assert service.find_missing_citations(markdown) == []


def test_build_reference_profiles_matches_by_doi():
    discovery = _discovery()
    verification = _verification("draft")
    profiles = service.build_reference_profiles(discovery, verification)
    assert 1 in profiles
    assert "memori" in profiles[1] or "memory" in profiles[1] or any("memor" in t for t in profiles[1])


def test_find_unsupported_claims_flags_low_overlap_and_skips_unmatched():
    discovery = _discovery()
    verification = _verification("draft")
    profiles = service.build_reference_profiles(discovery, verification)

    aligned = "## Introduction\n\nIntermittent fasting improved memory performance in a randomized trial [1].\n\n## References\n"
    assert service.find_unsupported_claims(aligned, profiles) == []

    misaligned = "## Introduction\n\nQuantum computing will revolutionize cryptography entirely [1].\n\n## References\n"
    unsupported = service.find_unsupported_claims(misaligned, profiles)
    assert len(unsupported) == 1
    assert unsupported[0].citation_numbers == [1]

    # A citation number with no matched profile must not be flagged as unsupported.
    unmatched = "## Introduction\n\nSome unrelated claim about a topic entirely elsewhere [2].\n\n## References\n"
    assert service.find_unsupported_claims(unmatched, profiles) == []


def test_find_missing_sections_reports_absent_required_headings():
    markdown = "# Title\n## Introduction\n## Conclusion\n"
    missing = service.find_missing_sections(markdown)
    assert "## Literature Review" in missing
    assert "## Introduction" not in missing


def test_run_quality_assurance_produces_result_with_scores():
    markdown = (
        "## Introduction\n\nIntermittent fasting improved memory performance in a randomized trial [1].\n\n"
        "## Literature Review\n\ncontent\n\n## Research Gap\n\ncontent\n\n"
        "## Proposed Novelty and Contribution\n\ncontent\n\n## Limitations\n\ncontent\n\n"
        "## Conclusion\n\ncontent\n\n## References\n\n"
        '[1] A. Author, "Fasting Improves Memory," Journal X, 2020, doi: 10.1/real.\n'
    )
    request = QualityAssuranceRequest(
        discovery=_discovery(), writing=_writing(), verification=_verification(markdown),
    )

    async def run():
        result = None
        async for event in service.run_quality_assurance(request):
            if event["type"] == "result":
                result = event["result"]
        return result

    result = asyncio.run(run())
    assert result.scores.overall > 0
    assert result.missing_sections == []
    assert result.unsupported_claims == []
    assert "Quality Assurance Report" in result.quality_report_markdown
    assert result.audit_metadata["run_id"] == "run1"
