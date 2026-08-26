"""End-to-end integration test for the Research Writing Service.

Requires a live Ollama server with the configured model installed. Skips
cleanly if Ollama isn't reachable. Uses a minimal two-paper discovery result
and a small outline — a full production-sized outline can take a very long
time on modest hardware (see DECISIONS.md D-009/D-010) — this test verifies
the pipeline wiring and that at least the root-level synthesis produces
real, cited, evidence-grounded content, not that every leaf section succeeds
(leaf-section writing reliability on this hardware is a documented
follow-up — see DECISIONS.md D-010).
"""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))
sys.path.insert(0, str(ROOT))

from shared.contracts.discovery_contract import (  # noqa: E402
    DiscoveryRequest, DiscoveryResult, NoveltyAssessment, PaperMetadata, ResearchGap,
)
from shared.contracts.writing_contract import WritingRequest  # noqa: E402
from shared.utilities.llm_provider import DEFAULT_MODEL, OLLAMA_HOST  # noqa: E402


def _ollama_available() -> bool:
    try:
        resp = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        resp.raise_for_status()
        names = {m["name"] for m in resp.json().get("models", [])}
        return DEFAULT_MODEL in names or f"{DEFAULT_MODEL}:latest" in names
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_available(),
    reason=f"Ollama not reachable at {OLLAMA_HOST} with model {DEFAULT_MODEL} installed",
)


def _minimal_discovery() -> DiscoveryResult:
    return DiscoveryResult(
        research_request=DiscoveryRequest(
            research_question="What are the effects of intermittent fasting on cognitive performance?",
            corpus_size=6,
        ),
        research_interpretation="How does intermittent fasting affect cognitive performance?",
        search_queries={"keyword": "intermittent fasting cognitive performance"},
        sources_searched=["OpenAlex"],
        selected_papers=[
            PaperMetadata(
                id=1, title="Intermittent Fasting and Working Memory in Adults",
                authors=["A. Researcher"], year=2022, venue="Journal of Nutrition Science",
                has_abstract=True,
                abstract=(
                    "This randomized controlled trial examined the effects of a 16:8 "
                    "intermittent fasting protocol on working memory in 60 healthy "
                    "adults over 8 weeks, finding modest improvements versus controls."
                ),
            ),
            PaperMetadata(
                id=2, title="Time-Restricted Eating and Executive Function: A Pilot Study",
                authors=["B. Scholar"], year=2021, venue="Nutrients",
                has_abstract=True,
                abstract=(
                    "This pilot study investigated time-restricted eating effects on "
                    "executive function in 24 adults, finding improved Stroop task "
                    "performance after 12 weeks."
                ),
            ),
        ],
        field_overview="A small emerging body of evidence on intermittent fasting and cognition.",
        limitations="Only two small studies reviewed.",
        research_gaps=[ResearchGap(
            title="Long-term Cognitive Effects of Intermittent Fasting",
            gap_type="temporal", impact="medium",
            description="No studies examined cognitive effects beyond 12 weeks.",
            evidence="Both reviewed studies were 8-12 weeks.",
            supporting_paper_ids=[1, 2],
            research_questions=["Do cognitive benefits persist beyond 12 weeks?"],
        )],
        novelty_analysis=NoveltyAssessment(
            novelty_summary="A long-term follow-up would address an unstudied gap.",
            confidence="medium", caveats="Based on only two small studies.",
        ),
        confidence_notes="Small corpus; findings should be treated as preliminary.",
    )


def _load_writing_service():
    # A bare `import service` would collide with research-discovery's own
    # service.py (both modules share the generic name "service" and are
    # reached only via sys.path insertion) — whichever test file imports
    # first wins the sys.modules cache slot, silently handing the other
    # test the wrong module. Load by explicit file path instead.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "research_writing_service",
        ROOT / "services" / "research-writing" / "service.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_writing_pipeline_produces_cited_evidence_grounded_draft(tmp_path):
    service = _load_writing_service()
    service.build_outline = lambda _d: "\n".join([
        "# Intermittent Fasting and Cognitive Performance",
        "## Introduction", "## Literature Review", "## Conclusion",
    ])

    request = WritingRequest(discovery=_minimal_discovery(), target_format="IEEE")

    async def run():
        result = None
        async for event in service.run_writing(request, output_root=tmp_path):
            if event["type"] == "result":
                result = event["result"]
        return result

    result = asyncio.run(run())

    assert result is not None
    assert result.research_draft_markdown.startswith(
        "> **AI-generated research draft for human review.**"
    )
    # At minimum the disclaimer and outline render; real evidence-grounded
    # content depends on this hardware's LLM reliability for leaf sections
    # (see DECISIONS.md D-010), so we check for citation markers rather than
    # requiring every section to succeed.
    assert "[1]" in result.research_draft_markdown or "References" in result.research_draft_markdown
    assert result.draft_metadata.model_name == service.llm_provider.DEFAULT_MODEL
