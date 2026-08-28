"""Regression tests for DECISIONS.md D-026's "bookend audit investigation":
a real live-model run reproduced (with `diagnose_bookend.py`, see the
analytics doc) the actual cause of the Introduction/Conclusion bookend
sections being discarded so often — NOT a genuine evidence-boundary
violation, but the model writing a range/list shorthand placeholder like
`[P003-P006]` instead of repeating the placeholder for each paper
(`[@P003][@P004][@P005][@P006]`). The old `_CITATION` regex required the
bracket to close immediately after the digits, so `[P003-P006]` matched
NOTHING at all — the section's own `cited_paper_ids` field (correctly
listing P003-P006) then looked like it named papers the prose never cited,
failing the audit and discarding an otherwise fully evidence-grounded
section.

Fix: `_CITATION` now recognizes an optional range suffix and
`_expand_citation_match()` expands it to every ID it covers, used by both
`extract_cited_paper_ids()` (audit/provenance) and `format_citations()`
(final rendering) — the same "prompt fix + tolerant parsing" pattern D-021
already established for the missing-"@" case.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.modules.citation_formatter import (  # noqa: E402
    extract_cited_paper_ids, format_citations,
)
from writing.modules.section_auditor import audit_section  # noqa: E402
from writing.schemas import (  # noqa: E402
    CitationInfo, SectionDraft, SectionWritingContext, TagIndexItem,
)


def _citation(key: str) -> CitationInfo:
    return CitationInfo(
        citation_key=key, in_text_citation=f"({key}, 2024)",
        narrative_citation=f"{key} (2024)", reference_entry=f"{key}. (2024). Title.",
    )


def test_range_shorthand_expands_to_every_covered_id():
    assert extract_cited_paper_ids("Evidence spans several studies [P003-P006].") == [
        "P003", "P004", "P005", "P006",
    ]


def test_range_shorthand_with_at_symbols_also_expands():
    assert extract_cited_paper_ids("See [@P003-@P006] for details.") == [
        "P003", "P004", "P005", "P006",
    ]


def test_single_placeholder_is_unaffected():
    assert extract_cited_paper_ids("Finding one [@P001]. Finding two [P002].") == [
        "P001", "P002",
    ]


def test_mismatched_digit_width_range_is_not_guessed_as_sequential():
    # "P003" (3 digits) to "P0006" (4 digits) is not a genuine range — treat
    # the two ends literally rather than silently guessing a numeric span.
    assert extract_cited_paper_ids("[P003-P0006]") == ["P003", "P0006"]


def test_absurdly_wide_or_reversed_range_falls_back_to_literal_endpoints():
    assert extract_cited_paper_ids("[P010-P003]") == ["P010", "P003"]  # reversed
    assert extract_cited_paper_ids("[P001-P999]") == ["P001", "P999"]  # 998-ID span


def test_reproduction_real_bug_range_shorthand_no_longer_fails_the_audit():
    """Reproduces the exact real-run scenario found via `diagnose_bookend.py`
    against a live model run: content cites a range shorthand covering only
    allowed papers, and cited_paper_ids correctly lists every one of them —
    this must pass, not be discarded as "citing outside its evidence"."""
    allowed = ["P003", "P004", "P005", "P006"]
    context = SectionWritingContext(
        tag_id="TAG-2", title="Literature Review", outline_path=["Q", "Literature Review"],
        depth=1, writing_mode="leaf_section",
        direct_points=[
            TagIndexItem(
                tag_id="TAG-2", paper_id=pid, point_id=f"{pid}-POINT-01", content="A finding.",
                content_type="empirical_finding", stance="neutral", certainty="supported",
                citation=_citation(pid),
            )
            for pid in allowed
        ],
        ancestor_context=[], child_summaries=[], allowed_paper_ids=allowed,
        allowed_point_ids=[f"{pid}-POINT-01" for pid in allowed],
        citations={pid: _citation(pid) for pid in allowed},
        sibling_titles=[], prohibited_topics=[],
    )
    draft = SectionDraft(
        tag_id="TAG-2",
        content="Flexibility alone is insufficient without tailored support [P003-P006].",
        cited_paper_ids=["P003", "P004", "P005", "P006"],
        used_point_ids=[f"{pid}-POINT-01" for pid in allowed],
    )
    audit = audit_section(draft, context)
    assert audit.passed, audit.revision_instructions
    assert "citation placeholders do not match cited_paper_ids" not in audit.out_of_scope_content


def test_format_citations_renders_every_paper_in_the_range_not_just_one():
    citations = {pid: _citation(pid) for pid in ["P003", "P004", "P005", "P006"]}
    rendered = format_citations("Evidence [P003-P006] converges.", citations)
    assert "(P003, 2024)" in rendered
    assert "(P004, 2024)" in rendered
    assert "(P005, 2024)" in rendered
    assert "(P006, 2024)" in rendered
