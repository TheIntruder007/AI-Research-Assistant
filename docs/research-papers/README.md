# 📚 Research Papers — Real ResearchGenie Output

Every research paper here is **real, unedited output** from an actual pipeline run made during this project's development and reliability testing — none of it is fabricated or staged. Each folder contains the full artifact set: `draft.md`, `paper.tex`, `paper.pdf`, the quality report, the citation validation report, the reference list, and the original request/metadata.

These are the *same* real runs referenced throughout `DECISIONS.md` and `analytics_and_results.md` — several were produced specifically to stress-test the pipeline's reliability across repeated runs of the same topic, which is why some topics appear multiple times with different scores. That repetition is itself part of the honest record: it shows the pipeline's real output evolving as reliability fixes were made, not a cherry-picked single result.

## 📖 Index

| Topic | Run | Quality Score | PDF |
|---|---|---|---|
| Intermittent fasting & cognitive performance | `73f8ad88` | 3.75 / 5.0 | [paper.pdf](what-are-the-effects-of-intermittent-fasting-on-cognitive-pe/73f8ad88/paper.pdf) |
| Intermittent fasting & cognitive performance | `75dd0de0` | 3.60 / 5.0 | [paper.pdf](what-are-the-effects-of-intermittent-fasting-on-cognitive-pe/75dd0de0/paper.pdf) |
| Intermittent fasting & cognitive performance | `a8e525ae` | 4.25 / 5.0 | [paper.pdf](what-are-the-effects-of-intermittent-fasting-on-cognitive-pe/a8e525ae/paper.pdf) |
| Intermittent fasting & cognitive performance | `afbbc837` | 3.50 / 5.0 | [paper.pdf](what-are-the-effects-of-intermittent-fasting-on-cognitive-pe/afbbc837/paper.pdf) |
| Intermittent fasting & cognitive performance | `c25e8dd4` | 4.25 / 5.0 | [paper.pdf](what-are-the-effects-of-intermittent-fasting-on-cognitive-pe/c25e8dd4/paper.pdf) |
| Intermittent fasting & cognitive performance | `e4f1f200` | 3.50 / 5.0 | [paper.pdf](what-are-the-effects-of-intermittent-fasting-on-cognitive-pe/e4f1f200/paper.pdf) |
| Intermittent fasting & cognitive performance | `eb894ebf` | 4.10 / 5.0 | [paper.pdf](what-are-the-effects-of-intermittent-fasting-on-cognitive-pe/eb894ebf/paper.pdf) |
| Intermittent fasting & cognitive performance | `ef142146` | 3.65 / 5.0 | [paper.pdf](what-are-the-effects-of-intermittent-fasting-on-cognitive-pe/ef142146/paper.pdf) |
| Remote work & employee productivity/well-being | `274a0da3` | 3.60 / 5.0 | [paper.pdf](what-is-the-impact-of-remote-work-on-employee-productivity-a/274a0da3/paper.pdf) |
| Remote work & employee productivity/well-being | `5d362353` | 4.25 / 5.0 | [paper.pdf](what-is-the-impact-of-remote-work-on-employee-productivity-a/5d362353/paper.pdf) |
| Urban green space & residents' mental health | `0687fc86` | 4.25 / 5.0 | [paper.pdf](how-does-urban-green-space-access-affect-residents-mental-he/0687fc86/paper.pdf) |

**Best starting point if you just want to see one:** [`5d362353`](what-is-the-impact-of-remote-work-on-employee-productivity-a/5d362353/paper.pdf) or [`0687fc86`](how-does-urban-green-space-access-affect-residents-mental-he/0687fc86/paper.pdf) — both are among the highest-scoring, fully complete (`draft_status: "complete"`) runs.

## ⚠️ Honest notes

- These PDFs were compiled with [`tectonic`](https://tectonic-typesetting.github.io/), a lightweight LaTeX engine, using the deterministic `.tex` export the pipeline generates (`shared/utilities/latex_export.py`) — no LLM involvement in the conversion itself.
- A few of the earlier runs (from before LaTeX export existed in the pipeline) had their `.tex`/`.pdf` generated retroactively from their already-saved `draft.md`, using the exact same converter the live pipeline uses — not hand-edited.
- Quality scores below 5.0 reflect real, deterministic findings from the Quality Assurance service (missing citations, claims not fully matched to their source) — not display bugs. See each run's `quality_report.md` for the specific findings behind its score.
- `docs/sample-output/` (a single earlier example, run `75dd0de0`) still exists separately and is unchanged — this folder is the complete set, not a replacement.
