"""Unit test for the targeted (not blind) literature-card retry.

See DECISIONS.md D-019: the original retry loop in writing/graph.py called
build_literature_card() a second time with the EXACT SAME prompt after a
validation failure — an identical, blind repeat that gave the model no
reason to produce a different (correct) answer. This test verifies the fix
at the unit level, without needing a live Ollama server: the previous
attempt's validation errors must actually reach the model's prompt on retry.
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.modules.literature_card import build_literature_card  # noqa: E402
from writing.schemas import PaperDocument, PartialPaperMetadata, TagDefinition  # noqa: E402


class _RecordingModel:
    """Fake LanguageModel that records the prompt it was called with and
    returns a fixed, schema-valid literature card every time."""

    def __init__(self):
        self.calls: list[dict] = []

    async def generate_structured(self, *, system_prompt, user_prompt, response_model):
        self.calls.append(json.loads(user_prompt))
        return response_model.model_validate({
            "metadata": {"title": "A Paper", "authors": ["A. Author"]},
            "citation": {
                "citation_key": "author2024", "in_text_citation": "(Author, 2024)",
                "narrative_citation": "Author (2024)", "reference_entry": "Author, A. (2024). A Paper.",
            },
            "points": {},
            "tag_values": {"TAG-ROOT": []},
        })


def _document(tmp_path) -> PaperDocument:
    paper_path = tmp_path / "P001.md"
    paper_path.write_text("# A Paper\n\nSome content.", encoding="utf-8")
    return PaperDocument(
        paper_id="P001", source_path=str(paper_path), relative_path="P001.md",
        content_hash="a" * 64, evidence_depth="abstract",
        metadata=PartialPaperMetadata(title="A Paper", authors=["A. Author"]),
    )


def _definitions() -> list[TagDefinition]:
    return [TagDefinition(
        tag_id="TAG-ROOT", title="Root", normalized_label="root", description="d",
        include_when=["x"], exclude_when=["y"], child_ids=[], depth=0, node_type="root",
    )]


def test_first_attempt_has_no_previous_errors_key(tmp_path):
    model = _RecordingModel()
    asyncio.run(build_literature_card("Q?", _definitions(), _document(tmp_path), model))
    assert "previous_attempt_errors" not in model.calls[0]


def test_retry_attempt_carries_previous_errors_into_the_prompt(tmp_path):
    model = _RecordingModel()
    errors = ["point P001-POINT-01 is duplicated across ancestor TAG-ROOT and descendant TAG-1"]
    asyncio.run(build_literature_card(
        "Q?", _definitions(), _document(tmp_path), model, previous_errors=errors,
    ))
    assert model.calls[0]["previous_attempt_errors"] == errors


def test_empty_previous_errors_list_is_treated_as_no_prior_attempt(tmp_path):
    model = _RecordingModel()
    asyncio.run(build_literature_card(
        "Q?", _definitions(), _document(tmp_path), model, previous_errors=[],
    ))
    assert "previous_attempt_errors" not in model.calls[0]
