# Project Notes

## 📑 Index
- [🎯 Project Overview](#-project-overview)
- [❗ Problem Statement](#-problem-statement)
- [💡 Proposed Solution](#-proposed-solution)
- [🔄 Complete Pipeline](#-complete-pipeline)
- [🧩 Internal Services](#-internal-services)
- [🤖 AI Model](#-ai-model)
- [🏗️ Architecture](#-architecture)
- [📥 Inputs](#-inputs)
- [📤 Outputs](#-outputs)
- [📁 Artifact Storage](#-artifact-storage)
- [🧪 Testing Strategy](#-testing-strategy)
- [📊 Review Milestones](#-review-milestones)
- [🚧 Limitations](#-limitations)
- [➡️ Next Steps](#-next-steps)

## 🎯 Project Overview
- A local-first AI research assistant.
- Takes one research request and produces an evidence-grounded draft research paper.
- Runs entirely on a local Ollama model — no cloud AI dependency for reasoning/generation.

## ❗ Problem Statement
- Early-stage academic research (literature discovery, gap analysis, drafting, citation checking) is slow and fragmented across many manual tools.
- Researchers need a single local pipeline that goes from a research idea to a verified, evidence-grounded draft.

## 💡 Proposed Solution
- A four-stage internal pipeline, each stage with a defined input/output contract.
- A terminal application (`researchgenie`) as the current interface.
- Every stage persists artifacts so a run can be inspected, resumed, and audited.

## 🔄 Complete Pipeline
```
User Research Request
   ↓
Research Discovery Service (search, rank, gap & novelty analysis)
   ↓
Research Writing Service (outline + evidence-grounded draft)
   ↓
Citation Verification Service (source/DOI/reference validation)
   ↓
Quality Assurance Service (independent audit)
   ↓
Final Research Paper Draft (MD + LaTeX + PDF + BibTeX)
```

## 🧩 Internal Services
- 🔍 **Research Discovery Service** — query generation, scholarly search, dedup, ranking, evidence/limitation/future-work extraction, gap & novelty analysis.
- 📝 **Research Writing Service** — evidence structuring, outline, evidence-grounded draft generation, citation mapping.
- 🔗 **Citation Verification Service** — source existence, DOI, URL, and citation correctness checks; flags issues rather than inventing fixes.
- 🛡️ **Quality Assurance Service** — independent evidence review, citation audit, consistency checks, audit trail, final quality report.

## 🤖 AI Model
- See [DECISIONS.md](DECISIONS.md) for the selection record.
- Accessed through an internal `LLMProvider` abstraction (Ollama is the initial/default provider).

## 🏗️ Architecture
```
Terminal UI (researchgenie)
   ↓
Orchestrator (event bus + pipeline runner)
   ↓
Service 1 → Service 2 → Service 3 → Service 4
   ↓
Research Artifacts + Final PDF
```
- Shared contracts/schemas live in `shared/`.
- Each service is independently testable in isolation before integration.
- Backend is API/event-driven so a future web frontend can consume the same orchestrator.

## 📥 Inputs
- Research topic/question/problem statement.
- Target publication type (conference/journal/other).
- Target venue.
- Target format (IEEE/Springer/ACM/APA/other, extensible).
- Deadline (optional timezone).
- Number of papers (6–9 for MVP).
- Optional: domain, year range, preferred databases, language, max draft length, keywords, excluded topics.

## 📤 Outputs
- Per-run folder under `outputs/` with structured artifacts at every stage.
- Final draft in Markdown, LaTeX, and compiled PDF.
- Final reference list in BibTeX.
- Validation and quality-assurance reports.

## 📁 Artifact Storage
- One folder per research run: `outputs/<ai-generated-topic-slug>_<run-id>/`.
- Numbered subfolders per stage (request, discovery, gap analysis, evidence, outline, draft, verification, QA, final, metadata).

## 🧪 Testing Strategy
- Unit tests per service (schemas, adapters, dedup logic, citation validation, file/LaTeX generation).
- Integration test across the full pipeline with a small controlled request.
- Regression tests re-run whenever a service changes.

## 📊 Review Milestones
- Review 1 (~33%) — workspace, local AI, Service 1 working in isolation.
- Review 2 (~66%) — Services 1–3 integrated end-to-end.
- Review 3 (~100%) — full pipeline, terminal app, tests, docs complete.

## 🚧 Limitations
- MVP paper-count range fixed at 6–9.
- LaTeX templates are generic where an official venue template can't be legally auto-retrieved.
- External APIs (paper search, DOI lookup) may require user-provided keys; see DECISIONS.md when this occurs.

## ➡️ Next Steps
- See [TILL_NOW.md](TILL_NOW.md) for the current task and status.
