"""Build code-controlled evidence contexts for section writing."""

from typing import Literal

from writing.modules.hierarchical_recall import (
    direct_items,
    recall_subtree,
)
from writing.modules.tag_tree import validate_tag_tree
from writing.schemas import (
    OutlineNode,
    SectionSummary,
    SectionWritingContext,
    TagDefinition,
    TagIndex,
    TagIndexItem,
)


class SectionContextError(ValueError):
    """Raised when a context cannot be derived from the supplied artifacts."""


def _deduplicate(items: list[TagIndexItem]) -> list[TagIndexItem]:
    seen: set[str] = set()
    result: list[TagIndexItem] = []
    for item in items:
        if item.point_id not in seen:
            seen.add(item.point_id)
            result.append(item)
    return result


def build_section_context(
    tag_id: str,
    tree: list[OutlineNode],
    definitions: list[TagDefinition],
    index: TagIndex,
    child_summaries: dict[str, SectionSummary] | None = None,
    target_words: int | None = None,
    writing_mode: Literal["leaf_section", "parent_intro", "subtree"] | None = None,
    output_language: str = "en",
) -> SectionWritingContext:
    """Derive all evidence and allowed citations for exactly one section."""

    validate_tag_tree(tree)
    by_id = {node.tag_id: node for node in tree}
    definition_by_id = {definition.tag_id: definition for definition in definitions}
    if set(definition_by_id) != set(by_id):
        raise SectionContextError("tag definitions must exactly cover the tag tree")
    try:
        node = by_id[tag_id]
    except KeyError as error:
        raise SectionContextError(f"unknown tag ID: {tag_id}") from error

    mode = writing_mode or ("leaf_section" if not node.child_ids else "parent_intro")
    if mode == "leaf_section" and node.child_ids:
        raise SectionContextError(f"non-leaf tag cannot use leaf_section mode: {tag_id}")

    if mode == "subtree":
        direct = recall_subtree(tag_id, index, tree)
    else:
        direct = direct_items(tag_id, index)

    direct_ids = {item.point_id for item in direct}
    ancestors = (
        []
        if mode == "parent_intro"
        else _deduplicate(
            [
                item
                for ancestor_id in node.ancestor_ids
                for item in direct_items(ancestor_id, index)
                if item.point_id not in direct_ids
            ]
        )
    )

    supplied_summaries = child_summaries or {}
    summary_records = [
        supplied_summaries[child_id]
        for child_id in node.child_ids
        if child_id in supplied_summaries
    ]
    allowed_paper_ids = list(
        dict.fromkeys(
            [item.paper_id for item in [*direct, *ancestors]]
            + [paper_id for summary in summary_records for paper_id in summary.cited_paper_ids]
        )
    )
    allowed_point_ids = list(
        dict.fromkeys(
            [item.point_id for item in [*direct, *ancestors]]
            + [point_id for summary in summary_records for point_id in summary.used_point_ids]
        )
    )
    all_items = [item for values in index.values() for item in values]
    citation_lookup = {item.paper_id: item.citation for item in all_items}
    missing_citations = [
        paper_id for paper_id in allowed_paper_ids if paper_id not in citation_lookup
    ]
    if missing_citations:
        raise SectionContextError(
            f"missing citations for allowed papers: {', '.join(missing_citations)}"
        )

    sibling_titles: list[str] = []
    if node.parent_id is not None:
        sibling_titles = [
            by_id[sibling_id].title
            for sibling_id in by_id[node.parent_id].child_ids
            if sibling_id != tag_id
        ]

    return SectionWritingContext(
        tag_id=tag_id,
        title=node.title,
        outline_path=node.path_titles,
        depth=node.depth,
        writing_mode=mode,
        direct_points=direct,
        ancestor_context=ancestors,
        child_summaries=[summary.summary for summary in summary_records],
        allowed_paper_ids=allowed_paper_ids,
        allowed_point_ids=allowed_point_ids,
        citations={paper_id: citation_lookup[paper_id] for paper_id in allowed_paper_ids},
        sibling_titles=sibling_titles,
        prohibited_topics=sibling_titles,
        target_words=target_words,
        output_language=output_language,
    )
