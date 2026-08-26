"""Build and validate the stable tag tree derived from a parsed outline."""

from typing import Any

from writing.modules.outline_parser import OutlineStructureError
from writing.schemas import OutlineNode, ParsedHeading


def build_tag_tree(headings: list[ParsedHeading]) -> list[OutlineNode]:
    """Build a validated tag tree while preserving source order.

    Structural paths, rather than title text, determine IDs. As a result,
    repeated titles in different branches remain distinct.
    """

    if not headings:
        raise OutlineStructureError("outline contains no headings")
    if headings[0].level != 1:
        raise OutlineStructureError("the first heading must be the root at level 1")

    records: list[dict[str, Any]] = []
    stack: list[int] = []
    child_counts: dict[str, int] = {}

    for order, heading in enumerate(headings):
        if heading.level == 1 and order != 0:
            raise OutlineStructureError("outline must contain exactly one root heading")
        if heading.level > len(stack) + 1:
            raise OutlineStructureError(
                f"illegal level jump before heading: {heading.title}"
            )

        if heading.level == 1:
            parent_id = None
            ancestor_ids: list[str] = []
            path_titles: list[str] = [heading.title]
            tag_id = "TAG-ROOT"
            stack = []
        else:
            parent_index = stack[heading.level - 2]
            parent = records[parent_index]
            parent_id = str(parent["tag_id"])
            next_child = child_counts.get(parent_id, 0) + 1
            child_counts[parent_id] = next_child
            parent_suffix = parent_id.removeprefix("TAG-")
            tag_id = (
                f"TAG-{heading.number}"
                if heading.number is not None
                else (
                    f"TAG-{next_child}"
                    if parent_suffix == "ROOT"
                    else f"TAG-{parent_suffix}.{next_child}"
                )
            )
            ancestor_ids = [*parent["ancestor_ids"], parent_id]
            path_titles = [*parent["path_titles"], heading.title]
            parent["child_ids"].append(tag_id)

        record: dict[str, Any] = {
            "tag_id": tag_id,
            "number": heading.number,
            "title": heading.title,
            "normalized_label": None,
            "parent_id": parent_id,
            "child_ids": [],
            "ancestor_ids": ancestor_ids,
            "depth": heading.level - 1,
            "order": order,
            "path_titles": path_titles,
        }
        records.append(record)
        stack = stack[: heading.level - 1]
        stack.append(order)

    tree = [OutlineNode.model_validate(record) for record in records]
    validate_tag_tree(tree)
    return tree


def validate_tag_tree(tree: list[OutlineNode]) -> None:
    """Reject duplicate IDs, dangling relationships, cycles, and unreachable nodes."""

    if not tree or tree[0].tag_id != "TAG-ROOT":
        raise OutlineStructureError("tag tree must start with TAG-ROOT")

    by_id = {node.tag_id: node for node in tree}
    if len(by_id) != len(tree):
        raise OutlineStructureError("tag IDs must be unique")
    if [node.order for node in tree] != list(range(len(tree))):
        raise OutlineStructureError("tag traversal order must be unique and contiguous")
    root = tree[0]
    if any(
        [
            root.parent_id is not None,
            bool(root.ancestor_ids),
            root.depth != 0,
            root.path_titles != [root.title],
        ]
    ):
        raise OutlineStructureError("TAG-ROOT has invalid structural fields")

    visited: set[str] = set()
    active: set[str] = set()

    def visit(tag_id: str) -> None:
        if tag_id in active:
            raise OutlineStructureError("tag tree contains a cycle")
        if tag_id in visited:
            return
        node = by_id.get(tag_id)
        if node is None:
            raise OutlineStructureError(f"unknown tag ID: {tag_id}")
        active.add(tag_id)
        if len(node.child_ids) != len(set(node.child_ids)):
            raise OutlineStructureError(f"duplicate child IDs under {tag_id}")
        for child_id in node.child_ids:
            child = by_id.get(child_id)
            if child is None or child.parent_id != tag_id:
                raise OutlineStructureError(f"invalid child relationship: {tag_id} -> {child_id}")
            expected_ancestors = [*node.ancestor_ids, tag_id]
            if child.ancestor_ids != expected_ancestors:
                raise OutlineStructureError(f"invalid ancestor relationship for {child_id}")
            if child.depth != node.depth + 1:
                raise OutlineStructureError(f"invalid depth for {child_id}")
            if child.path_titles != [*node.path_titles, child.title]:
                raise OutlineStructureError(f"invalid title path for {child_id}")
            visit(child_id)
        active.remove(tag_id)
        visited.add(tag_id)

    visit("TAG-ROOT")
    if visited != set(by_id):
        unreachable = sorted(set(by_id) - visited)
        raise OutlineStructureError(f"unreachable tags: {', '.join(unreachable)}")


def postorder_tag_ids(tree: list[OutlineNode]) -> list[str]:
    """Return stable bottom-up traversal order for later writing stages."""

    validate_tag_tree(tree)
    by_id = {node.tag_id: node for node in tree}
    ordered: list[str] = []

    def visit(tag_id: str) -> None:
        for child_id in by_id[tag_id].child_ids:
            visit(child_id)
        ordered.append(tag_id)

    visit("TAG-ROOT")
    return ordered
