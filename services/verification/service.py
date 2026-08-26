"""Public entry point for the Citation Verification Service.

Takes a WritingResult (Service 2's output) and checks each rendered
reference-list entry's DOI against free, keyless scholarly APIs (Crossref,
then OpenAlex as a fallback — the same "no external key" pattern Service 1
uses, see DECISIONS.md D-007). This service never invents or silently
repairs a reference: an entry with no extractable DOI, or a DOI that
resolves nowhere, is flagged in the validation report rather than dropped,
corrected, or hidden — see PROJECT_NOTES.md's "must not silently invent or
repair references" rule and DECISIONS.md D-012.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import AsyncIterator

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.contracts.verification_contract import (  # noqa: E402
    ReferenceCheck, VerificationRequest, VerificationResult,
)

CROSSREF_URL = "https://api.crossref.org/works/{doi}"
OPENALEX_URL = "https://api.openalex.org/works/doi:{doi}"
REQUEST_TIMEOUT = 10.0

# Matches a DOI trailed by "doi: 10.x/y" (IEEE/Vancouver style) or
# "https://doi.org/10.x/y" (author-year/MLA styles) at the end of a
# rendered reference entry (see writing/modules/citation_formatter.py).
_DOI_PATTERNS = (
    re.compile(r"doi:\s*(10\.\d{4,9}/\S+?)[.\s]*$", re.IGNORECASE),
    re.compile(r"https?://doi\.org/(10\.\d{4,9}/\S+?)[.\s]*$", re.IGNORECASE),
)

NO_DOI_ISSUE = "No DOI found in this reference entry — existence could not be checked automatically."


def extract_doi(reference_entry: str) -> str | None:
    """Return the DOI embedded in a rendered reference entry, if any."""
    stripped = reference_entry.rstrip()
    for pattern in _DOI_PATTERNS:
        match = pattern.search(stripped)
        if match:
            return match.group(1).rstrip(".,;").lower()
    return None


async def _resolves(client: httpx.AsyncClient, url: str) -> bool:
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


async def check_reference(client: httpx.AsyncClient, reference_entry: str) -> ReferenceCheck:
    doi = extract_doi(reference_entry)
    if doi is None:
        return ReferenceCheck(reference_entry=reference_entry, verified=False, issue=NO_DOI_ISSUE)
    if await _resolves(client, CROSSREF_URL.format(doi=doi)):
        return ReferenceCheck(
            reference_entry=reference_entry, doi=doi, verified=True, verification_source="Crossref",
        )
    if await _resolves(client, OPENALEX_URL.format(doi=doi)):
        return ReferenceCheck(
            reference_entry=reference_entry, doi=doi, verified=True, verification_source="OpenAlex",
        )
    return ReferenceCheck(
        reference_entry=reference_entry, doi=doi, verified=False,
        issue=f"DOI {doi} was not found in Crossref or OpenAlex — it may be incorrect or fabricated.",
    )


def build_validation_report(
    *, checked: int, verified: list[ReferenceCheck], invalid: list[ReferenceCheck],
    unverifiable: list[ReferenceCheck], missing_references: list[str],
    citation_issues: list[str],
) -> str:
    lines = [
        "# Citation Verification Report", "",
        f"- References checked: {checked}",
        f"- Verified: {len(verified)}",
        f"- Invalid (DOI not found): {len(invalid)}",
        f"- Unverifiable (no DOI to check): {len(unverifiable)}",
        "",
    ]
    if invalid:
        lines.append("## Invalid references")
        lines += [f"- {c.reference_entry}\n  - {c.issue}" for c in invalid]
        lines.append("")
    if unverifiable:
        lines.append("## Unverifiable references")
        lines += [f"- {c.reference_entry}\n  - {c.issue}" for c in unverifiable]
        lines.append("")
    if missing_references:
        lines.append("## Missing references")
        lines += [f"- {m}" for m in missing_references]
        lines.append("")
    if citation_issues:
        lines.append("## Citation issues")
        lines += [f"- {c}" for c in citation_issues]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


async def run_verification(request: VerificationRequest) -> AsyncIterator[dict]:
    """Yields progress events, then a final {"type": "result", "result": VerificationResult}
    event."""
    writing = request.writing
    references = writing.reference_candidates

    yield {"type": "status", "stage": "verify", "state": "running",
           "message": f"Verifying {len(references)} reference(s) against Crossref/OpenAlex…"}

    verified: list[ReferenceCheck] = []
    invalid: list[ReferenceCheck] = []
    unverifiable: list[ReferenceCheck] = []
    async with httpx.AsyncClient() as client:
        for entry in references:
            check = await check_reference(client, entry)
            if check.verified:
                verified.append(check)
            elif check.doi is None:
                unverifiable.append(check)
            else:
                invalid.append(check)

    missing_references: list[str] = []
    cited_count = writing.draft_metadata.papers_cited
    if cited_count and cited_count != len(references):
        missing_references.append(
            f"Draft metadata reports {cited_count} paper(s) cited, but the reference "
            f"list has {len(references)} entr{'y' if len(references) == 1 else 'ies'} "
            "— counts should match; check for citations without a reference entry."
        )

    citation_issues: list[str] = [
        f"Carried over from the writing stage: {error}" for error in writing.draft_metadata.errors
    ]

    validation_report = build_validation_report(
        checked=len(references), verified=verified, invalid=invalid,
        unverifiable=unverifiable, missing_references=missing_references,
        citation_issues=citation_issues,
    )

    yield {"type": "status", "stage": "verify", "state": "done",
           "message": f"Verification complete — {len(verified)} verified, "
                      f"{len(invalid)} invalid, {len(unverifiable)} unverifiable."}

    validated_draft_markdown = writing.research_draft_markdown
    if invalid or unverifiable or missing_references:
        validated_draft_markdown += (
            "\n> **Citation verification found issues — see the validation report "
            "before using this draft.**\n"
        )

    result = VerificationResult(
        validated_draft_markdown=validated_draft_markdown,
        verified_references=verified,
        invalid_references=invalid,
        unverifiable_references=unverifiable,
        missing_references=missing_references,
        citation_issues=citation_issues,
        validation_report=validation_report,
    )
    yield {"type": "result", "result": result}
