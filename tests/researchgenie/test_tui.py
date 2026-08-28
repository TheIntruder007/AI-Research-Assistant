"""Tests for the live progress view's event-ingestion logic — the part that
matters for correctness (Rich's actual terminal rendering is out of scope
for unit tests)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from researchgenie.tui import PipelineView  # noqa: E402


def _event(stage, status, message):
    return {"stage": stage, "status": status, "message": message, "emoji": "•", "type": "progress"}


def test_ingest_ignores_unknown_stage_keys():
    view = PipelineView()
    view.ingest({"stage": "not_a_real_stage", "status": "done", "message": "x"})
    assert all(log.lines == [] for log in view.stages.values())


def test_ingest_tracks_messages_per_stage_in_order():
    view = PipelineView()
    view.ingest(_event("discovery", "running", "Searching sources"))
    view.ingest(_event("discovery", "done", "Selected 6 papers"))
    lines = view.stages["discovery"].lines
    assert lines == [("Searching sources", "running"), ("Selected 6 papers", "done")]


def test_stage_status_becomes_running_on_first_event():
    view = PipelineView()
    assert view.stages["writing"].status == "pending"
    view.ingest(_event("writing", "running", "Writing section 1"))
    assert view.stages["writing"].status == "running"


def test_stage_status_becomes_done_only_on_a_done_event():
    view = PipelineView()
    view.ingest(_event("verification", "running", "Checking DOIs"))
    assert view.stages["verification"].status == "running"
    view.ingest(_event("verification", "done", "6 verified"))
    assert view.stages["verification"].status == "done"


def test_stage_status_becomes_failed_on_a_failed_event():
    view = PipelineView()
    view.ingest(_event("writing", "failed", "Section generation failed"))
    assert view.stages["writing"].status == "failed"


def test_stage_reporting_done_after_an_earlier_warning_shows_degraded_not_clean():
    """Reproduces a real observed run: Research Writing reported a warning
    for an unresolved section, then its own final event said "done" — the
    stage must not display as a plain, all-clear success in that case."""
    view = PipelineView()
    view.ingest(_event("writing", "warning", "Section TAG-4 has unresolved issues"))
    view.ingest(_event("writing", "done", "4 section(s) written, 6 reference(s) cited."))
    assert view.stages["writing"].status == "warning"


def test_consecutive_duplicate_messages_are_collapsed_not_spammed():
    view = PipelineView()
    view.ingest(_event("discovery", "running", "Searching 4 database(s)..."))
    view.ingest(_event("discovery", "running", "Searching 4 database(s)..."))
    view.ingest(_event("discovery", "running", "Searching 4 database(s)..."))
    assert len(view.stages["discovery"].lines) == 1


def test_render_does_not_raise_for_a_completely_empty_view():
    view = PipelineView()
    view.render()  # must not raise, even with nothing ingested yet


def test_render_does_not_raise_after_a_full_run_of_events():
    view = PipelineView()
    for stage in ("discovery", "writing", "verification", "quality_assurance"):
        view.ingest(_event(stage, "running", "working"))
        view.ingest(_event(stage, "done", "finished"))
    view.render()
