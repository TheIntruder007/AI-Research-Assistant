"""FastAPI backend exposing the pipeline as a set of research endpoints.

POST /research runs the full four-stage pipeline synchronously and returns
the final result directly — the original MVP endpoint, kept unchanged for
callers happy to block for the run's full duration (see DECISIONS.md D-015).

POST /research/runs, GET /research/runs/{run_id}, and
GET /research/runs/{run_id}/events add the asynchronous path deferred at
that point: start a run in the background, poll its status, or stream its
progress events over SSE as they happen (see DECISIONS.md D-017).

Run locally with:
    uvicorn orchestrator.api:app --reload
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402

from orchestrator import run_registry  # noqa: E402
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


@app.post("/research/runs", status_code=202)
async def start_research_run(request: ResearchRequest) -> dict[str, str]:
    """Starts a pipeline run in the background and returns its run_id
    immediately, instead of blocking until the run finishes. Poll
    GET /research/runs/{run_id} for status, or GET
    /research/runs/{run_id}/events for a live SSE progress stream."""
    run_id = uuid4().hex
    await run_registry.start_run(request, run_id, run_pipeline)
    return {"run_id": run_id}


@app.get("/research/runs/{run_id}")
async def get_research_run(run_id: str) -> dict[str, object]:
    state = run_registry.get_run(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id: {run_id}")
    return {
        "run_id": state.run_id,
        "status": state.status,
        "result": jsonable_encoder(state.result) if state.result is not None else None,
        "error": state.error,
    }


@app.get("/research/runs/{run_id}/events")
async def stream_research_run_events(run_id: str) -> StreamingResponse:
    state = run_registry.get_run(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id: {run_id}")

    async def event_stream():
        queue = run_registry.subscribe(state)
        try:
            while True:
                event = await queue.get()
                if event.get("type") == "end":
                    yield "event: end\ndata: {}\n\n"
                    break
                payload = json.dumps(jsonable_encoder(event))
                yield f"data: {payload}\n\n"
        finally:
            run_registry.unsubscribe(state, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
