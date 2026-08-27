# Review 2 (~66%)

*Written retroactively — work had already progressed to Review 3 scope by the time this was written up, so this reconstructs the project's state as of the Service 3 milestone from `DECISIONS.md`/`TILL_NOW.md`.*

## 🎯 Project objective
Unchanged from Review 1: a local-first pipeline that takes one research request and, running entirely on a local model, produces an evidence-grounded academic paper draft — discovery, drafting, citation verification, and quality assurance — with every artifact preserved per run.

## 🏗️ Overall architecture
```
Terminal UI (not yet built)
   ↓
Orchestrator (not yet built)
   ↓
Research Discovery Service → Research Writing Service → Citation Verification Service → Quality Assurance Service (not yet built)
   ↓
Research Artifacts + Final PDF
```
Unchanged from Review 1 — `shared/contracts/` per-stage Pydantic contracts, `shared/utilities/llm_provider.py` as the single local-model abstraction, one independently testable service per stage, each an async generator emitting structured progress events.

## 📚 Internal services — status at this milestone
- 🔍 **Research Discovery Service** — done, unchanged since Review 1.
- 📝 **Research Writing Service** — **built and tested.** Takes a `DiscoveryResult`, builds an outline plus one evidence file per selected paper, runs an outline-driven writing pipeline against the local model, and produces a `WritingResult` (draft Markdown, citation mapping, reference candidates). A real structural bug was found via a full-corpus timing run: giving each Discovery-identified research gap its own literature-review subsection made the writing pipeline's own evidence-tagging step correctly exclude almost the entire corpus per subsection (each gap statement is narrow and paper-specific, not a shared theme multiple papers can speak to). Fixed by flattening the outline to Introduction / Literature Review / Limitations / Conclusion and rendering Discovery's gap/novelty analysis directly into the draft rather than routing it back through evidence-gated writing (`DECISIONS.md` D-010/D-011).
- 🔗 **Citation Verification Service** — **built and tested.** Extracts a DOI from each rendered reference-list entry and checks it against Crossref (primary) then OpenAlex (fallback), both free and keyless. Classifies every reference as verified / invalid / unverifiable — three distinct outcomes, never silently repaired or collapsed into a binary pass/fail (`DECISIONS.md` D-012).
- 🛡️ **Quality Assurance Service** — not yet started.

## 🔄 Pipeline status
```
User research request
   ↓
Research Discovery Service (done)
   ↓
Research Writing Service (done)
   ↓
Citation Verification Service (done)
   ↓
Quality Assurance Service (next)
   ↓
Final research draft + reference list
```

## 🟢 Work completed since Review 1
- Research Writing Service built, including its own local-model adapter, outline/evidence-file generation, and the outline-structure fix above.
- Citation Verification Service built, using a keyless Crossref-then-OpenAlex check in place of a paid-API-dependent design.
- Both services' input/output contracts added to `shared/contracts/`.
- `_context_window_for()` in the shared LLM provider extended to size context off actual prompt length, not just output length — needed once per-section writing prompts grew large.
- Discovery's paper contract extended to carry the raw abstract text through (previously only a boolean "has abstract" flag), since the writing service's evidence files need the real text.

## 🧪 Tests performed
- Unit tests for outline/evidence-file construction (Research Writing) and DOI extraction plus verified/invalid/unverifiable/missing-reference classification (Citation Verification), the latter using a mocked HTTP transport — no network required.
- Live integration test for Research Writing against the real local model with a minimal two-paper/four-section case, checking for real cited, evidence-grounded output (skips cleanly if the local model isn't reachable).
- Live integration test for Citation Verification against real Crossref/OpenAlex with one real DOI, one fabricated DOI, and one DOI-less reference — confirming all three outcome branches.
- Two full end-to-end timing runs chaining Discovery → Writing → Verification manually, used to find and confirm the outline-structure fix above.

## 📦 Current outputs
- A real cited, evidence-grounded draft (Introduction / Literature Review / Limitations / Conclusion) with an IEEE-style numbered reference list, generated end-to-end from a research question through Discovery and Writing.
- Each reference in that list independently classified as verified, invalid, or unverifiable against a live scholarly API.

## 🚧 Current limitations
- Leaf-section writing reliability: on this hardware, typically only 2 of 4 leaf sections succeed per run, usually because the small local model occasionally double-tags a piece of evidence to both a tag and its own ancestor tag — a validation rule correctly rejects this rather than silently accepting bad tagging. Mitigated with capped retries, not eliminated; surfaced honestly via `WritingResult.draft_metadata.warnings`/`errors` rather than hidden.
- Citation Verification only checks the reference list, not positional in-text citation markers against the draft body — a deliberate scope decision, not an oversight (documented as a future enhancement).
- One full-corpus Discovery run selected an unrelated paper (an asthma-management guideline) for an intermittent-fasting/cognition query — not yet investigated.
- No Quality Assurance stage yet, so nothing independently audits the draft/citations together.
- No orchestrator, terminal app, or backend API yet — each service is still only callable directly as a Python library.

## ➡️ Next work
- Study and build the Quality Assurance Service (Service 4): an independent audit taking Discovery + Writing + Verification output together, checking for uncited high-risk claims and cited claims that don't actually support their citation, plus required-section presence — a final trustworthy gate before the pipeline is chained end-to-end through an orchestrator.
- Once all four services exist, build the orchestrator, terminal app, and backend API.
