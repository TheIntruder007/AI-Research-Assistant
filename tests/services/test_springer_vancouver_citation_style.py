"""Regression tests for DECISIONS.md D-028's Springer citation-style fix.

Root cause: `_FORMAT_TO_CITATION_STYLE["Springer"]` was `"chicago-author-date"`
(parenthetical author-year, e.g. "(Smith, 2020)") even though the LaTeX
template actually used for Springer (`llncs`) documents numbered citations
as its real convention. "vancouver" (a real, standard numbered style) was
already implemented in `citation_formatter.py` and declared in
`SUPPORTED_CITATION_STYLES`, but had never been reachable through any real
`target_format` and had zero test coverage anywhere in the repository —
both gaps are closed here.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.modules.citation_formatter import (  # noqa: E402
    build_citation_map, citation_format_errors,
)
from writing.schemas import PaperMetadata  # noqa: E402


def _paper(title, authors, year, journal="Journal of Testing", volume="12",
           issue="3", pages="45-60", doi="10.1000/xyz123") -> PaperMetadata:
    return PaperMetadata(
        title=title, authors=authors, year=year, journal=journal,
        volume=volume, issue=issue, pages=pages, doi=doi,
    )


def test_writing_contract_maps_springer_to_vancouver_not_author_year():
    from shared.contracts.writing_contract import _FORMAT_TO_CITATION_STYLE

    assert _FORMAT_TO_CITATION_STYLE["Springer"] == "vancouver"
    assert _FORMAT_TO_CITATION_STYLE["Springer"] != "chicago-author-date"
    assert _FORMAT_TO_CITATION_STYLE["IEEE"] == "ieee"


def test_vancouver_produces_numbered_parenthetical_in_text_citations():
    metadata = {
        "P001": _paper("A Study of X", ["Jane Smith", "John Doe"], 2020),
        "P002": _paper("A Study of Y", ["Ann Lee"], 2021),
    }
    citations = build_citation_map(["P001", "P002"], metadata, "vancouver")
    assert citations["P001"].in_text_citation == "(1)"
    assert citations["P002"].in_text_citation == "(2)"


def test_vancouver_reference_entries_are_numbered_in_citation_order_not_alphabetical():
    """Numeric styles order the bibliography by first-citation order, not
    alphabetically by author — verifies build_citation_map's own
    `style in _NUMERIC_STYLES` branch for vancouver specifically."""
    metadata = {
        "P001": _paper("Zebra Study", ["Zed Author"], 2020),
        "P002": _paper("Alpha Study", ["Aaron Author"], 2019),
    }
    citations = build_citation_map(["P001", "P002"], metadata, "vancouver")
    assert citations["P001"].reference_entry.startswith("1. ")
    assert citations["P002"].reference_entry.startswith("2. ")
    # Vancouver style renders family name + compact initials ("Author Z."),
    # not the full given name — this checks citation ORDER, not name format.
    assert "Author Z." in citations["P001"].reference_entry
    assert "Author A." in citations["P002"].reference_entry


def test_vancouver_reference_entry_includes_journal_volume_issue_pages_and_doi():
    metadata = {"P001": _paper("A Study of X", ["Jane Smith"], 2020)}
    citations = build_citation_map(["P001"], metadata, "vancouver")
    entry = citations["P001"].reference_entry
    assert "Journal of Testing" in entry
    assert "2020" in entry
    assert "12" in entry  # volume
    assert "3" in entry  # issue
    assert "45-60" in entry
    assert "10.1000/xyz123" in entry


def test_vancouver_citation_passes_its_own_format_validation():
    metadata = {"P001": _paper("A Study of X", ["Jane Smith"], 2020)}
    citations = build_citation_map(["P001"], metadata, "vancouver")
    assert citation_format_errors(citations["P001"], "vancouver") == []


def test_vancouver_and_ieee_are_both_numeric_but_visually_distinct():
    """Guards against silently collapsing Springer's style back to a
    reused/aliased IEEE style — they must render distinctly (brackets vs
    parentheses) so a reader can't confuse which convention a paper used."""
    metadata = {"P001": _paper("A Study of X", ["Jane Smith"], 2020)}
    ieee = build_citation_map(["P001"], metadata, "ieee")
    vancouver = build_citation_map(["P001"], metadata, "vancouver")
    assert ieee["P001"].in_text_citation == "[1]"
    assert vancouver["P001"].in_text_citation == "(1)"
    assert ieee["P001"].in_text_citation != vancouver["P001"].in_text_citation
