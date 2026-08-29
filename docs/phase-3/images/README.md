# Phase 3 — Terminal UI Screenshots

Eight real terminal-UI screenshots, one per stage of an actual `researchgenie` run — see `../PHASE_3_NOTES.md` §13 for the embedded images with captions.

Each is an SVG exported directly from the real terminal app's own Rich console output via Rich's own `Console.save_svg()` export — a faithful, pixel-accurate rendering of exactly what a real user's terminal would show, not a hand-drawn mockup or a staged image. All eight come from **one single real, complete pipeline run** (topic: "What is the effect of green tea consumption on metabolic health markers?", IEEE format, standard length, live `qwen3.5:9b`), captured by replaying that run's own real orchestrator events into the same `PipelineView`/`render_banner`/`render_summary`/`render_completion` code the actual CLI uses.

| File | Stage |
|---|---|
| `01-launch-banner.svg` | App launch |
| `02-research-summary.svg` | Research summary, after the setup questions |
| `03-stage-discovery.svg` | Research Discovery running |
| `04-stage-writing.svg` | Research Writing begins (Discovery done) |
| `05-stage-verification.svg` | Citation Verification (Writing done, with a real warning) |
| `06-stage-quality-assurance.svg` | Quality Assessment (Verification done) |
| `07-all-stages-complete.svg` | All four stages resolved |
| `08-completion.svg` | Final completion screen |

This particular real run finished with `draft_status: partial` (one section genuinely failed its own audit) — visible honestly in screenshots 5, 7, and 8, exactly as the real terminal app reports it. Not staged as a success case.

A previously-captured plain-text terminal output from an earlier run is also kept, folded into a collapsible note in `PHASE_3_NOTES.md`, for historical record.
