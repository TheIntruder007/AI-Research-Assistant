"""Deterministic, non-LLM completeness validation of the ACTUAL RENDERED
paper (draft_text), not just the writing graph's internal success signal.

Why this exists (DECISIONS.md D-026 / diagnostic run a8e525ae): the graph's
own `succeeded`/`failed_tag_ids` only reflect whether every OUTLINE tag's
section resolved. They say nothing about the two bookend sections
(Introduction/Conclusion, generated separately — see review_writer.py) or
about whether a "resolved" section actually rendered as real, non-blank,
non-placeholder prose in the document a human or reviewer would read. A run
was observed where `draft_status` reported "complete" while the rendered
paper's Introduction was blank. This module inspects the same markdown
string that becomes draft.md / paper.tex / paper.pdf, exactly as it will be
read, and is the only source of truth for `draft_status`.

Scope, stated honestly: this is a structural/textual check (heading
present? content present? does it match a known failure-placeholder
string?) — it cannot judge writing quality or factual correctness. That is
what the separate Quality Assurance stage (Service 4) is for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Placeholders emitted by writing/graph.py / writing/modules/section_writer.py
# when a section's audit could not be resolved within the bounded retry
# budget, or the model call itself raised — genuine failures, not content.
_FAILURE_PLACEHOLDERS = [
    "Section generation failed; no unsupported content was inserted.",
    "This section audit could not be resolved; unsupported content was omitted.",
    "本节审计未能解决，因此未纳入未经支持的内容。",
    "Introduction generation did not satisfy evidence constraints.",
    "No evidence-backed conclusion can be drawn.",
]

# Placeholders emitted deliberately when a section has zero supplied
# evidence at all (writing/modules/section_writer.py::write_section) — an
# honest "nothing to write" outcome, not a failure. Counted as present and
# evidence-limited, never as blank/failed.
_NO_EVIDENCE_PLACEHOLDERS = [
    "Insufficient evidence is available for this section.",
    "本节可用证据不足。",
]

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class SectionCompletenessReport:
    title: str
    present: bool
    blank: bool
    is_failure_placeholder: bool
    is_no_evidence_placeholder: bool
    word_count: int


@dataclass
class CompletenessReport:
    status: str  # "complete" | "partial" | "failed"
    sections: list[SectionCompletenessReport] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    blank_sections: list[str] = field(default_factory=list)
    failed_sections: list[str] = field(default_factory=list)
    evidence_limited_sections: list[str] = field(default_factory=list)
    duplicate_sections: list[str] = field(default_factory=list)


def _word_count(text: str) -> int:
    return len(text.split())


def _split_top_level_sections(draft_text: str) -> tuple[list[str], dict[str, str]]:
    """Splits on "## " headings only (not "### " or deeper) — the same
    level every outline section and both bookends render at (see
    review_assembler.py). Returns (heading order incl. duplicates, content
    keyed by heading — last occurrence wins for lookup, duplicates are
    reported separately from `_split_top_level_sections`'s own order list)."""

    matches = list(_HEADING_RE.finditer(draft_text))
    order = [match.group(1).strip() for match in matches]
    content_by_title: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(draft_text)
        title = match.group(1).strip()
        block = draft_text[start:end]
        # Accumulate rather than overwrite so a duplicate heading's content
        # is still inspected (e.g. two "## Limitations" blocks, one blank).
        content_by_title[title] = content_by_title.get(title, "") + block
    return order, content_by_title


def required_section_titles(outline: str, *, output_language: str = "en") -> list[str]:
    """The full set of top-level sections a complete rendered paper must
    contain: the bookend Introduction/Conclusion (owned by review_writer.py,
    never present as their own outline tags — see DECISIONS.md D-025) plus
    every "## " section the outline itself defines."""

    introduction_heading = "引言" if output_language.casefold().startswith("zh") else "Introduction"
    conclusion_heading = "结论" if output_language.casefold().startswith("zh") else "Conclusion"
    outline_sections = [
        line[3:].strip() for line in outline.splitlines() if line.startswith("## ")
    ]
    return [introduction_heading, *outline_sections, conclusion_heading]


def assess_completeness(
    draft_text: str, outline: str, *, output_language: str = "en",
) -> CompletenessReport:
    """Inspects the final rendered draft markdown section-by-section."""

    required = required_section_titles(outline, output_language=output_language)
    order, content_by_title = _split_top_level_sections(draft_text)

    duplicate_sections = sorted(
        {title for title in required if order.count(title) > 1}
    )

    reports: list[SectionCompletenessReport] = []
    missing: list[str] = []
    blank: list[str] = []
    failed: list[str] = []
    evidence_limited: list[str] = []

    for title in required:
        if title not in content_by_title:
            missing.append(title)
            reports.append(SectionCompletenessReport(
                title=title, present=False, blank=True,
                is_failure_placeholder=False, is_no_evidence_placeholder=False,
                word_count=0,
            ))
            continue
        block = content_by_title[title]
        stripped = block.strip()
        is_blank = not stripped
        is_failure = any(marker in block for marker in _FAILURE_PLACEHOLDERS)
        is_no_evidence = (not is_failure) and any(
            marker in block for marker in _NO_EVIDENCE_PLACEHOLDERS
        )
        if is_blank:
            blank.append(title)
        elif is_failure:
            failed.append(title)
        elif is_no_evidence:
            evidence_limited.append(title)
        reports.append(SectionCompletenessReport(
            title=title, present=True, blank=is_blank,
            is_failure_placeholder=is_failure, is_no_evidence_placeholder=is_no_evidence,
            word_count=_word_count(stripped),
        ))

    broken = set(missing) | set(blank) | set(failed)
    # "failed": the document is unusable — every required section is broken,
    # or both anchor sections (Introduction and Conclusion) are, which makes
    # the paper unreadable as a coherent piece regardless of the body.
    introduction_heading, conclusion_heading = required[0], required[-1]
    anchors_broken = (
        introduction_heading in broken and conclusion_heading in broken
    )
    if required and (len(broken) == len(required) or anchors_broken):
        status = "failed"
    elif broken:
        status = "partial"
    else:
        status = "complete"

    return CompletenessReport(
        status=status,
        sections=reports,
        missing_sections=missing,
        blank_sections=blank,
        failed_sections=failed,
        evidence_limited_sections=evidence_limited,
        duplicate_sections=duplicate_sections,
    )
