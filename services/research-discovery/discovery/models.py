"""Shared data structures for the Research Discovery Service pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


class PipelineError(Exception):
    """An error with a user-facing message; shown verbatim in the UI."""


@dataclass
class Paper:
    title: str
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    authors: list[str] = field(default_factory=list)
    citations: int | None = None
    doi: str | None = None
    url: str | None = None
    source: str = ""
    relevance_rank: int = 0  # 0-based position in the source's relevance-sorted results
    id: int = 0              # assigned after dedupe/rank; used for citations in the report
    pdf_url: str | None = None    # direct open-access PDF link, when a source provides one
    pmcid: str | None = None      # PubMed Central ID, e.g. "PMC1234567" (full-text XML route)
    future_text: str | None = None  # extracted Discussion/Limitations/Future-research text
    role: str = "corpus"          # "corpus" or "verification" (found while checking candidates)

    @property
    def link(self) -> str | None:
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return self.url

    def to_client_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.authors[:3] + (["et al."] if len(self.authors) > 3 else []),
            "year": self.year,
            "venue": self.venue,
            "citations": self.citations,
            "link": self.link,
            "doi": self.doi,
            "source": self.source,
            "has_abstract": bool(self.abstract),
            "has_fulltext": bool(self.future_text),
            "role": self.role,
        }


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/",
                   "https://dx.doi.org/", "http://dx.doi.org/",
                   "dx.doi.org/", "doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]  # "doi: 10.x" (with a space) needs the strip below
            break
    return d.strip() or None


NORMALIZED_TITLE_MIN = 20  # below this a title is too generic to match on ("Editorial")


def normalize_title(title: str) -> str:
    """Alphanumeric-only, lower-cased title for cross-source matching.

    Returns "" for very short/generic titles ("Editorial", "Introduction",
    all-punctuation → "") so callers skip title-only matching on them: otherwise
    distinct papers sharing a stock title collapse during dedupe. Matching still
    falls back to DOI, which is unambiguous.
    """
    norm = "".join(ch for ch in title.lower() if ch.isalnum())
    return norm if len(norm) >= NORMALIZED_TITLE_MIN else ""
