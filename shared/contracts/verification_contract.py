"""Input/output contract for the Citation Verification Service (pipeline stage 3)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from shared.contracts.writing_contract import WritingResult


class VerificationRequest(BaseModel):
    """Input to the Citation Verification Service — Service 2's output."""
    writing: WritingResult


class ReferenceCheck(BaseModel):
    """One reference-list entry's verification outcome."""
    reference_entry: str
    doi: str | None = None
    verified: bool
    verification_source: Literal["Crossref", "OpenAlex", "none"] = "none"
    issue: str | None = None


class VerificationResult(BaseModel):
    """Output of the Citation Verification Service — direct input to Service 4."""
    validated_draft_markdown: str
    verified_references: list[ReferenceCheck] = Field(default_factory=list)
    invalid_references: list[ReferenceCheck] = Field(default_factory=list)
    unverifiable_references: list[ReferenceCheck] = Field(default_factory=list)
    missing_references: list[str] = Field(default_factory=list)
    citation_issues: list[str] = Field(default_factory=list)
    validation_report: str
