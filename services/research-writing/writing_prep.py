"""Prepares inputs for the writing graph from a Service 1 DiscoveryResult:
an outline (Markdown headings) and one literature file per selected paper.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.contracts.discovery_contract import DiscoveryResult, PaperMetadata  # noqa: E402


def _slug(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len] or "section"


def build_outline(discovery: DiscoveryResult) -> str:
    """A Markdown heading outline covering the evidence-backed sections (see
    PROJECT_NOTES.md). Exactly one root heading, as required by the writing
    graph's outline parser.

    Deliberately does NOT give each Discovery research gap its own
    literature-review subsection (see DECISIONS.md D-011): each gap is
    already a narrow, specific statement about a single missing angle, and
    turning it into its own evidence-required leaf tag causes the writing
    graph's per-paper tagging step to (correctly, per its own no-invented-
    evidence rule) exclude almost the entire corpus from every subsection —
    verified on a real 6-paper run where this produced only 2 of 13
    sections. A single flat Literature Review section lets papers'
    abstract-level evidence roll up naturally instead of being sliced into
    slots most of the corpus can't satisfy. The gaps themselves are
    Service 1's own already-synthesized output, not something Service 2
    needs to re-derive from literature evidence — see
    render_research_gap_section() below, which renders them directly."""
    return "\n".join([
        f"# {discovery.research_request.research_question}",
        "## Introduction",
        "## Literature Review",
        "## Limitations",
        "## Conclusion",
    ])


def render_research_gap_section(discovery: DiscoveryResult) -> str:
    """Render Service 1's research-gap and novelty analysis directly as
    Markdown, rather than asking the writing graph's strict evidence-only
    leaf writer to "find evidence" for gaps and proposed future work that,
    by definition, no existing paper in the corpus documents (see
    DECISIONS.md D-011). Spliced into the assembled draft by service.py."""
    lines = ["## Research Gap", ""]
    for gap in discovery.research_gaps:
        lines.append(f"### {gap.title}")
        lines.append("")
        lines.append(gap.description)
        lines.append("")
        if gap.evidence:
            lines.append(f"*Evidence:* {gap.evidence}")
            lines.append("")
    lines.append("## Proposed Novelty and Contribution")
    lines.append("")
    lines.append(discovery.novelty_analysis.novelty_summary)
    lines.append("")
    if discovery.novelty_analysis.caveats:
        lines.append(f"*Caveats:* {discovery.novelty_analysis.caveats}")
        lines.append("")
    return "\n".join(lines)


def _front_matter(paper: PaperMetadata) -> str:
    lines = ["---", "evidence_depth: abstract", f"title: {paper.title!r}"]
    if paper.authors:
        authors = ", ".join(f"{a!r}" for a in paper.authors)
        lines.append(f"authors: [{authors}]")
    if paper.year:
        lines.append(f"year: {paper.year}")
    if paper.venue:
        lines.append(f"journal: {paper.venue!r}")
    if paper.doi:
        lines.append(f"doi: {paper.doi!r}")
    lines.append("---")
    return "\n".join(lines)


def write_literature_files(discovery: DiscoveryResult, literature_directory: Path) -> int:
    """Writes one Markdown file per selected paper (evidence_depth: abstract,
    per DECISIONS.md D-010) with whatever text Service 1 actually retrieved.
    Returns the number of files written."""
    literature_directory.mkdir(parents=True, exist_ok=True)
    written = 0
    for paper in discovery.selected_papers:
        if not paper.abstract and not paper.has_abstract:
            continue
        body = paper.abstract or "(Abstract not available; metadata only.)"
        path = literature_directory / f"{_slug(paper.title)}-{paper.id}.md"
        path.write_text(f"{_front_matter(paper)}\n\n{body}\n", encoding="utf-8")
        written += 1
    return written
