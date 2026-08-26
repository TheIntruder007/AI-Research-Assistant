"""Deterministic and optional semantic validation for literature cards."""

import json

from writing.adapters.language_model import (
    LanguageModel,
    generate_validated,
)
from writing.modules.prompt_loader import load_prompt
from writing.schemas import (
    CardAudit,
    CardSemanticAuditContent,
    LiteratureCard,
    OutlineNode,
    TagDefinition,
)


def validate_literature_card(
    card: LiteratureCard, tree: list[OutlineNode]
) -> CardAudit:
    """Validate tag coverage and point references without invoking an LLM."""

    errors: list[str] = []
    expected_tags = {node.tag_id for node in tree}
    actual_tags = set(card.tag_values)

    missing = sorted(expected_tags - actual_tags)
    if missing:
        errors.append(f"missing tag keys: {', '.join(missing)}")
    unknown = sorted(actual_tags - expected_tags)
    if unknown:
        errors.append(f"unknown tag keys: {', '.join(unknown)}")

    point_ids = [point.point_id for point in card.points.values()]
    if len(point_ids) != len(set(point_ids)):
        errors.append("point IDs must be unique")

    mismatched_keys = sorted(
        key for key, point in card.points.items() if key != point.point_id
    )
    if mismatched_keys:
        errors.append(f"point dictionary keys do not match point IDs: {', '.join(mismatched_keys)}")
    invalid_prefixes = sorted(
        point_id
        for point_id in point_ids
        if not point_id.startswith(f"{card.paper_id}-POINT-")
    )
    if invalid_prefixes:
        errors.append(
            "point IDs must be scoped to the paper: " + ", ".join(invalid_prefixes)
        )

    duplicate_tag_references = sorted(
        tag_id
        for tag_id, values in card.tag_values.items()
        if len(values) != len(set(values))
    )
    if duplicate_tag_references:
        errors.append(
            "duplicate point references within tags: "
            + ", ".join(duplicate_tag_references)
        )

    referenced = {
        point_id for values in card.tag_values.values() for point_id in values
    }
    dangling = sorted(referenced - set(card.points))
    if dangling:
        errors.append(f"dangling point IDs: {', '.join(dangling)}")

    by_id = {node.tag_id: node for node in tree}
    duplicate_pairs: set[tuple[str, str, str]] = set()
    for tag_id, values in card.tag_values.items():
        node = by_id.get(tag_id)
        if node is None:
            continue
        for ancestor_id in node.ancestor_ids:
            shared = set(values) & set(card.tag_values.get(ancestor_id, []))
            duplicate_pairs.update((point_id, ancestor_id, tag_id) for point_id in shared)
    for point_id, ancestor_id, descendant_id in sorted(duplicate_pairs):
        errors.append(
            f"point {point_id} is duplicated across ancestor {ancestor_id} "
            f"and descendant {descendant_id}"
        )

    return CardAudit(
        paper_id=card.paper_id,
        passed=not errors,
        errors=errors,
    )


async def audit_literature_card_semantics(
    card: LiteratureCard,
    definitions: list[TagDefinition],
    model: LanguageModel,
) -> CardAudit:
    """Audit meaning, attribution, causality, and most-specific tag placement."""

    system_prompt = load_prompt("validate_literature_card.md")
    output = await generate_validated(
        model,
        system_prompt=system_prompt,
        user_prompt=json.dumps(
            {
                "tag_definitions": [
                    definition.model_dump(mode="json") for definition in definitions
                ],
                "literature_card": card.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        response_model=CardSemanticAuditContent,
    )
    return CardAudit(
        paper_id=card.paper_id,
        passed=output.passed and not output.errors,
        errors=output.errors,
        revision_instructions=output.revision_instructions,
        semantic_checked=True,
    )
