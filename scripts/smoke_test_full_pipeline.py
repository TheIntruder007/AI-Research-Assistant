"""Manual end-to-end run of the full four-stage pipeline via the orchestrator.

Runs a real research question through all four services (Discovery ->
Writing -> Verification -> Quality Assurance) using the same
orchestrator.pipeline.run_pipeline() the terminal app calls, so this
exercises the real integration path rather than a hand-chained approximation
of it.

Usage (from the project venv):
    python scripts/smoke_test_full_pipeline.py "Your research question here"

Not part of the automated test suite. Expect Discovery+Writing to take a
long time on modest hardware (see DECISIONS.md D-009/D-010/D-011);
Verification and QA are fast (network lookups and pure Python respectively).
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.pipeline import run_pipeline  # noqa: E402
from shared.contracts.pipeline_contract import ResearchRequest  # noqa: E402


async def main(question: str) -> None:
    t0 = time.monotonic()
    request = ResearchRequest(research_question=question, corpus_size=6)
    async for event in run_pipeline(request):
        if event["type"] == "result":
            result = event["result"]
            elapsed = time.monotonic() - t0
            print("\n=== PIPELINE RESULT ===")
            print(f"Run ID: {result.run_id}")
            print(f"Run directory: {result.run_directory}")
            print(f"Total wall time: {elapsed:.1f}s")
            print(f"Timings: {result.timings.model_dump()}")
            print(f"Papers selected: {len(result.discovery.selected_papers)}")
            for p in result.discovery.selected_papers:
                print(f"  [{p.id}] relevance={p.relevance_score} — {p.title!r}")
            print(f"Draft status: {result.writing.draft_metadata.draft_status} "
                  f"({result.writing.draft_metadata.sections_written}/"
                  f"{result.writing.draft_metadata.total_sections} sections, "
                  f"{result.writing.draft_metadata.failed_sections} failed)")
            print(f"Writing warnings: {result.writing.draft_metadata.warnings}")
            print(f"Writing errors: {result.writing.draft_metadata.errors}")
            print(
                "Verified/invalid/unverifiable refs: "
                f"{len(result.verification.verified_references)}/"
                f"{len(result.verification.invalid_references)}/"
                f"{len(result.verification.unverifiable_references)}"
            )
            print(f"QA overall score: {result.quality_assurance.scores.overall:.1f}/5.0")
            print(f"QA unsupported claims: {len(result.quality_assurance.unsupported_claims)}")
            print(f"QA missing citations: {len(result.quality_assurance.missing_citations)}")
            print(f"Final draft: {result.run_directory}\\final\\draft.md")
        else:
            print(f"{event['emoji']} [{event['stage']}] {event['message']}")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What are the effects of intermittent fasting on cognitive performance?"
    asyncio.run(main(q))
