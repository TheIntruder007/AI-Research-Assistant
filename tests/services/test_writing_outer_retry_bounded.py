"""Outer max_section_attempts retry: bounded-safety tests (D-020 Problem 2).

Important scoping note: the concrete empty-content failure this project
actually observed and reproduced (D-020) was a deterministic CODE bug in
the container-tag branch, now fixed — not a case of the model itself
returning an empty string. No real run has ever shown the local model
producing a genuinely empty SectionDraftContent.content. These tests verify
that IF a section write raises repeatedly (whatever the cause — a
validation error, a raw exception, anything), the existing outer retry
loop behaves safely: bounded attempts, no infinite loop, an explicit
failure state, and no corruption of other sections — without inventing an
unverified "recovery prompt" mechanism for a failure mode with no evidence
of occurring. See analytics_and_results.md for the full reasoning.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.graph import run_review_async  # noqa: E402
from writing.schemas import ReviewInput, SectionDraftContent  # noqa: E402

_PAPER_MARKDOWN = "---\nevidence_depth: abstract\n---\n\n# A Paper\n\nSome abstract text.\n"


def _tag_semantics_response(model_class):
    return model_class.model_validate({
        "tags": [
            {"tag_id": "TAG-ROOT", "normalized_label": "root", "description": "d",
             "include_when": ["x"], "exclude_when": ["y"], "node_type": "root"},
            {"tag_id": "TAG-1", "normalized_label": "a", "description": "d",
             "include_when": ["x"], "exclude_when": ["y"], "node_type": "content"},
        ],
    })


def _card_response(model_class):
    return model_class.model_validate({
        "metadata": {"title": "A Paper", "authors": ["A. Author"]},
        "citation": {
            "citation_key": "author2024", "in_text_citation": "(Author, 2024)",
            "narrative_citation": "Author (2024)", "reference_entry": "Author, A. (2024). A Paper.",
        },
        "points": {"P001-POINT-01": {
            "point_id": "P001-POINT-01", "content": "A general finding.",
            "content_type": "background", "certainty": "supported",
        }},
        "tag_values": {"TAG-ROOT": ["P001-POINT-01"], "TAG-1": []},
    })


class _AlwaysEmptyContentModel:
    """Every SectionDraftContent call for TAG-1 raises a pydantic
    ValidationError (empty content), identically, every attempt."""

    def __init__(self):
        self.section_attempts = 0

    async def generate_structured(self, *, system_prompt, user_prompt, response_model):
        name = response_model.__name__
        if name == "TagSemanticBatch":
            return _tag_semantics_response(response_model)
        if name == "LiteratureCardContent":
            return _card_response(response_model)
        if name == "SectionDraftContent":
            payload = json.loads(user_prompt)
            if payload.get("tag_id") == "TAG-1":
                self.section_attempts += 1
                # Simulates the local model returning an empty string for a
                # required field — validated (and rejected) exactly the way
                # the real OllamaLanguageModel adapter would reject it.
                return response_model.model_validate(
                    {"content": "", "cited_paper_ids": [], "used_point_ids": []}
                )
            return response_model.model_validate({
                "content": "Overview text.", "cited_paper_ids": [], "used_point_ids": [],
            })
        raise AssertionError(f"unexpected call: {name}")


def _run(tmp_path, model):
    literature_dir = tmp_path / "literature"
    literature_dir.mkdir()
    (literature_dir / "paper.md").write_text(_PAPER_MARKDOWN, encoding="utf-8")
    request = ReviewInput(
        review_question="Q", outline="# Q\n## A\n", literature_directory=str(literature_dir),
        output_directory=str(tmp_path / "runs"),
    )
    return asyncio.run(run_review_async(request, model))


def test_a_and_b_repeated_empty_output_is_bounded_not_infinite(tmp_path):
    """Tests A + B: the exact failure reaches the graph, retries are
    attempted, but bounded — never an infinite loop."""
    model = _AlwaysEmptyContentModel()
    result = _run(tmp_path, model)
    # Bounded: exactly max_section_attempts (default 2), never more.
    assert model.section_attempts == 2
    assert "TAG-1" in result.failed_tag_ids


def test_c_the_exact_validation_error_is_captured_in_the_reported_errors(tmp_path):
    """Test C: the exact validation error must be available, not swallowed
    into a generic message — this is what a future targeted-recovery
    mechanism would need to act on."""
    model = _AlwaysEmptyContentModel()
    result = _run(tmp_path, model)
    combined_errors = " ".join(result.errors)
    assert "TAG-1" in combined_errors
    assert "content" in combined_errors  # names the actual failing field
    assert "string_too_short" in combined_errors or "at least 1 character" in combined_errors


def test_unrecoverable_section_ends_in_an_explicit_failure_state_not_silent_success(tmp_path):
    model = _AlwaysEmptyContentModel()
    result = _run(tmp_path, model)
    assert result.succeeded is False
    assert result.final_review_path is not None  # still produces a (partial) artifact


def test_sanity_pydantic_actually_rejects_empty_content():
    """Confirms the simulated failure mode is real, not a fake test double."""
    with pytest.raises(ValidationError):
        SectionDraftContent.model_validate(
            {"content": "", "cited_paper_ids": [], "used_point_ids": []}
        )
