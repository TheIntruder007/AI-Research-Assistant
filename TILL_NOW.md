# Till Now

**Overall completion: ~66%** (Phase 2 complete — Review 2 milestone reached)

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
- `shared/contracts/discovery_contract.py` / `writing_contract.py` / `verification_contract.py` — Pydantic input/output contracts for Services 1, 2, and 3.
- **Research Discovery Service — fully working end-to-end** (`services/research-discovery/`): query generation → multi-source literature search (Semantic Scholar, OpenAlex, PubMed, arXiv — all keyless) → dedupe/rank → full-text mining → gap & novelty analysis. Reliability fixes in DECISIONS.md D-009. Verified via a real end-to-end run (120 papers found, 6 analyzed, 11 gaps identified). `PaperMetadata`/`Paper` now also carry the raw `abstract` text through to the contract (needed by Service 2).
- **Research Writing Service — built and tested in isolation** (`services/research-writing/`): adapted a LangGraph-based outline-driven writing agent (DECISIONS.md D-010). Takes a `DiscoveryResult`, builds an outline + one literature file per selected paper, runs the writing graph against the local model, and produces a `WritingResult` (draft markdown with disclaimer banner, citation mapping, reference candidates, run metadata). A real structural bug found via full-corpus timing runs (per-gap literature-review subsections guaranteed near-total section failure) was fixed and re-verified — see DECISIONS.md D-011.
- **Citation Verification Service — built and tested in isolation** (`services/verification/`): adapted the DOI/URL-verification piece of a full-stack literature-review app (see DECISIONS.md D-012), swapping its paid Scopus-primary check for a keyless Crossref-then-OpenAlex check (matching Service 1's "no external key" pattern). Takes a `WritingResult`, extracts the DOI from each rendered reference entry, and classifies each as verified / invalid (DOI found but resolves nowhere — possibly fabricated) / unverifiable (no DOI to check) — never silently inventing or repairing a bad reference. Produces a `VerificationResult` with a Markdown validation report. Unit tests use a mocked HTTP transport; an integration test and smoke script both verified live against real Crossref/OpenAlex with a real DOI, a fabricated DOI, and a DOI-less reference.

## 🔄 Current working pipeline
- Service 1 (Research Discovery) — working and verified in isolation. Known relevance/ranking bug: one full-corpus run selected an unrelated paper (an asthma-management guideline) for an intermittent-fasting/cognition query — not yet investigated.
- Service 2 (Research Writing) — working; the structural bug that guaranteed near-total section failure on a full-size outline is fixed and re-verified. Residual per-section reliability (typically 2 of 4 leaf sections succeed per run on this hardware) is a documented, accepted limitation of running a 9B model locally, not a blocker.
- Service 3 (Citation Verification) — working and verified in isolation, live against real Crossref/OpenAlex. Reference-list-level checking only (verified/invalid/unverifiable classification plus a cited-vs-listed count check); positional in-text citation-marker verification is a documented future enhancement, not a blocker.
- Service 4 (Quality Assurance) — not yet started.

## 🐙 GitHub status
- No remote repository yet. User will handle `gh auth login` later; local commits continue in the meantime.

## 📊 Review milestone status
- **Review 1 (~33%): reached.** `docs/reviews/review_1.md` written. Workspace, local AI, and Service 1 are done and tested.
- **Review 2 (~66%): reached.** Services 1–3 are each built and verified working in isolation (Service 3 has not yet been chained live to a real Service 1→2 output — see next steps).

## ⚠️ Known problems / limitations
- This hardware (RTX 4060, 8GB VRAM) is slow for larger-context LLM calls on a 9B model. Service 2 runs with all revision/audit rounds disabled (`FAST_REVIEW_CONFIG`) for this reason — see DECISIONS.md D-010.
- Leaf-section writing reliability in Service 2 (one LLM call per outline leaf) remains the main open source of partial drafts — typically 2 of 4 leaf sections succeed on this hardware/model, usually due to the small model occasionally mis-tagging evidence (assigning a point to both a tag and its ancestor). Mitigated with capped retries, not eliminated; failures surface as `WritingResult.draft_metadata.warnings`/`errors` rather than being hidden. See DECISIONS.md D-011.
- Service 1 relevance/ranking: at least one full-corpus run included an unrelated paper (an asthma-management guideline) among the "top 6" for an intermittent-fasting/cognition query. Not yet investigated — worth a look before Review 3, since a bad paper in the corpus wastes an entire Service 2 literature-card slot.
- Service 3 only checks the reference list, not positional in-text citation markers against the draft body — a documented scope decision (DECISIONS.md D-012), not a defect, but worth revisiting for Review 3.
- Service 3 has been verified with the live Crossref/OpenAlex APIs using hand-written `WritingResult` fixtures, not yet chained end-to-end onto a real Service 1→2 output — worth doing once before considering Review 2 fully closed out.
- `gh` CLI unavailable/unauthenticated — GitHub repo creation deferred by user request.
- Semantic Scholar / OpenAlex-based verification searches intermittently fail with rate-limit-style errors in testing; the pipeline degrades gracefully in both cases.
- Recurring test-isolation issue: every pipeline service's entry point is named `service.py` and reached only via `sys.path` insertion, so a bare `import service` in a test file silently reuses whichever service module another test file imported first in the same pytest session. Fixed per-occurrence (now in three places — discovery/writing/verification test files and smoke scripts) by loading via `importlib.util.spec_from_file_location` under a unique name; worth a structural fix (e.g. proper package names per service) if a fourth service hits the same issue.

## ➡️ Next technical task
1. Run Service 3 against a real Service 1→2 chained output (not just hand-written fixtures) at least once, to confirm the DOI-extraction regexes hold up against real writing-service output across citation styles.
2. Optionally investigate Service 1's paper-relevance bug (unrelated paper in a "top 6" corpus) before Review 3 — not a blocker, but worth a look.
3. Begin Repository 4 (Quality Assurance Service): study its architecture, confirm what it needs beyond what Service 3 already outputs (`VerificationResult`), and design the adapter following the same reuse-first, reliability-fixes-up-front approach as D-009 through D-012.
4. Define the QA service's input/output contract in `shared/contracts/`.
5. Once Service 4 is confirmed working in isolation: wire all four services together behind the orchestrator (`orchestrator/`) and the terminal app (`terminal_app/`), per PROJECT_NOTES.md's architecture — this is the remaining work for Review 3 (~100%).
