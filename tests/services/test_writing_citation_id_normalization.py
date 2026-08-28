"""Regression tests for DECISIONS.md D-021: a real stress-test run reported
a section citing "papers outside its allowed evidence set" — but tracing
the actual run's artifacts (section_contexts/TAG-2.json,
section_audits/TAG-2.json) showed the model cited ONLY allowed papers
(P001, P003, P004, P005). The audit's own cited_paper_ids field values
were decorated with a literal "@" prefix (e.g. "@P001" instead of "P001"),
copied from the `[@P001]` prose placeholder syntax — a false-positive
detection bug, not a genuine evidence-boundary violation.

Fix: SectionDraft/SectionDraftContent normalize cited_paper_ids at the
schema boundary (writing/schemas.py), so every comparison downstream
(against allowed_paper_ids, against placeholder-extracted IDs) sees bare
IDs regardless of which decorated form a model happens to produce.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.modules.citation_formatter import extract_cited_paper_ids  # noqa: E402
from writing.modules.section_auditor import audit_section  # noqa: E402
from writing.schemas import (  # noqa: E402
    CitationInfo, SectionDraft, SectionDraftContent, SectionWritingContext, TagIndexItem,
)

_CITATION = CitationInfo(
    citation_key="a2024", in_text_citation="(A, 2024)",
    narrative_citation="A (2024)", reference_entry="A. (2024). Title.",
)


def _context(allowed_paper_ids: list[str]) -> SectionWritingContext:
    direct_points = [
        TagIndexItem(
            tag_id="TAG-2", paper_id=pid, point_id=f"{pid}-POINT-01", content="A finding.",
            content_type="empirical_finding", stance="neutral", certainty="supported",
            citation=_CITATION,
        )
        for pid in allowed_paper_ids
    ]
    return SectionWritingContext(
        tag_id="TAG-2", title="Literature Review", outline_path=["Q", "Literature Review"],
        depth=1, writing_mode="leaf_section", direct_points=direct_points, ancestor_context=[],
        child_summaries=[], allowed_paper_ids=allowed_paper_ids,
        allowed_point_ids=[f"{pid}-POINT-01" for pid in allowed_paper_ids],
        citations={pid: _CITATION for pid in allowed_paper_ids},
        sibling_titles=[], prohibited_topics=[],
    )


def test_at_prefixed_cited_paper_ids_are_normalized_on_section_draft():
    draft = SectionDraft(
        tag_id="TAG-2", content="Finding [@P001].",
        cited_paper_ids=["@P001", "@P003"], used_point_ids=[],
    )
    assert draft.cited_paper_ids == ["P001", "P003"]


def test_bracket_wrapped_cited_paper_ids_are_also_normalized():
    draft = SectionDraft(
        tag_id="TAG-2", content="Finding [@P001].",
        cited_paper_ids=["[@P001]"], used_point_ids=[],
    )
    assert draft.cited_paper_ids == ["P001"]


def test_already_bare_ids_are_unchanged():
    draft = SectionDraft(
        tag_id="TAG-2", content="Finding [@P001].",
        cited_paper_ids=["P001"], used_point_ids=[],
    )
    assert draft.cited_paper_ids == ["P001"]


def test_section_draft_content_normalizes_too():
    content = SectionDraftContent(
        content="Finding [@P001].", cited_paper_ids=["@P001"], used_point_ids=[],
    )
    assert content.cited_paper_ids == ["P001"]


def test_reproduction_real_bug_at_prefixed_ids_no_longer_fail_the_audit():
    """Reproduces the exact real-run scenario: the model cites only allowed
    papers in prose, but declares them with an "@" prefix in
    cited_paper_ids. Before the fix, this was misclassified as citing
    "papers outside the allowed list" for every single citation used."""
    allowed = ["P001", "P002", "P003", "P004", "P005"]
    context = _context(allowed)
    draft = SectionDraft(
        tag_id="TAG-2",
        content="Remote workers face challenges [@P001]. Teachers report burnout [@P004].",
        # The model echoed the "@" placeholder decoration into the
        # structured field — exactly as observed in the real failing run.
        cited_paper_ids=["@P001", "@P004"],
        used_point_ids=["P001-POINT-01", "P004-POINT-01"],
    )
    audit = audit_section(draft, context)
    assert audit.passed, audit.revision_instructions
    assert audit.invalid_paper_ids == []
    assert "citation placeholders do not match cited_paper_ids" not in audit.out_of_scope_content


def test_prose_placeholder_missing_at_symbol_is_still_extracted():
    """Mirror-image real bug (same stress-test pass, a different topic):
    the model correctly kept cited_paper_ids bare ("P002", "P001") but wrote
    prose placeholders without the "@" ("[P002]" instead of "[@P002]").
    Before this fix, extraction found zero placeholders, so a fully valid,
    in-scope citation looked like a placeholder/cited_paper_ids mismatch."""
    assert extract_cited_paper_ids("Finding one [P002]. Finding two [@P001].") == ["P002", "P001"]


def test_reproduction_real_bug_missing_at_symbol_no_longer_fails_the_audit():
    allowed = ["P001", "P002"]
    context = _context(allowed)
    draft = SectionDraft(
        tag_id="TAG-2",
        # Both placeholders are missing "@" — the exact real-run pattern.
        content="Diet affects brain plasticity [P002]. Obesity affects the gut-brain axis [P001].",
        cited_paper_ids=["P002", "P001"],
        used_point_ids=["P002-POINT-01", "P001-POINT-01"],
    )
    audit = audit_section(draft, context)
    assert audit.passed, audit.revision_instructions


def test_genuinely_out_of_scope_citation_is_still_correctly_rejected():
    """The normalization fix must not weaken real evidence-boundary
    enforcement — a paper genuinely outside the allowed list must still
    be caught, "@"-prefixed or not."""
    context = _context(["P001", "P004"])
    draft = SectionDraft(
        tag_id="TAG-2", content="Finding [@P001]. Unrelated finding [@P999].",
        cited_paper_ids=["P001", "P999"], used_point_ids=["P001-POINT-01"],
    )
    audit = audit_section(draft, context)
    assert not audit.passed
    assert audit.invalid_paper_ids == ["P999"]
    assert any("P999" in instruction for instruction in audit.revision_instructions)
