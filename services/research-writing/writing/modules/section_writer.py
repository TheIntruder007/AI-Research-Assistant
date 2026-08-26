"""Write sections from code-controlled contexts."""

import json

from writing.adapters.language_model import (
    LanguageModel,
    generate_validated,
)
from writing.modules.prompt_loader import load_prompt
from writing.modules.section_auditor import (
    audit_section,
    audit_section_semantics,
)
from writing.schemas import (
    SectionAudit,
    SectionDraft,
    SectionDraftContent,
    SectionRunResult,
    SectionWritingContext,
)


async def write_section(
    context: SectionWritingContext,
    model: LanguageModel,
) -> SectionDraft:
    """Write one section, or emit an evidence warning without calling the model."""

    if not context.direct_points and not context.ancestor_context and not context.child_summaries:
        warning = (
            "*本节可用证据不足。*"
            if context.output_language.casefold().startswith("zh")
            else "*Insufficient evidence is available for this section.*"
        )
        return SectionDraft(
            tag_id=context.tag_id,
            content=warning,
            cited_paper_ids=[],
            used_point_ids=[],
        )

    prompt_name = (
        "write_parent_intro.md"
        if context.writing_mode == "parent_intro"
        else "write_leaf_section.md"
    )
    system_prompt = load_prompt(prompt_name)
    user_prompt = json.dumps(context.model_dump(mode="json"), ensure_ascii=False, indent=2)
    content = await generate_validated(
        model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=SectionDraftContent,
    )
    return SectionDraft(tag_id=context.tag_id, **content.model_dump())


async def revise_section(
    context: SectionWritingContext,
    draft: SectionDraft,
    audit: SectionAudit,
    model: LanguageModel,
) -> SectionDraft:
    """Apply only audit-directed changes using the original immutable context."""

    system_prompt = load_prompt("revise_section.md")
    user_prompt = json.dumps(
        {
            "context": context.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "audit": audit.model_dump(mode="json"),
        },
        ensure_ascii=False,
        indent=2,
    )
    content = await generate_validated(
        model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=SectionDraftContent,
    )
    return SectionDraft(tag_id=context.tag_id, **content.model_dump())


async def write_section_with_revisions(
    context: SectionWritingContext,
    model: LanguageModel,
    *,
    max_revision_rounds: int = 2,
    semantic_audit: bool = False,
) -> SectionRunResult:
    """Write, audit, and revise a section without an unbounded loop."""

    if max_revision_rounds < 0:
        raise ValueError("max_revision_rounds must be non-negative")

    async def run_audit(current: SectionDraft) -> SectionAudit:
        program_audit = audit_section(current, context)
        if semantic_audit and program_audit.passed:
            return await audit_section_semantics(current, context, model)
        return program_audit

    draft = await write_section(context, model)
    audits = [await run_audit(draft)]
    rounds = 0
    while not audits[-1].passed and rounds < max_revision_rounds:
        draft = await revise_section(context, draft, audits[-1], model)
        audits.append(await run_audit(draft))
        rounds += 1

    final_audit = audits[-1]
    return SectionRunResult(
        draft=draft,
        audits=audits,
        resolved=final_audit.passed,
        unresolved_issues=[] if final_audit.passed else final_audit.revision_instructions,
    )
