"""Manual end-to-end timing baseline: real Discovery output -> full-size Writing outline.

Unlike scripts/smoke_test_writing.py (which uses a hand-written 2-paper,
4-section case for fast wiring checks), this runs a real Discovery Service
pass (6-9 papers) and lets the Writing Service build its normal
production-sized outline (one Literature Review subsection per research gap
found) — see DECISIONS.md D-010's "Known limitation" for why this hasn't
been timed on this hardware yet.

Usage (from the project venv):
    python scripts/smoke_test_full_pipeline.py "Your research question here"

Not part of the automated test suite. Expect this to take a long time on
modest hardware (each leaf section is a separate LLM call) — this script
exists specifically to measure that, not to be fast.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "research-discovery"))
sys.path.insert(0, str(ROOT))

from shared.contracts.discovery_contract import DiscoveryRequest  # noqa: E402
from shared.contracts.writing_contract import WritingRequest  # noqa: E402

import importlib.util  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


discovery_service = _load("research_discovery_service", ROOT / "services" / "research-discovery" / "service.py")
writing_service = _load("research_writing_service", ROOT / "services" / "research-writing" / "service.py")


async def main(question: str) -> None:
    t0 = time.monotonic()
    print(f"[discovery] starting for: {question!r}")
    discovery_request = DiscoveryRequest(research_question=question, corpus_size=6)
    discovery_result = None
    async for event in discovery_service.run_discovery(discovery_request):
        if event["type"] == "result":
            discovery_result = event["result"]
        else:
            print(f"[discovery] {event.get('message') or event['type']}")
    t1 = time.monotonic()
    print(f"[discovery] done in {t1 - t0:.1f}s — "
          f"{len(discovery_result.selected_papers)} papers, "
          f"{len(discovery_result.research_gaps)} gaps")

    print("[writing] starting (full production-sized outline)...")
    writing_request = WritingRequest(discovery=discovery_result, target_format="IEEE")
    writing_result = None
    async for event in writing_service.run_writing(writing_request):
        if event["type"] == "result":
            writing_result = event["result"]
        else:
            print(f"[writing] {event.get('message') or event['type']}")
    t2 = time.monotonic()

    print("\n=== TIMING BASELINE ===")
    print(f"Discovery: {t1 - t0:.1f}s")
    print(f"Writing:   {t2 - t1:.1f}s")
    print(f"Total:     {t2 - t0:.1f}s")
    print(f"\nSections written: {writing_result.draft_metadata.sections_written}")
    print(f"References: {len(writing_result.reference_candidates)}")
    print(f"Warnings: {writing_result.draft_metadata.warnings}")
    print(f"Errors: {writing_result.draft_metadata.errors}")
    print(f"Run directory: {writing_result.run_directory}")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What are the effects of intermittent fasting on cognitive performance?"
    asyncio.run(main(q))
