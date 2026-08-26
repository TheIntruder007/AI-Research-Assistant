# Review 1 (~33%)

## 🎯 Project objective
Build a local-first AI research assistant that takes one research request and, running entirely on a local model, produces an evidence-grounded academic paper draft — literature discovery, gap and novelty analysis, evidence-grounded drafting, citation verification, and independent quality assurance — with every artifact preserved per research run.

## ❗ Problem being solved
Early-stage academic research (finding relevant literature, spotting genuine gaps, drafting an evidence-grounded outline, checking citations) is slow, manual, and spread across many disconnected tools. This project consolidates that workflow into a single local pipeline that a researcher can run against a topic and get a structured, auditable starting point — never presented as a finished or verified paper, always as AI-assisted synthesis for human review.

## 🏗️ Overall architecture
```
Terminal UI (researchgenie — not yet built)
   ↓
Orchestrator (event bus + pipeline runner — not yet built)
   ↓
Research Discovery Service → Research Writing Service → Citation Verification Service → Quality Assurance Service
   ↓
Research Artifacts + Final PDF
```
- `shared/contracts/` — Pydantic input/output contracts between stages, so each service can be built and tested independently.
- `shared/utilities/llm_provider.py` — a single local-model abstraction every service calls through, so the underlying model is replaceable without touching service code.
- `services/<name>/` — one independently testable service per pipeline stage.
- Each service is an async generator that yields structured progress events, matching the project's required progress-streaming architecture from day one.

## 🤖 Local AI model decision
- **Selected:** `qwen3.5:9b` (6.6GB), run locally via Ollama.
- **Why:** Verified against actual hardware — Intel i7-13700HX (16 cores/24 threads), 16GB system RAM, NVIDIA RTX 4060 Laptop GPU with 8GB VRAM (measured with `nvidia-smi`, not assumed). `qwen3.5:9b` fits the 8GB VRAM budget; the next tier up (27B, ~17GB) does not, and would force heavy CPU offload making development impractically slow.
- **Verification:** Confirmed via direct prompts and a full pipeline run (see below).
- Full record, including the model-selection reasoning and every reliability fix discovered while integrating it, is in `DECISIONS.md`.

## 📚 Internal services
- 🔍 **Research Discovery Service** — interprets the research question, generates search queries, searches multiple scholarly databases in parallel, deduplicates and ranks results, retrieves available full text, extracts limitations and future-research directions, and produces a structured gap and novelty analysis. **Built and verified.**
- 📝 **Research Writing Service** — will organize selected literature, build an evidence structure, and generate an evidence-grounded outline and draft with citation mapping. Not yet started.
- 🔗 **Citation Verification Service** — will verify source existence, DOI/metadata, and citation correctness, flagging rather than silently repairing problems. Not yet started.
- 🛡️ **Quality Assurance Service** — will perform an independent evidence and consistency audit with a full audit trail. Not yet started.

## 🔄 Planned pipeline
```
User research request
   ↓
Research Discovery Service (done)
   ↓
Research Writing Service (next)
   ↓
Citation Verification Service
   ↓
Quality Assurance Service
   ↓
Final research draft (Markdown + LaTeX + PDF) + BibTeX references
```

## 🟢 Work actually completed
- Project workspace, git repository, and core documentation (`README.md`, `PROJECT_NOTES.md`, `DECISIONS.md`, `TILL_NOW.md`) set up.
- Local AI installed, hardware-matched, and verified working.
- **Research Discovery Service fully built and verified end-to-end**, including:
  - Query generation from a natural-language research question.
  - Parallel search across four scholarly databases, none requiring an API key.
  - Deduplication (by DOI and normalized title) and relevance ranking.
  - Open-access full-text retrieval and extraction of Discussion/Limitations/Future-research sections.
  - Author-flagged future-research candidate extraction, each verified against a fresh literature search.
  - A structured gap and novelty analysis report, distinguishing corpus-supported claims from hedged novelty assessments and honest confidence/uncertainty notes.
- A stable `DiscoveryResult` contract that Service 2 will consume directly.
- Four reliability fixes for running structured-output generation reliably on local, VRAM-constrained hardware (documented in `DECISIONS.md` D-009) — these lessons carry forward to every remaining service.

## 🧪 Tests performed
- Unit tests: request/result contract validation and round-tripping, paper deduplication (by DOI, by normalized title, and correctly *not* merging distinct papers with short generic titles), relevance ranking, and the discovery-result adapter's field mapping.
- Integration test: a full pipeline run against the live local model with a small controlled research question, asserting a schema-valid, non-empty result. Skips cleanly if Ollama isn't reachable, since it depends on real network calls and a real local model.
- Manual verification: a full live run against the research question "What are the effects of intermittent fasting on cognitive performance?" completed successfully end-to-end.

## 📦 Current outputs
From the verification run:
- 120 papers found across the search stage → 118 unique after deduplication → 6 selected for the analysis corpus.
- 5 author-flagged future-research candidates extracted and independently checked against the literature.
- 11 research gaps identified, each with supporting evidence and impact rating.
- A novelty assessment at "medium" confidence, with stated caveats.
- All output validated against the `DiscoveryResult` Pydantic contract.

## 🚧 Current limitations
- Only Service 1 of 4 is built; the pipeline does not yet produce a full draft or final output.
- This hardware (8GB VRAM) is inherently slow for the larger-context calls a synthesis step needs — a full discovery run's final analysis step can take several minutes to tens of minutes depending on system load. Schemas and output sizes need to stay deliberately compact for the remaining services.
- Two of the four literature sources intermittently return rate-limit-style errors in testing; the pipeline degrades gracefully (continues without that source) rather than failing, but this reduces corpus diversity on some runs.
- No terminal application yet — the pipeline is currently only callable as a Python library.
- No GitHub remote yet (local git history only, by the user's choice for now).

## ➡️ Next work
- Study and build the Research Writing Service (Service 2), accepting `DiscoveryResult` as input and producing an evidence-grounded outline and draft with citation mapping.
- Define its input/output contract in `shared/contracts/`.
- Apply the reliability lessons from Service 1 (local-model-aware schema sizing, capped unbounded lists, `think=False` by default) from the start.
- Begin work toward the main orchestration API and the terminal application once at least two services are integrated.
