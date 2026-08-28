"""Tests for the under-generation detection added in DECISIONS.md D-026:
a section with real, substantive, genuinely-evidenced content that still
falls short of its planned minimum length must be flagged and revised —
distinct from "no evidence available" (which is not a failure at all)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.modules.section_auditor import audit_section  # noqa: E402
from writing.schemas import (  # noqa: E402
    CitationInfo, SectionDraft, SectionWritingContext, TagIndexItem,
)

_CITATION = CitationInfo(
    citation_key="a2024", in_text_citation="(A, 2024)",
    narrative_citation="A (2024)", reference_entry="A. (2024). Title.",
)


def _context(min_words=None, max_words=None) -> SectionWritingContext:
    direct_points = [
        TagIndexItem(
            tag_id="TAG-2", paper_id="P001", point_id="P001-POINT-01", content="A finding.",
            content_type="empirical_finding", stance="neutral", certainty="supported",
            citation=_CITATION,
        )
    ]
    return SectionWritingContext(
        tag_id="TAG-2", title="Literature Review", outline_path=["Q", "Literature Review"],
        depth=1, writing_mode="leaf_section", direct_points=direct_points, ancestor_context=[],
        child_summaries=[], allowed_paper_ids=["P001"], allowed_point_ids=["P001-POINT-01"],
        citations={"P001": _CITATION}, sibling_titles=[], prohibited_topics=[],
        min_words=min_words, max_words=max_words,
    )


def test_section_below_minimum_fails_the_audit_and_is_flagged():
    context = _context(min_words=100)
    draft = SectionDraft(
        tag_id="TAG-2", content="A short finding [@P001].",  # well under 100 words
        cited_paper_ids=["P001"], used_point_ids=["P001-POINT-01"],
    )
    audit = audit_section(draft, context)
    assert audit.below_minimum_length is True
    assert audit.passed is False
    assert any("shorter than its planned scope" in i for i in audit.revision_instructions)


def test_section_meeting_minimum_passes():
    context = _context(min_words=5)
    draft = SectionDraft(
        tag_id="TAG-2", content="A short finding about the evidence [@P001].",
        cited_paper_ids=["P001"], used_point_ids=["P001-POINT-01"],
    )
    audit = audit_section(draft, context)
    assert audit.below_minimum_length is False
    assert audit.passed is True


def test_no_minimum_configured_never_flags_length():
    context = _context(min_words=None)
    draft = SectionDraft(
        tag_id="TAG-2", content="x [@P001].", cited_paper_ids=["P001"],
        used_point_ids=["P001-POINT-01"],
    )
    audit = audit_section(draft, context)
    assert audit.below_minimum_length is False


def test_insufficient_evidence_placeholder_is_not_flagged_as_under_generation():
    """A genuine "no evidence" placeholder must never be treated as an
    under-generation failure to fix — there is nothing to expand."""
    context = SectionWritingContext(
        tag_id="TAG-2", title="Literature Review", outline_path=["Q", "Literature Review"],
        depth=1, writing_mode="leaf_section", direct_points=[], ancestor_context=[],
        child_summaries=[], allowed_paper_ids=[], allowed_point_ids=[],
        citations={}, sibling_titles=[], prohibited_topics=[], min_words=200,
    )
    draft = SectionDraft(
        tag_id="TAG-2", content="*Insufficient evidence is available for this section.*",
        cited_paper_ids=[], used_point_ids=[],
    )
    audit = audit_section(draft, context)
    assert audit.below_minimum_length is False


def test_max_words_still_flags_genuinely_excessive_length():
    context = _context(max_words=5)
    draft = SectionDraft(
        tag_id="TAG-2",
        content="This is a much longer finding than the configured maximum allows [@P001].",
        cited_paper_ids=["P001"], used_point_ids=["P001-POINT-01"],
    )
    audit = audit_section(draft, context)
    assert not audit.passed
    assert any("exceeds max_words" in item for item in audit.out_of_scope_content)
