import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.contracts.discovery_contract import (
    DiscoveryRequest, DiscoveryResult, PaperMetadata, ResearchGap, NoveltyAssessment,
)


def test_discovery_request_validates_paper_count_range():
    req = DiscoveryRequest(research_question="How does X affect Y?", corpus_size=8)
    assert req.corpus_size == 8


def test_discovery_result_round_trip():
    result = DiscoveryResult(
        research_request=DiscoveryRequest(research_question="Q", corpus_size=6),
        research_interpretation="Interpreted question",
        search_queries={"keyword": "x"},
        sources_searched=["OpenAlex"],
        selected_papers=[PaperMetadata(id=1, title="Paper 1")],
        field_overview="Overview",
        limitations="None noted",
        research_gaps=[ResearchGap(
            title="Gap 1", gap_type="methodological", impact="high",
            description="desc", evidence="evi", supporting_paper_ids=[1],
            research_questions=["Q1?"],
        )],
        novelty_analysis=NoveltyAssessment(
            novelty_summary="summary", confidence="medium", caveats="caveat",
        ),
        confidence_notes="notes",
    )
    dumped = result.model_dump_json()
    restored = DiscoveryResult.model_validate_json(dumped)
    assert restored.selected_papers[0].title == "Paper 1"
