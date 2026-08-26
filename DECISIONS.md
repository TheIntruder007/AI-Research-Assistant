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
- **Verification result:** _pending — recorded once `ollama run qwen3.5:9b` responds successfully (see TILL_NOW.md)._

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

## D-006 — GitHub repository setup deferred pending CLI auth
- **Date:** 2026-08-26
- **Decision:** GitHub CLI (`gh`) is now installed (v2.98.0) but not authenticated on this machine — `gh auth login` requires an interactive browser/token step only the user can complete. Repository creation and collaborator invite (Sadiq8064) will be attempted immediately once auth succeeds; not retried indefinitely.
- **Reason:** Per spec — don't assume GitHub auth, don't get stuck retrying.
- **Alternatives considered:** None — this is a hard environment constraint.
- **Impact:** Local git history is being built regardless; push happens once remote is available. User action needed: run `gh auth login` in a terminal and follow the prompts.
