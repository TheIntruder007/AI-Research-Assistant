"""Manual end-to-end run of the full four-stage pipeline against real services.

Unlike scripts/smoke_test_writing.py or smoke_test_verification.py (which use
hand-written fixtures for fast wiring checks), this chains real Discovery ->
Writing -> Verification -> Quality Assurance output, so Services 3 and 4 get
exercised against whatever citation styles and reference formats Service 2
actually produces, not just constructed test cases.

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
sys.path.insert(0, str(ROOT / "services" / "research-discovery"))
sys.path.insert(0, str(ROOT))

from shared.contracts.discovery_contract import DiscoveryRequest  # noqa: E402
from shared.contracts.writing_contract import WritingRequest  # noqa: E402
from shared.contracts.verification_contract import VerificationRequest  # noqa: E402
from shared.contracts.qa_contract import QualityAssuranceRequest  # noqa: E402

import importlib.util  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


discovery_service = _load("research_discovery_service", ROOT / "services" / "research-discovery" / "service.py")
writing_service = _load("research_writing_service", ROOT / "services" / "research-writing" / "service.py")
verification_service = _load("research_verification_service", ROOT / "services" / "verification" / "service.py")
qa_service = _load("research_qa_service", ROOT / "services" / "quality-assurance" / "service.py")


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

    print("[verification] starting (live Crossref/OpenAlex)...")
    verification_result = None
    async for event in verification_service.run_verification(
        VerificationRequest(writing=writing_result)
    ):
        if event["type"] == "result":
            verification_result = event["result"]
        else:
            print(f"[verification] {event.get('message') or event['type']}")
    t3 = time.monotonic()

    print("[qa] starting (deterministic, no LLM calls)...")
    qa_result = None
    async for event in qa_service.run_quality_assurance(
        QualityAssuranceRequest(
            discovery=discovery_result, writing=writing_result, verification=verification_result,
        )
    ):
        if event["type"] == "result":
            qa_result = event["result"]
        else:
            print(f"[qa] {event.get('message') or event['type']}")
    t4 = time.monotonic()

    print("\n=== TIMING BASELINE ===")
    print(f"Discovery:    {t1 - t0:.1f}s")
    print(f"Writing:      {t2 - t1:.1f}s")
    print(f"Verification: {t3 - t2:.1f}s")
    print(f"QA:           {t4 - t3:.1f}s")
    print(f"Total:        {t4 - t0:.1f}s")
    print(f"\nSections written: {writing_result.draft_metadata.sections_written}")
    print(f"References: {len(writing_result.reference_candidates)}")
    print(f"Writing warnings: {writing_result.draft_metadata.warnings}")
    print(f"Writing errors: {writing_result.draft_metadata.errors}")
    print(f"Verified/invalid/unverifiable refs: "
          f"{len(verification_result.verified_references)}/"
          f"{len(verification_result.invalid_references)}/"
          f"{len(verification_result.unverifiable_references)}")
    print(f"QA overall score: {qa_result.scores.overall:.1f}/5.0")
    print(f"QA unsupported claims: {len(qa_result.unsupported_claims)}")
    print(f"QA missing citations: {len(qa_result.missing_citations)}")
    print(f"QA missing sections: {qa_result.missing_sections}")
    print(f"QA known limitations: {qa_result.known_limitations}")
    print(f"Run directory: {writing_result.run_directory}")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What are the effects of intermittent fasting on cognitive performance?"
    asyncio.run(main(q))
