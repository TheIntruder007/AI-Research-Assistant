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
- **Fixed a real structural bug found via full-corpus timing runs** (DECISIONS.md D-011): the original outline gave each Discovery research gap its own literature-review subsection, which guaranteed near-total section failure (2 of 13 sections on a real 6-paper run) because each gap's narrow, specific wording excluded almost the whole corpus from its own subsection by the writing graph's own evidence rules. Fixed by flattening the outline (Introduction / Literature Review / Limitations / Conclusion) and rendering Discovery's gap/novelty synthesis directly as Markdown instead of asking the evidence-gated writer to source it. Re-verified: the guaranteed failure is gone, though the local 9B model still intermittently mis-tags evidence (assigns a point to both a tag and its ancestor) causing occasional section failures — this is an ordinary model-reliability limitation, not a design defect, and is already surfaced via `warnings`/`errors` rather than hidden.

## 🔄 Current working pipeline
- Service 1 (Research Discovery) — working and verified in isolation. Known relevance/ranking bug: one full-corpus run selected an unrelated paper (an asthma-management guideline) for an intermittent-fasting/cognition query — not yet investigated.
- Service 2 (Research Writing) — working; the structural bug that guaranteed near-total section failure on a full-size outline is fixed and re-verified. Residual per-section reliability (typically 2 of 4 leaf sections succeed per run on this hardware) is a documented, accepted limitation of running a 9B model locally, not a blocker.
- Services 3–4 not yet started.

## 🐙 GitHub status
- No remote repository yet. User will handle `gh auth login` later; local commits continue in the meantime.

## 📊 Review milestone status
- **Review 1 (~33%): reached.** `docs/reviews/review_1.md` written. Workspace, local AI, and Service 1 are done and tested.
- **Review 2 (~66%): in progress.** Service 2 is built and tested in isolation; Service 3 (Citation Verification) not yet started.

## ⚠️ Known problems / limitations
- This hardware (RTX 4060, 8GB VRAM) is slow for larger-context LLM calls on a 9B model. Service 2 runs with all revision/audit rounds disabled (`FAST_REVIEW_CONFIG`) for this reason — see DECISIONS.md D-010.
- Leaf-section writing reliability in Service 2 (one LLM call per outline leaf) remains the main open source of partial drafts — typically 2 of 4 leaf sections succeed on this hardware/model, usually due to the small model occasionally mis-tagging evidence (assigning a point to both a tag and its ancestor). Mitigated with capped retries, not eliminated; failures surface as `WritingResult.draft_metadata.warnings`/`errors` rather than being hidden. See DECISIONS.md D-011.
- Service 1 relevance/ranking: at least one full-corpus run included an unrelated paper (an asthma-management guideline) among the "top 6" for an intermittent-fasting/cognition query. Not yet investigated — worth a look before Review 2, since a bad paper in the corpus wastes an entire Service 2 literature-card slot.
- `gh` CLI unavailable/unauthenticated — GitHub repo creation deferred by user request.
- Semantic Scholar / OpenAlex-based verification searches intermittently fail with rate-limit-style errors in testing; the pipeline degrades gracefully in both cases.
- Fixed a test-isolation bug (2026-08-27): both `research-discovery/service.py` and `research-writing/service.py` are loaded as the bare module name `service` via `sys.path` insertion, so importing both in the same pytest session caused whichever loaded second to silently reuse the first one's cached module. Fixed by loading the writing service via `importlib.util.spec_from_file_location` under a unique name in `tests/services/test_writing_pipeline_integration.py` and `scripts/smoke_test_writing.py`.

## ➡️ Next technical task
1. Optionally investigate Service 1's paper-relevance bug (unrelated paper in a "top 6" corpus) before Review 2 — not a blocker, but worth a look since it wastes a Service 2 literature-card slot.
2. Begin Repository 3 (Citation Verification Service): study its architecture, confirm what it needs beyond what Service 2 already outputs (`WritingResult` — draft markdown, citation mapping, reference candidates), and design the adapter following the same reuse-first, reliability-fixes-up-front approach as D-009/D-010/D-011.
3. Define the verification service's input/output contract in `shared/contracts/`.
4. Only after Service 3 is confirmed working in isolation: begin Repository 4 (Quality Assurance Service).
