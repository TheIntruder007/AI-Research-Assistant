# Till Now

**Overall completion: ~15%** (Phase 2 in progress — Service 1 adaptation)

## ✅ Completed components
- Project workspace created at `Desktop/AI-Research-Assistant` with full folder structure.
- Git repository initialized locally, `.gitignore` in place (includes `.dev-private/` for source study material — never committed).
- Core documentation created: `README.md`, `PROJECT_NOTES.md`, `DECISIONS.md`, `TILL_NOW.md`.
- Hardware inspected (i7-13700HX, 16GB RAM, RTX 4060 8GB VRAM) and recorded.
- Ollama installed (v0.32.15) and verified.
- Local AI model selected: `qwen3.5:9b` — **pull in progress** (large download, connection has been unstable/restarting; not yet verified working).
- GitHub CLI installed (v2.98.0) but not authenticated — user chose to hold off on GitHub setup for now (see D-006).
- Project Python venv created at `.venv` with `httpx`, `pydantic`, `python-dotenv`, `pytest` installed.
- `shared/utilities/llm_provider.py` — local-first LLM abstraction (streaming JSON via Ollama's native `/api/chat`, no cloud fallback).
- `shared/contracts/discovery_contract.py` — Pydantic input/output contract for the Research Discovery Service.
- `services/research-discovery/` — Service 1 adapted and in place:
  - `discovery/` package (models, pipeline, analysis, fulltext, sources: Semantic Scholar/OpenAlex/PubMed/arXiv — all keyless).
  - Rewired to `shared/utilities/llm_provider.py`.
  - Removed reference-manager sync and citation-enrichment integrations, and the web frontend/HTTP layer (see DECISIONS.md D-007).
  - Extended output schema with `novelty_analysis`, `confidence_notes`, `research_interpretation` per the project's required output contract.
  - `service.py::run_discovery()` — the stable entry point, adapts pipeline output to `DiscoveryResult`.
- Tests: 9 unit tests passing (contract validation, adapter mapping, dedupe/rank pure-logic tests). **Not yet tested**: an actual end-to-end run against a live model (blocked on the model pull finishing).
- `scripts/smoke_test_discovery.py` — manual end-to-end smoke test script, ready to run once the model finishes downloading.

## 🔄 Current working pipeline
- Service 1 (Research Discovery) code complete and import-clean; not yet run end-to-end (needs the local model available).

## 🐙 GitHub status
- No remote repository yet. User will handle `gh auth login` later; local commits continue in the meantime.

## 📝 Latest commits
- `chore: initialize project workspace and documentation`
- `feat: integrate research discovery service`
- `fix: remove leftover references to fields dropped from Paper model` (caught by new dedupe/rank unit tests)

## 📊 Review milestone status
- Review 1 (~33%): not started — will be written once Service 1 is verified working end-to-end.

## ⚠️ Known problems
- `qwen3.5:9b` download has been slow and repeatedly restarting mid-transfer (network instability), and the working session itself restarted once mid-download, killing the in-progress pull — `ollama list` was empty on resume. Restarted again as background task `b1utqory8`. If a session restarts again before this finishes, just re-run `ollama pull qwen3.5:9b` (resumable) and check `ollama list`.
- `gh` CLI unavailable/unauthenticated — GitHub repo creation deferred by user request.

## ➡️ Next technical task
1. Check background task `b1utqory8` (or `ollama list`) — confirm `qwen3.5:9b` finished downloading. If missing/interrupted again, just re-run `ollama pull qwen3.5:9b` (this has needed 2+ restarts already due to network + one session restart — keep retrying, it's a one-time setup cost).
2. Run a smoke prompt (`ollama run qwen3.5:9b "reply with OK"`) to verify the model responds; record result in DECISIONS.md D-002.
3. Run `python scripts/smoke_test_discovery.py "<a small test question>"` end-to-end; fix any JSON-schema/parsing issues Ollama's structured output surfaces (Ollama's schema support may behave slightly differently from the original cloud providers — expect some iteration here, especially around `additionalProperties: False` strictness and streaming delta shape).
4. Add an integration test for Service 1 (`tests/services/test_discovery_pipeline_integration.py`) using a small controlled question — mark it to skip cleanly if Ollama isn't running.
5. Update `PROJECT_NOTES.md`/`DECISIONS.md` if the live run reveals adaptation issues; commit fixes.
6. Only after Service 1 is confirmed working end-to-end in isolation: write `docs/reviews/review_1.md` (Review 1 ~33% milestone — workspace + local AI + Service 1 done), then begin Repository 2 (Research Writing Service) study and adaptation.
