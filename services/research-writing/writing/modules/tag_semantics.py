"""Assign model-generated semantics while preserving the deterministic tag tree."""

import json

from writing.adapters.language_model import (
    LanguageModel,
    generate_validated,
)
from writing.modules.prompt_loader import load_prompt
from writing.schemas import (
    OutlineNode,
    TagDefinition,
    TagSemanticBatch,
)


class TagSemanticsError(ValueError):
    """Raised when semantic output does not match the immutable tag tree."""


async def define_tag_semantics(
    review_question: str,
    tree: list[OutlineNode],
    model: LanguageModel,
    *,
    outline_context: str | None = None,
) -> list[TagDefinition]:
    """Define every tag's semantics through a structure-preserving interface."""

    system_prompt = load_prompt("define_tag_semantics.md")
    user_prompt = json.dumps(
        {
            "review_question": review_question,
            "outline_tree": [node.model_dump(mode="json") for node in tree],
            "outline_context": outline_context,
        },
        ensure_ascii=False,
        indent=2,
    )
    result = await generate_validated(
        model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=TagSemanticBatch,
    )

    expected_ids = [node.tag_id for node in tree]
    returned_ids = [semantic.tag_id for semantic in result.tags]
    if returned_ids != expected_ids:
        raise TagSemanticsError(
            "semantic output must contain every tag exactly once in outline order"
        )
    if result.tags[0].node_type != "root":
        raise TagSemanticsError("TAG-ROOT node_type must be root")
    invalid_roots = [
        semantic.tag_id
        for semantic in result.tags[1:]
        if semantic.node_type == "root"
    ]
    if invalid_roots:
        raise TagSemanticsError(
            "only TAG-ROOT may use root node_type: " + ", ".join(invalid_roots)
        )

    return [
        TagDefinition(
            tag_id=node.tag_id,
            title=node.title,
            normalized_label=semantic.normalized_label,
            description=semantic.description,
            include_when=semantic.include_when,
            exclude_when=semantic.exclude_when,
            parent_id=node.parent_id,
            child_ids=node.child_ids,
            depth=node.depth,
            # A "container" node has no prose of its own (graph.py renders
            # only its heading; its children's summaries carry the content —
            # see D-020) — but `child_ids` comes from the deterministic
            # outline structure, independent of this LLM-assigned
            # `node_type`. A childless node classified as "container" is a
            # guaranteed, model-luck-independent blank section: nothing can
            # ever carry its content. Confirmed on a real run (a flat,
            # childless "Background" section rendered permanently empty,
            # caught by completeness.py — see DECISIONS.md D-026). Force such
            # a node to "content" (a real, writable leaf) instead of trusting
            # a structurally-impossible classification.
            node_type=(
                "content" if semantic.node_type == "container" and not node.child_ids
                else semantic.node_type
            ),
        )
        for node, semantic in zip(tree, result.tags, strict=True)
    ]
