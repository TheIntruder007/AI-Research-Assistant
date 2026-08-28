"""Test D from the outer-retry test list: one section failing must not
corrupt the graph or prevent other independent sections from completing,
and the final status must correctly reflect the mixed outcome.

No live Ollama needed — a fake model scripts tag semantics, one literature
card, and per-tag section responses (failing every attempt for TAG-1,
succeeding immediately for TAG-2).
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.graph import run_review_async  # noqa: E402
from writing.schemas import ReviewInput  # noqa: E402

_PAPER_MARKDOWN = "---\nevidence_depth: abstract\n---\n\n# A Paper\n\nSome abstract text.\n"


class _OneSectionAlwaysFailsModel:
    """TAG-1 fails on every attempt (a genuinely blind-retried failure,
    since nothing about the request changes between attempts); TAG-2
    succeeds immediately. Both share one ancestor-owned point from TAG-ROOT."""

    def __init__(self):
        self.tag1_attempts = 0

    async def generate_structured(self, *, system_prompt, user_prompt, response_model):
        name = response_model.__name__
        if name == "TagSemanticBatch":
            return response_model.model_validate({
                "tags": [
                    {"tag_id": "TAG-ROOT", "normalized_label": "root", "description": "d",
                     "include_when": ["x"], "exclude_when": ["y"], "node_type": "root"},
                    {"tag_id": "TAG-1", "normalized_label": "a", "description": "d",
                     "include_when": ["x"], "exclude_when": ["y"], "node_type": "content"},
                    {"tag_id": "TAG-2", "normalized_label": "b", "description": "d",
                     "include_when": ["x"], "exclude_when": ["y"], "node_type": "content"},
                ],
            })
        if name == "LiteratureCardContent":
            return response_model.model_validate({
                "metadata": {"title": "A Paper", "authors": ["A. Author"]},
                "citation": {
                    "citation_key": "author2024", "in_text_citation": "(Author, 2024)",
                    "narrative_citation": "Author (2024)",
                    "reference_entry": "Author, A. (2024). A Paper.",
                },
                "points": {"P001-POINT-01": {
                    "point_id": "P001-POINT-01", "content": "A general finding.",
                    "content_type": "background", "certainty": "supported",
                }},
                "tag_values": {"TAG-ROOT": ["P001-POINT-01"], "TAG-1": [], "TAG-2": []},
            })
        if name == "SectionDraftContent":
            # Only a real per-section write (SectionWritingContext.model_dump()
            # carries a top-level "tag_id") should match — the introduction/
            # conclusion prompts embed the whole outline tree, which contains
            # "tag_id" values nested inside other nodes too.
            payload = json.loads(user_prompt)
            if payload.get("tag_id") == "TAG-1":
                self.tag1_attempts += 1
                raise RuntimeError(f"simulated model failure (attempt {self.tag1_attempts})")
            if payload.get("tag_id") == "TAG-2":
                return response_model.model_validate({
                    "content": "Section B body citing [@P001].",
                    "cited_paper_ids": ["P001"], "used_point_ids": ["P001-POINT-01"],
                })
            # Introduction/conclusion: no evidence assigned to TAG-ROOT's own
            # summaries beyond ancestor points, so keep these trivial and
            # evidence-honest (cite nothing rather than inventing content).
            return response_model.model_validate({
                "content": "Overview text.", "cited_paper_ids": [], "used_point_ids": [],
            })
        raise AssertionError(f"unexpected call: {name}")


def test_one_failing_section_does_not_block_or_corrupt_other_sections(tmp_path):
    literature_dir = tmp_path / "literature"
    literature_dir.mkdir()
    (literature_dir / "paper.md").write_text(_PAPER_MARKDOWN, encoding="utf-8")
    outline = "# Q\n## A\n## B\n"
    request = ReviewInput(
        review_question="Q", outline=outline, literature_directory=str(literature_dir),
        output_directory=str(tmp_path / "runs"),
    )
    model = _OneSectionAlwaysFailsModel()

    result = asyncio.run(run_review_async(request, model))

    # TAG-1 failed after exhausting its retry budget — every attempt was
    # identical (blind), which is exactly why it never recovers on its own.
    assert model.tag1_attempts == 2  # default max_section_attempts
    assert "TAG-1" in result.failed_tag_ids
    # TAG-2 is completely unaffected by TAG-1's failure.
    assert "TAG-2" not in result.failed_tag_ids
    # The graph did not crash or halt early — it produced a final review
    # with TAG-2's real content, and correctly reports overall failure
    # (never silently treated as a full success).
    assert result.succeeded is False
    assert result.final_review_path is not None
    markdown = Path(result.final_review_path).read_text(encoding="utf-8")
    assert "Section B body" in markdown
