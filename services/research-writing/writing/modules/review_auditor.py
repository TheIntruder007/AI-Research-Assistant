"""Deterministic whole-review structure, citation, and provenance audit."""

import json
import re
from collections.abc import Mapping

from writing.adapters.language_model import (
    LanguageModel,
    generate_validated,
)
from writing.modules.citation_formatter import (
    citation_format_errors,
    extract_cited_paper_ids,
)
from writing.modules.prompt_loader import load_prompt
from writing.schemas import (
    CitationInfo,
    FullReviewAudit,
    FullReviewSemanticAudit,
    OutlineNode,
    ReviewDocument,
    SectionDraft,
    SectionSummary,
    TagDefinition,
    VisualRecommendation,
    VisualRecommendationEvidenceAudit,
    VisualRecommendationEvidenceAuditItem,
)

_HEADING = re.compile(r"^(?P<marks>#+)\s+(?P<title>.+?)\s*$", re.MULTILINE)
_PLACEHOLDER = re.compile(r"\[@P\d{3,}\]")


def audit_full_review(
    review: ReviewDocument,
    tree: list[OutlineNode],
    definitions: list[TagDefinition],
    drafts: dict[str, SectionDraft],
    introduction: SectionDraft,
    conclusion: SectionDraft,
    citations: dict[str, CitationInfo],
    *,
    citation_style: str = "elsevier-harvard",
) -> FullReviewAudit:
    """Check final artifacts against the immutable outline and body provenance."""

    definition_by_id = {definition.tag_id: definition for definition in definitions}
    required = [
        node.tag_id
        for node in tree[1:]
        if definition_by_id.get(node.tag_id) is None
        or definition_by_id[node.tag_id].node_type != "container"
    ]
    missing_sections = [
        tag_id
        for tag_id in required
        if tag_id not in drafts or not drafts[tag_id].content.strip()
    ]

    expected_headings = [(node.depth + 1, node.title) for node in tree]
    actual_headings = [
        (len(match.group("marks")), match.group("title"))
        for match in _HEADING.finditer(review.markdown)
        if match.group("title") not in {"References", "参考文献"}
    ]
    heading_errors = (
        []
        if actual_headings == expected_headings
        else ["final heading sequence does not match the user outline"]
    )

    missing_reference_paper_ids = sorted(
        paper_id for paper_id in review.cited_paper_ids if paper_id not in citations
    )
    counts = {entry: review.references.count(entry) for entry in review.references}
    duplicate_references = sorted(entry for entry, count in counts.items() if count > 1)
    unresolved_placeholders = sorted(set(_PLACEHOLDER.findall(review.markdown)))

    body_paper_ids = {
        paper_id for draft in drafts.values() for paper_id in draft.cited_paper_ids
    }
    body_point_ids = {
        point_id for draft in drafts.values() for point_id in draft.used_point_ids
    }
    new_conclusion_paper_ids = sorted(
        set(conclusion.cited_paper_ids) - body_paper_ids
    )
    new_conclusion_point_ids = sorted(
        set(conclusion.used_point_ids) - body_point_ids
    )

    errors: list[str] = []
    for label, draft in [
        ("introduction", introduction),
        ("conclusion", conclusion),
    ]:
        if set(extract_cited_paper_ids(draft.content)) != set(draft.cited_paper_ids):
            errors.append(
                f"{label} citation placeholders do not match cited_paper_ids"
            )
    if set(introduction.cited_paper_ids) - set(citations):
        errors.append("introduction cites papers without citation records")
    bookend_content = f"{introduction.content}\n{conclusion.content}"
    if re.search(r'^\s*>|"[^"\n]{5,}"|“[^”\n]{2,}”', bookend_content, re.MULTILINE):
        errors.append("introduction or conclusion contains a possible direct quotation")
    if re.search(r"\bpp?\.\s*\d+", bookend_content, re.IGNORECASE):
        errors.append("introduction or conclusion contains a page-level citation")
    if len(review.references) != len(set(review.references)):
        errors.append("reference list contains duplicates")
    if len(review.references) != len(review.cited_paper_ids):
        errors.append("in-text citations and references are not one-to-one")
    if not missing_reference_paper_ids:
        expected_references = [
            citation.reference_entry for citation in citations.values()
        ]
        if review.references != expected_references:
            errors.append("reference entries do not match cited paper IDs in order")
        for paper_id in review.cited_paper_ids:
            citation = citations[paper_id]
            errors.extend(
                f"{paper_id}: {message}"
                for message in citation_format_errors(citation, citation_style)
            )
            if citation.in_text_citation not in review.markdown:
                errors.append(
                    f"{paper_id}: formatted in-text citation is absent from the review"
                )

    revision_instructions: list[str] = []
    if missing_sections or heading_errors:
        revision_instructions.append("Restore every user-outline heading in original order.")
    if missing_reference_paper_ids or duplicate_references or unresolved_placeholders:
        revision_instructions.append("Repair citation and reference correspondence.")
    if new_conclusion_paper_ids or new_conclusion_point_ids:
        revision_instructions.append(
            "Remove conclusion evidence that was not used in the body."
        )
    if errors and not revision_instructions:
        revision_instructions.append("Repair the reported full-review audit errors.")

    passed = not any(
        [
            missing_sections,
            heading_errors,
            missing_reference_paper_ids,
            duplicate_references,
            unresolved_placeholders,
            new_conclusion_paper_ids,
            new_conclusion_point_ids,
            errors,
        ]
    )
    return FullReviewAudit(
        passed=passed,
        missing_sections=missing_sections,
        heading_errors=heading_errors,
        missing_reference_paper_ids=missing_reference_paper_ids,
        duplicate_references=duplicate_references,
        unresolved_placeholders=unresolved_placeholders,
        new_conclusion_paper_ids=new_conclusion_paper_ids,
        new_conclusion_point_ids=new_conclusion_point_ids,
        errors=errors,
        revision_instructions=revision_instructions,
    )


async def audit_full_review_semantics(
    review_question: str,
    review: ReviewDocument,
    section_summaries: list[SectionSummary],
    model: LanguageModel,
    *,
    section_contents: Mapping[str, str] | None = None,
) -> FullReviewSemanticAudit:
    """Audit cross-section meaning with a prompt separate from generation."""

    system_prompt = load_prompt("audit_full_review.md")
    output = await generate_validated(
        model,
        system_prompt=system_prompt,
        user_prompt=json.dumps(
            {
                "review_question": review_question,
                "section_summaries": [
                    summary.model_dump(mode="json") for summary in section_summaries
                ],
                "section_contents": dict(section_contents or {}),
                "review_markdown": review.markdown,
            },
            ensure_ascii=False,
            indent=2,
        ),
        response_model=FullReviewSemanticAudit,
    )
    summary_by_id = {summary.tag_id: summary for summary in section_summaries}
    recommendations = []
    seen_recommendations: set[tuple[str, str, str, str, str, str]] = set()
    for recommendation in output.visual_recommendations:
        identity = (
            recommendation.tag_id,
            recommendation.visual_type,
            recommendation.prompt,
            recommendation.caption,
            recommendation.placement_after,
            ",".join(recommendation.source_point_ids),
        )
        summary = summary_by_id.get(recommendation.tag_id)
        points_are_valid = summary is not None and set(
            recommendation.source_point_ids
        ).issubset(summary.used_point_ids)
        anchor_is_valid = section_contents is None or (
            section_contents.get(recommendation.tag_id, "").count(
                recommendation.placement_after
            )
            == 1
        )
        if points_are_valid and anchor_is_valid and identity not in seen_recommendations:
            recommendations.append(recommendation)
            seen_recommendations.add(identity)
    return output.model_copy(
        update={
            "passed": output.passed and not output.issues,
            "visual_recommendations": recommendations,
        }
    )


async def audit_visual_recommendation_evidence(
    recommendations: list[VisualRecommendation],
    point_contents: Mapping[str, str],
    model: LanguageModel,
) -> list[VisualRecommendation]:
    """Keep only visual prompts and captions supported by their bound point text."""

    candidates = [
        recommendation
        for recommendation in recommendations
        if all(point_id in point_contents for point_id in recommendation.source_point_ids)
    ]
    if not candidates:
        return []
    system_prompt = load_prompt("audit_visual_recommendations.md")
    output = await generate_validated(
        model,
        system_prompt=system_prompt,
        user_prompt=json.dumps(
            {
                "recommendations": [
                    {
                        "recommendation_index": index,
                        "recommendation": recommendation.model_dump(mode="json"),
                        "source_points": {
                            point_id: point_contents[point_id]
                            for point_id in recommendation.source_point_ids
                        },
                    }
                    for index, recommendation in enumerate(candidates)
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        response_model=VisualRecommendationEvidenceAudit,
    )
    verdicts_by_index: dict[int, list[VisualRecommendationEvidenceAuditItem]] = {}
    for item in output.items:
        verdicts_by_index.setdefault(item.recommendation_index, []).append(item)
    return [
        recommendation
        for index, recommendation in enumerate(candidates)
        if len(verdicts_by_index.get(index, [])) == 1
        and verdicts_by_index[index][0].supported
        and not verdicts_by_index[index][0].issues
    ]
