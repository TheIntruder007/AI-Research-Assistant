"""Regression test for DECISIONS.md D-028's cross-section duplication fix.

Root cause (found via real-run manual inspection —
PAPER_OUTPUT_FINAL_DIAGNOSTIC.md finding #2): `write_conclusion()` had no
way to know what the already-generated Introduction actually said. Both
bookends draw on overlapping evidence (Introduction's `top_level_summaries`
is a subset of Conclusion's full `section_summaries`), so with zero
cross-awareness the model had every reason to independently converge on the
same restatement — observed as word-for-word duplicate sentences in 2 of 4
real runs.

Fix: `write_conclusion()` now accepts `introduction_content` (the real,
already-generated Introduction text — always available, since
write_review() generates the Introduction first) and forwards it to the
model as `introduction_already_written`; the prompt explicitly instructs
the model not to restate it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.modules.review_writer import write_conclusion  # noqa: E402
from writing.schemas import SectionDraftContent, SectionSummary  # noqa: E402


class _CapturingModel:
    """Fake LanguageModel that records the exact payload it received."""

    def __init__(self):
        self.last_user_prompt: str | None = None

    async def generate_structured(self, *, system_prompt, user_prompt, response_model):
        self.last_user_prompt = user_prompt
        return SectionDraftContent(
            content="A distinct concluding synthesis [@P001].",
            summary="s", cited_paper_ids=["P001"], used_point_ids=["P001-POINT-01"],
        )


def _summary() -> SectionSummary:
    return SectionSummary(
        tag_id="TAG-1", summary="A body finding.", cited_paper_ids=["P001"],
        used_point_ids=["P001-POINT-01"],
    )


def test_introduction_content_is_forwarded_to_the_model():
    import asyncio

    model = _CapturingModel()
    intro_text = "This review examines X because Y matters [@P001]."
    asyncio.run(write_conclusion(
        "What is X?", [_summary()], model, introduction_content=intro_text,
    ))
    assert intro_text in model.last_user_prompt
    assert "introduction_already_written" in model.last_user_prompt


def test_none_introduction_content_is_forwarded_as_null_not_omitted():
    """When there was no real Introduction (e.g. no intro evidence at all),
    the field is still present but null — never silently dropped, so the
    prompt's own "if introduction_already_written is present" branch behaves
    predictably rather than depending on key absence."""
    import asyncio

    model = _CapturingModel()
    asyncio.run(write_conclusion("What is X?", [_summary()], model))
    assert '"introduction_already_written": null' in model.last_user_prompt


def test_write_conclusion_md_instructs_against_restating_the_introduction():
    """The static prompt itself must carry the anti-duplication instruction,
    not just the payload field — verifies the actual packaged prompt text,
    not a hypothesis about it."""
    from writing.modules.prompt_loader import load_prompt

    prompt = load_prompt("write_conclusion.md")
    assert "introduction_already_written" in prompt
    assert "restate" in prompt.casefold()


def test_write_introduction_md_warns_against_pre_narrating_the_body():
    """A separate, related real-run finding (PAPER_OUTPUT_FINAL_DIAGNOSTIC.md
    finding #2, Run 2): the Introduction independently restated the same
    specific statistics as the Background section, since both draw on
    overlapping evidence (`overview_points` includes every top-level
    section's own direct points). The prompt now explicitly instructs
    map-level framing over reproducing body-level specifics."""
    from writing.modules.prompt_loader import load_prompt

    prompt = load_prompt("write_introduction.md")
    assert "near copy" in prompt.casefold() or "near-identical" in prompt.casefold()
