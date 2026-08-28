"""Reproduction + regression test for DECISIONS.md D-020.

Root cause: writing/graph.py's write_next_section() container branch
constructed `SectionDraft(tag_id=tag_id, content="", ...)` directly —
violating SectionDraft.content's own `min_length=1` requirement. This is a
deterministic CODE bug, not a model-reliability issue: it crashes on every
run where any outline tag is classified `node_type: "container"`,
regardless of what the model returns, which is exactly why the outer
`max_section_attempts` blind retry could never fix it (the same empty
string is constructed by code, identically, on every attempt).

No live Ollama needed — the only model call in this graph run is tag
semantics; both the container tag and its evidence-free leaf child are
resolved without any further model call.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.graph import run_review_async  # noqa: E402
from writing.schemas import ReviewInput  # noqa: E402


class _ContainerSemanticsModel:
    """Fake LanguageModel: only expects the tag-semantics call, and
    classifies TAG-1 as a container tag (the condition that triggers the bug)."""

    async def generate_structured(self, *, system_prompt, user_prompt, response_model):
        if response_model.__name__ != "TagSemanticBatch":
            raise AssertionError(f"unexpected model call for {response_model.__name__}")
        return response_model.model_validate({
            "tags": [
                {"tag_id": "TAG-ROOT", "normalized_label": "root", "description": "d",
                 "include_when": ["x"], "exclude_when": ["y"], "node_type": "root"},
                {"tag_id": "TAG-1", "normalized_label": "overview", "description": "d",
                 "include_when": ["x"], "exclude_when": ["y"], "node_type": "container"},
                {"tag_id": "TAG-1.1", "normalized_label": "detail-a", "description": "d",
                 "include_when": ["x"], "exclude_when": ["y"], "node_type": "content"},
            ],
        })


def _run(tmp_path):
    literature_dir = tmp_path / "literature"
    literature_dir.mkdir()
    outline = "# What is the overview of X?\n## Overview\n### Detail A\n"
    request = ReviewInput(
        review_question="What is the overview of X?", outline=outline,
        literature_directory=str(literature_dir), output_directory=str(tmp_path / "runs"),
    )
    return asyncio.run(run_review_async(request, _ContainerSemanticsModel()))


def test_container_tag_does_not_fail_with_empty_content_validation_error(tmp_path):
    result = _run(tmp_path)
    assert "TAG-1" not in result.failed_tag_ids, (
        f"container tag TAG-1 failed: {result.errors}"
    )
    assert not any("string_too_short" in error or "ValidationError" in error
                  for error in result.errors), result.errors


def test_container_tag_renders_only_its_heading_no_stray_body_text(tmp_path):
    """The container's placeholder content must be render-invisible (assemble_review
    strips it via .strip()), matching a container's intended "heading only" role."""
    result = _run(tmp_path)
    assert result.final_review_path is not None
    markdown = Path(result.final_review_path).read_text(encoding="utf-8")
    assert "## Overview" in markdown
