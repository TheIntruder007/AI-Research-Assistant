"""Manual smoke test for the Research Discovery Service against the live local model.

Usage (from the project venv):
    python scripts/smoke_test_discovery.py "Your research question here"

Prints each progress event as it streams, then the final structured result.
Not part of the automated test suite — requires Ollama running with the
configured model installed (see shared/utilities/llm_provider.py).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "research-discovery"))
sys.path.insert(0, str(ROOT))

from shared.contracts.discovery_contract import DiscoveryRequest  # noqa: E402
from service import run_discovery  # noqa: E402


async def main(question: str) -> None:
    request = DiscoveryRequest(research_question=question, corpus_size=6)
    async for event in run_discovery(request):
        if event["type"] == "result":
            result = event["result"]
            print("\n=== DISCOVERY RESULT ===")
            print(f"Interpretation: {result.research_interpretation}")
            print(f"Papers selected: {len(result.selected_papers)}")
            print(f"Research gaps found: {len(result.research_gaps)}")
            print(f"Novelty confidence: {result.novelty_analysis.confidence}")
            print(f"\nField overview:\n{result.field_overview}")
            print("\n=== SELECTED PAPER RELEVANCE (DECISIONS.md D-018) ===")
            for p in result.selected_papers:
                print(f"  [{p.id}] score={p.relevance_score} — {p.title!r}")
        elif event["type"] == "relevance_filter":
            print(f"\n=== RELEVANCE SCREENING === accepted={event['accepted']} "
                  f"rejected={event['rejected']}")
            for ex in event["rejected_examples"]:
                print(f"  REJECTED (score={ex['relevance_score']}): {ex['title']!r} — {ex['reason']}")
        else:
            label = event.get("message") or event.get("type")
            print(f"[{event['type']}] {label}")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What are the effects of intermittent fasting on cognitive performance?"
    asyncio.run(main(q))
