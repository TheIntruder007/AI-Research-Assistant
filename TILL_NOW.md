# Till Now

**Overall completion: ~50%** (Phase 2 — Service 2 built and unit/integration tested)

## ✅ Completed components
- Project workspace, now located at `E:\Agentic AI\AI-Research-Assistant` (moved 2026-08-27 from `Desktop\AI-Research-Assistant`; `.venv` was rebuilt fresh at the new path since venvs bake in an absolute path).
- Git repository (local history intact through the move), `.gitignore` in place.
- Core documentation: `README.md`, `PROJECT_NOTES.md`, `DECISIONS.md`, `TILL_NOW.md`.
- Hardware inspected (i7-13700HX, 16GB RAM, RTX 4060 8GB VRAM) and recorded.
- Ollama installed and running, model storage at `D:\ollama_models` (unaffected by the project move — see DECISIONS.md D-008).
- Local AI model selected and **verified working**: `qwen3.5:9b`.
- GitHub CLI installed but not authenticated — user chose to hold off on GitHub setup for now.
- Project Python venv (`.venv`) with `httpx`, `pydantic`, `python-dotenv`, `pytest`, `langgraph` + langchain-core stack, plus service-specific deps (`pypdf`, `defusedxml`, `PyYAML`).
- `shared/utilities/llm_provider.py` — local-first LLM abstraction (Ollama `/api/chat`, streaming JSON, tiered context sizing that now accounts for actual prompt length, not just output length — see DECISIONS.md D-010).
- `shared/contracts/discovery_contract.py` / `shared/contracts/writing_contract.py` — Pydantic input/output contracts for Services 1 and 2.
- **Research Discovery Service — fully working end-to-end** (`services/research-discovery/`): query generation → multi-source literature search (Semantic Scholar, OpenAlex, PubMed, arXiv — all keyless) → dedupe/rank → full-text mining → gap & novelty analysis. Reliability fixes in DECISIONS.md D-009. Verified via a real end-to-end run (120 papers found, 6 analyzed, 11 gaps identified). `PaperMetadata`/`Paper` now also carry the raw `abstract` text through to the contract (needed by Service 2).
- **Research Writing Service — built and tested in isolation** (`services/research-writing/`): adapted a LangGraph-based outline-driven writing agent (see DECISIONS.md D-010 for the full adaptation record). Takes a `DiscoveryResult`, builds an outline + one literature file per selected paper, runs the writing graph against the local model, and produces a `WritingResult` (draft markdown with disclaimer banner, citation mapping, reference candidates, run metadata). Unit tests cover outline/literature-file prep; an integration test runs the full service against the live local model on a minimal 2-paper/4-section case.

## 🔄 Current working pipeline
- Service 1 (Research Discovery) — working and verified in isolation.
- Service 2 (Research Writing) — working and verified in isolation on a minimal case; a full production-sized outline run has not yet been timed/verified end-to-end (see Known problems).
- Services 3–4 not yet started.

## 🐙 GitHub status
- No remote repository yet. User will handle `gh auth login` later; local commits continue in the meantime.

## 📊 Review milestone status
- **Review 1 (~33%): reached.** `docs/reviews/review_1.md` written. Workspace, local AI, and Service 1 are done and tested.
- **Review 2 (~66%): in progress.** Service 2 is built and tested in isolation; Service 3 (Citation Verification) not yet started.

## ⚠️ Known problems / limitations
- This hardware (RTX 4060, 8GB VRAM) is slow for larger-context LLM calls on a 9B model. Service 2 runs with all revision/audit rounds disabled (`FAST_REVIEW_CONFIG`) for this reason — see DECISIONS.md D-010.
- Leaf-section writing reliability in Service 2 (one LLM call per outline leaf) is the main open risk for a full-size outline — mitigated with capped retries, not eliminated; failures surface as `WritingResult.draft_metadata.warnings`/`errors` rather than being hidden.
- A full production-sized Service 2 outline has not been run end-to-end yet — only a minimal 2-paper/4-section case has been verified live. Each leaf section is a separate LLM call, so a full run's duration on this hardware is untested; budget real time for this before Review 2 is considered fully done.
- `gh` CLI unavailable/unauthenticated — GitHub repo creation deferred by user request.
- Semantic Scholar / OpenAlex-based verification searches intermittently fail with rate-limit-style errors in testing; the pipeline degrades gracefully in both cases.
- Fixed a test-isolation bug (2026-08-27): both `research-discovery/service.py` and `research-writing/service.py` are loaded as the bare module name `service` via `sys.path` insertion, so importing both in the same pytest session caused whichever loaded second to silently reuse the first one's cached module. Fixed by loading the writing service via `importlib.util.spec_from_file_location` under a unique name in `tests/services/test_writing_pipeline_integration.py` and `scripts/smoke_test_writing.py`.

## ➡️ Next technical task
1. Run a full (not minimal) Service 2 outline end-to-end at least once to get a real timing/reliability baseline on this hardware, and record it in DECISIONS.md.
2. Commit the current Service 2 work (writing service, contract, tests, D-010) plus the project-move housekeeping.
3. Begin Repository 3 (Citation Verification Service): study its architecture, confirm what it needs beyond what Service 2 already outputs (`WritingResult` — draft markdown, citation mapping, reference candidates), and design the adapter following the same reuse-first, reliability-fixes-up-front approach as D-009/D-010.
4. Define the verification service's input/output contract in `shared/contracts/`.
5. Only after Service 3 is confirmed working in isolation: begin Repository 4 (Quality Assurance Service).
