"""Build a deterministic tag-to-paper inverted index."""

from writing.schemas import (
    LiteratureCard,
    OutlineNode,
    TagIndex,
    TagIndexItem,
)


class TagIndexError(ValueError):
    """Raised when cards cannot be expanded against the supplied tag tree."""


def build_tag_index(
    cards: list[LiteratureCard], tree: list[OutlineNode]
) -> TagIndex:
    """Expand direct card assignments without model calls or parent rollups."""

    expected_ids = [node.tag_id for node in tree]
    expected_set = set(expected_ids)
    index: TagIndex = {tag_id: [] for tag_id in expected_ids}

    for card in cards:
        actual_set = set(card.tag_values)
        if actual_set != expected_set:
            missing = sorted(expected_set - actual_set)
            unknown = sorted(actual_set - expected_set)
            details = []
            if missing:
                details.append(f"missing={','.join(missing)}")
            if unknown:
                details.append(f"unknown={','.join(unknown)}")
            raise TagIndexError(
                f"card {card.paper_id} does not cover the tag tree ({'; '.join(details)})"
            )
        for tag_id in expected_ids:
            for point_id in card.tag_values[tag_id]:
                point = card.points.get(point_id)
                if point is None:
                    raise TagIndexError(
                        f"card {card.paper_id} references unknown point {point_id}"
                    )
                index[tag_id].append(
                    TagIndexItem(
                        tag_id=tag_id,
                        paper_id=card.paper_id,
                        point_id=point.point_id,
                        content=point.content,
                        content_type=point.content_type,
                        stance=point.stance,
                        certainty=point.certainty,
                        citation=card.citation,
                    )
                )
    return index
