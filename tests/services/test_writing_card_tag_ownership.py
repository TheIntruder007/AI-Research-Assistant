"""Tag-ownership tests for the deterministic literature-card validator
(writing/modules/card_validation.py) — see DECISIONS.md D-020.

These test the DETECTOR side directly (no LLM involved): given a
hand-constructed card and tag tree, does validate_literature_card() enforce
the intended ownership rules? This detector was already proven correct in
production (it caught the real P003 ancestor/descendant duplication that
motivated D-019/D-020's tag-semantics fix) but had no direct unit test of
its own before this pass.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.modules.card_validation import validate_literature_card  # noqa: E402
from writing.schemas import (  # noqa: E402
    CitationInfo, LiteratureCard, OutlineNode, PaperMetadata, TaggedPoint,
)

_CITATION = CitationInfo(
    citation_key="a2024", in_text_citation="(A, 2024)",
    narrative_citation="A (2024)", reference_entry="A. (2024). Title.",
)
_METADATA = PaperMetadata(title="Title", authors=["A. Author"])


def _tree() -> list[OutlineNode]:
    """TAG-ROOT with two children TAG-1/TAG-2 (siblings), TAG-1 with one
    child TAG-1.1 (an ancestor/descendant pair distinct from the siblings)."""
    return [
        OutlineNode(tag_id="TAG-ROOT", title="Root", parent_id=None,
                    child_ids=["TAG-1", "TAG-2"], ancestor_ids=[], depth=0, order=0,
                    path_titles=["Root"]),
        OutlineNode(tag_id="TAG-1", title="A", parent_id="TAG-ROOT",
                    child_ids=["TAG-1.1"], ancestor_ids=["TAG-ROOT"], depth=1, order=1,
                    path_titles=["Root", "A"]),
        OutlineNode(tag_id="TAG-1.1", title="A detail", parent_id="TAG-1",
                    child_ids=[], ancestor_ids=["TAG-ROOT", "TAG-1"], depth=2, order=2,
                    path_titles=["Root", "A", "A detail"]),
        OutlineNode(tag_id="TAG-2", title="B", parent_id="TAG-ROOT",
                    child_ids=[], ancestor_ids=["TAG-ROOT"], depth=1, order=3,
                    path_titles=["Root", "B"]),
    ]


def _card(tag_values: dict[str, list[str]], point_ids: list[str]) -> LiteratureCard:
    points = {pid: TaggedPoint(point_id=pid, content="c", content_type="background",
                               certainty="supported") for pid in point_ids}
    return LiteratureCard(paper_id="P001", metadata=_METADATA, citation=_CITATION,
                          points=points, tag_values=tag_values)


def test_a_root_only_evidence_is_valid():
    """A point relevant to the overall question but not owned by any child
    tag may legitimately live on TAG-ROOT alone."""
    card = _card(
        tag_values={"TAG-ROOT": ["P001-POINT-01"], "TAG-1": [], "TAG-1.1": [], "TAG-2": []},
        point_ids=["P001-POINT-01"],
    )
    audit = validate_literature_card(card, _tree())
    assert audit.passed, audit.errors


def test_b_child_owned_evidence_is_valid_and_root_need_not_duplicate_it():
    card = _card(
        tag_values={"TAG-ROOT": [], "TAG-1": ["P001-POINT-01"], "TAG-1.1": [], "TAG-2": []},
        point_ids=["P001-POINT-01"],
    )
    audit = validate_literature_card(card, _tree())
    assert audit.passed, audit.errors


def test_c_ancestor_descendant_conflict_is_rejected():
    """The exact real-world failure (D-019/D-020): the same point assigned
    to both a tag and its own ancestor."""
    card = _card(
        tag_values={"TAG-ROOT": ["P001-POINT-01"], "TAG-1": ["P001-POINT-01"],
                   "TAG-1.1": [], "TAG-2": []},
        point_ids=["P001-POINT-01"],
    )
    audit = validate_literature_card(card, _tree())
    assert not audit.passed
    assert any("duplicated across ancestor" in error for error in audit.errors)


def test_c_deeper_ancestor_descendant_conflict_is_also_rejected():
    card = _card(
        tag_values={"TAG-ROOT": [], "TAG-1": ["P001-POINT-01"], "TAG-1.1": ["P001-POINT-01"],
                   "TAG-2": []},
        point_ids=["P001-POINT-01"],
    )
    audit = validate_literature_card(card, _tree())
    assert not audit.passed
    assert any("duplicated across ancestor" in error for error in audit.errors)


def test_d_sibling_sharing_is_permitted_not_flagged_as_duplication():
    """Per build_literature_card.md: 'A genuinely cross-branch claim may
    reuse one point ID across those branches' — siblings (not ancestor/
    descendant) may legitimately share a point without triggering the
    ancestor/descendant duplication check."""
    card = _card(
        tag_values={"TAG-ROOT": [], "TAG-1": ["P001-POINT-01"], "TAG-1.1": [],
                   "TAG-2": ["P001-POINT-01"]},
        point_ids=["P001-POINT-01"],
    )
    audit = validate_literature_card(card, _tree())
    assert audit.passed, audit.errors
