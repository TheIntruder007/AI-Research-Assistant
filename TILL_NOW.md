# Till Now

**Overall completion: ~33%** (Phase 1 complete — Review 1 milestone reached)

## ✅ Completed components
- Project workspace created at `Desktop/AI-Research-Assistant` with full folder structure.
- Git repository initialized locally, `.gitignore` in place.
- Core documentation: `README.md`, `PROJECT_NOTES.md`, `DECISIONS.md`, `TILL_NOW.md`.
- Hardware inspected (i7-13700HX, 16GB RAM, RTX 4060 8GB VRAM) and recorded.
- Ollama installed and running, model storage relocated to `D:\ollama_models` (C: drive was nearly full — see DECISIONS.md D-008).
- Local AI model selected and **verified working**: `qwen3.5:9b`, confirmed via direct prompts and a full pipeline run.
- GitHub CLI installed but not authenticated — user chose to hold off on GitHub setup for now.
- Project Python venv (`.venv`) with `httpx`, `pydantic`, `python-dotenv`, `pytest`, plus service-specific deps (`pypdf`, `defusedxml`).
- `shared/utilities/llm_provider.py` — local-first LLM abstraction (Ollama `/api/chat`, streaming JSON, tiered context sizing).
- `shared/contracts/discovery_contract.py` — Pydantic input/output contract for the Research Discovery Service.
- **Research Discovery Service — fully working end-to-end** (`services/research-discovery/`):
  - Query generation → multi-source literature search (Semantic Scholar, OpenAlex, PubMed, arXiv — all keyless) → dedupe/rank → full-text mining → gap & novelty analysis, all as an async-generator pipeline emitting structured progress events.
  - Adapted to the local model provider with four reliability fixes documented in DECISIONS.md D-009 (thinking mode, tiered context sizing, schema trimming, candidate capping).
  - **Verified via a real end-to-end run**: research question "What are the effects of intermittent fasting on cognitive performance?" → 120 papers found, 118 unique, 6 analyzed, 5 author-flagged future-research candidates, 11 research gaps identified, novelty confidence "medium". Full JSON output validated against the `DiscoveryResult` contract.

## 🔄 Current working pipeline
- Service 1 (Research Discovery) — working and verified in isolation.
- Services 2–4 not yet started.

## 🐙 GitHub status
- No remote repository yet. User will handle `gh auth login` later; local commits continue in the meantime.

## 📝 Latest commits
- `chore: initialize project workspace and documentation`
- `feat: integrate research discovery service`
- `fix: remove leftover references to fields dropped from Paper model`
- `chore: add discovery smoke-test script; update progress notes`
- `docs: record OLLAMA_MODELS relocation to D: drive and resume instructions`
- `feat: verify research discovery service end-to-end against local model` (this session — reliability fixes, integration test, Review 1 docs)

## 📊 Review milestone status
- **Review 1 (~33%): reached.** `docs/reviews/review_1.md` written. Workspace, local AI, and Service 1 are done and tested.

## ⚠️ Known problems / limitations
- This hardware (RTX 4060, 8GB VRAM) is slow for larger-context LLM calls on a 9B model — a full discovery run's gap-analysis step alone can take several minutes to tens of minutes depending on system load. Later services should keep schemas compact and cap any unbounded lists before they reach a synthesis prompt (see DECISIONS.md D-009's closing note).
- `gh` CLI unavailable/unauthenticated — GitHub repo creation deferred by user request.
- Semantic Scholar search intermittently fails with a rate-limit-style HTTP error in testing; the pipeline already degrades gracefully (continues without that source), so this hasn't blocked anything, just reduces corpus diversity slightly.
- OpenAlex-based verification searches for author-flagged candidates have been failing in testing (HTTPStatusError) — also degrades gracefully (judged on main corpus only), but worth a look if it persists.

## ➡️ Next technical task
1. Begin Phase 2, Repository 2: study and adapt the Research Writing Service (evidence structuring, outline generation, evidence-grounded draft generation, citation mapping) so it accepts `DiscoveryResult` as input.
2. Define `shared/contracts/writing_contract.py` for its input/output.
3. Reuse the same reliability lessons from D-009 (think=False by default, tiered context, compact schemas, cap unbounded lists) from the start rather than discovering them again.
4. Only after Service 2 is confirmed working in isolation: begin Repository 3 (Citation Verification Service).
