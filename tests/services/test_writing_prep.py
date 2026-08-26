import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from shared.contracts.discovery_contract import (
    DiscoveryRequest, DiscoveryResult, PaperMetadata, ResearchGap, NoveltyAssessment,
)
from writing_prep import build_outline, write_literature_files


def _sample_discovery() -> DiscoveryResult:
    return DiscoveryResult(
        research_request=DiscoveryRequest(research_question="Q?", corpus_size=6),
        research_interpretation="interp",
        search_queries={"keyword": "x"},
        sources_searched=["OpenAlex"],
        selected_papers=[
            PaperMetadata(id=1, title="Paper One", abstract="Abstract text one.", has_abstract=True),
            PaperMetadata(id=2, title="Paper Two", has_abstract=False),
        ],
        field_overview="overview",
        limitations="none",
        research_gaps=[ResearchGap(
            title="Gap About Something", gap_type="methodological", impact="high",
            description="desc", evidence="evi", supporting_paper_ids=[1],
            research_questions=["Q1?"],
        )],
        novelty_analysis=NoveltyAssessment(
            novelty_summary="summary", confidence="medium", caveats="caveat",
        ),
        confidence_notes="notes",
    )


def test_build_outline_includes_gap_titles_and_required_sections():
    outline = build_outline(_sample_discovery())
    lines = outline.splitlines()
    assert sum(1 for line in lines if line.startswith("# ")) == 1  # exactly one root heading
    assert "## Introduction" in outline
    assert "### Gap About Something" in outline
    assert "References" not in outline  # added separately by the writer, not the outline


def test_write_literature_files_skips_papers_without_abstract(tmp_path):
    written = write_literature_files(_sample_discovery(), tmp_path)
    assert written == 1
    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "evidence_depth: abstract" in content
    assert "Abstract text one." in content
