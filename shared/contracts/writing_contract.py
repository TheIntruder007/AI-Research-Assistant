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
    total_sections: int = 0
    failed_sections: int = 0
    # Explicit completeness classification (see DECISIONS.md D-019, revised
    # by D-026's real-rendered-paper completeness check). This is computed
    # from the ACTUAL RENDERED draft text (services/research-writing/
    # completeness.py), not just the writing graph's internal tag-resolution
    # signal — see that module's docstring for why the two can disagree.
    # "complete": every required section (bookends + outline sections) is
    # present with real, non-placeholder prose (short-but-evidence-limited
    # sections still count as complete — see length_status/
    # evidence_limited_sections below for that distinction, per Fix 7).
    # "partial": the draft is usable but at least one required section is
    # missing, blank, or a failure placeholder.
    # "failed": every required section is broken, or both bookends
    # (Introduction and Conclusion) are — the document is not usable.
    draft_status: Literal["complete", "partial", "failed"] = "complete"
    # Length planning/analytics (Fix 3/7/8, DECISIONS.md D-026). All are
    # None/empty when no length target was requested, preserving the old
    # length-unaware behavior for any caller that doesn't set
    # ResearchRequest.max_draft_length.
    target_words: int | None = None
    actual_words: int = 0
    # "short" / "on_target" / "over_target" — see word_budget.classify_length.
    # None when no target_words was requested.
    length_status: Literal["short", "on_target", "over_target"] | None = None
    # Section titles (as rendered, e.g. "Introduction", "Literature Review")
    # whose content is real but shorter than planned because the available
    # evidence was genuinely too thin to develop further — never because the
    # model was told to pad or fabricate anything (Fix 9 "Case B"). Tracked
    # separately from failed_sections so a short-but-honest paper is never
    # confused with a broken one.
    evidence_limited_sections: list[str] = Field(default_factory=list)
    # Section titles that are missing, blank, or rendered as a genuine
    # failure placeholder (as opposed to evidence-limited) in the final
    # document — the human-readable counterpart to `failed_sections`'s count.
    broken_sections: list[str] = Field(default_factory=list)
    duplicate_sections: list[str] = Field(default_factory=list)


class WritingResult(BaseModel):
    """Output of the Research Writing Service — direct input to Service 3."""
    research_outline: str
    research_draft_markdown: str
    citation_mapping: dict[str, CitationEntry] = Field(default_factory=dict)
    reference_candidates: list[str] = Field(default_factory=list)
    run_directory: str
    draft_metadata: DraftMetadata
