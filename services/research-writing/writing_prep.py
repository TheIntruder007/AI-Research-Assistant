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
    """A Markdown heading outline covering the required output sections
    (see PROJECT_NOTES.md), populated with gap titles so each gets its own
    literature-review subsection. Exactly one root heading, as required by
    the writing graph's outline parser."""
    lines = [
        f"# {discovery.research_request.research_question}",
        "## Introduction",
        "### Problem Statement",
        "## Literature Review",
    ]
    for gap in discovery.research_gaps:
        lines.append(f"### {gap.title}")
    lines += [
        "## Research Gap",
        "## Proposed Novelty and Contribution",
        "## Methodology",
        "## Discussion",
        "## Limitations",
        "## Conclusion",
    ]
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
