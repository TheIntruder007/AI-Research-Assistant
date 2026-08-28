"""Unit tests for Service 2 section-generation reliability, exercising the
already-correct-but-previously-untested targeted revision mechanism, plus a
zero-model-call missing-evidence path. See DECISIONS.md D-019.

These run without Ollama — the writing graph's audit/revision logic is pure
Python plus a fake LanguageModel, which is exactly what makes it fast and
reliable to test on every commit (unlike the full graph, which needs a real
local model).
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from writing.modules.section_writer import write_section, write_section_with_revisions  # noqa: E402
from writing.schemas import SectionDraftContent, SectionWritingContext  # noqa: E402


def _context(**overrides) -> SectionWritingContext:
    base = dict(
        tag_id="TAG-1", title="Literature Review", outline_path=["Root", "Literature Review"],
        depth=1, writing_mode="leaf_section", direct_points=[], ancestor_context=[],
        child_summaries=[], allowed_paper_ids=["P001"], allowed_point_ids=["P001-POINT-01"],
        citations={}, sibling_titles=[], prohibited_topics=[],
    )
    base.update(overrides)
    return SectionWritingContext(**base)


class _ScriptedModel:
    """Fake LanguageModel returning a scripted sequence of responses,
    one per call, regardless of which prompt module invokes it."""

    def __init__(self, responses: list[SectionDraftContent]):
        self._responses = list(responses)
        self.call_count = 0

    async def generate_structured(self, *, system_prompt, user_prompt, response_model):
        response = self._responses[self.call_count]
        self.call_count += 1
        return response


def test_b_missing_evidence_returns_warning_without_calling_the_model():
    """No direct points, ancestor context, or child summaries at all —
    write_section must not call the model or hallucinate content."""
    context = _context(direct_points=[], ancestor_context=[], child_summaries=[])
    model = _ScriptedModel([])  # any call would raise IndexError

    draft = asyncio.run(write_section(context, model))

    assert model.call_count == 0
    assert "insufficient evidence" in draft.content.casefold()
    assert draft.cited_paper_ids == []
    assert draft.used_point_ids == []


def test_c_invalid_citation_triggers_targeted_revision_not_blind_retry():
    """First attempt cites a paper outside the allowed list (an invalid tag/
    evidence assignment) — audit_section must catch it deterministically,
    and the revision call must be given the audit's specific instructions
    rather than the section simply being regenerated blind."""
    context = _context(allowed_paper_ids=["P001"], allowed_point_ids=["P001-POINT-01"],
                       direct_points=[], ancestor_context=[], child_summaries=["prior summary"])
    bad_draft = SectionDraftContent(
        content="Some finding [@P999].", cited_paper_ids=["P999"], used_point_ids=[],
    )
    good_draft = SectionDraftContent(
        content="Some finding [@P001].", cited_paper_ids=["P001"],
        used_point_ids=["P001-POINT-01"],
    )
    model = _ScriptedModel([bad_draft, good_draft])

    result = asyncio.run(write_section_with_revisions(context, model, max_revision_rounds=1))

    assert model.call_count == 2  # one write + one targeted revision, not a blind repeat
    assert result.resolved is True
    assert result.draft.cited_paper_ids == ["P001"]
    assert len(result.audits) == 2
    assert not result.audits[0].passed
    assert "Remove citations outside the allowed paper list: P999" in result.audits[0].revision_instructions


def test_unrecoverable_section_is_explicitly_marked_unresolved_not_silently_accepted():
    """If every revision round still fails the audit, the section must be
    reported as unresolved — never silently treated as a success."""
    context = _context(allowed_paper_ids=["P001"], allowed_point_ids=["P001-POINT-01"],
                       direct_points=[], ancestor_context=[], child_summaries=["prior summary"])
    always_bad = SectionDraftContent(
        content="Some finding [@P999].", cited_paper_ids=["P999"], used_point_ids=[],
    )
    model = _ScriptedModel([always_bad, always_bad, always_bad])

    result = asyncio.run(write_section_with_revisions(context, model, max_revision_rounds=2))

    assert result.resolved is False
    assert result.unresolved_issues
    assert model.call_count == 3  # 1 initial write + 2 revision rounds, all attempted
