"""Deterministic provenance and scope audit for section drafts."""

import json
import re

from writing.adapters.language_model import (
    LanguageModel,
    generate_validated,
)
from writing.modules.citation_formatter import extract_cited_paper_ids
from writing.modules.prompt_loader import load_prompt
from writing.schemas import (
    SectionAudit,
    SectionAuditContent,
    SectionDraft,
    SectionWritingContext,
)


def _is_insufficient_evidence_warning(content: str) -> bool:
    folded = content.casefold()
    return "insufficient evidence" in folded or "证据不足" in content


def _word_count(content: str) -> int:
    return len(
        re.findall(
            r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*|[\u3400-\u9fff]",
            content,
        )
    )


def audit_section(
    draft: SectionDraft,
    context: SectionWritingContext,
) -> SectionAudit:
    """Check a draft against the exact code-generated citation and point allowlists."""

    unsupported_claims: list[str] = []
    out_of_scope_content: list[str] = []
    placeholder_ids = extract_cited_paper_ids(draft.content)
    invalid_paper_ids = sorted(
        (set(draft.cited_paper_ids) | set(placeholder_ids))
        - set(context.allowed_paper_ids)
    )
    invalid_point_ids = sorted(
        set(draft.used_point_ids) - set(context.allowed_point_ids)
    )
    unsupported_claims.extend(
        f"point outside context: {point_id}" for point_id in invalid_point_ids
    )
    if re.search(r'^\s*>|"[^"\n]{5,}"|“[^”\n]{2,}”', draft.content, re.MULTILINE):
        unsupported_claims.append("possible direct quotation")
    if re.search(r"\bpp?\.\s*\d+|\[@P\d{3,}[^\]]*,\s*pp?\.", draft.content, re.IGNORECASE):
        unsupported_claims.append("page-level citation is prohibited")

    if draft.tag_id != context.tag_id:
        out_of_scope_content.append(
            f"draft tag {draft.tag_id} does not match context tag {context.tag_id}"
        )
    if set(placeholder_ids) != set(draft.cited_paper_ids):
        out_of_scope_content.append(
            "citation placeholders do not match cited_paper_ids"
        )
    substantive = bool(draft.content.strip()) and not _is_insufficient_evidence_warning(
        draft.content
    )
    if substantive and (not draft.used_point_ids or not draft.cited_paper_ids):
        unsupported_claims.append("substantive prose has no evidence provenance")
    below_minimum_length = False
    if context.max_words is not None:
        actual_words = _word_count(draft.content)
        if actual_words > context.max_words:
            out_of_scope_content.append(
                f"section exceeds max_words: {actual_words} > {context.max_words}"
            )
    if context.min_words is not None and substantive:
        actual_words = _word_count(draft.content)
        if actual_words < context.min_words:
            below_minimum_length = True
    if (
        not context.direct_points
        and not context.ancestor_context
        and not context.child_summaries
        and not _is_insufficient_evidence_warning(draft.content)
    ):
        unsupported_claims.append("empty context produced substantive prose")

    revision_instructions: list[str] = []
    if invalid_paper_ids:
        revision_instructions.append(
            "Remove citations outside the allowed paper list: "
            + ", ".join(invalid_paper_ids)
        )
    if invalid_point_ids:
        revision_instructions.append(
            "Remove claims based on points outside the context: "
            + ", ".join(invalid_point_ids)
        )
    if "possible direct quotation" in unsupported_claims:
        revision_instructions.append("Paraphrase direct quotations without quotation marks.")
    if "page-level citation is prohibited" in unsupported_claims:
        revision_instructions.append("Remove page numbers and use paper-level citations.")
    if out_of_scope_content:
        revision_instructions.append(
            "Keep the draft under the requested tag and make [@paper_id] placeholders "
            "match cited_paper_ids."
        )
    if "empty context produced substantive prose" in unsupported_claims:
        revision_instructions.append(
            "Replace substantive prose with an insufficient-evidence warning."
        )
    if "substantive prose has no evidence provenance" in unsupported_claims:
        revision_instructions.append(
            "Bind substantive prose to cited_paper_ids and used_point_ids from the context."
        )
    if any(item.startswith("section exceeds max_words:") for item in out_of_scope_content):
        revision_instructions.append("Shorten the section to its configured max_words limit.")
    if below_minimum_length:
        revision_instructions.append(
            f"This section is shorter than its planned scope ({_word_count(draft.content)} of "
            f"{context.min_words}+ words expected). Develop the analysis further using the "
            "evidence already available in direct_points/ancestor_context/child_summaries — "
            "add depth, comparison, or distinct supported claims. Do not repeat existing "
            "sentences, pad with filler, or introduce any claim, paper, or point outside the "
            "allowed evidence."
        )

    passed = not (
        unsupported_claims or out_of_scope_content or invalid_paper_ids or below_minimum_length
    )
    return SectionAudit(
        tag_id=context.tag_id,
        passed=passed,
        unsupported_claims=unsupported_claims,
        out_of_scope_content=out_of_scope_content,
        invalid_paper_ids=invalid_paper_ids,
        below_minimum_length=below_minimum_length,
        missing_key_points=[],
        duplicated_child_content=[],
        revision_instructions=revision_instructions,
    )


async def audit_section_semantics(
    draft: SectionDraft,
    context: SectionWritingContext,
    model: LanguageModel,
) -> SectionAudit:
    """Use a dedicated audit prompt to check claims that code cannot interpret."""

    system_prompt = load_prompt("audit_section.md")
    output = await generate_validated(
        model,
        system_prompt=system_prompt,
        user_prompt=json.dumps(
            {
                "context": context.model_dump(mode="json"),
                "draft": draft.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        response_model=SectionAuditContent,
    )
    findings = any(
        [
            output.unsupported_claims,
            output.out_of_scope_content,
            output.invalid_paper_ids,
            output.missing_key_points,
            output.duplicated_child_content,
        ]
    )
    return SectionAudit(
        tag_id=context.tag_id,
        passed=output.passed and not findings,
        unsupported_claims=output.unsupported_claims,
        out_of_scope_content=output.out_of_scope_content,
        invalid_paper_ids=output.invalid_paper_ids,
        missing_key_points=output.missing_key_points,
        duplicated_child_content=output.duplicated_child_content,
        revision_instructions=output.revision_instructions,
    )
