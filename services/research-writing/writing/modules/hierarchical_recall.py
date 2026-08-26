"""Deterministic direct, rollup, leaf, and subtree recall."""

from collections.abc import Iterable

from writing.modules.tag_tree import validate_tag_tree
from writing.schemas import (
    OutlineNode,
    TagCoverage,
    TagCoverageReport,
    TagIndex,
    TagIndexItem,
)


class RecallError(ValueError):
    """Raised when a requested tag does not exist."""


def _deduplicate(items: Iterable[TagIndexItem]) -> list[TagIndexItem]:
    seen: set[str] = set()
    result: list[TagIndexItem] = []
    for item in items:
        if item.point_id in seen:
            continue
        seen.add(item.point_id)
        result.append(item)
    return result


def _node(tag_id: str, tree: list[OutlineNode]) -> OutlineNode:
    try:
        return next(node for node in tree if node.tag_id == tag_id)
    except StopIteration as error:
        raise RecallError(f"unknown tag ID: {tag_id}") from error


def direct_items(tag_id: str, index: TagIndex) -> list[TagIndexItem]:
    """Return only points directly assigned to a tag."""

    try:
        return list(index[tag_id])
    except KeyError as error:
        raise RecallError(f"unknown tag ID: {tag_id}") from error


def recall_leaf(
    tag_id: str,
    index: TagIndex,
    tree: list[OutlineNode],
) -> list[TagIndexItem]:
    """Recall a leaf's direct points followed by ancestor direct context."""

    validate_tag_tree(tree)
    node = _node(tag_id, tree)
    if node.child_ids:
        raise RecallError(f"tag is not a leaf: {tag_id}")
    items = direct_items(tag_id, index)
    for ancestor_id in node.ancestor_ids:
        items.extend(direct_items(ancestor_id, index))
    return _deduplicate(items)


def _descendant_ids(tag_id: str, tree: list[OutlineNode]) -> list[str]:
    by_id = {node.tag_id: node for node in tree}
    ordered: list[str] = []

    def visit(current_id: str) -> None:
        for child_id in by_id[current_id].child_ids:
            ordered.append(child_id)
            visit(child_id)

    visit(tag_id)
    return ordered


def rollup_items(
    tag_id: str,
    index: TagIndex,
    tree: list[OutlineNode],
) -> list[TagIndexItem]:
    """Aggregate a tag's direct points and all descendant direct points."""

    validate_tag_tree(tree)
    _node(tag_id, tree)
    ids = [tag_id, *_descendant_ids(tag_id, tree)]
    return _deduplicate(
        item for current_id in ids for item in direct_items(current_id, index)
    )


def recall_subtree(
    tag_id: str,
    index: TagIndex,
    tree: list[OutlineNode],
) -> list[TagIndexItem]:
    """Recall one complete branch for explicitly requested subtree generation."""

    return rollup_items(tag_id, index, tree)


def analyze_tag_coverage(
    index: TagIndex,
    tree: list[OutlineNode],
) -> TagCoverageReport:
    """Report empty tags without deleting them or inventing evidence."""

    validate_tag_tree(tree)
    tags: dict[str, TagCoverage] = {}
    insufficient: list[str] = []
    for node in tree:
        direct = direct_items(node.tag_id, index)
        rolled_up = rollup_items(node.tag_id, index, tree)
        is_insufficient = not rolled_up
        if is_insufficient:
            insufficient.append(node.tag_id)
        tags[node.tag_id] = TagCoverage(
            tag_id=node.tag_id,
            direct_point_count=len(direct),
            rollup_point_count=len(rolled_up),
            paper_ids=list(dict.fromkeys(item.paper_id for item in rolled_up)),
            insufficient_evidence=is_insufficient,
        )
    return TagCoverageReport(tags=tags, insufficient_tag_ids=insufficient)
