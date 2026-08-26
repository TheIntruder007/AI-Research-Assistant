"""Manual smoke test for the Research Writing Service against the live local model.

Deliberately uses a MINIMAL outline (few sections) and a small paper set —
on this project's reference hardware, each section/card is a separate LLM
call, and a full production-sized outline can take many hours end-to-end
(see DECISIONS.md D-009/D-010). This script is for verifying the pipeline
wiring works, not for timing a realistic run.

Usage (from the project venv):
    python scripts/smoke_test_writing.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "research-writing"))
sys.path.insert(0, str(ROOT))

from shared.contracts.discovery_contract import (  # noqa: E402
    DiscoveryRequest, DiscoveryResult, NoveltyAssessment, PaperMetadata, ResearchGap,
)
from shared.contracts.writing_contract import WritingRequest  # noqa: E402

# A bare `import service` would collide with research-discovery's own
# service.py (both modules share the generic name "service" and are reached
# only via sys.path insertion) — load by explicit file path instead.
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "research_writing_service", ROOT / "services" / "research-writing" / "service.py",
)
service = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(service)
run_writing = service.run_writing


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
                    "intermittent fasting protocol on working memory and attention in "
                    "60 healthy adults over 8 weeks. Participants in the fasting group "
                    "showed modest improvements in working memory scores compared to "
                    "controls, with no significant change in attention measures. The "
                    "authors note the small sample size and short duration as limitations."
                ),
            ),
            PaperMetadata(
                id=2, title="Time-Restricted Eating and Executive Function: A Pilot Study",
                authors=["B. Scholar", "C. Investigator"], year=2021, venue="Nutrients",
                has_abstract=True,
                abstract=(
                    "This pilot study investigated time-restricted eating (TRE) effects "
                    "on executive function in 24 middle-aged adults. After 12 weeks of "
                    "TRE, participants showed improved performance on the Stroop task "
                    "but no change in task-switching ability. Future research should "
                    "explore longer intervention periods and larger, more diverse samples."
                ),
            ),
        ],
        field_overview="A small emerging body of evidence suggests intermittent fasting "
                       "protocols may modestly benefit certain cognitive domains.",
        limitations="Only two studies reviewed; both small sample sizes.",
        research_gaps=[ResearchGap(
            title="Long-term Cognitive Effects of Intermittent Fasting",
            gap_type="temporal", impact="medium",
            description="No studies examined cognitive effects beyond 12 weeks.",
            evidence="Both reviewed studies were 8-12 weeks; neither followed up long-term.",
            supporting_paper_ids=[1, 2],
            research_questions=["Do cognitive benefits of intermittent fasting persist beyond 12 weeks?"],
        )],
        novelty_analysis=NoveltyAssessment(
            novelty_summary="A long-term follow-up study would address an unstudied gap.",
            supporting_gap_titles=["Long-term Cognitive Effects of Intermittent Fasting"],
            confidence="medium", caveats="Based on only two small studies.",
        ),
        confidence_notes="Small corpus; findings should be treated as preliminary.",
    )


MINIMAL_OUTLINE = "\n".join([
    "# Intermittent Fasting and Cognitive Performance",
    "## Introduction",
    "## Literature Review",
    "## Conclusion",
])


async def main() -> None:
    discovery = _minimal_discovery()
    request = WritingRequest(discovery=discovery, target_format="IEEE")

    # Patch in the minimal outline instead of the full production template,
    # so this smoke test stays fast — service.py binds build_outline into
    # its own namespace at import time, so patch that name specifically.
    service.build_outline = lambda _discovery: MINIMAL_OUTLINE

    async for event in run_writing(request):
        if event["type"] == "result":
            result = event["result"]
            print("\n=== WRITING RESULT ===")
            print(f"Run directory: {result.run_directory}")
            print(f"Sections written: {result.draft_metadata.sections_written}")
            print(f"References: {len(result.reference_candidates)}")
            print(f"Warnings: {result.draft_metadata.warnings}")
            print(f"Errors: {result.draft_metadata.errors}")
            print(f"\n--- Draft (first 1500 chars) ---\n{result.research_draft_markdown[:1500]}")
        else:
            label = event.get("message") or event.get("type")
            print(f"[{event['type']}] {label}")


if __name__ == "__main__":
    asyncio.run(main())
