"""Manual smoke test for the Citation Verification Service against live Crossref/OpenAlex.

Uses a hand-written WritingResult with one real DOI, one fabricated DOI, and
one DOI-less reference, so all three outcome branches (verified / invalid /
unverifiable) are exercised against the real APIs.

Usage (from the project venv):
    python scripts/smoke_test_verification.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "verification"))
sys.path.insert(0, str(ROOT))

from shared.contracts.writing_contract import DraftMetadata, WritingResult  # noqa: E402
from shared.contracts.verification_contract import VerificationRequest  # noqa: E402

# A bare `import service` would collide with the other pipeline services'
# own service.py modules — load by explicit file path instead.
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "research_verification_service", ROOT / "services" / "verification" / "service.py",
)
service = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(service)
run_verification = service.run_verification


def _sample_writing_result() -> WritingResult:
    references = [
        # A real, resolvable DOI (Liu et al., used in earlier discovery/writing smoke tests).
        '[1] Z. Liu, X. Dai, and H. Zhang, "Gut microbiota mediates intermittent-fasting '
        'alleviation of diabetes-induced cognitive impairment," *Nature Communications*, '
        "2020, doi: 10.1038/s41467-020-14676-4.",
        # A syntactically valid but almost certainly nonexistent DOI.
        '[2] A. Nobody, "A Paper That Does Not Exist," *Journal of Nothing*, 2099, '
        "doi: 10.9999/does-not-exist-12345.",
        # No DOI at all.
        '[3] B. Someone, "An Older Report With No DOI," Internal Technical Report, 1995.',
    ]
    return WritingResult(
        research_outline="# Sample\n## Introduction\n## Literature Review\n## Conclusion",
        research_draft_markdown="Sample draft body citing [1], [2], and [3].",
        reference_candidates=references,
        run_directory=str(ROOT / "outputs" / ".verification_smoke_test"),
        draft_metadata=DraftMetadata(
            model_name="qwen3.5:9b", run_id="smoke-test",
            generated_at="2026-08-27T00:00:00Z", papers_cited=3,
        ),
    )


async def main() -> None:
    request = VerificationRequest(writing=_sample_writing_result())
    async for event in run_verification(request):
        if event["type"] == "result":
            result = event["result"]
            print("\n=== VERIFICATION RESULT ===")
            print(f"Verified: {len(result.verified_references)}")
            print(f"Invalid: {len(result.invalid_references)}")
            print(f"Unverifiable: {len(result.unverifiable_references)}")
            print(f"\n--- Validation report ---\n{result.validation_report}")
        else:
            print(f"[{event['type']}] {event.get('message') or event['type']}")


if __name__ == "__main__":
    asyncio.run(main())
