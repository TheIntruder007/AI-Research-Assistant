"""Regression test for DECISIONS.md D-026's container/child_ids fix.

Root cause (found via a real end-to-end validation run — see
analytics_and_results.md §15): `define_tag_semantics.py` took `node_type`
directly from the model's own judgment, independent of whether the tag
structurally has any children (`child_ids`, fixed by the deterministic
outline parser). A flat outline section (no "### " subheadings, so
child_ids == []) that the model nonetheless classified as "container" (no
prose of its own — see D-020) rendered as a permanently, deterministically
blank section: nothing could ever carry its content. Confirmed on a real
run: a childless "Background" section rendered completely empty every time,
regardless of model variance.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.modules.tag_semantics import define_tag_semantics  # noqa: E402
from writing.schemas import OutlineNode  # noqa: E402


def _node(tag_id, title, *, parent_id, child_ids, depth) -> OutlineNode:
    return OutlineNode(
        tag_id=tag_id, title=title, parent_id=parent_id, child_ids=child_ids,
        ancestor_ids=[] if parent_id is None else [parent_id], depth=depth,
        order=0, path_titles=[title],
    )


class _FakeModel:
    def __init__(self, node_types: dict[str, str]):
        self._node_types = node_types

    async def generate_structured(self, *, system_prompt, user_prompt, response_model):
        return response_model.model_validate({
            "tags": [
                {"tag_id": tag_id, "normalized_label": tag_id, "description": "d",
                 "include_when": ["x"], "exclude_when": ["y"], "node_type": node_type}
                for tag_id, node_type in self._node_types.items()
            ],
        })


def test_childless_container_is_downgraded_to_content():
    tree = [
        _node("TAG-ROOT", "Q", parent_id=None, child_ids=["TAG-1"], depth=0),
        _node("TAG-1", "Background", parent_id="TAG-ROOT", child_ids=[], depth=1),
    ]
    model = _FakeModel({"TAG-ROOT": "root", "TAG-1": "container"})
    definitions = asyncio.run(define_tag_semantics("Q?", tree, model))
    background = next(d for d in definitions if d.tag_id == "TAG-1")
    assert background.node_type == "content"


def test_container_with_real_children_is_left_unchanged():
    tree = [
        _node("TAG-ROOT", "Q", parent_id=None, child_ids=["TAG-1"], depth=0),
        _node("TAG-1", "Overview", parent_id="TAG-ROOT", child_ids=["TAG-1.1"], depth=1),
        _node("TAG-1.1", "Detail", parent_id="TAG-1", child_ids=[], depth=2),
    ]
    model = _FakeModel({"TAG-ROOT": "root", "TAG-1": "container", "TAG-1.1": "content"})
    definitions = asyncio.run(define_tag_semantics("Q?", tree, model))
    overview = next(d for d in definitions if d.tag_id == "TAG-1")
    assert overview.node_type == "container"


def test_childless_content_node_is_unaffected():
    tree = [
        _node("TAG-ROOT", "Q", parent_id=None, child_ids=["TAG-1"], depth=0),
        _node("TAG-1", "Background", parent_id="TAG-ROOT", child_ids=[], depth=1),
    ]
    model = _FakeModel({"TAG-ROOT": "root", "TAG-1": "content"})
    definitions = asyncio.run(define_tag_semantics("Q?", tree, model))
    background = next(d for d in definitions if d.tag_id == "TAG-1")
    assert background.node_type == "content"
