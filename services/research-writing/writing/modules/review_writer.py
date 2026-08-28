"""Write introduction and conclusion after audited body sections exist."""

import json

from writing.adapters.language_model import (
    LanguageModel,
    generate_validated,
)
from writing.modules.prompt_loader import load_prompt
from writing.schemas import (
    FullReviewAudit,
    OutlineNode,
    ReviewRevisionContent,
    SectionDraft,
    SectionDraftContent,
    SectionSummary,
    SectionWritingContext,
    TagIndexItem,
)


class FullRevisionError(ValueError):
    """Raised when a full-review revision changes the editable section set."""


async def _write_part(
    prompt_name: str,
    tag_id: str,
    payload: dict[str, object],
    model: LanguageModel,
) -> SectionDraft:
    system_prompt = load_prompt(prompt_name)
    output = await generate_validated(
        model,
        system_prompt=system_prompt,
        user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
        response_model=SectionDraftContent,
    )
    return SectionDraft(tag_id=tag_id, **output.model_dump())


async def write_introduction(
    review_question: str,
    tree: list[OutlineNode],
    top_level_summaries: list[SectionSummary],
    overview_points: list[TagIndexItem],
    model: LanguageModel,
    *,
    output_language: str = "en",
    target_words: int | None = None,
    min_words: int | None = None,
    max_words: int | None = None,
) -> SectionDraft:
    """Introduce the stable body using only overview evidence and top-level summaries.

    target_words/min_words/max_words: this bookend's planned length budget
    (see DECISIONS.md D-025/D-026) — None when no total paper length was
    requested, exactly preserving pre-D-025 behavior."""

    return await _write_part(
        "write_introduction.md",
        "INTRODUCTION",
        {
            "review_question": review_question,
            "outline": [node.model_dump(mode="json") for node in tree],
            "top_level_summaries": [
                summary.model_dump(mode="json") for summary in top_level_summaries
            ],
            "overview_points": [point.model_dump(mode="json") for point in overview_points],
            "output_language": output_language,
            "target_words": target_words,
            "min_words": min_words,
            "max_words": max_words,
        },
        model,
    )


async def write_conclusion(
    review_question: str,
    section_summaries: list[SectionSummary],
    model: LanguageModel,
    *,
    output_language: str = "en",
    target_words: int | None = None,
    min_words: int | None = None,
    max_words: int | None = None,
) -> SectionDraft:
    """Conclude from audited body summaries without introducing new evidence."""

    return await _write_part(
        "write_conclusion.md",
        "CONCLUSION",
        {
            "review_question": review_question,
            "section_summaries": [
                summary.model_dump(mode="json") for summary in section_summaries
            ],
            "output_language": output_language,
            "target_words": target_words,
            "min_words": min_words,
            "max_words": max_words,
        },
        model,
    )


async def revise_full_review(
    introduction: SectionDraft,
    sections: dict[str, SectionDraft],
    conclusion: SectionDraft,
    contexts: dict[str, SectionWritingContext],
    audit: FullReviewAudit,
    model: LanguageModel,
) -> tuple[SectionDraft, dict[str, SectionDraft], SectionDraft]:
    """Revise prose while deterministic code retains every structural tag ID."""

    if set(contexts) != set(sections):
        raise FullRevisionError("every editable section must have its original context")
    system_prompt = load_prompt("revise_full_review.md")
    output = await generate_validated(
        model,
        system_prompt=system_prompt,
        user_prompt=json.dumps(
            {
                "introduction": introduction.model_dump(mode="json"),
                "sections": {
                    tag_id: {
                        "draft": draft.model_dump(mode="json"),
                        "context": contexts[tag_id].model_dump(mode="json"),
                    }
                    for tag_id, draft in sections.items()
                },
                "conclusion": conclusion.model_dump(mode="json"),
                "audit": audit.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        response_model=ReviewRevisionContent,
    )
    if set(output.sections) != set(sections):
        raise FullRevisionError(
            "revision must return every editable section exactly once"
        )
    revised_sections = {
        tag_id: SectionDraft(tag_id=tag_id, **content.model_dump())
        for tag_id, content in output.sections.items()
    }
    return (
        SectionDraft(tag_id="INTRODUCTION", **output.introduction.model_dump()),
        revised_sections,
        SectionDraft(tag_id="CONCLUSION", **output.conclusion.model_dump()),
    )
