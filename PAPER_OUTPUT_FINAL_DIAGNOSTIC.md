# 📄 Final Paper Output Diagnostic

**Date:** 2026-08-29
**Branch inspected:** `fix/paper-length-completeness-ieee-springer` (not yet merged to `master`)
**Rule followed throughout:** no production code, prompts, model parameters, or thresholds were changed during this investigation. All runs use the real, currently-configured provider (Ollama, `qwen3.5:9b`) and the pipeline exactly as it exists on disk.

## 📖 Index
1. Purpose
2. Current Implementation (Length / Structure / Completeness / IEEE / Springer)
3. Real End-to-End Test Matrix
4. Results Table
5. Section-by-Section Analysis
6. Target vs Actual Length
7. Manual Paper Inspection
8. Completeness Consistency Check ("fake complete" test)
9. IEEE Validation
10. Springer Validation
11. Performance Results
12. Test Suite Results
13. Bugs or Weaknesses Found
14. Before vs Current Results
15. Remaining Limitations
16. Final Verdict

---

## 🎯 1. Purpose

Determine — with real evidence, not unit tests alone — whether ResearchGenie can now reliably generate complete, appropriately-sized IEEE and Springer research papers. **This report makes no code changes; it only inspects and measures the current implementation.**

---

## 🏗️ 2. Current Implementation

### 📏 Length Control

| Question | Answer (verified by reading the current code) |
|---|---|
| Where does the user select length? | `researchgenie/cli.py::_collect_request()` (rich CLI) and `terminal_app/cli.py::collect_request_interactively()` (older CLI) — both prompt "Short / Standard / Detailed". |
| What length options exist? | `word_budget.py::LENGTH_PRESETS = {"short": 2200, "standard": 4000, "detailed": 6000}` words. Default preset: `"standard"`. |
| How is the selection represented internally? | The chosen preset's word count is passed as `ResearchRequest.max_draft_length` (an existing field, reused rather than renamed) → `WritingRequest.target_words` (`orchestrator/pipeline.py:161`) → `ReviewInput.target_words` (`service.py`) → `state["target_words"]` in the writing graph. |
| How is the word target calculated? | It is **not** calculated — it is the user's raw preset value, unmodified, used as the "total target words for the whole paper." |
| How is the total budget divided between sections? | `word_budget.py::allocate_section_budgets(total)` applies fixed weights: `Introduction 0.12, Background 0.13, Literature Review 0.32, Discussion 0.22, Limitations 0.11, Conclusion 0.10` (sums to 1.0). Each section gets `WordBudget(target, minimum=target×0.55, maximum=target×1.75)`. |
| Minimum section length | `target × MIN_FRACTION (0.55)`, floored at `_MIN_SECTION_WORDS = 40`. |
| Maximum section length | `target × MAX_FRACTION (1.75)`. |
| What happens if the model generates too little? | `section_auditor.py::audit_section()` sets `below_minimum_length=True` (a real audit failure) when substantive content is under `min_words`. This drives the **existing** 1-round bounded revision loop with a targeted "expand using available evidence" instruction. If, after that one revision, the ONLY remaining issue is still length, `section_writer.py::write_section_with_revisions()` treats it as genuine evidence scarcity: the section is **kept** (not blanked) and flagged `evidence_limited=True`, `resolved=True` even though the raw last audit's `passed` is `False`. If other correctness issues remain too, the section is a real failure (placeholder text, `resolved=False`). |
| What happens if evidence is insufficient? | `writing/modules/section_writer.py::write_section()`: if a section has zero `direct_points`/`ancestor_context`/`child_summaries` at all, it never calls the model — it emits a fixed placeholder ("*Insufficient evidence is available for this section.*") directly. This is recognized by `completeness.py` as `evidence_limited`, not broken. |

**Whole-paper length classification** (`word_budget.py::classify_length`): `short` if `actual < target × 0.7`; `over_target` if `actual > target × 1.4`; else `on_target`. **This IS an explicit tolerance the implementation defines** — not invented for this report.

### 🧩 Paper Structure

Current outline, verified by reading `services/research-writing/writing_prep.py::build_outline()` directly (unchanged during this investigation):

```
# {research question}
## Background
## Literature Review
## Discussion
## Limitations
```

| Question | Answer |
|---|---|
| All planned sections | Introduction (bookend), Background, Literature Review, Discussion, Limitations, Conclusion (bookend), plus a deterministic "Research Gap" + "Proposed Novelty" block spliced in by `render_research_gap_section()`, and a "References" section. |
| LLM-generated | Background, Literature Review, Discussion, Limitations (via the outline/tag-tree writing graph); Introduction and Conclusion (via separate `write_introduction()`/`write_conclusion()` "bookend" calls in `review_writer.py`). |
| Deterministic (no LLM) | "Research Gap"/"Proposed Novelty" (rendered directly from Discovery's own synthesis) and "References" (built from verified citation metadata). |
| Optional sections | None are conditionally skipped — the 4 outline sections and 2 bookends are always attempted for every research question, regardless of question breadth or corpus size. This is a **deliberate, documented, fixed-not-adaptive** design (DECISIONS.md D-025) — Methodology/Results are never included because this pipeline only synthesizes existing literature and never produces original results, for any question. |
| Is Introduction generated more than once? | **No** — as of `writing_prep.py::build_outline()` (current state), the outline itself does NOT define its own `## Introduction` tag. The bookend `write_introduction()` call in `review_writer.py` is the single, sole generation path. Verified by reading `build_outline()`'s return value directly (no "Introduction" string present) and by `tests/services/test_writing_prep.py::test_build_outline_no_longer_has_its_own_introduction_or_conclusion_tags`. |
| Is Conclusion generated more than once? | **No**, same reasoning — single bookend path only. |
| Is duplicate content possible? | `completeness.py::assess_completeness()` explicitly checks for a heading appearing more than once (`duplicate_sections`) and none of the 4 real runs in this diagnostic produced one (see §4/§8). Architecturally prevented for Introduction/Conclusion specifically (only one call site each); still theoretically possible if a leaf section's own generated prose happened to repeat a heading-like line, which the current check would catch. |
| Can container tags produce empty sections? | This was a **real, previously-found bug** (fixed on this branch, not during this investigation — see `tag_semantics.py`): a tag classified `"container"` by the model with zero children used to render permanently blank. The current code forces such a node to `"content"` instead. `tests/services/test_tag_semantics_container_fix.py` (3 tests, passing) covers this. No container-tag-caused blank section occurred in any of this diagnostic's real runs. |

### 📝 Completeness Validation

`services/research-writing/completeness.py::assess_completeness()` is the **only** place `draft_status` is decided (wired in `service.py`). It parses the **actual rendered `draft_text`** (the same string that becomes `draft.md`/`paper.tex`/`paper.pdf`) by its `## ` headings — not the writing graph's internal `succeeded`/`failed_tag_ids` signal alone.

| Check | Detected? | How |
|---|---|---|
| Empty sections | ✅ | `block.strip()` is empty → `blank_sections` |
| Whitespace-only sections | ✅ | Same check — `.strip()` normalizes whitespace-only to empty |
| Failure placeholder text | ✅ | Matches a fixed list of known placeholder strings (`_FAILURE_PLACEHOLDERS`) emitted by the graph on unresolved sections/bookends |
| Missing Introduction | ✅ | `Introduction` is in `required_section_titles()`; absence → `missing_sections` |
| Missing Conclusion | ✅ | Same, for `Conclusion` |
| Duplicate sections | ✅ | A required title appearing more than once in heading order → `duplicate_sections` |
| Missing required body sections | ✅ | Every outline `## ` heading is required |
| Present but no meaningful prose | ✅ (via blank/placeholder checks) — **not** a prose-quality judgment. A section with real but very short text is NOT flagged by this module at all (word-count sufficiency is `word_budget`'s/`section_auditor`'s job, not `completeness.py`'s) — this is an intentional separation of concerns, verified by reading the code, not assumed. |

`draft_status` logic (`service.py`): `"failed"` if `completeness.status == "failed"` (every required section broken, or both bookends); `"partial"` if `completeness.status == "partial"` **or** `not result.succeeded` **or** `failed_sections > 0` (belt-and-braces — never trusts one signal alone); else `"complete"`.

### 🎓 IEEE Support

- **Selection**: CLI prompt "[1] IEEE [2] Springer" → `ResearchRequest.target_format = "IEEE"`.
- **Reaches the writer**: `WritingRequest.target_format` → `citation_style` property maps `"IEEE"` → `"ieee"` (numeric in-text citations, e.g. `[1]`).
- **Reaches LaTeX**: `orchestrator/pipeline.py` passes `request.target_format` into `latex_export.markdown_to_latex(..., target_format=request.target_format)`.
- **LaTeX class**: `\documentclass[conference]{IEEEtran}`. Real class, genuinely available in this environment's `tectonic` distribution (verified by direct compile, this report's runs, and prior work).

### 🎓 Springer Support

- **Selection/wiring**: identical mechanism, `target_format = "Springer"`.
- **Citation style**: maps to `"chicago-author-date"` (parenthetical author-year, e.g. `(Smith, 2020)`) — **not** numeric.
  - ⚠️ **Noted inconsistency (not fixed, per instructions)**: LNCS-published papers in practice commonly use numbered/Vancouver-style citations, not author-year. This implementation pairs the `llncs` document class with an author-year citation style. This is not necessarily wrong (LNCS technically supports either), but it is a real style choice worth the user knowing about — found by reading `writing_contract.py::_FORMAT_TO_CITATION_STYLE`, not assumed.
- **LaTeX class**: `\documentclass{llncs}`. **This is a substitution, and the code says so explicitly**: Springer's actual "official" class, `svjour3`, was confirmed NOT available in this environment's `tectonic` TeX distribution by direct compile test. `llncs` (Springer's real Lecture Notes in Computer Science class) is used instead. **This report does not call it "official Springer format" — it is a genuine, real, standard Springer class, but not the specific `svjour3` template.**

---

## 🧪 3. Real End-to-End Test Matrix

All 4 runs use the real orchestrator (`orchestrator.pipeline.run_pipeline`), the real Discovery/Writing/Verification/QA services, the real local Ollama provider (`qwen3.5:9b`), corpus size 6. No cherry-picking — every run's real result is recorded below regardless of outcome.

| # | Format | Length preset | Research question | Domain, vs. previously tested |
|---|---|---|---|---|
| 1 | IEEE | Standard (medium) | "What are the effects of artificial intelligence adoption on primary school teaching practices?" | New — education/AI-in-teaching |
| 2 | IEEE | Detailed (longer) | "How does microplastic pollution affect marine ecosystem biodiversity?" | New — environmental/marine science |
| 3 | Springer | Standard (medium) | "What is the relationship between sleep quality and workplace decision-making?" | New — sleep/occupational cognition |
| 4 | Springer | Detailed (longer) | "What is the impact of telemedicine adoption on patient health outcomes in rural areas?" (2 prior attempts on a different topic — "renewable energy policies... developing countries" — failed for real Discovery-stage reasons, see §4) | New — telemedicine/rural healthcare |

---

## 📊 4. Results Table

### Run 1 — IEEE, Standard

| Field | Value |
|---|---|
| Run ID | `87519d90b04e421da5c0faba3ed474d6` |
| Provider / Model | Ollama / `qwen3.5:9b` |
| Papers found → selected | 80 unique → 6 selected |
| Research gaps found | 5 |
| Target words | 4,000 |
| Actual words | 3,222 |
| % of target | **80.5%** |
| Length status (implementation's own classification) | `on_target` (0.7×–1.4× band) |
| `draft_status` | **`partial`** |
| Failed sections (graph-internal count) | 0 |
| Broken sections (rendered-text check) | **Conclusion** |
| Evidence-limited sections | none flagged at paper level (Literature Review was evidence-limited at the section level, see §5) |
| Duplicate sections | none |
| `.tex` generated | ✅ |
| PDF compiled | ✅ |
| **PDF pages (real, via `pypdf`)** | **5** |
| QA overall score | 3.0 / 5.0 (citation_integrity 2.0, claim_source_alignment 3.0, process_control 2.0, literature_coverage 5.0) |
| References verified / invalid / unverifiable | 3 / 0 / 2 |
| Discovery / Writing / Verification / QA time | 659.4s / 1071.7s / 1.6s / 0.0s |
| **Total time** | **1,733.4s (28m 53s)** — see §11 for a performance caveat (ran concurrently with the full test suite) |
| Output directory | `outputs/what-are-the-effects-of-artificial-intelligence-adoption-on-_87519d90b04e421da5c0faba3ed474d6` |

### Run 2 — IEEE, Detailed

| Field | Value |
|---|---|
| Run ID | `6ea5834d6dbf4276b2478bec733dda74` |
| Provider / Model | Ollama / `qwen3.5:9b` |
| Papers found → selected | 41 unique → 6 selected |
| Research gaps found | 5 |
| Target words | 6,000 |
| Actual words | 3,585 |
| % of target | **59.8%** |
| Length status (implementation's own classification) | 🔴 `short` (below the 0.7× floor) |
| `draft_status` | **`partial`** |
| Failed sections (graph-internal count) | **1** (Literature Review) |
| Broken sections (rendered-text check) | **Literature Review** |
| Evidence-limited sections | none flagged at paper level (Discussion was evidence-limited at the section level, see §5) |
| Duplicate sections (heading-level) | none |
| **Duplicate CONTENT across different sections (not detected by any current check)** | **Yes — see §13, major finding** |
| `.tex` generated | ✅ |
| PDF compiled | ✅ |
| **PDF pages (real, via `pypdf`)** | **5** |
| QA overall score | 3.0 / 5.0 (citation_integrity 2.0, claim_source_alignment 3.0, process_control 2.0, literature_coverage 5.0) |
| References verified / invalid / unverifiable | 6 / 0 / 0 |
| Discovery / Writing / Verification / QA time | 384.3s / 1021.1s / 2.3s / 0.0s |
| **Total time** | **1,408.4s (23m 28s)** |
| Output directory | `outputs/how-does-microplastic-pollution-affect-marine-ecosystem-biod_6ea5834d6dbf4276b2478bec733dda74` |

### Run 3 — Springer, Standard

| Field | Value |
|---|---|
| Run ID | `2b00d613c8534932bde76decf9399d7c` |
| Provider / Model | Ollama / `qwen3.5:9b` |
| Papers found → selected | 49 unique → 6 selected |
| Research gaps found | 5 |
| Target words | 4,000 |
| Actual words | 3,928 |
| % of target | **98.2%** |
| Length status | 🟢 `on_target` |
| `draft_status` | **`partial`** — **but see the critical finding below: every section, heading, and reference check is clean** |
| Failed sections | 0 |
| Broken sections | **none** |
| Evidence-limited sections | none |
| Duplicate sections | none |
| `.tex` generated | ✅ |
| PDF compiled | ✅ |
| **PDF pages** | **10** |
| QA overall score | 3.5 / 5.0 |
| References verified / invalid / unverifiable | 5 / 0 / 0 |
| Discovery / Writing / Verification / QA time | 516.1s / 877.8s / 2.9s / 0.0s |
| **Total time** | **1,397.6s (23m 18s)** |
| Output directory | `outputs/what-is-the-relationship-between-sleep-quality-and-workplace_2b00d613c8534932bde76decf9399d7c` |

### 🚨 CRITICAL FINDING — `draft_status: "complete"` is currently unreachable for ANY run

Run 3's own `full_review_audit.json` (read directly, not inferred):
```json
{
  "errors": [],
  "heading_errors": ["final heading sequence does not match the user outline"],
  "missing_sections": [],
  "missing_reference_paper_ids": [],
  "duplicate_references": [],
  "unresolved_placeholders": [],
  "passed": false
}
```
Every check is clean **except** `heading_errors` — and that single failure is enough to make `passed: false`, which makes `result.succeeded: False` (`graph.py:1040`), which makes `service.py`'s `draft_status` fall back to `"partial"` even though `completeness.py` independently reports **zero** broken/missing/duplicate sections for this run.

**Root cause, found by reading the code (not fixed, per instructions):** `review_auditor.py::audit_full_review()` builds its `expected_headings` list from `tree` — the outline's own tag tree, which (since the D-025 restructuring) contains only `[root title, Background, Literature Review, Discussion, Limitations]`. It compares this against `actual_headings`, extracted from the **real rendered markdown**, which now **also contains `## Introduction` and `## Conclusion`** — real headings added by `review_assembler.py` specifically so `completeness.py` could detect a blank bookend (a fix made earlier in this same overall pass, see DECISIONS.md D-026). **`audit_full_review()`'s own expected-heading list was never updated to account for those two new headings.** The comparison `actual_headings == expected_headings` is therefore now **structurally guaranteed to fail on every single run**, regardless of paper quality, topic, or model behavior — because the actual list will always have exactly 2 more entries (Introduction, Conclusion) than the expected list.

**This was verified identically in ALL 4 real runs completed for this report** — every single `full_review_audit.json` shows the exact same `heading_errors`, even in runs with other, genuine problems and in the one run (Run 4) with zero warnings of any other kind:
```
Run 1: {"errors": [], "heading_errors": ["final heading sequence does not match the user outline"], ..., "passed": false}
Run 2: {"errors": [], "heading_errors": ["final heading sequence does not match the user outline"], ..., "passed": false}
Run 3: {"errors": [], "heading_errors": ["final heading sequence does not match the user outline"], ..., "passed": false}
Run 4: {"errors": [], "heading_errors": ["final heading sequence does not match the user outline"], ..., "passed": false}
```
**4 for 4 — a 100% reproduction rate**, fully explained by reading the code (not model variance). `max_full_revision_rounds=0` (`FAST_REVIEW_CONFIG`), so this failure is never retried — it is permanent, on every run.

**Impact**: since `service.py`'s `draft_status` logic ORs in `not result.succeeded` as one of its three "downgrade to partial" conditions (a deliberate "belt-and-braces" design so it never trusts completeness.py alone), and `result.succeeded` is now unconditionally `False`, **`draft_status` can currently never be `"complete"` for any research question, any format, any length, regardless of how good the actual paper is.** Run 3 is direct proof: a paper with zero missing sections, zero blank sections, zero duplicate sections, zero broken references, and 98.2% of its target length still reports `"partial"`.

**This is the single most consequential finding of this diagnostic.**

### Run 4 — Springer, Detailed

**First attempt: FAILED (recorded honestly, not hidden, per instructions).**

| Field | Value |
|---|---|
| Research question | "How do renewable energy policies influence economic growth in developing countries?" |
| Error | `PipelineError: No papers found in any source. Try rephrasing the question or enabling more sources.` |
| Cause | All 3 attempted external search sources (Semantic Scholar, OpenAlex, arXiv) returned `HTTPStatusError` for this query — a Discovery-stage external-API reliability issue, not a writing/length/completeness/format issue. Consistent with this project's own documented "Semantic Scholar/OpenAlex intermittently fail with rate-limit-style errors" limitation. |
| Elapsed before failure | 102.6s |

**Second attempt (identical question, retried once): ALSO FAILED — recorded honestly.**

| Field | Value |
|---|---|
| Error | `PipelineError: No papers found in any source. Try rephrasing the question or enabling more sources.` |
| Cause | 2 sources returned a result this time (vs. 0 in the first attempt) but OpenAlex and arXiv still failed with `HTTPStatusError`, and the overall corpus still ended up empty. |
| Elapsed before failure | 94.9s |

**This specific research question genuinely could not be completed twice in a row for Discovery-stage reasons — recorded as a real weakness (§13), not glossed over.** Per this report's explicit instruction not to "silently retry until you get a better result," a third attempt on the *identical* question was not made. Instead, to still obtain the required Springer/detailed data point for the matrix, **a different research question** was used for one final attempt — this is a change of topic to work around a Discovery-layer API issue, not a retry of the same run seeking a better outcome, and is reported as such.

**Third attempt (different topic): SUCCEEDED.**

| Field | Value |
|---|---|
| Run ID | `4831faf5f0ee45ef963e17659b207aaa` |
| Research question | "What is the impact of telemedicine adoption on patient health outcomes in rural areas?" (new domain — telemedicine/rural healthcare) |
| Provider / Model | Ollama / `qwen3.5:9b` |
| Papers found → selected | 80 unique → 6 selected |
| Research gaps found | 5 |
| Target words | 6,000 |
| Actual words | 4,028 |
| % of target | **67.1%** |
| Length status | 🔴 `short` (just below the 0.7× floor) |
| `draft_status` | **`partial`** — again solely from the heading-audit bug (see below) |
| Failed sections | 0 |
| Broken sections | **none** |
| Evidence-limited sections | **Literature Review, Discussion, Limitations** (3 of 4 outline sections) |
| Duplicate sections | none |
| `.tex` generated | ✅ |
| PDF compiled | ✅ |
| **PDF pages** | **10** |
| QA overall score | 3.5 / 5.0 |
| References verified / invalid / unverifiable | 3 / 0 / 3 |
| Discovery / Writing / Verification / QA time | 506.9s / 906.5s / 1.5s / 0.0s |
| **Total time** | **1,415.7s (23m 36s)** |
| Output directory | `outputs/what-is-the-impact-of-telemedicine-adoption-on-patient-healt_4831faf5f0ee45ef963e17659b207aaa` |

Run 4's own `full_review_audit.json` shows the **identical** heading-audit bug a 4th time: `{"errors": [], "heading_errors": ["final heading sequence does not match the user outline"], "missing_sections": [], "passed": false}` — every other check clean, `warnings: []` this time (no bookend or section-audit warnings at all), yet still `"partial"` for the same code-level reason as Run 3.

---

## 📄 5. Section-by-Section Analysis

### Run 1

| Section | Target | Min | Max | Actual | Audit rounds | Resolved | Evidence-limited | Final audit passed |
|---|---|---|---|---|---|---|---|---|
| Background | 520 | 286 | 910 | 334 | 2 | ✅ | No | ✅ |
| Literature Review | 1,280 | 704 | 2,240 | 620 | 2 | ✅ | **Yes** | ❌ (length-only failure, correctly downgraded to evidence-limited per Case B) |
| Discussion | 880 | 484 | 1,540 | 634 | 1 | ✅ | No | ✅ |
| Limitations | 440 | 242 | 770 | 267 | 2 | ✅ | No | ✅ |
| Introduction (bookend) | ~480 | ~264 | ~840 | not separately persisted (see §13 weakness) | n/a | ✅ (rendered, non-blank) | — | — |
| Conclusion (bookend) | ~400 | ~220 | ~700 | 0 (replaced with failure placeholder) | n/a | ❌ | No | — |

Note: **Literature Review is a real, direct confirmation of the "Case B" evidence-limited design working correctly in a brand-new topic**: its final raw audit `passed=False` (still under its word minimum after one revision) but the section's real, non-invented content was kept and the section is marked `evidence_limited` rather than being discarded — exactly as designed.

### Run 2

| Section | Target | Min | Max | Actual | Audit rounds | Resolved | Evidence-limited | Final audit passed |
|---|---|---|---|---|---|---|---|---|
| Background | 780 | 429 | 1,365 | 475 | 1 | ✅ | No | ✅ |
| Literature Review | 1,920 | 1,056 | 3,360 | 1,093 (then discarded) | 2 | **❌** | No | ❌ |
| Discussion | 1,320 | 726 | 2,310 | 581 | 2 | ✅ | **Yes** | ❌ (length-only, correctly downgraded to evidence-limited) |
| Limitations | 660 | 363 | 1,155 | 397 | 2 | ✅ | No | ✅ |
| Introduction (bookend) | ~720 | ~396 | ~1,260 | rendered, non-blank (not separately persisted) | n/a | ✅ | — | — |
| Conclusion (bookend) | ~600 | ~330 | ~1,050 | rendered, non-blank | n/a | ✅ | — | — |

**Literature Review is a real, genuine failure** — not evidence-limited, not a false positive: `unresolved_issues: "Keep the draft under the requested tag and make [@paper_id] placeholders match cited_paper_ids."` means the model's revision attempt still cited something outside its allowed scope or mismatched its own placeholders, and the 1-round revision budget was exhausted. The section was correctly discarded (rendered as the fixed failure-placeholder text in `draft.md`, confirmed by direct inspection in §7) rather than silently left with the last bad draft.

Both bookends resolved cleanly in this run (no "evidence context violated" warning) — a useful data point that the bookend audit does **not** fail on every run, consistent with the citation-range-shorthand fix's earlier verified improvement.

### Run 3

| Section | Target | Min | Max | Actual | Audit rounds | Resolved | Evidence-limited | Final audit passed |
|---|---|---|---|---|---|---|---|---|
| Background | 520 | 286 | 910 | 302 | 2 | ✅ | No | ✅ |
| Literature Review | 1,280 | 704 | 2,240 | 894 | 1 | ✅ | No | ✅ |
| Discussion | 880 | 484 | 1,540 | 642 | 1 | ✅ | No | ✅ |
| Limitations | 440 | 242 | 770 | 410 | 1 | ✅ | No | ✅ |
| Introduction (bookend) | ~480 | ~264 | ~840 | rendered, non-blank | n/a | ✅ | — | — |
| Conclusion (bookend) | ~400 | ~220 | ~700 | rendered, non-blank | n/a | ✅ | — | — |

**Every section resolved cleanly on this run** — no failures, no evidence-limited flags, no revisions exhausted. This is the strongest section-level result of all 4 runs, and yet — per §4's critical finding — still reports `draft_status: "partial"` due to the unrelated heading-audit bug.

### Run 4

| Section | Target | Min | Max | Actual | Audit rounds | Resolved | Evidence-limited | Final audit passed |
|---|---|---|---|---|---|---|---|---|
| Background | 780 | 429 | 1,365 | 431 | 2 | ✅ | No | ✅ |
| Literature Review | 1,920 | 1,056 | 3,360 | 612 | 2 | ✅ | **Yes** | ❌ (length-only) |
| Discussion | 1,320 | 726 | 2,310 | 597 | 2 | ✅ | **Yes** | ❌ (length-only) |
| Limitations | 660 | 363 | 1,155 | 298 | 2 | ✅ | **Yes** | ❌ (length-only) |
| Introduction (bookend) | ~720 | ~396 | ~1,260 | rendered, non-blank | n/a | ✅ | — | — |
| Conclusion (bookend) | ~600 | ~330 | ~1,050 | rendered, non-blank | n/a | ✅ | — | — |

**3 of 4 outline sections are evidence-limited** — all resolved (kept, not discarded) but well under their word minimums after one revision each. This is the clearest example across all 4 runs of a thin real corpus (6 papers, several apparently offering limited directly-relevant evidence for this specific question) driving the whole paper's shortfall — the length-planning machinery correctly identified and reported this as `evidence_limited` rather than either padding or wrongly failing the sections.

---

## 📏 6. Target vs Actual Length

| Run | Target | Actual | % of target | Implementation's own classification |
|---|---|---|---|---|
| 1 (IEEE, standard) | 4,000 | 3,222 | 80.5% | 🟢 `on_target` (within the implementation's own 0.7×–1.4× band) |
| 2 (IEEE, detailed) | 6,000 | 3,585 | **59.8%** | 🔴 `short` (below the system's own 0.7× floor) |
| 3 (Springer, standard) | 4,000 | 3,928 | **98.2%** | 🟢 `on_target` — the closest of any run in this diagnostic |
| 4 (Springer, detailed) | 6,000 | 4,028 | **67.1%** | 🔴 `short` (just under the 0.7× floor) |

**Overall pattern across all 4 runs**: both "detailed" (6,000-word) runs (2 and 4) landed further from target (59.8%, 67.1%) than both "standard" (4,000-word) runs (1 and 3, 80.5%, 98.2%). This is consistent with a fixed 6-paper corpus simply not containing enough distinct, directly-relevant evidence to responsibly reach a 6,000-word target without the system inventing content it was explicitly built not to invent — i.e., the shortfall looks like the *length-limited-by-honest-evidence* design working as intended, not a length-planning arithmetic error. This report does not have visibility into a larger corpus size to test that hypothesis directly.

The system's own explicit tolerance is `word_budget.py`'s `_TOTAL_MIN_FRACTION = 0.7` / `_TOTAL_MAX_FRACTION = 1.4` — quoted directly from the code, not invented for this report.

Run 2's shortfall is **directly attributable to a real section failure** (Literature Review, budgeted at 1,920 words, discarded entirely — 0 words counted from it in the final total) rather than the length-planning mechanism being wrong per se — the 3 sections that DID resolve (Background 475/780, Discussion 581/1,320, Limitations 397/660) are themselves also under their individual targets, showing evidence-availability (only 6 papers, several evidence-limited) is the dominant constraint on this corpus, not the length-planning arithmetic. Run 4's shortfall (67.1%) is similarly explained: 3 of its 4 outline sections were genuinely `evidence_limited` (§5), not a planning defect.

---

## 📝 7. Manual Paper Inspection

### Run 1 (`outputs/.../final/draft.md`, read directly, not inferred from `draft_status`)

- **Introduction**: Real, substantive, on-topic (AI adoption in primary-school teaching, adaptive instructional design, ethics, gaps). Not duplicated. One cosmetic defect: the paragraph ends with a stray `",` character (`...between educators and AI engineers.",`) — a rendering artifact, not a content problem (see §13).
- **Body**: Background/Literature Review/Discussion/Limitations are all real, developed academic prose citing specific real papers (Latif et al. 2023, etc.), not placeholders. Literature Review is noticeably shorter (620 words vs. a 1,280 target) — genuinely evidence-limited given only 6 papers in the corpus, not padded and not fabricated.
- **Conclusion**: **Broken** — replaced with the fixed placeholder text (its own generation failed the bookend evidence-context audit; the specific cause was not the previously-fixed citation-range-shorthand bug, since no `[Pxxx-Pxxx]` pattern appears anywhere in this draft — a *different* trigger of the same audit path, not re-diagnosed further per this report's "do not fix" rule).
- **Overall manual classification**: 🟡 **Technically complete but with one real broken section** (Conclusion) — matches the automated `draft_status: partial` exactly. No disagreement between manual inspection and the automated result for this run.

### Run 2 (`outputs/how-does-microplastic.../final/draft.md`, read directly)

- **Introduction**: Present, substantive on its own, real citations. **However — major finding**: it is **substantially duplicated** with the Background section. Compare (verbatim from the actual file):
  > Introduction: *"Microplastic pollution has established itself as a pervasive phenomenon across diverse aquatic environments, affecting marine ecosystem biodiversity through widespread distribution and variable accumulation. Thushari and Senevirathna (2020) documented that microplastics are distributed widely in the water, sediment, and biota of marine and coastal habitats globally [1]. The concentrations observed vary significantly depending on the medium; for instance, water samples show counts ranging from 0.001 to 140 particles/m³, whereas sediments contain substantially higher loads, ranging from 0.2 to 8766 particles/m³ [1]."*
  >
  > Background (opens with): *"Microplastic pollution has established itself as a pervasive phenomenon across diverse aquatic environments, affecting marine ecosystem biodiversity through widespread distribution and variable accumulation. Thushari and Senevirathna (2020) documented that microplastics are distributed widely in the water, sediment, and biota of marine and coastal habitats globally [1]. The concentrations observed vary significantly depending on the medium; for instance, water samples show counts ranging from 0.001 to 140 particles/m³, whereas sediments contain substantially higher loads, ranging from 0.2 to 8766 particles/m³ [1]."*

  This is **word-for-word identical** for two full sentences, and the following paragraph (the "0.1 to over 15,000 particles per organism" statistic) is also repeated near-verbatim. The **same core statistics recur a third time** in the Conclusion ("sediments act as primary sinks containing loads up to 8766 particles/m³... 0.1 to over 15,000 particles per organism"). The Introduction also independently contains its own mini "In conclusion, this review synthesizes..." wrap-up paragraph — i.e. the Introduction is doing part of the Conclusion's job too.
- **Body**: Discussion and Limitations are real, developed prose. **Literature Review is a genuine failure placeholder** (`*This section audit could not be resolved; unsupported content was omitted.*`) — confirmed by direct inspection, matching `draft_status`'s own `broken_sections: ["Literature Review"]` exactly.
- **Conclusion**: Present, not blank — but as shown above, substantially recycles the Introduction/Background's opening facts rather than being a distinct, non-redundant synthesis.
- **Overall manual classification**: 🟠 **Partial — and manual inspection finds a second, unreported problem beyond what `draft_status` shows.** The automated `partial` status is correct about Literature Review, but does not, and structurally cannot, detect the Introduction/Background/Conclusion content duplication, since `completeness.py` only checks for duplicate **headings**, never duplicate **prose** across different headings. **This is not a "fake complete" case** (the run was never reported as `"complete"`), but it is a real gap: a future run could have every section technically "resolve" and still be reported `"complete"` while three of its six required sections recycle the same paragraph.

### Run 3 (`outputs/what-is-the-relationship.../final/draft.md`, read directly)

- **Introduction**: Real, substantive, on-topic — sleep quality's cognitive mechanisms, workplace stressors, evidence limitations. Not duplicated with Background this time (Background is instead about OSA clinical/diagnostic guidelines specifically).
- **Body**: Background, Literature Review, Discussion, Limitations are all real, developed, evidence-grounded prose citing specific real sources (Mohamud et al. 2025, Coelho et al. 2023, etc.) — no placeholders, no blanks.
- **Conclusion**: Present, real prose — **but substantially duplicates the Introduction.** Compare: Introduction opens *"The relationship between sleep quality and workplace decision-making is mediated by physiological deficits in cognitive function and structural characteristics of the work environment. Evidence indicates that compromised sleep quality directly impairs neural mechanisms required for complex judgment, leading to increased error rates and safety risks..."* vs. Conclusion opens *"The relationship between sleep quality and workplace decision-making is mediated by physiological deficits in cognitive function and structural work environment stressors. Compromised sleep directly impairs neural mechanisms required for complex judgment, leading to measurable increases in error rates and safety risks..."* — same claims, same citations (Mohamud et al. 2025; Coelho et al. 2023), same sentence structure, lightly reworded. This is the **second of three runs so far** (Run 2 and Run 3) to show substantial bookend/body content duplication — a real, recurring pattern, not a one-off.
- **Overall manual classification**: 🟡 **Technically strong content, but the automated `draft_status: "partial"` is misleading for the WRONG reason** — the actual paper has no missing/blank/duplicate-heading sections at all (confirmed by `completeness.py`'s own report), but is marked `"partial"` purely because of the heading-audit bug (§13, critical finding). If anything, this paper's real, human-relevant weakness (Introduction/Conclusion redundancy) is **not** what triggered its `"partial"` label — a different kind of validator/reality mismatch than Run 1/2, but still a mismatch.

### Run 4 (`outputs/what-is-the-impact-of-telemedicine.../final/draft.md`, read directly)

- **Introduction**: Real, substantive, on-topic (telemedicine efficacy vs. rural infrastructure barriers), grounded in specific cited studies (Kumari et al. 2025, Bell et al. 2023). **Not** substantially duplicated with Background or Conclusion this time — each section reframes the same underlying evidence base with a distinct emphasis (Introduction: tension between potential and infrastructure; Background: the specific broadband-access statistics; Conclusion: efficacy is conditional on infrastructure readiness). This is legitimate, expected thematic continuity (all bookends/sections draw from the same 6-paper corpus), not the word-for-word repetition seen in Runs 2 and 3.
- **Body**: Literature Review, Discussion, and Limitations are real prose (not placeholders) but visibly thinner than their targets (612/1,920, 597/1,320, 298/660 words respectively) — correctly flagged `evidence_limited` rather than padded or wrongly failed.
- **Conclusion**: Real, distinct synthesis, not a placeholder, not a near-duplicate of the Introduction.
- **Overall manual classification**: 🟡 **Technically complete and honest, but visibly thin** — a real, evidence-constrained paper that neither pads nor duplicates, correctly self-reports its own thinness via `evidence_limited_sections`, and is again only marked `"partial"` because of the unrelated heading-audit bug rather than any real content problem.

---

## 🧩 8. Completeness Consistency Check ("fake complete" test)

For every run, the chain **Writing graph status → Completeness validator → Rendered Markdown → PDF → Manual inspection** is compared.

| Run | Graph `succeeded` | Completeness validator | Rendered Markdown matches? | PDF matches? | Manual inspection agrees? | **Disagreement?** |
|---|---|---|---|---|---|---|
| 1 | `False` (bookend replaced) | `partial` (Conclusion broken) | ✅ Conclusion is genuinely the failure placeholder in `draft.md` | ✅ Same text is in the compiled PDF | ✅ Matches | **No — all four signals agree** |
| 2 | `False` (Literature Review unresolved) | `partial` (Literature Review broken) | ✅ Literature Review is genuinely the failure placeholder in `draft.md` | ✅ Same text is in the compiled PDF | ⚠️ Matches on the *reported* failure, but manual inspection found an **additional, unreported problem** (Introduction/Background/Conclusion content duplication) that none of the first four signals detect | **Partial disagreement — not a false "complete," but a real detection gap** |

| 3 | `False` (**solely due to the heading-audit bug — §13**) | `complete` (zero broken/missing/blank/duplicate sections) | ✅ every section present with real prose | ✅ | ✅ Genuinely strong paper, though Introduction/Conclusion redundantly overlap (a real weakness `completeness.py` cannot see, being a prose-duplication issue not a heading one) | **Yes — the OPPOSITE of "fake complete": this is a "fake partial."** The rendered paper, PDF, and manual inspection all agree this run is essentially complete and usable, yet `draft_status` says `"partial"` for a reason (`heading_errors`) that has nothing to do with any of them. |
| 4 | `False` (**solely due to the heading-audit bug**) | `complete` (zero broken/missing/blank/duplicate sections) | ✅ every section present, real (if thin) prose, correctly `evidence_limited` | ✅ | ✅ Honest, evidence-constrained but genuine paper, no duplication | **Yes — same "fake partial" pattern as Run 3.** |

**Across all 4 runs: zero cases of the original "fake complete" scenario** (draft_status: "complete" while genuinely broken) — the completeness validator itself works correctly for every broken-section case observed (Runs 1, 2). **But 2 of 4 runs (3 and 4) show the inverse: a genuinely complete, evidence-honest paper permanently denied the `"complete"` label** by the heading-audit bug (§13 #1) — a new, different kind of reporting inaccuracy this diagnostic was specifically designed to catch. Separately, Run 2's (and Run 3's) content duplication (§13 #2) shows a second, independent gap: the completeness validator's duplicate-detection only operates at the heading level, so substantial duplicate *prose* across distinct sections remains invisible to every automated signal regardless of the heading-audit bug.

---

## 🎓 9. IEEE Validation — Run 1

| Check | Result |
|---|---|
| Correct format selected | ✅ `target_format: "IEEE"` throughout the request/result |
| Correct citation style | ✅ Numeric `[1]`, `[2]`, `[3]` markers observed directly in `draft.md` |
| Correct LaTeX class | ✅ `paper.tex` begins `\documentclass[conference]{IEEEtran}` |
| Successful PDF compilation | ✅ |
| Non-empty PDF | ✅ |
| Real page count | **5 pages** (via `pypdf.PdfReader`, not estimated) |
| Obvious formatting failure | None observed |

### Run 2

| Check | Result |
|---|---|
| Correct format selected | ✅ |
| Correct citation style | ✅ Numeric `[1]`–`[6]` markers observed directly in `draft.md` |
| Correct LaTeX class | ✅ `\documentclass[conference]{IEEEtran}` |
| Successful PDF compilation | ✅ |
| Non-empty PDF | ✅ |
| Real page count | **5 pages** (via `pypdf`) |
| Obvious formatting failure | None (though the Literature Review's failure-placeholder text does render into the PDF as-is — visible, not hidden, but a human reader would see italic placeholder text mid-document) |

## 🎓 10. Springer Validation

### Run 3

| Check | Result |
|---|---|
| Correct format selected | ✅ `target_format: "Springer"` |
| Correct citation style | ✅ Author-year markers observed directly in `draft.md`, e.g. `(Mohamud et al. 2025)`, `(Coelho et al. 2023)` — matches the `chicago-author-date` mapping (see §2's noted caveat about this pairing vs. LNCS convention) |
| Correct LaTeX class/template | ✅ `paper.tex` begins `\documentclass{llncs}` — **this is the `llncs` substitution, not the official `svjour3` template; this report does not call it "official Springer format"** (see §2) |
| Successful PDF compilation | ✅ |
| Non-empty PDF | ✅ |
| Real page count | **10 pages** (via `pypdf`) |
| Obvious formatting failure | None observed |

### Run 4

| Check | Result |
|---|---|
| Correct format selected | ✅ |
| Correct citation style | ✅ Author-year markers observed directly in `draft.md`, e.g. `(Kumari et al. 2025)`, `(Bell et al. 2023)` |
| Correct LaTeX class/template | ✅ `llncs` (the same documented substitution as Run 3 — never presented as `svjour3`) |
| Successful PDF compilation | ✅ |
| Non-empty PDF | ✅ |
| Real page count | **10 pages** |
| Obvious formatting failure | None observed |

**Both Springer runs compiled successfully with the same `llncs` class, the same citation style, and produced substantive, non-empty, correctly-paginated PDFs — Springer support is exercised consistently across 2 real runs, not just 1.**

---

## ⚡ 11. Performance Results

| Run | Discovery | Writing | Verification | QA | Total |
|---|---|---|---|---|---|
| 1 | 659.4s | 1,071.7s | 1.6s | 0.0s | **1,733.4s (28m 53s)** |
| 2 | 384.3s | 1,021.1s | 2.3s | 0.0s | **1,408.4s (23m 28s)** |
| 3 | 516.1s | 877.8s | 2.9s | 0.0s | **1,397.6s (23m 18s)** |
| 4 (successful attempt) | 506.9s | 906.5s | 1.5s | 0.0s | **1,415.7s (23m 36s)** |
| 4 (failed attempt 1) | — | — | — | — | 102.6s (Discovery failure) |
| 4 (failed attempt 2) | — | — | — | — | 94.9s (Discovery failure) |

⚠️ **Caveat, reported honestly**: Run 1 executed concurrently with this session's full regression test suite (which itself includes one real live-model call), both competing for the same local Ollama server/GPU. Its total time is very likely inflated versus a fully isolated run. Runs 2, 3, and 4 executed in isolation and are cleaner measurements — **all three land within a narrow 23–24 minute band**, which this report treats as the representative, consistent figure for a 6-paper-corpus run on this hardware (i7-13700HX / RTX 4060 8GB / `qwen3.5:9b`), independent of format or length preset (writing time does not scale much with the "detailed" vs. "standard" target, since actual output length is evidence-bound, not target-bound — see §6).

---

## 🧪 12. Test Suite Results

**Targeted tests** (length, word budgeting, under-generation, completeness, IEEE/Springer formatting, citation handling): `test_word_budget.py`, `test_writing_under_generation.py`, `test_completeness.py`, `test_tag_semantics_container_fix.py`, `test_writing_citation_range_shorthand.py`, `test_writing_citation_id_normalization.py`, `test_latex_export.py`, `test_writing_prep.py` —
**65 passed, 0 failed, 0 skipped**, 0.69s.

**Full regression suite** (includes the real live-model pipeline integration test), run twice:
- Concurrently with diagnostic Run 1 (contended for the same Ollama server): **163 passed, 1 skipped, 0 failed**, 1,346.72s (22m 26s).
- **Final, isolated run** (after all 4 diagnostic runs completed, no contention) — the authoritative number for this report: **163 passed, 1 skipped (the opt-in extra-heavy live test, gated behind an env var), 0 failed**, **642.44s (10m 42s)**.

No tests were modified to make them pass. No thresholds were changed. Zero production code, prompts, or configuration were changed at any point during this diagnostic — confirmed via `git status` immediately before writing this report, showing only this new report file as a change against the `fix/paper-length-completeness-ieee-springer` branch.

---

## 🐛 13. Bugs or Weaknesses Found (observation only — not fixed), ranked by severity

1. **🔴🔴 CRITICAL — `draft_status: "complete"` is currently unreachable, for any run.** `review_auditor.py::audit_full_review()`'s expected-heading list is built from the outline's tag tree, which does not include the `Introduction`/`Conclusion` headings `review_assembler.py` now renders (a fix made earlier in this same overall pass, D-026, so `completeness.py` could detect a blank bookend). The two were never reconciled: the audit's heading-sequence comparison now fails on **every single run**, unconditionally, confirmed identically in **all 4 real runs executed for this report** (`heading_errors: ["final heading sequence does not match the user outline"]`, `passed: false`, with every other check clean in all four — including Run 4, which had zero warnings of any kind otherwise). Since `service.py`'s `draft_status` logic downgrades to `"partial"` whenever `not result.succeeded`, and `result.succeeded` depends on this now-permanently-failing check, **`"complete"` cannot currently be produced regardless of paper quality.** Runs 3 and 4 are direct proof: both had zero missing/blank/duplicate/broken sections, yet both report `"partial"`. **4 of 4 runs (100%) reproduced this identically.** See §4 for the full evidence. **This is a direct, self-contained regression from this same overall pass's own earlier work (the D-026 heading-rendering fix), not a pre-existing or model-reliability issue** — it is 100% deterministic and code-level, not variance.
2. **🔴 MAJOR — substantial cross-section content duplication is possible and currently undetected.** Observed in **2 of 4 runs**:
   - Run 2: Introduction and Background share two **word-for-word identical** sentences, and the same key statistics recur a third time in the Conclusion.
   - Run 3: Introduction and Conclusion share the same core claims, citations, and sentence structure, lightly reworded.
   - Runs 1 and 4 did **not** show this pattern — their bookends/sections shared themes and evidence (expected, since they draw from the same corpus) but not verbatim sentences.
   `completeness.py`'s `duplicate_sections` check only compares **heading titles**, never **prose content** across different headings — this class of duplication is invisible to `draft_status`, the pipeline, and every existing test. At 2 of 4 (50%), this is a real, recurring — not universal — pattern.
3. **🟡 Discovery-stage external API fragility caused a full run failure that took 2 attempts on the same query to work around.** The original Run 4 topic ("renewable energy policies... developing countries") failed **twice consecutively** with `PipelineError: No papers found in any source` — Semantic Scholar, OpenAlex, and arXiv all returned `HTTPStatusError` for that specific query both times. This is consistent with this project's own long-documented rate-limit fragility in these external, keyless APIs, but this diagnostic is the first time it has been observed to fully block a run (not just degrade corpus quality) for a specific query, twice in a row. A third attempt with a *different* topic succeeded normally. Not a writing/length/completeness/format problem — a Discovery-stage/external-dependency reliability gap.
4. **Conclusion bookend failure (Run 1), from a different apparent cause than the previously-fixed citation-range bug.** The specific previously-diagnosed cause (a `[Pxxx-Pxxx]` citation range shorthand) is **not** present anywhere in Run 1's draft — evidence the bookend audit can still fail for reasons beyond the one already fixed. Not re-diagnosed further per the "do not fix" instruction.
5. **A genuine, correctly-handled section failure (Run 2, Literature Review)**: exhausted its 1-round revision budget still citing outside its allowed scope, and was correctly discarded as a failure placeholder rather than left in a bad state — `draft_status` and `broken_sections` reported this accurately. Not a bug; recorded as evidence the failure path works as designed.
6. **Evidence-limited handling works correctly under real thin-corpus stress (Run 4)**: 3 of 4 outline sections were genuinely evidence-limited (298–612 actual words against 660–1,920 targets) and all were correctly kept and flagged rather than padded or discarded. Not a bug; positive confirmation.
7. **Cosmetic rendering artifact**: the Introduction's final sentence in Run 1 ends with a stray `",` character in the raw markdown (`...AI engineers.",`). Purely cosmetic.
8. **Bookend section audits are not individually persisted to disk** (unlike outline-tag sections). Diagnosability gap, not a correctness bug.
9. **Springer's citation style (`chicago-author-date`) vs. its LaTeX class (`llncs`)** is a real, unusual pairing worth the user's awareness (see §2) — not necessarily wrong, but not the typical LNCS convention either. Confirmed identically in both Springer runs (3 and 4).

---

## 📈 14. Before vs Current Results

Historical baseline (from `PAPER_OUTPUT_DIAGNOSTIC.md`, the original diagnostic, 11 real runs, **before** any of the length/completeness fixes on this branch): average **~1,353 words**, no length control, hardcoded 4-section outline with a duplicated/blank-prone Introduction/Conclusion path, `draft_status` blind to bookend failures, always the plain `article` LaTeX class regardless of format.

| Metric | Historical (11 runs, before) | This report's 4 real runs (current) |
|---|---|---|
| Average words | ~1,353 | **(3,222 + 3,585 + 3,928 + 4,028) / 4 = 3,691** — a real ~173% increase |
| Length control | None | User-selected preset (Short/Standard/Detailed), all 4 runs used it |
| Outline duplication (Intro/Conclusion generated twice) | Architecturally possible (D-025's diagnosed root cause) | **Not observed in any of the 4 runs** — no duplicate section headings in any run |
| `draft_status` blind to bookend failure? | Yes (3 of 11 historical runs proven mislabeled `"complete"` — see D-026) | **Partially fixed, but see the new problem below**: bookend/section failures ARE now correctly caught (Runs 1, 2) — but... |
| `draft_status: "complete"` reachable at all? | Yes (albeit sometimes wrongly, per the row above) | **🔴 No — currently unreachable for ANY run** (§13 #1), a new, different problem introduced by fixing the old one |
| IEEE/Springer template | Always plain `article`, regardless of format | **Genuinely switches** — `IEEEtran` used and confirmed in 2 IEEE runs, `llncs` used and confirmed in 2 Springer runs |
| Content duplication across sections | Not specifically measured historically | **New finding this report**: observed in 2 of 4 current runs (§13 #2) — not comparable to a historical baseline since this check did not exist before |

Clearly separated: historical numbers are **not** re-measured in this report; all 4 runs in the table above are fresh, current measurements from this diagnostic session only.

---

## ⚠️ 15. Remaining Limitations

1. **`draft_status: "complete"` is not currently achievable** (§13 #1) — the single highest-priority item for any follow-up work. Until `audit_full_review()`'s expected-heading list is reconciled with the bookend headings `review_assembler.py` now renders, every run will report at best `"partial"`, regardless of actual quality.
2. **Cross-section content duplication has no automated detection** (§13 #2) — occurred in 2 of 4 real runs. A user reading the delivered paper may notice redundant paragraphs that no current signal (`draft_status`, `duplicate_sections`, QA score) flags.
3. **Discovery-stage external API calls (Semantic Scholar, OpenAlex, arXiv) are fragile enough to occasionally return zero results for a well-formed query**, blocking a run entirely — observed once in 4 attempts (25%) in this diagnostic session, requiring a topic change to complete the required test matrix.
4. **Neither Springer run used the actual official `svjour3` template** — `llncs` is a real, standard, but different Springer class, consistently and honestly labeled as a substitution in the code and in this report.
5. **The Springer citation style (`chicago-author-date`) is paired with the `llncs` document class**, an unusual combination relative to typical LNCS convention (which more often uses numbered citations) — not necessarily incorrect, but a real design detail the user should be aware of.
6. **Both "detailed" (6,000-word) runs fell further short of target (59.8%, 67.1%) than both "standard" (4,000-word) runs (80.5%, 98.2%)** — consistent with a fixed 6-paper corpus limiting how much can be honestly written, not a length-planning defect, but a real practical ceiling on how long a paper can get without either a larger corpus or accepting more evidence-limited sections.
7. **Bookend (Introduction/Conclusion) audit outcomes are not individually persisted**, limiting how deeply any future diagnostic can inspect their own attempt/revision history without a live re-run.
8. This diagnostic used **corpus size 6 throughout** (not varied) and the **local Ollama `qwen3.5:9b` provider only** (Gemini was not exercised) — findings are specific to this configuration and have not been verified to generalize to a larger corpus size or the alternate provider.

---

## 🏆 16. Final Verdict

### 🟠 PARTIALLY FIXED — core improvements work but the original problem still occurs, and a new, different problem was introduced while fixing it

**Evidence for real, substantial progress:**
- Average length across 4 fresh real runs (3,691 words) is a genuine ~173% increase over the 11-run historical baseline (~1,353 words).
- Length planning demonstrably works: one run reached 98.2% of its target, and the shortfalls observed elsewhere are attributable to real corpus-evidence limits, not a planning defect — confirmed by direct inspection of each section's actual content, not assumed from the summary numbers alone.
- Evidence-limited handling works correctly and was stress-tested for real in Run 4 (3 of 4 sections genuinely evidence-limited, all correctly kept rather than padded or wrongly failed).
- No outline-level Introduction/Conclusion duplication (the original D-025 problem) occurred in any of the 4 runs.
- IEEE and Springer format selection both genuinely change the LaTeX document class, citation style, and produce real, correctly-paginated, compiling PDFs — verified with 2 real runs per format, not one.
- The completeness validator (`completeness.py`) correctly identified every genuinely broken section observed (Runs 1 and 2) — the original "fake complete" scenario did not recur for any section-level failure in this diagnostic.

**Evidence the original problem is not fully solved, and a new one exists:**
- **`draft_status: "complete"` is currently unreachable for any run** — confirmed with a 100% (4 of 4) reproduction rate, and directly caused by this same overall pass's own earlier fix (the D-026 Introduction/Conclusion heading change was never reconciled with `audit_full_review()`'s heading-sequence check). Two of the four real runs in this diagnostic (Runs 3 and 4) were, by every other measure — section completeness, length, references, manual inspection — genuinely complete papers, and both were denied that label for a reason unrelated to their actual quality.
- Cross-section content duplication (2 of 4 runs) is real, currently invisible to any automated check, and was not part of what this pass's completeness validator was built to catch.
- Discovery-stage reliability (a pre-existing, previously-documented issue, not part of this pass's scope) blocked one run outright.

**Why not 🟡 MOSTLY FIXED**: a verdict of "mostly fixed" would require the core claim — that the system can correctly tell the user whether a paper is complete — to be trustworthy in the common case. It currently is not: `"complete"` is never reported at all, for any paper, regardless of quality, which is arguably a **more severe** usability problem than the original one-sided "fake complete" issue, because it gives zero positive signal ever, rather than an occasionally-wrong one.

**Why not 🔴 NOT FIXED**: the underlying paper-generation quality, length-handling, and format-support improvements are real, verified with real evidence across 4 runs, and represent genuine progress over the historical baseline. The `draft_status` regression is a specific, narrow, well-understood, one-line-root-cause bug (a heading-list mismatch) — not a sign that the broader architecture is unsound.

**Bottom line**: the underlying paper generation is genuinely better and more honestly self-reporting than before (evidence-limited vs. broken vs. duplicate content are now real, mostly-correct distinctions) — but the single most visible, decision-relevant signal (`draft_status`) is currently **always wrong in the pessimistic direction**, which should be treated as a release-blocking finding for anyone relying on that field, separate from and in addition to the two remaining un-caught weaknesses (content duplication, Discovery fragility).
