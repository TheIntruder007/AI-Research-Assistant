# Decisions Log

Every important technical decision is recorded here: what was decided, why, alternatives considered, and impact.

---

## D-001 — Project workspace location and structure
- **Date:** 2026-08-26
- **Decision:** Create the project at `Desktop/AI-Research-Assistant` with the standard `services/ orchestrator/ shared/ outputs/ docs/ tests/ scripts/` layout.
- **Reason:** Matches the required architecture; keeps each pipeline stage independently testable.
- **Alternatives considered:** Monolithic single-app structure — rejected, breaks the "test each service in isolation" requirement.
- **Impact:** All later services/adapters follow this layout.

## D-002 — Local AI model selection: qwen3.5:9b
- **Date:** 2026-08-26
- **Decision:** Use `qwen3.5:9b` (6.6GB) via Ollama as the default local reasoning/generation model.
- **Reason:**
  - Machine hardware: Intel i7-13700HX (16 cores/24 threads), 16GB system RAM, NVIDIA RTX 4060 Laptop GPU with 8GB VRAM (verified via `nvidia-smi`).
  - qwen3.5:9b (6.6GB) fits comfortably within 8GB VRAM with headroom for context.
  - Larger variants (qwen3.5:27b ≈17GB, qwen3.5:35b ≈24GB) exceed available VRAM and would require heavy CPU offload on a 16GB-RAM machine, making development unusably slow.
  - Verified via web search against the live Ollama library (not guessed) that `qwen3.5:9b` is a real, currently published tag.
- **Alternatives considered:** qwen3.5:27b/35b (rejected — hardware too small), a non-Qwen family (rejected — doc specifies Qwen 3.5 family as preferred starting point and it is available and fits).
- **Impact:** All four services call the local model through an `LLMProvider` abstraction defaulting to `qwen3.5:9b`; swapping models later requires no service code changes.
- **Installation command:** `ollama pull qwen3.5:9b`
- **Verification result:** Confirmed working 2026-08-27. `ollama run qwen3.5:9b "Reply with exactly: OK"` responded correctly (model shows a visible reasoning trace before its answer, then replied "OK"). Download took far longer than expected (~24h) due to two compounding environmental issues on this machine, unrelated to the model choice itself — see D-008.

## D-003 — Model abstraction layer
- **Date:** 2026-08-26
- **Decision:** All services call an internal `LLMProvider` interface rather than the Ollama SDK directly.
- **Reason:** Keeps the model replaceable without touching service logic; required by project spec.
- **Alternatives considered:** Direct Ollama calls per service — rejected, creates tight coupling.
- **Impact:** `shared/utilities` will host the provider abstraction; each service imports it.

## D-004 — Documentation privacy on original components
- **Date:** 2026-08-26
- **Decision:** All project-facing documentation (README, PROJECT_NOTES, DECISIONS, reviews, TILL_NOW, commits) describes each pipeline stage as an internal project service by function only. Provenance of any component adapted during development is not recorded in project-facing files or commit history.
- **Reason:** Per explicit project requirement — present the system as one unified in-house codebase.
- **Alternatives considered:** Standard OSS attribution in README — rejected per explicit instruction.
- **Impact:** Service names used throughout: Research Discovery Service, Research Writing Service, Citation Verification Service, Quality Assurance Service.

## D-005 — Secrets handling
- **Date:** 2026-08-26
- **Decision:** Use `.env` for any external API keys, with `.env.example` committed and `.env` gitignored. No key is ever logged, printed, or committed.
- **Reason:** Standard secret hygiene; required by project spec.
- **Alternatives considered:** Hardcoding keys — rejected outright.
- **Impact:** Any service requiring an external API (paper search, DOI lookup) reads keys from environment variables only, and the pipeline stops with clear instructions if a required key is missing.

## D-008 — Ollama model storage moved to D: drive
- **Date:** 2026-08-27
- **Decision:** Set `OLLAMA_MODELS=D:\ollama_models` (persisted as a Windows user environment variable) instead of the default `C:\Users\<user>\.ollama\models`.
- **Reason:** The `qwen3.5:9b` pull repeatedly failed/stalled over many hours. Initial diagnosis suspected network throttling by the Killer Wi-Fi adapter's traffic-shaping software (confirmed as a contributing factor — `curl` to the same registry URL was consistently faster than `ollama.exe`'s own download). However, the actual failure was a `curl exit code 23` (disk write failure): the C: drive was completely full (0 bytes free at the time), which silently truncated every download attempt regardless of network speed. This was the root cause; the network throttling only made the symptom slower to diagnose.
- **Alternatives considered:** Freeing up space on C: instead — rejected as fragile; C: was at 98% capacity independent of this project, so any future model pull would risk hitting the same wall. D: has 52GB free, comfortably enough for this and future models.
- **Impact:** The Ollama tray watchdog (`ollama app.exe`, which auto-relaunches `ollama.exe serve` on kill) had to be stopped so a manually-launched server with the correct `OLLAMA_MODELS` env var would stick. `shared/utilities/llm_provider.py` is unaffected (it only needs `OLLAMA_HOST`, not the model storage path). Anyone resuming this project on this machine should launch Ollama's server manually with `OLLAMA_MODELS=D:\ollama_models` if the tray app was disabled, or re-enable the tray app after confirming it picks up the persisted env var on next login.

## D-009 — Reliability fixes for local-model structured output (discovery pipeline)
- **Date:** 2026-08-27
- **Decision:** Four fixes were required to get the Research Discovery Service running reliably end-to-end against `qwen3.5:9b`, all in `shared/utilities/llm_provider.py` and `services/research-discovery/discovery/`:
  1. **`think=False` on all three LLM calls** (query generation, full-text mining, gap/novelty analysis). The model runs a visible "thinking" reasoning mode by default, and reasoning tokens count against the same output budget as the actual JSON answer. Thinking unpredictably consumed the entire token budget before any schema JSON was produced — first on query generation (1000-token budget, empty result), then on full-text mining (12000-token budget, empty result, handled gracefully as best-effort), then on the main gap analysis (32000-token budget, empty result — NOT best-effort, aborted the run). Confirmed via direct Ollama API testing that `think:false` produces the same correct JSON in a fraction of the time and cost.
  2. **Explicit, tiered `num_ctx`** (`_context_window_for()` in `llm_provider.py`). Ollama's server-side default context window is far smaller than this model's 256K support and silently truncates generation once prompt+output exceed it — regardless of `num_predict`/`max_tokens`. A single large fixed context (tried at 24576) fixed the truncation but caused a different problem: on an 8GB GPU, a bigger context reserves proportionally more VRAM for KV cache, and this pushed inference into partial CPU offload (`31/34 layers to GPU`) even for small calls, making everything much slower. The fix scales `num_ctx` to each call's actual need (`_context_window_for`, tiered at 4096/8192/16384/24576/32768) so cheap calls stay cheap and only the calls that need headroom pay for it.
  3. **Trimmed `REPORT_SCHEMA` verbosity and reduced `max_tokens`** in `analysis.py` (themes 3-6→2-4, gaps 4-8→2-4; mining 12000→6000, gap analysis 32000→8000). A schema demanding 4-8 well-evidenced gaps is disproportionate for a 6-9 paper MVP corpus, and was driving unnecessarily long generations on this hardware.
  4. **`MAX_CANDIDATES_FOR_ANALYSIS = 5` cap** in `pipeline.py`. The gap-analysis schema requires one full JSON entry per author-flagged candidate with no cap of its own, so an uncapped mining result (observed: 10 candidates) scaled the final synthesis call's output size directly. Mining already orders candidates most-to-least substantive, so capping keeps the strongest ones.
  - A fifth, trivial bug (not a design decision, just a typo) was also fixed: `analyze_gaps()` read `comp.input_tokens`/`comp.output_tokens`, but `llm_provider.Completion` names those fields `prompt_tokens`/`completion_tokens`. This crashed the pipeline on the very last line, *after* a fully successful generation — first found when a run reached `n_tokens=8235, truncated=0` (proof the earlier fixes worked) and then crashed on this attribute access.
- **Reason:** Verified via multiple full end-to-end runs against the live model; see TILL_NOW.md for the successful run's stats.
- **Alternatives considered:** For (2), raising `max_tokens`/context indefinitely instead of tiering — rejected, this is what caused the CPU-offload slowdown in the first place. For (3)/(4), leaving the schema as-is and just waiting longer — rejected as impractical; a production run needs to complete in reasonable time on this hardware.
- **Impact:** `services/research-discovery/service.py::run_discovery()` now completes reliably end-to-end. This hardware (RTX 4060 8GB) is inherently slow for larger-context calls on a 9B model — later services should budget for this (keep schemas as compact as the task allows, cap any unbounded list before it reaches a synthesis prompt, and prefer `think=False` unless a specific step needs visible reasoning with a tested, generous token budget).

## D-007 — Research Discovery Service adaptation approach
- **Date:** 2026-08-26
- **Decision:** The Research Discovery Service's core pipeline (query generation → multi-source search → dedupe → rank → full-text mining → gap/novelty analysis) is retained as an async-generator pipeline emitting structured progress events — this already matches the project's required progress-event architecture. Adapted:
  - Swapped the cloud-provider LLM layer for `shared/utilities/llm_provider.py` (local Ollama only, no cloud fallback).
  - Removed personal-library integrations (a reference-manager sync feature and a citation-context enrichment feature) — out of scope for the MVP, added complexity/failure surface, and required data this system doesn't have.
  - Removed the bundled web frontend and HTTP server layer — this becomes an in-process importable service (`services/research-discovery/service.py`) called directly by the orchestrator, not a standalone web app.
  - Extended the gap-analysis output schema with explicit `novelty_analysis` (summary, supporting gaps, confidence, caveats) and `confidence_notes` fields, and extended query generation to also produce a `research_interpretation` field — both required by the project's output contract but not present in the original schema.
- **Reason:** Reuse-first per project rules; the four literature sources kept (Semantic Scholar, OpenAlex, PubMed, arXiv) all work with no API key, satisfying the "local AI + no external key" requirement for this stage.
- **Alternatives considered:** Running it as a separate HTTP microservice — rejected for MVP simplicity; can be revisited if a future web frontend needs direct access to this stage in isolation.
- **Impact:** `services/research-discovery/service.py::run_discovery()` is the stable entry point Service 2 and the orchestrator depend on; output conforms to `shared/contracts/discovery_contract.py::DiscoveryResult`.

## D-006 — GitHub repository setup deferred pending CLI auth
- **Date:** 2026-08-26
- **Decision:** GitHub CLI (`gh`) is now installed (v2.98.0) but not authenticated on this machine — `gh auth login` requires an interactive browser/token step only the user can complete. Repository creation and collaborator invite (Sadiq8064) will be attempted immediately once auth succeeds; not retried indefinitely.
- **Reason:** Per spec — don't assume GitHub auth, don't get stuck retrying.
- **Alternatives considered:** None — this is a hard environment constraint.
- **Impact:** Local git history is being built regardless; push happens once remote is available. User action needed: run `gh auth login` in a terminal and follow the prompts.
