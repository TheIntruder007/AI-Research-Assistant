# 📄 Sample Output

A **real, unedited** output from an actual `researchgenie` run — not a fabricated demo. This is the exact run shown in the terminal-output capture in [`docs/phase-3/PHASE_3_NOTES.md`](../phase-3/PHASE_3_NOTES.md).

## 🔬 Run details

- **Question:** "What are the effects of intermittent fasting on cognitive performance?"
- **Papers:** 6
- **Format:** IEEE
- **AI engine:** Ollama · `qwen3.5:9b` (fully local, no cloud call)
- **Overall quality score:** 3.6 / 5.0
- **Run time:** ~4.9 min discovery + ~8.8 min writing + ~2.5s verification

## 📁 What's here

| File | What it is |
|---|---|
| `final/draft.md` | The generated research draft (Markdown) |
| `final/paper.tex` | Deterministically generated LaTeX source of the same draft |
| `final/quality_report.md` | The independent, deterministic quality audit (Service 4) |
| `final/validation_report.md` | Citation verification results (Service 3) |
| `final/references.md` | The verified reference list |
| `00_request.json` | The exact request that produced this run |
| `metadata.json` | Run ID, timings, overall score |

## ⚠️ Honest notes on this specific run

This is real output, kept exactly as generated — including its imperfections, not cherry-picked:

- The **Introduction** section failed its own evidence-context check and was replaced with an honest placeholder rather than unsupported prose — a real, currently-documented Research Writing limitation (see `DECISIONS.md` D-019–D-021).
- The outline's own **Conclusion** section (a regular content section) also failed and shows a placeholder, immediately followed by a *separately generated* conclusion summary that did succeed — the pipeline generates the document's overall conclusion independently from the outline's own "Conclusion" heading, which is why both appear back-to-back here. This is a known architectural quirk, not corruption.
- The Quality Assurance report's **citation integrity score (2.0/5.0)** reflects real missing-citation findings the deterministic auditor caught in this specific run — the low score is the auditor doing its job, not a display bug.

Every other pipeline run this project has produced is intentionally excluded from version control (see `.gitignore`'s `outputs/*` rule) since generated research runs are data, not source code. This one sample is committed deliberately, so the actual product output is visible without having to run the pipeline yourself.
