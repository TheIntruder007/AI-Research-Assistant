# AI Research Assistant

A local-first AI research pipeline that turns a research request into an evidence-grounded academic paper draft — literature discovery, gap/novelty analysis, evidence-grounded drafting, citation verification, and independent quality assurance — running entirely on local AI (Ollama).

## What it does

1. Collects a research request (topic, target venue/format, deadline, paper count).
2. Runs the request through four internal services:
   - **Research Discovery Service** — literature search, ranking, gap & novelty analysis.
   - **Research Writing Service** — evidence-grounded outline and draft generation.
   - **Citation Verification Service** — source, DOI, and reference validation.
   - **Quality Assurance Service** — independent evidence and consistency audit.
3. Produces a final research draft in Markdown, LaTeX, and PDF, with a BibTeX reference file.
4. Saves every artifact (queries, evidence, drafts, validation reports) to a per-run output folder.

## Status

See [TILL_NOW.md](TILL_NOW.md) for current progress and [DECISIONS.md](DECISIONS.md) for technical decisions.

## Local AI

All reasoning and generation runs on a local [Ollama](https://ollama.com) model — no data leaves the machine.

## Usage

Once installed, run:

```
researchgenie
```

from any terminal to start the interactive research wizard.
