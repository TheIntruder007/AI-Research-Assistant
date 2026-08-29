"""Regression test for DECISIONS.md D-028: `audit_full_review()`'s heading-
sequence check compared the outline's own tag tree against the ACTUAL
rendered markdown, which (since D-026) also contains real `## Introduction`/
`## Conclusion` headings that are not part of the outline's tag tree at all
(they are bookend sections — see review_writer.py). The comparison never
accounted for those two extra headings, so it failed unconditionally on
every real run (confirmed in `PAPER_OUTPUT_FINAL_DIAGNOSTIC.md`: 4 of 4 real
runs reproduced the identical `heading_errors`), which in turn made
`draft_status: "complete"` structurally unreachable regardless of paper
quality (`service.py`'s draft_status falls back to "partial" whenever
`not result.succeeded`, and `result.succeeded` depends on this check).

This test builds the outline the same way the real pipeline does
(`parse_outline` + `build_tag_tree` from the real outline text
`writing_prep.py::build_outline()` produces) and renders a full review via
the real `assemble_review()`, then feeds it into the real `audit_full_review()`
— reproducing the exact bug end-to-end, not a synthetic shortcut.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.modules.outline_parser import parse_outline  # noqa: E402
from writing.modules.review_assembler import assemble_review  # noqa: E402
from writing.modules.review_auditor import audit_full_review  # noqa: E402
from writing.modules.tag_tree import build_tag_tree  # noqa: E402
from writing.schemas import CitationInfo, SectionDraft, TagDefinition  # noqa: E402

_OUTLINE = (
    "# What is the impact of remote work on employee productivity?\n"
    "## Background\n## Literature Review\n## Discussion\n## Limitations\n"
)


def _build_tree_and_definitions():
    headings = parse_outline(_OUTLINE)
    tree = build_tag_tree(headings)
    definitions = [
        TagDefinition(
            tag_id=node.tag_id, title=node.title, normalized_label=node.title,
            description="d", include_when=["x"], exclude_when=["y"],
            parent_id=node.parent_id, child_ids=node.child_ids, depth=node.depth,
            node_type="root" if node.tag_id == "TAG-ROOT" else "content",
        )
        for node in tree
    ]
    return tree, definitions


def _draft(tag_id: str) -> SectionDraft:
    return SectionDraft(
        tag_id=tag_id, content=f"Real prose for {tag_id} discussing the evidence [@P001].",
        cited_paper_ids=["P001"], used_point_ids=[],
    )


_CITATION = CitationInfo(
    citation_key="a2024", in_text_citation="[1]",
    narrative_citation="[1]", reference_entry="Author, A. (2024). Title.",
)


def _assemble_and_audit(*, introduction_content="Real introduction prose [@P001].",
                         conclusion_content="Real conclusion prose [@P001]."):
    tree, definitions = _build_tree_and_definitions()
    drafts = {node.tag_id: _draft(node.tag_id) for node in tree[1:]}
    introduction = SectionDraft(
        tag_id="INTRODUCTION", content=introduction_content,
        cited_paper_ids=["P001"] if introduction_content.strip() else [], used_point_ids=[],
    )
    conclusion = SectionDraft(
        tag_id="CONCLUSION", content=conclusion_content,
        cited_paper_ids=["P001"] if conclusion_content.strip() else [], used_point_ids=[],
    )
    citations = {"P001": _CITATION}
    review = assemble_review(
        tree, definitions, drafts, introduction, conclusion, citations,
        citation_style="ieee",
    )
    audit = audit_full_review(
        review, tree, definitions, drafts, introduction, conclusion, citations,
        citation_style="ieee",
    )
    return review, audit


def test_real_bookend_headings_no_longer_trip_the_heading_sequence_check():
    """Reproduces the exact real-run bug end-to-end: a normal, fully valid
    review with real Introduction/Conclusion prose used to always fail this
    check. It must now pass."""
    review, audit = _assemble_and_audit()
    assert "## Introduction" in review.markdown
    assert "## Conclusion" in review.markdown
    assert audit.heading_errors == []
    assert audit.passed, audit.revision_instructions


def test_chinese_bookend_headings_are_also_excluded():
    tree, definitions = _build_tree_and_definitions()
    drafts = {node.tag_id: _draft(node.tag_id) for node in tree[1:]}
    introduction = SectionDraft(
        tag_id="INTRODUCTION", content="真实的引言内容 [@P001]。", cited_paper_ids=["P001"], used_point_ids=[],
    )
    conclusion = SectionDraft(
        tag_id="CONCLUSION", content="真实的结论内容 [@P001]。", cited_paper_ids=["P001"], used_point_ids=[],
    )
    citations = {"P001": _CITATION}
    review = assemble_review(
        tree, definitions, drafts, introduction, conclusion, citations,
        citation_style="ieee", output_language="zh",
    )
    assert "## 引言" in review.markdown
    assert "## 结论" in review.markdown
    audit = audit_full_review(
        review, tree, definitions, drafts, introduction, conclusion, citations,
        citation_style="ieee",
    )
    assert audit.heading_errors == []


def test_a_missing_outline_section_is_still_caught():
    """The fix must not weaken real section-presence enforcement — only the
    bookends are excluded from the heading-sequence comparison, not the
    outline's own sections. assemble_review() itself refuses to assemble a
    review missing a required section's draft, so this is exercised via
    audit_full_review()'s own `missing_sections` computation directly
    (mirroring how graph.py actually calls it — against `drafts`, not
    against what assemble_review() would have raised on)."""
    tree, definitions = _build_tree_and_definitions()
    # Drop one real outline section's draft entirely.
    drafts = {node.tag_id: _draft(node.tag_id) for node in tree[1:] if node.title != "Discussion"}
    full_drafts = {node.tag_id: _draft(node.tag_id) for node in tree[1:]}
    introduction = SectionDraft(
        tag_id="INTRODUCTION", content="Real introduction [@P001].",
        cited_paper_ids=["P001"], used_point_ids=[],
    )
    conclusion = SectionDraft(
        tag_id="CONCLUSION", content="Real conclusion [@P001].",
        cited_paper_ids=["P001"], used_point_ids=[],
    )
    citations = {"P001": _CITATION}
    # Assemble with the FULL set (assemble_review requires every draft to
    # exist) to get a realistic rendered document, then audit against the
    # incomplete `drafts` dict — exactly what graph.py does when a section
    # failed and was excluded from the drafts passed to the audit.
    review = assemble_review(
        tree, definitions, full_drafts, introduction, conclusion, citations, citation_style="ieee",
    )
    audit = audit_full_review(
        review, tree, definitions, drafts, introduction, conclusion, citations,
        citation_style="ieee",
    )
    assert not audit.passed
    assert "TAG-3" in audit.missing_sections


def test_a_genuinely_reordered_heading_is_still_caught():
    """Only the bookend headings are excluded from the sequence comparison —
    a real outline section rendered out of order must still be caught."""
    review, audit = _assemble_and_audit()
    reordered_markdown = review.markdown.replace(
        "## Background", "## TEMP-SWAP", 1
    ).replace("## Discussion", "## Background", 1).replace("## TEMP-SWAP", "## Discussion", 1)
    tree, definitions = _build_tree_and_definitions()
    drafts = {node.tag_id: _draft(node.tag_id) for node in tree[1:]}
    introduction = SectionDraft(
        tag_id="INTRODUCTION", content="Real introduction [@P001].",
        cited_paper_ids=["P001"], used_point_ids=[],
    )
    conclusion = SectionDraft(
        tag_id="CONCLUSION", content="Real conclusion [@P001].",
        cited_paper_ids=["P001"], used_point_ids=[],
    )
    citations = {"P001": _CITATION}
    from writing.schemas import ReviewDocument
    reordered_review = ReviewDocument(
        markdown=reordered_markdown, cited_paper_ids=review.cited_paper_ids,
        references=review.references,
    )
    audit = audit_full_review(
        reordered_review, tree, definitions, drafts, introduction, conclusion, citations,
        citation_style="ieee",
    )
    assert not audit.passed
    assert audit.heading_errors == ["final heading sequence does not match the user outline"]


def test_blank_bookend_is_omitted_from_markdown_and_does_not_trip_heading_check():
    """assemble_review() only renders a bookend heading when its content is
    non-blank (see review_assembler.py) — a whitespace-only Introduction
    (SectionDraft requires min_length=1, so "blank" means whitespace-only,
    not a literal empty string) must not leave a dangling "## Introduction"
    heading with nothing under it, and must still not trip the (now
    bookend-excluding) heading-sequence check."""
    review, audit = _assemble_and_audit(introduction_content=" ")
    assert "## Introduction" not in review.markdown
    assert audit.heading_errors == []
