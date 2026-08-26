"""Input/output contract for the Research Writing Service (pipeline stage 2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from shared.contracts.discovery_contract import DiscoveryResult

TargetFormat = Literal["IEEE", "Springer", "ACM", "APA", "Other"]

# Extensible: a target format not listed here can still be passed as "Other"
# with format_other_name set — see WritingRequest.
_FORMAT_TO_CITATION_STYLE = {
    "IEEE": "ieee",
    "Springer": "chicago-author-date",
    "ACM": "elsevier-harvard",
    "APA": "apa-7",
    "Other": "elsevier-harvard",
}


class WritingRequest(BaseModel):
    """Input to the Research Writing Service — Service 1's output plus the
    venue/format details from the original research request."""
    discovery: DiscoveryResult
    target_format: TargetFormat = "IEEE"
    format_other_name: str | None = None
    output_language: str = "en"
    target_words: int | None = Field(default=None, gt=0)

    @property
    def citation_style(self) -> str:
        return _FORMAT_TO_CITATION_STYLE[self.target_format]


class CitationEntry(BaseModel):
    paper_id: str
    citation_key: str
    in_text_citation: str
    narrative_citation: str
    reference_entry: str


class DraftMetadata(BaseModel):
    """Required disclosure that this is AI-generated synthesis, not a
    verified publication — see PROJECT_NOTES.md safety rules."""
    disclaimer: str = (
        "AI-generated research draft for human review. Not a verified or "
        "published research paper. Claims must be checked against cited "
        "sources before any external use."
    )
    model_name: str
    run_id: str
    generated_at: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    papers_cited: int = 0
    sections_written: int = 0


class WritingResult(BaseModel):
    """Output of the Research Writing Service — direct input to Service 3."""
    research_outline: str
    research_draft_markdown: str
    citation_mapping: dict[str, CitationEntry] = Field(default_factory=dict)
    reference_candidates: list[str] = Field(default_factory=list)
    run_directory: str
    draft_metadata: DraftMetadata
