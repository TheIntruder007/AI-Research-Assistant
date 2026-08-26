"""Assemble audited section artifacts into the final Markdown review."""

from collections.abc import Sequence

from writing.modules.citation_formatter import (
    build_citation_map,
    build_reference_list,
    extract_cited_paper_ids,
    format_citations,
)
from writing.modules.tag_tree import validate_tag_tree
from writing.schemas import (
    CitationInfo,
    OutlineNode,
    PaperMetadata,
    ReviewDocument,
    SectionDraft,
    TagDefinition,
    VisualRecommendation,
)


class ReviewAssemblyError(ValueError):
    """Raised when section artifacts cannot preserve the supplied outline."""


def _visual_placeholder(
    recommendation: VisualRecommendation, output_language: str
) -> list[str]:
    """Render one explicit, non-executable placeholder for later human production."""

    prompt = " ".join(recommendation.prompt.split())
    caption = " ".join(recommendation.caption.split())
    if output_language.casefold().startswith("zh"):
        kind = "图片" if recommendation.visual_type == "figure" else "表格"
        title = f"图表占位：{kind}"
        prompt_label = "制作提示词"
        caption_label = "图注" if recommendation.visual_type == "figure" else "表注"
        source_label = "证据观点 IDs"
    else:
        kind = "Figure" if recommendation.visual_type == "figure" else "Table"
        title = f"Visual placeholder: {kind}"
        prompt_label = "Visual prompt"
        caption_label = "Caption"
        source_label = "Source point IDs"
    return [
        (
            "<!-- VISUAL_RECOMMENDATION_START "
            f"type={recommendation.visual_type} tag_id={recommendation.tag_id} -->"
        ),
        f"> **{title}**",
        ">",
        f"> **{prompt_label}:** {prompt}",
        ">",
        f"> **{caption_label}:** {caption}",
        ">",
        f"> **{source_label}:** {', '.join(recommendation.source_point_ids)}",
        "<!-- VISUAL_RECOMMENDATION_END -->",
    ]


def _insert_visual_placeholders(
    content: str,
    recommendations: Sequence[VisualRecommendation],
    output_language: str,
) -> str:
    rendered = content
    for recommendation in recommendations:
        anchor = recommendation.placement_after
        if rendered.count(anchor) != 1:
            raise ReviewAssemblyError(
                f"visual placement anchor must occur exactly once in {recommendation.tag_id}"
            )
        placeholder = "\n".join(_visual_placeholder(recommendation, output_language))
        rendered = rendered.replace(anchor, f"{anchor}\n\n{placeholder}", 1)
    return rendered


def assemble_review(
    tree: list[OutlineNode],
    definitions: list[TagDefinition],
    drafts: dict[str, SectionDraft],
    introduction: SectionDraft,
    conclusion: SectionDraft,
    citations: dict[str, CitationInfo],
    *,
    citation_style: str = "elsevier-harvard",
    metadata_by_paper_id: dict[str, PaperMetadata] | None = None,
    output_language: str = "en",
    visual_recommendations: Sequence[VisualRecommendation] = (),
) -> ReviewDocument:
    """Render the immutable outline in source order and append unique references."""

    validate_tag_tree(tree)
    definition_by_id = {definition.tag_id: definition for definition in definitions}
    tree_ids = {node.tag_id for node in tree}
    if set(definition_by_id) != tree_ids:
        raise ReviewAssemblyError("tag definitions must exactly cover the tag tree")
    unknown_drafts = sorted(set(drafts) - (tree_ids - {"TAG-ROOT"}))
    if unknown_drafts:
        raise ReviewAssemblyError(f"drafts contain unknown tags: {', '.join(unknown_drafts)}")
    unknown_visual_tags = sorted(
        {item.tag_id for item in visual_recommendations} - set(drafts)
    )
    if unknown_visual_tags:
        raise ReviewAssemblyError(
            "visual recommendations contain unknown or root tags: "
            + ", ".join(unknown_visual_tags)
        )
    visuals_by_tag: dict[str, list[VisualRecommendation]] = {}
    for recommendation in visual_recommendations:
        if not set(recommendation.source_point_ids).issubset(
            drafts[recommendation.tag_id].used_point_ids
        ):
            raise ReviewAssemblyError(
                f"visual recommendation uses points outside {recommendation.tag_id}"
            )
        visuals_by_tag.setdefault(recommendation.tag_id, []).append(recommendation)

    required_ids = [
        node.tag_id
        for node in tree[1:]
        if definition_by_id[node.tag_id].node_type != "container"
    ]
    missing = [tag_id for tag_id in required_ids if tag_id not in drafts]
    if missing:
        raise ReviewAssemblyError(f"missing required section drafts: {', '.join(missing)}")

    raw_parts = [introduction.content]
    for node in tree[1:]:
        draft = drafts.get(node.tag_id)
        if draft is not None:
            if draft.tag_id != node.tag_id:
                raise ReviewAssemblyError(f"draft tag mismatch for {node.tag_id}")
            raw_parts.append(draft.content)
    raw_parts.append(conclusion.content)
    cited_paper_ids = list(
        dict.fromkeys(
            paper_id
            for part in raw_parts
            for paper_id in extract_cited_paper_ids(part)
        )
    )
    if metadata_by_paper_id is not None:
        citations = build_citation_map(
            cited_paper_ids, metadata_by_paper_id, citation_style
        )
        reference_paper_ids = list(citations)
    else:
        reference_paper_ids = cited_paper_ids
    references = build_reference_list(reference_paper_ids, citations)

    rendered: list[str] = [f"# {tree[0].title}", ""]
    if introduction.content.strip():
        rendered.extend(
            [format_citations(introduction.content, citations, citation_style), ""]
        )
    for node in tree[1:]:
        rendered.extend([f"{'#' * (node.depth + 1)} {node.title}", ""])
        draft = drafts.get(node.tag_id)
        if draft is not None and draft.content.strip():
            content = _insert_visual_placeholders(
                draft.content,
                visuals_by_tag.get(node.tag_id, []),
                output_language,
            )
            rendered.extend(
                [format_citations(content, citations, citation_style), ""]
            )
    if conclusion.content.strip():
        rendered.extend([format_citations(conclusion.content, citations, citation_style), ""])

    reference_heading = "参考文献" if output_language.casefold().startswith("zh") else "References"
    rendered.extend([f"## {reference_heading}", ""])
    rendered.extend(f"- {entry}" for entry in references)
    markdown = "\n".join(rendered).rstrip() + "\n"
    return ReviewDocument(
        markdown=markdown,
        cited_paper_ids=cited_paper_ids,
        references=references,
    )
