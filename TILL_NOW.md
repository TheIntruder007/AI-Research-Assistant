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
- Tests: 5 unit tests passing (`tests/shared/test_discovery_contract.py`, `tests/shared/test_llm_provider.py`, `tests/services/test_discovery_service.py`) — schema validation and adapter mapping logic. **Not yet tested**: an actual end-to-end run against a live model (blocked on the model pull finishing).

## 🔄 Current working pipeline
- Service 1 (Research Discovery) code complete and import-clean; not yet run end-to-end (needs the local model available).

## 🐙 GitHub status
- No remote repository yet. User will handle `gh auth login` later; local commits continue in the meantime.

## 📝 Latest commits
- `chore: initialize project workspace and documentation`
- (this session's Service 1 work not yet committed — see Next task)

## 📊 Review milestone status
- Review 1 (~33%): not started — will be written once Service 1 is verified working end-to-end.

## ⚠️ Known problems
- `qwen3.5:9b` download has been slow and repeatedly restarting mid-transfer (network instability) — verification blocked until it completes.
- `gh` CLI unavailable/unauthenticated — GitHub repo creation deferred by user request.

## ➡️ Next technical task
1. Check background task `bb6xoi7wt` (or `ollama list`) — confirm `qwen3.5:9b` finished downloading.
2. Run a smoke prompt (`ollama run qwen3.5:9b "reply with OK"`) to verify the model responds; record result in DECISIONS.md D-002.
3. Run `service.run_discovery()` end-to-end with a small test research question (small `corpus_size`, e.g. 6) against the live model; fix any JSON-schema/parsing issues Ollama's structured output surfaces (Ollama's schema support may behave slightly differently from the original cloud providers — expect some iteration here).
4. Add an integration test for Service 1 (`tests/services/test_discovery_pipeline_integration.py`) using a small controlled question.
5. Commit this Service 1 work with message `feat: integrate research discovery service`.
6. Update `PROJECT_NOTES.md`/`DECISIONS.md` if the live run reveals adaptation issues.
7. Only after Service 1 is confirmed working in isolation: begin Repository 2 (Research Writing Service) study and adaptation.
