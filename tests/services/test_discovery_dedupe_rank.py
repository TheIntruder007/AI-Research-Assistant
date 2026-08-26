import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-discovery"))

from discovery.models import Paper
from discovery.pipeline import dedupe, rank


def test_dedupe_merges_by_doi_across_sources():
    a = Paper(title="Deep Learning for X", doi="10.1/abc", source="OpenAlex", citations=5)
    b = Paper(title="Deep Learning for X (preprint)", doi="10.1/abc", source="arXiv",
              abstract="An abstract only arXiv has.")
    merged = dedupe([a, b])
    assert len(merged) == 1
    assert merged[0].abstract == "An abstract only arXiv has."
    assert merged[0].citations == 5
    assert "OpenAlex" in merged[0].source and "arXiv" in merged[0].source


def test_dedupe_merges_by_normalized_title_when_no_doi():
    a = Paper(title="A Survey of Machine Learning Methods for Tabular Data", source="S2")
    b = Paper(title="a survey of machine learning methods for tabular data", source="PubMed")
    merged = dedupe([a, b])
    assert len(merged) == 1


def test_dedupe_keeps_distinct_papers_with_short_generic_titles():
    # Titles below NORMALIZED_TITLE_MIN don't title-match, so distinct papers
    # sharing a stock title must NOT collapse into one.
    a = Paper(title="Editorial", source="S2")
    b = Paper(title="Editorial", source="PubMed")
    merged = dedupe([a, b])
    assert len(merged) == 2


def test_rank_prefers_papers_with_abstracts_and_higher_relevance():
    with_abstract = Paper(title="A", abstract="text", relevance_rank=5, citations=0)
    without_abstract = Paper(title="B", abstract=None, relevance_rank=0, citations=0)
    ranked = rank([without_abstract, with_abstract], per_source_limit=40)
    assert ranked[0] is with_abstract
