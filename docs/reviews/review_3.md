# Review 3 (~95%)

## 🎯 Project objective
Unchanged from Reviews 1–2: a local-first pipeline that takes one research request and, running entirely on a local model, produces an evidence-grounded academic paper draft — discovery, drafting, citation verification, and independent quality assurance — with every artifact preserved per run and no cloud AI dependency for reasoning.

## 🏗️ Overall architecture
```
Terminal app  ─┐
               ├─→ Orchestrator (run_pipeline) ─→ Research Discovery Service
Backend API   ─┘         │                     ─→ Research Writing Service
                          │                     ─→ Citation Verification Service
                          │                     ─→ Quality Assurance Service
                          ↓
              outputs/<slug>_<run-id>/ (per-stage artifacts + final/)
```
- `shared/contracts/` — one Pydantic input/output contract per stage, plus a top-level `pipeline_contract.py::ResearchRequest`/`PipelineResult` wrapping all four.
- `shared/utilities/llm_provider.py` — the single local-model abstraction every service (and only every service — the orchestrator, API, and Quality Assurance stage make no model calls of their own beyond what each service already does).
- `orchestrator/pipeline.py::run_pipeline()` — one async generator that runs all four services in sequence for a request, persists every stage's structured result plus a consolidated `final/` folder, and standardizes each service's own ad hoc progress-event shape into one format.
- `terminal_app/cli.py` and `orchestrator/api.py` are two independent consumers of the same `run_pipeline()` — neither duplicates pipeline logic.

## 📚 Internal services — final status
- 🔍 **Research Discovery Service** — done. Query generation → multi-source keyless literature search → dedupe/rank → full-text mining → gap and novelty analysis.
- 📝 **Research Writing Service** — done. Outline-driven, evidence-grounded drafting against the local model; the outline-structure bug from Review 2 remains fixed and re-verified.
- 🔗 **Citation Verification Service** — done. Keyless Crossref-then-OpenAlex DOI verification, three-way verified/invalid/unverifiable classification.
- 🛡️ **Quality Assurance Service** — **built and tested** (new since Review 2). Takes Discovery + Writing + Verification output together and independently checks for uncited high-risk claims, cited claims that don't token-overlap their cited paper's title/abstract (matched back to the original Discovery record by DOI), and required-section presence, producing a 0–5 score across four dimensions plus an overall score. Deliberately makes **no LLM calls at all** — grading a draft with the same model that wrote it is a weaker independence guarantee than deterministic checks, and this hardware is already the bottleneck for the earlier stages.
- **Orchestrator** (new) — `run_pipeline()` runs all four services in sequence for one `ResearchRequest`, persisting each stage's result under `outputs/<slug>_<run-id>/NN_<stage>/result.json` plus a `final/` folder (draft, quality report, validation report, reference list) and `metadata.json`.
- **Terminal app** (new) — `terminal_app/cli.py` collects a request interactively (or from one command-line argument) and calls the orchestrator, printing progress events and a final summary.
- **Backend API** (new) — `orchestrator/api.py`, a FastAPI app with `POST /research` (validates a request, runs the pipeline, returns the final result) and `GET /health`. Synchronous/blocking by design for this milestone — a run can take 15+ minutes on this hardware, and per the project's own sequencing rule, streaming is an explicit later step, not part of getting the core pipeline working through an API first.

## 🔄 Pipeline status
```
User research request
   ↓
Research Discovery Service   (done)
   ↓
Research Writing Service     (done)
   ↓
Citation Verification Service (done)
   ↓
Quality Assurance Service    (done)
   ↓
Final research draft + quality report + validation report + reference list
```
All four stages chained and verified live end-to-end multiple times, both by hand and through the real orchestrator.

## 🟢 Work completed since Review 2
- Quality Assurance Service built: deterministic citation-integrity and claim-alignment auditing, DOI-based cross-referencing back to Discovery records, four-dimension + overall scoring.
- Orchestrator built: sequences all four services, persists a consistent artifact layout, standardizes progress events, resolves a recurring module-naming collision (every service's entry point is a same-named `service.py` reached only via path insertion) by loading each one from an explicit file path under a unique module name.
- Terminal app built: the current user-facing interface, calling the orchestrator directly.
- Backend API built: `POST /research` and `GET /health`, verified both via `TestClient` unit tests and a real running `uvicorn` server.
- **Full-pipeline live integration test added** (`tests/integration/test_full_pipeline_live.py`): runs the real orchestrator through all four services against the live model and live external APIs with a fresh full-size (6-paper) corpus, and asserts every stage's artifact and every `final/` file exists and is contract-valid — not just that the console output looks right. Gated behind an opt-in environment variable since a full run takes about 15 minutes, keeping the routine test suite fast (~8–9 minutes) for everyday development. Ran successfully in 913.01 seconds.

## 🧪 Tests performed
- Unit tests for every service (contracts, dedupe/ranking, outline building, DOI extraction and classification, citation-audit and scoring logic) — fast, network- and model-free where the logic allows it (Quality Assurance makes no LLM/HTTP calls at all).
- Live integration tests per service (Discovery, Writing, Verification), each scoped to be fast (minimal fixtures, single real checks), skipping cleanly if the local model or network isn't reachable.
- Fully mocked orchestrator and API tests (`tests/orchestrator/test_pipeline.py`, `tests/orchestrator/test_api.py`) covering artifact persistence, standardized progress-event shape, `PipelineError` propagation to a 502, and request validation to a 422 — all fast, no network or model calls.
- Terminal app's interactive prompt-collection logic unit-tested against simulated input.
- **New:** an opt-in full-pipeline live integration test exercising the real chain end-to-end, run manually and passing.
- Full test suite: 35 passed, 1 (the opt-in full-pipeline test) correctly skipped by default, in roughly 8–9 minutes.

## 📦 Current outputs
- A complete, real end-to-end run persists: the original request, each stage's structured result, and a `final/` folder with the draft, quality report, validation report, and reference list — all under one `outputs/<slug>_<run-id>/` directory.
- Quality scores observed across multiple real runs ranged from 3.5/5.0 to 4.2/5.0 overall, correctly reflecting each run's actual citation count and section-writing success rate rather than a fixed or inflated number.
- A live FastAPI server confirmed serving `/health` (200) and rejecting a malformed `/research` request (422) over a real HTTP connection.

## 🚧 Current limitations
- Leaf-section writing reliability in the Research Writing Service remains the main source of partial drafts on this hardware (typically 2 of 4 leaf sections succeed per run) — a documented, accepted limitation of running a 9B model locally, surfaced honestly via warnings/errors rather than hidden, and reflected in the Quality Assurance service's process-control score.
- Research Discovery has an unresolved relevance/ranking edge case: one full-corpus run selected an unrelated paper for an otherwise on-topic query. Not yet investigated; not a blocker.
- Citation Verification checks the reference list only, not positional in-text citation markers against the draft body — a deliberate scope decision, documented as a future enhancement.
- The backend API is synchronous/blocking by design; a caller must wait out the full run (which can exceed 15 minutes). `GET /research/{run_id}` and progress/event streaming (SSE) are explicitly deferred, not overlooked — the project's own working rule is to prove the simple synchronous path first.
- The new full-pipeline integration test is opt-in (env-var gated) rather than part of every routine test run, given its ~15-minute cost; it is a documented manual gate to run before milestones and after any orchestrator/contract change, not a CI-enforced check.
- No GitHub remote yet — local git history only, by choice, pending the user completing `gh auth login`.

## ➡️ Next work
- Optional, non-blocking follow-ups: wire `GET /research/{run_id}` and SSE progress streaming over the backend API now that the synchronous path is proven; investigate the Research Discovery relevance edge case.
- No further core pipeline work is planned — Services 1–4, the orchestrator, the terminal app, the backend API, and full-pipeline regression coverage are all built and verified live.
