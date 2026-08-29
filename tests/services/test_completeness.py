"""Tests for the deterministic rendered-paper completeness validator."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from completeness import assess_completeness, required_section_titles  # noqa: E402

_OUTLINE = "# What are the effects of X on Y?\n## Background\n## Literature Review\n## Discussion\n## Limitations\n"


def _draft(introduction="Real introduction prose.", background="Background prose.",
           literature_review="Literature review prose.", discussion="Discussion prose.",
           limitations="Limitations prose.", conclusion="Real conclusion prose."):
    return (
        "# What are the effects of X on Y?\n\n"
        f"## Introduction\n\n{introduction}\n\n"
        f"## Background\n\n{background}\n\n"
        f"## Literature Review\n\n{literature_review}\n\n"
        f"## Discussion\n\n{discussion}\n\n"
        f"## Limitations\n\n{limitations}\n\n"
        f"## Conclusion\n\n{conclusion}\n\n"
        "## References\n\n- Smith, J. (2020).\n"
    )


def test_required_section_titles_includes_bookends_and_outline_sections():
    titles = required_section_titles(_OUTLINE)
    assert titles == ["Introduction", "Background", "Literature Review", "Discussion",
                       "Limitations", "Conclusion"]


def test_required_section_titles_uses_chinese_bookends_for_zh():
    titles = required_section_titles(_OUTLINE, output_language="zh")
    assert titles[0] == "引言"
    assert titles[-1] == "结论"


def test_all_valid_sections_report_complete():
    report = assess_completeness(_draft(), _OUTLINE)
    assert report.status == "complete"
    assert report.missing_sections == []
    assert report.blank_sections == []
    assert report.failed_sections == []
    assert report.evidence_limited_sections == []


def test_blank_introduction_is_detected_and_marks_partial():
    report = assess_completeness(_draft(introduction=""), _OUTLINE)
    assert "Introduction" in report.blank_sections
    assert report.status == "partial"


def test_whitespace_only_section_counts_as_blank():
    report = assess_completeness(_draft(discussion="   \n\n  "), _OUTLINE)
    assert "Discussion" in report.blank_sections


def test_missing_heading_is_detected_as_missing_not_blank():
    draft = _draft().replace("## Discussion\n\nDiscussion prose.\n\n", "")
    report = assess_completeness(draft, _OUTLINE)
    assert "Discussion" in report.missing_sections
    assert "Discussion" not in report.blank_sections


def test_error_placeholder_is_flagged_as_failed_not_valid_content():
    report = assess_completeness(
        _draft(limitations="*Section generation failed; no unsupported content was inserted.*"),
        _OUTLINE,
    )
    assert "Limitations" in report.failed_sections
    assert report.status == "partial"


def test_no_evidence_placeholder_is_flagged_evidence_limited_not_failed():
    report = assess_completeness(
        _draft(limitations="*Insufficient evidence is available for this section.*"),
        _OUTLINE,
    )
    assert "Limitations" in report.evidence_limited_sections
    assert "Limitations" not in report.failed_sections
    assert "Limitations" not in report.blank_sections
    # A legitimate evidence-limited section does not, by itself, break
    # completeness — see Fix 9 "Case B" / DECISIONS.md D-026.
    assert report.status == "complete"


def test_duplicate_section_heading_is_reported():
    draft = _draft() + "\n## Discussion\n\nA second, duplicate Discussion block.\n"
    report = assess_completeness(draft, _OUTLINE)
    assert "Discussion" in report.duplicate_sections


def test_both_bookends_broken_marks_the_whole_draft_failed():
    report = assess_completeness(_draft(introduction="", conclusion=""), _OUTLINE)
    assert report.status == "failed"


def test_every_required_section_broken_marks_failed():
    report = assess_completeness(
        _draft(introduction="", background="", literature_review="", discussion="",
               limitations="", conclusion=""),
        _OUTLINE,
    )
    assert report.status == "failed"


def test_single_non_anchor_section_broken_is_only_partial_not_failed():
    report = assess_completeness(_draft(background=""), _OUTLINE)
    assert report.status == "partial"
