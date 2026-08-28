# ResearchGenie

A local-first AI research assistant. Give it a research question — it discovers relevant literature, identifies genuine research gaps, drafts an evidence-grounded paper, verifies every citation against real scholarly databases, and independently audits its own quality. Everything runs on your own machine by default.

## 📦 Install

```
pip install researchgenie
```

## 🚀 Run

```
researchgenie
```

That's it. The first run walks you through a one-time setup; every run after that goes straight to research.

## ✨ What happens the first time

1. **Choose your AI engine**
   - 🟢 **Ollama** *(recommended)* — runs entirely on your machine, your research data never leaves your device, no API key needed.
   - 🔵 **Gemini** — a cloud alternative for machines without the hardware to comfortably run a local model. Requires your own [Gemini API key](https://aistudio.google.com/apikey).
2. If you chose Ollama, ResearchGenie checks whether it's installed and the model is downloaded — and does both automatically where it can be done safely on your operating system.
3. Your choice is saved locally. You won't be asked again.

Run `researchgenie config` any time to change your setup.

## 🔬 Doing research

Answer a few short questions — your research topic, how many papers to include (6–9), and your preferred format (IEEE or Springer) — confirm the summary, and watch live progress as each stage of the pipeline runs:

- 🔍 **Research Discovery** — searches multiple scholarly databases, filters for genuine topical relevance, and selects the strongest papers.
- ✍️ **Research Writing** — builds an evidence-grounded outline and draft, citing only the literature it actually found.
- 🔗 **Citation Verification** — checks every reference against real scholarly databases (Crossref, OpenAlex).
- 🛡️ **Quality Assessment** — an independent, fully deterministic audit of citation integrity and claim-to-evidence alignment.

## 📁 What you get

Every run saves a complete, timestamped project folder containing:

- The research draft (Markdown)
- LaTeX source, and a compiled PDF when a LaTeX toolchain is available on your machine
- The reference list
- The quality and citation-validation reports
- Full run metadata

ResearchGenie always tells you the exact folder path when a run finishes.

## 🔒 Privacy

With the default Ollama engine, your research question, retrieved literature, and generated draft never leave your machine — there is no cloud AI call anywhere in the pipeline. Choosing the optional Gemini engine sends prompts to Google's API, same as using any cloud AI service; your API key is stored locally and never logged, committed, or embedded in generated output.

## 📊 Project status

See [TILL_NOW.md](TILL_NOW.md) for current progress and [DECISIONS.md](DECISIONS.md) for technical decisions and their reasoning. [analytics_and_results.md](analytics_and_results.md) documents the reliability work behind the pipeline, with real measured results.

## 🛠️ For developers

This repository *is* the ResearchGenie source — `pip install researchgenie` installs it directly from here. See `DECISIONS.md` for the internal architecture (a four-service pipeline behind one orchestrator) and `pyproject.toml` for the packaging setup.
