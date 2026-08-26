# Till Now

**Overall completion: ~75%** (all four pipeline services built and verified individually and chained; orchestrator/terminal app remain for Review 3)

## ✅ Completed components
- Project workspace, now located at `E:\Agentic AI\AI-Research-Assistant` (moved 2026-08-27 from `Desktop\AI-Research-Assistant`; `.venv` was rebuilt fresh at the new path since venvs bake in an absolute path).
- Git repository (local history intact through the move), `.gitignore` in place.
- Core documentation: `README.md`, `PROJECT_NOTES.md`, `DECISIONS.md`, `TILL_NOW.md`.
- Hardware inspected (i7-13700HX, 16GB RAM, RTX 4060 8GB VRAM) and recorded.
- Ollama installed and running, model storage at `D:\ollama_models` (unaffected by the project move — see DECISIONS.md D-008).
- Local AI model selected and **verified working**: `qwen3.5:9b`.
- GitHub CLI installed but not authenticated — user chose to hold off on GitHub setup for now.
- Project Python venv (`.venv`) with `httpx`, `pydantic`, `python-dotenv`, `pytest`, `langgraph` + langchain-core stack, plus service-specific deps (`pypdf`, `defusedxml`, `PyYAML`).
- `shared/utilities/llm_provider.py` — local-first LLM abstraction (Ollama `/api/chat`, streaming JSON, tiered context sizing that accounts for actual prompt length, not just output length — see DECISIONS.md D-010).
- `shared/contracts/discovery_contract.py` / `writing_contract.py` / `verification_contract.py` / `qa_contract.py` — Pydantic input/output contracts for all four services.
- **Research Discovery Service — fully working end-to-end** (`services/research-discovery/`): query generation → multi-source literature search (Semantic Scholar, OpenAlex, PubMed, arXiv — all keyless) → dedupe/rank → full-text mining → gap & novelty analysis. Reliability fixes in DECISIONS.md D-009. `PaperMetadata`/`Paper` carry the raw `abstract` text through to the contract (needed by Services 2 and 4).
- **Research Writing Service — built and tested** (`services/research-writing/`): adapted a LangGraph-based outline-driven writing agent (DECISIONS.md D-010). Takes a `DiscoveryResult`, builds an outline + one literature file per selected paper, runs the writing graph against the local model, and produces a `WritingResult`. A real structural bug found via full-corpus timing runs (per-gap literature-review subsections guaranteed near-total section failure) was fixed and re-verified — see DECISIONS.md D-011.
- **Citation Verification Service — built and tested** (`services/verification/`): adapted the DOI/URL-verification piece of a full-stack literature-review app (DECISIONS.md D-012), swapping its paid Scopus-primary check for a keyless Crossref-then-OpenAlex check. Classifies each rendered reference as verified / invalid / unverifiable — never silently inventing or repairing a bad reference.
- **Quality Assurance Service — built and tested** (`services/quality-assurance/`): adapted the deterministic citation-audit and evaluation-reflection logic of a larger multi-agent review system (DECISIONS.md D-013). Takes Discovery + Writing + Verification output together and independently checks for uncited high-risk claims, cited claims that don't token-overlap their source's title/abstract (matched by DOI back to the original Discovery record), and required-section presence — producing a 0–5 quality score across four dimensions plus an overall score. Deliberately makes **no LLM calls** (grading a draft with the model that wrote it would be a weaker independence guarantee than deterministic checks, and this hardware is already the bottleneck elsewhere).
- **Full four-service pipeline verified live, chained end-to-end**: a real research question ran through Discovery → Writing → Verification → QA using `scripts/smoke_test_full_pipeline.py`, with each stage consuming the previous stage's actual structured output (no hand-written fixtures). Confirmed Service 3's DOI-extraction regex works against Service 2's real IEEE-formatted reference strings, and Service 4's scoring/limitation logic produces sensible output (3.5/5.0 overall on a run with 3 missing citations, 0 unsupported claims, no missing sections) — see DECISIONS.md D-013's verification note.

## 🔄 Current working pipeline
- Service 1 (Research Discovery) — working and verified in isolation. Known relevance/ranking bug: one full-corpus run selected an unrelated paper (an asthma-management guideline) for an intermittent-fasting/cognition query — not yet investigated.
- Service 2 (Research Writing) — working; the structural bug that guaranteed near-total section failure on a full-size outline is fixed and re-verified. Residual per-section reliability (typically 2 of 4 leaf sections succeed per run on this hardware) is a documented, accepted limitation of running a 9B model locally, not a blocker.
- Service 3 (Citation Verification) — working, verified in isolation and now live-chained onto real Service 1→2 output. Reference-list-level checking only; positional in-text citation-marker verification is a documented future enhancement.
- Service 4 (Quality Assurance) — working, verified in isolation and live-chained onto real Service 1→2→3 output. Fully deterministic (no LLM calls).
- **All four services now verified chained together end-to-end against a live run.** Remaining integration work is the orchestrator/API/terminal-app layer, not the services themselves.

## 🐙 GitHub status
- No remote repository yet. User will handle `gh auth login` later; local commits continue in the meantime.

## 📊 Review milestone status
- **Review 1 (~33%): reached.** `docs/reviews/review_1.md` written. Workspace, local AI, and Service 1 are done and tested.
- **Review 2 (~66%): reached.** Services 1–3 built and verified.
- **Review 3 (~100%): in progress.** All four services are built, individually tested, and verified chained together live. Remaining: the orchestrator (`orchestrator/`), the main backend API (`POST /research`, per PROJECT_NOTES.md), the terminal app (`terminal_app/`), progress/event-streaming wiring, integration/regression test coverage across the full pipeline, and final project documentation/review write-ups.

## ⚠️ Known problems / limitations
- This hardware (RTX 4060, 8GB VRAM) is slow for larger-context LLM calls on a 9B model. Service 2 runs with all revision/audit rounds disabled (`FAST_REVIEW_CONFIG`) for this reason — see DECISIONS.md D-010.
- Leaf-section writing reliability in Service 2 (one LLM call per outline leaf) remains the main open source of partial drafts — typically 2 of 4 leaf sections succeed on this hardware/model, usually due to the small model occasionally mis-tagging evidence (assigning a point to both a tag and its ancestor). Mitigated with capped retries, not eliminated; failures surface as `WritingResult.draft_metadata.warnings`/`errors` and are reflected in Service 4's `process_control` score, not hidden. See DECISIONS.md D-011.
- Service 1 relevance/ranking: at least one full-corpus run included an unrelated paper (an asthma-management guideline) among the "top 6" for an intermittent-fasting/cognition query. Not yet investigated — worth a look before Review 3 is considered fully closed, since a bad paper wastes a Service 2 literature-card slot and can starve Service 4's DOI-matched claim checking.
- Service 3 only checks the reference list, not positional in-text citation markers against the draft body — a documented scope decision (DECISIONS.md D-012), not a defect.
- Service 4's claim-to-evidence check depends on Service 3's extracted DOI matching a Discovery record; when Service 2's own leaf-section reliability issue leaves a draft with very few real citations (as in the live full-pipeline run — only 1 of the corpus's papers actually got cited), Service 4 has correspondingly little to check. This is expected given Service 2's known limitation, not a Service 4 defect.
- `gh` CLI unavailable/unauthenticated — GitHub repo creation deferred by user request.
- Semantic Scholar / OpenAlex-based verification searches intermittently fail with rate-limit-style errors in testing; the pipeline degrades gracefully in both cases.
- Recurring test-isolation issue: every pipeline service's entry point is named `service.py` and reached only via `sys.path` insertion, so a bare `import service` in a test file silently reuses whichever service module another test file imported first in the same pytest session. Fixed per-occurrence (now in four places — discovery/writing/verification/QA test files and smoke scripts) by loading via `importlib.util.spec_from_file_location` under a unique name; worth a structural fix (e.g. proper package names per service) if this keeps recurring once the orchestrator imports all four.

## ➡️ Next technical task
1. Build the orchestrator (`orchestrator/`): a pipeline runner that takes one research request, runs Services 1→2→3→4 in sequence, persists each stage's artifacts under `outputs/<topic-slug>_<run-id>/`, and exposes the structured progress events every service already emits.
2. Build the main backend API: a `POST /research` endpoint (per PROJECT_NOTES.md/docx spec) that validates input, creates a run, invokes the orchestrator, and returns the final result; a `GET /research/{run_id}` can follow once the core path works.
3. Build the terminal app (`terminal_app/`) as the current user-facing interface, per PROJECT_NOTES.md's architecture.
4. Add integration/regression tests across the full chained pipeline (building on `scripts/smoke_test_full_pipeline.py`, which currently only exercises this manually).
5. Progress/event streaming (SSE or similar) only after the above core pipeline works end-to-end via the API — per the project's explicit "build after the core pipeline" rule.
6. Optionally investigate Service 1's paper-relevance bug before final submission — not a blocker.
7. Write `docs/reviews/review_2.md` (retroactively, since work has moved past that point) and prepare `docs/reviews/review_3.md` once the orchestrator/API/terminal app are done.
