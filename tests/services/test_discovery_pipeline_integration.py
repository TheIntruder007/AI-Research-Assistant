"""End-to-end integration test for the Research Discovery Service.

Requires a live Ollama server with the configured model installed. Skips
cleanly (rather than failing) when Ollama isn't reachable, since this test
depends on real network calls to literature sources and a real local model —
it is not meant to run in an offline/CI environment without that setup.
"""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-discovery"))
sys.path.insert(0, str(ROOT))

from shared.contracts.discovery_contract import DiscoveryRequest  # noqa: E402
from shared.utilities.llm_provider import DEFAULT_MODEL, OLLAMA_HOST  # noqa: E402
from service import run_discovery  # noqa: E402


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


def test_discovery_pipeline_end_to_end():
    """A small controlled research question runs the full pipeline and
    produces a schema-valid DiscoveryResult with real evidence attached."""
    request = DiscoveryRequest(
        research_question="What are the effects of intermittent fasting on cognitive performance?",
        corpus_size=6,
    )

    async def run():
        result = None
        async for event in run_discovery(request):
            if event["type"] == "result":
                result = event["result"]
        return result

    result = asyncio.run(run())

    assert result is not None
    assert result.research_interpretation
    assert 1 <= len(result.selected_papers) <= request.corpus_size
    assert result.field_overview
    assert result.novelty_analysis.confidence in ("high", "medium", "low")
    assert result.confidence_notes
    # research_gaps may be empty for a well-covered small corpus, but if present
    # each must carry evidence text, not just an assertion.
    for gap in result.research_gaps:
        assert gap.evidence
