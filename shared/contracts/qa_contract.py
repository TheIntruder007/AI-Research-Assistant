"""Input/output contract for the Quality Assurance Service (pipeline stage 4)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shared.contracts.discovery_contract import DiscoveryResult
from shared.contracts.verification_contract import VerificationResult
from shared.contracts.writing_contract import WritingResult


class QualityAssuranceRequest(BaseModel):
    """Input to the Quality Assurance Service — all three prior stages'
    outputs, since an independent audit needs the original evidence
    (Discovery), the draft (Writing), and the citation checks (Verification)
    together."""
    discovery: DiscoveryResult
    writing: WritingResult
    verification: VerificationResult


class UnsupportedClaim(BaseModel):
    """A cited sentence whose wording does not overlap enough with its
    cited paper's title/abstract to be considered evidence-aligned."""
    sentence: str
    citation_numbers: list[int]


class MissingCitation(BaseModel):
    """A sentence that reads as a factual/empirical claim but cites no source."""
    sentence: str
    section: str


class QualityScores(BaseModel):
    citation_integrity: float = Field(ge=0.0, le=5.0)
    claim_source_alignment: float = Field(ge=0.0, le=5.0)
    process_control: float = Field(ge=0.0, le=5.0)
    literature_coverage: float = Field(ge=0.0, le=5.0)
    overall: float = Field(ge=0.0, le=5.0)


class QualityAssuranceResult(BaseModel):
    """Output of the Quality Assurance Service — the final pipeline artifact."""
    final_draft_markdown: str
    final_references: list[str] = Field(default_factory=list)
    final_validation_report: str
    quality_report_markdown: str
    scores: QualityScores
    unsupported_claims: list[UnsupportedClaim] = Field(default_factory=list)
    missing_citations: list[MissingCitation] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    audit_metadata: dict[str, Any] = Field(default_factory=dict)
