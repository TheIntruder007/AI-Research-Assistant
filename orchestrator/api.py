"""FastAPI backend exposing the pipeline as one primary research endpoint.

POST /research runs the full four-stage pipeline and returns the final
result. Synchronous and blocking by design for this MVP — a run can take a
long time on this hardware (see DECISIONS.md D-009/D-010), and the project's
own working rules say not to prioritize frontend/event streaming before the
core (non-streaming) pipeline works end-to-end through the API. A streaming
progress endpoint (e.g. GET /research/{run_id}/events via SSE) is a
documented next step, not part of this MVP.

Run locally with:
    uvicorn orchestrator.api:app --reload
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException  # noqa: E402

from orchestrator.pipeline import PipelineError, run_pipeline  # noqa: E402
from shared.contracts.pipeline_contract import PipelineResult, ResearchRequest  # noqa: E402

app = FastAPI(
    title="AI Research Assistant",
    description="Local-first pipeline: research request -> evidence-grounded, "
                "citation-verified, quality-audited draft.",
    version="0.1.0",
)


@app.post("/research", response_model=PipelineResult)
async def create_research_run(request: ResearchRequest) -> PipelineResult:
    """Validates the request, runs Services 1-4 in sequence, and returns
    the final PipelineResult. FastAPI/Pydantic reject a malformed request
    body with a 422 before this function runs."""
    result: PipelineResult | None = None
    try:
        async for event in run_pipeline(request):
            if event["type"] == "result":
                result = event["result"]
    except PipelineError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=500, detail="Pipeline finished without producing a result.")
    return result


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
