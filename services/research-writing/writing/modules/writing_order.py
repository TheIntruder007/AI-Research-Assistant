"""Plan deterministic bottom-up section generation."""

from writing.modules.tag_tree import postorder_tag_ids
from writing.schemas import OutlineNode


def plan_writing_order(tree: list[OutlineNode]) -> list[str]:
    """Return all body-section tags in postorder, excluding the document root."""

    return [tag_id for tag_id in postorder_tag_ids(tree) if tag_id != "TAG-ROOT"]
