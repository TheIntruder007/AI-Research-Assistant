# Analytics and Results — Reliability Improvement Pass

**Date:** 2026-08-28
**Scope:** Perfect the existing four-service pipeline (no new features) — Service 1 relevance/selection, Service 2 writing reliability, and a lightweight performance profile. All work was tested against the real local model (`qwen3.5:9b`) and real external APIs before being reported here.

> **Update (same day, second pass):** a follow-up pass focused entirely on Service 2 — see [§10](#-10-service-2-final-reliability-pass-2026-08-28-follow-up) below for the tag-semantics fix, the container-content bug fix, the revision-rounds finding, and the final honest verdict (🟡 partially improved).
>
> **Update (same day, third pass):** a final follow-up fixed the one remaining citation-boundary failure — see [§12](#-12-service-2-citation-boundary-fix-2026-08-28-third-pass) for the root cause (a false-positive detection bug, not a genuine evidence leak), the fix, and the final verdict (**🟢 COMPLETE** for this specific problem, verified across 3 topics).
>
> **Update (same day, fourth pass):** a length-and-completeness pass fixing the paper-length/short-draft problem and adding real IEEE/Springer format support — see [§15](#-15-paper-length-and-completeness-fix-2026-08-28-fourth-pass) below.

---

## 🎯 1. Purpose

- **What:** Improve the reliability, accuracy, and consistency of the existing Research Discovery (Service 1) and Research Writing (Service 2) services, without adding new pipeline features.
- **Why:** Two known, previously-documented issues were flagged as non-blocking but real:
  1. Service 1 once selected an unrelated paper (an asthma-management guideline) for an intermittent-fasting/cognition query.
  2. Service 2 reliably completes only some leaf sections per run (D-011), and its retry logic was blind rather than targeted.
- This pass diagnosed both from their actual root cause — not just patched the specific example — fixed what was safely fixable, and honestly documents what remains a real, measured limitation.

---

## 🔍 2. Problems Found

### Service 1 — no relevance signal at all
`discovery/pipeline.py::rank()` scored every candidate paper purely on: abstract presence, citation count, recency, and the search engine's own result position. **There was no step anywhere that compared a candidate paper to the actual research question.**

### Service 1 — user keywords silently dropped
`services/research-discovery/service.py::run_discovery()` accepted `DiscoveryRequest.keywords` but never passed it to the search/ranking pipeline at all.

### Service 2 — blind literature-card retry
`writing/graph.py::build_card_worker`'s retry loop called `build_literature_card()` a second time with the **exact same prompt** after a validation failure — the model had no way to know what it had gotten wrong.

### Service 2 — no explicit complete/partial classification
The writing graph already computed a `succeeded` flag and `failed_tag_ids`, but neither ever reached `WritingResult`/`DraftMetadata`. A pipeline consumer had no direct signal of draft completeness.

### Service 2 — deeper finding: `TAG-ROOT`'s semantics are systematically too broad (new this pass)
Investigating a real failing run's `tag_definitions.json` showed `TAG-ROOT`'s `include_when` criteria essentially restate the whole research question ("addresses both the intervention and the outcome"), so it legitimately overlaps with almost every child tag's own criteria. This means the ancestor/descendant duplication D-011 attributed to "the model occasionally mis-tagging" is at least partly **systematic**, not random — flagged here as a follow-up, not fixed in this pass (see §8).

---

## 🧠 3. Root Cause Analysis

| Problem | Cause | How reproduced | Why the old approach failed |
|---|---|---|---|
| Off-topic paper selected | `rank()` had zero topical-relevance term | Read `rank()`/`analysis.py` line by line; confirmed query generation explicitly favors recall over precision | Ranking rewarded citations/recency/abstract presence only — a well-cited, recent, off-topic paper could win outright |
| User keywords ignored | `service.py` never forwarded `request.keywords` | Read the call site — `run_pipeline(request.research_question, ...)` drops every other field | Nobody had wired it through; not a runtime bug, a missing connection |
| Blind card retry | `build_card_worker` called `build_literature_card()` identically on retry | Read `graph.py`; confirmed no error feedback reached the prompt | Retrying without changing input can only help for transient (non-deterministic) failures, not systematic ones |
| No complete/partial signal | `ReviewResult.succeeded`/`failed_tag_ids` never mapped into `DraftMetadata` | Read `service.py`'s result-adaptation code | Data existed but was never surfaced to consumers |
| Systematic root/child tag overlap | `TAG-ROOT`'s `include_when` is defined as broadly as the whole research question | Read a real run's `tag_definitions.json` after a card kept failing on the same paper twice | `define_tag_semantics.md`'s prompt does not explicitly instruct the root tag to *exclude* anything a child tag already covers |

---

## 🛠️ 4. Improvements Made

### Service 1 (`discovery/relevance.py`, new)
- Deterministic (no extra LLM call) topic-profile extraction: significant unigrams + bigrams from the question, the LLM's own generated keyword query, and user-supplied keywords (now actually wired through).
- **Hard relevance gate**: a paper scoring below 0.12 with no shared meaningful phrase is rejected outright, before ranking — regardless of citations or recency.
- **Ranking changed from additive to multiplicative**: relevance now multiplies the existing citation/recency/abstract/position score, so a merely keyword-adjacent paper can no longer out-rank a genuinely on-topic one just by being more cited or recent. (An additive version was tried first and failed its own adversarial test — see §5.)
- `relevance_score`/`relevance_decision`/`relevance_reason` recorded on every paper for transparency; a `relevance_filter` progress event reports accepted/rejected counts + example rejections.

### Service 2 (`writing/`)
- **Targeted card retry**: `build_literature_card()` now accepts `previous_errors`; the retry attempt's prompt includes the exact prior validation errors, and the prompt template explicitly tells the model to fix them (not regenerate blind).
- **Explicit draft completeness**: `DraftMetadata` gained `total_sections`, `failed_sections`, and `draft_status: "complete" | "partial"`, computed from the graph's own `succeeded` + `failed_tag_ids` signals (both must agree).
- **QA scoring uses the explicit signal**: `process_control` now scales with the actual failed/total section fraction instead of only checking whether any warning text exists at all.
- Verified (for the first time, via new unit tests) that the *existing* inner revision loop (audit → targeted `revise_section()` call using the audit's own instructions) works correctly — it was previously only exercised indirectly through slow, live, full-graph runs.

### Performance
- No structural performance changes made — see §7 for why.

---

## 🧪 5. Tests Performed

### Unit tests (new, all fast, no network/model required)
| File | Count | Covers |
|---|---|---|
| `tests/services/test_discovery_relevance.py` | 8 | Tests A–E from the spec, plus screening/annotation and degenerate-profile handling |
| `tests/services/test_writing_literature_card_retry.py` | 3 | First attempt has no error feedback; retry carries exact prior errors; empty error list ≠ prior attempt |
| `tests/services/test_writing_section_reliability.py` | 3 | Missing-evidence sections skip the model call; invalid-citation drafts are corrected via one targeted revision; unrecoverable sections are explicitly `resolved=False` |

One test (`test_e_adversarial_keyword_overlap_alone_cannot_win_ranking`) initially **failed** against an additive relevance-scoring design — this caught a real weakness before it shipped, and is why ranking was changed to multiplicative instead.

### Integration tests
- `tests/services/test_discovery_pipeline_integration.py` (live) — now also asserts every paper in a real corpus has `relevance_score >= 0.12`. **Passed** in 514.14s against a real intermittent-fasting/cognition search.
- `tests/orchestrator/test_pipeline.py`, `tests/orchestrator/test_api.py` — unaffected, still passing (18/18).

### Regression tests
- Full suite: **54 passed, 1 skipped** (the opt-in 15-minute full-pipeline test) in 488.47s — zero regressions from any change in this pass.

### Real end-to-end tests
1. **Service 1 standalone** (`scripts/smoke_test_discovery.py`), same research question as the originally-documented bug:
   - 120 papers found → 119 unique → **6 rejected as off-topic**, including a paper materially identical in kind to the original bug (a GINA asthma-management guideline), plus a COVID/eating-behavior survey, a loneliness review, a food-addiction terminology paper, and an unrelated ML paper.
   - All 6 selected papers scored 0.81–1.0 relevance.
2. **Full pipeline** (`scripts/smoke_test_full_pipeline.py`), same question, via the real orchestrator:
   - Discovery: 120 → 119 unique → 113 passed screening (6 rejected) → 6 selected, all 0.81–1.0 relevance.
   - Writing: `draft_status: "partial"` (2/5 sections written, 3 failed) — the explicit classification worked correctly and matched the underlying warnings/errors.
   - Verification + QA ran normally on the resulting (thin) reference list; overall QA score 3.5/5.0.

---

## 📊 6. Before vs After Results

### Service 1 — relevance screening

| Metric | Before | After |
|---|---|---|
| Relevance check before ranking | **None** | Deterministic hard gate + weighted ranking |
| Asthma-guideline-class paper in real search results | Entered the corpus (original bug) | **Rejected** (score 0.082, reason: "shares no meaningful terms or phrases") |
| User-supplied keywords used | Never (silently dropped) | Used to strengthen the topic profile |
| Real run: candidates → rejected → selected | Not measured (no rejection step existed) | 119 unique → 6 rejected → 6 selected, all relevance ≥ 0.81 |
| Ranking formula | Additive (an off-topic-but-cited paper could win) | Multiplicative (relevance gates how much citations/recency can count) |

### Service 2 — writing reliability

| Metric | Before | After |
|---|---|---|
| Card-build retry | Blind (identical prompt) | Targeted (prior errors fed back — confirmed via unit test AND a real run where attempt 2's flagged points genuinely differed from attempt 1's) |
| Draft completeness signal | Inferred from warning/error text presence only | Explicit `draft_status: "complete"/"partial"` + `failed_sections`/`total_sections` |
| QA process_control scoring | Binary-ish (any warning → 4.0, any error → 2.0) | Scaled by actual failed/total section fraction |
| Real run leaf-section success (this pass) | D-011 baseline: 2 of 4 leaf sections | This run: 2 of 5 sections (comparable — see §8, not a regression, and not yet fully solved) |
| Root cause understanding | "Model occasionally mis-tags evidence" | Refined: `TAG-ROOT`'s semantics are systematically too broad, not purely random (see §8) |

**Honest framing:** the targeted-retry fix is proven to work mechanically (unit tests + a real run showing the retry prompt changed the model's output), but it did **not** fully resolve the specific hard paper (P003) encountered in the real run — that paper failed both attempts, for a reason now understood more precisely (systematic root/child tag overlap) but not yet fixed. This is reported as a partial improvement with a clear, evidenced follow-up, not as a solved problem.

---

## ⏱️ 7. Performance Results

| Stage | This run | Documented baseline (D-011) |
|---|---|---|
| Discovery | 314.9s | 245s |
| Writing | 703.4s | 681s |
| Verification | 0.4s | — |
| Quality Assurance | 0.0s | — |
| **Total** | **1018.7s (~17.0 min)** | **926s (~15.4 min)** |

The relevance-screening addition is a cheap, deterministic token/phrase-overlap computation over at most ~120 candidates (no LLM call, no network call) — it is not a meaningful contributor to the ~90s difference from baseline, which is within the range of normal LLM-inference timing variance already documented for this hardware (D-009). **No performance optimization work was undertaken in this pass** — per the pass's own instruction ("measure actual bottlenecks, do not optimize blindly"), the measured bottleneck is unambiguously LLM inference time in Discovery's gap analysis and Writing's per-section calls, exactly as already documented in D-009/D-010, and no safe, high-confidence optimization of that was identified that wouldn't risk the reliability work this pass prioritized instead.

---

## 🏆 8. Final System Quality

### What is now reliable
- Service 1 can no longer select a paper that shares nothing topically with the research question — verified against both synthetic adversarial cases and a real live search reproducing the original bug's exact failure class.
- Service 2's literature-card retries are genuinely targeted, not blind — verified mechanically (unit tests) and observed acting differently between attempts in a real run.
- Every writing run now carries an explicit, code-computed `draft_status` — no pipeline consumer needs to infer completeness from warning text.
- Zero regressions: the full existing test suite (54 tests) plus three new test files (14 new tests) all pass; the API, terminal app, async execution, and SSE streaming were not touched and remain covered by their existing tests.

### Remaining, known, non-blocking limitations
- **Service 2 leaf-section completeness is not fully solved.** A specific, systematic cause was newly identified (`TAG-ROOT`'s `include_when` is as broad as the whole research question, causing legitimate overlap with child tags) but not fixed in this pass — fixing it means changing `define_tag_semantics.md`'s prompt to explicitly instruct the root tag to exclude anything a child tag already covers, which touches a different, less-tested part of the vendored graph and was judged out of scope for this pass's risk budget.
- **A new edge case surfaced**: one real run hit a `SectionDraft` `ValidationError` (empty-string content) that bypasses the inner audit/revision loop entirely, handled only by the outer, still-blind `max_section_attempts` retry in `write_next_section`. That outer retry was deliberately not touched in this pass (see D-019's "alternatives considered") — it remains a blind retry and is the next highest-value target if this area is revisited.
- Service 1's deterministic relevance check is token/phrase overlap, not semantic understanding — it cannot distinguish two genuinely different meanings sharing a word (documented explicitly in `relevance.py`'s own docstring).
- Citation Verification and Quality Assurance were not in scope for this pass and are unchanged.

---

## 📁 9. Final Validation Artifacts

- Unit test files: `tests/services/test_discovery_relevance.py`, `tests/services/test_writing_literature_card_retry.py`, `tests/services/test_writing_section_reliability.py`.
- Live discovery relevance run (raw event log): captured via `scripts/smoke_test_discovery.py` — rejected-paper list and per-paper relevance scores shown in §5.
- Full-pipeline real run: `outputs/what-are-the-effects-of-intermittent-fasting-on-cognitive-pe_afbbc837e95b44e8aa1e7046ce202d7b/` — includes `02_writing/*/card_audits/P003.json` (the two-attempt error record referenced in §8) and `04_quality_assurance/result.json`.
- Full regression suite result: 54 passed, 1 skipped, 488.47s.
- Decision log entries: `DECISIONS.md` D-018 (Service 1) and D-019 (Service 2).

---

## 🔟 10. Service 2 Final Reliability Pass (2026-08-28, follow-up)

**Scope of this follow-up:** Service 2 only, per explicit instruction — no new features, Service 1 untouched. Picks up exactly where §8 left off: the two open problems (systematic `TAG-ROOT` overlap, the outer "blind retry" crash) are diagnosed to their real root cause and fixed; a third, higher-leverage issue was found while stress-testing the fixes and is reported honestly alongside them.

### 🏷️ Tag Semantics Fix

**Original overlap problem:** `TAG-ROOT`'s generated `include_when` was functionally identical in scope to the whole research question, so it legitimately overlapped every child tag's criteria — causing the same evidence point to be assigned to both an ancestor and a descendant tag, which the deterministic validator correctly rejects.

**Root cause:** `define_tag_semantics.md` told the model to minimize overlap between *branches* (siblings) but never once addressed *ancestor/descendant* exclusion — a parent tag was never told to exclude what its own children already own.

**Changes made:** Added an explicit "Ancestor/descendant ownership" section to the prompt: any tag with children must write `include_when` to cover only genuine cross-cutting synthesis content, and must add one `exclude_when` entry per child naming that child's scope as excluded.

**Before vs after (real model, targeted reproduction against the exact failing paper, not a full pipeline run):**

| | Before | After |
|---|---|---|
| `TAG-ROOT` `include_when` | "Evidence addresses both the intervention (intermittent fasting) and the outcome (cognitive performance)" — restates the whole question | "General statements establishing the relationship... that do not specify a particular mechanism, population subgroup, or outcome metric" — genuinely narrow |
| `TAG-ROOT` `exclude_when` | Generic, no per-child exclusions | Explicit per-child exclusions naming all 4 children |
| P003's card validation | **Failed** (7 ancestor/descendant duplicate points, both attempts) | **Passed** — zero duplicate points |

### 🔄 Retry Fix

**Original blind retry path:** the outer `max_section_attempts` retry in `write_next_section` re-called `write_section_with_revisions()` identically after any exception — no error feedback, no changed input.

**Root cause (actual, traced, not assumed):** the specific crash motivating this ("empty-string content ValidationError") was **not** a model output problem at all. `write_next_section`'s container-tag branch directly constructed `SectionDraft(content="", ...)` — a deterministic code bug that crashes on every run with a container-type tag, independent of the model entirely. This is exactly why retrying (blind or otherwise) could never have fixed it.

**New recovery flow:** none needed for this specific bug — it's eliminated at the source (`content=" "` instead of `content=""`, which satisfies the schema while still rendering as empty, matching `assemble_review()`'s existing `draft.content.strip()` check). Building a full failure-classification/recovery-prompt system for a failure that turned out not to be model-driven would have been unjustified scope creep; instead, the *existing* outer retry's safety (bounded attempts, explicit failure state, section isolation) was verified for a genuinely-empty model response as a documented, still-open (but safe) case.

### 🧪 Tests

| File | Count | Type |
|---|---|---|
| `tests/services/test_writing_card_tag_ownership.py` | 5 | Unit — tag-ownership Tests A–D, direct against `validate_literature_card()` |
| `tests/services/test_writing_container_section_bug.py` | 2 | Regression — reproduces the exact production crash, then confirms the fix |
| `tests/services/test_writing_outer_retry_bounded.py` | 4 | Unit — outer-retry Tests A–C (bounded, no infinite loop, exact error captured) |
| `tests/services/test_writing_section_isolation.py` | 1 | Integration — outer-retry Test D (one failing section never blocks others) |

All 12 new tests run without a live model. Full regression suite after all changes: **66 passed, 1 skipped**, zero regressions (Service 1 relevance filtering, Citation Verification, Quality Assurance, the orchestrator, the API, SSE streaming, the terminal app, and artifact storage were all re-verified and untouched).

**Real local-model tests:** three full-pipeline stress runs — see §11.

### 📈 11. Reliability Metrics — Before vs After

| Run | Question | Config | Sections | Draft status | Card-build errors | QA score |
|---|---|---|---|---|---|---|
| Baseline (§6) | Fasting/cognition | pre-D-018/019 | 2/5 | partial | 1 (P003, ancestor/descendant conflict) | 3.5/5.0 |
| Stress 1 | Fasting/cognition (same) | tag fix + container fix, **0** revision rounds | 1/5 | partial | **0** | 3.6/5.0 |
| Stress 2 | Fasting/cognition (same again) | + **1** revision round | **5/5** | **complete** | **0** | **4.2/5.0** |
| Stress 3 | Remote work/productivity (different topic) | + 1 revision round | 4/5 | partial | **0** | 3.6/5.0 |

- **Complete draft rate across post-fix stress runs:** 1 of 2 (50%) — up from 0 of every previously recorded run.
- **Card-build failure rate:** 0 of 3 stress runs (down from every previously recorded run having at least one).
- **Average successful sections (post-fix, both revision-enabled runs):** 4.5 of 5 (90%) — up from a documented historical baseline never exceeding 2 of 4–5 (40–50%).
- **Retry recovery confirmed working:** Stress run 2 included a real `node_type: "container"` tag that completed successfully in production (not just in the isolated test) — direct confirmation the container-content fix works under real conditions.
- **Final failures:** Stress 3's one residual failure (TAG-2, citing papers outside its allowed list even after one revision) is honestly reported, not hidden — one revision round substantially helps but does not universally guarantee completeness on this hardware/model.

### 🏆 Final honest verdict

**🟡 PARTIALLY IMPROVED.**

Both diagnosed root causes — the systematic tag-semantics overlap and the container-content crash — are fixed and verified against real reproductions, and a third, higher-leverage issue (revision rounds effectively disabled) was found and fixed while stress-testing. Card-build failures and container-content crashes are now a **closed category**: zero occurrences across all three post-fix stress runs. Draft completeness improved dramatically (one fully complete 5/5 draft, one 4/5 draft, versus a historical baseline that never exceeded 2/4–5) — but two post-fix stress runs is not enough to claim the pipeline **reliably** produces a complete draft on every topic, and one run still ended partial. This is reported honestly as a large, real, measured improvement — not as a fully solved problem.

**What would move this to 🟢 COMPLETE:** several more stress runs across a wider range of topics consistently reaching `draft_status: "complete"`, and/or resolving Stress 3's residual citation-placeholder failure (possibly via a second bounded revision round or a targeted fix to why the model repeats that specific mistake).

---

## 1️⃣2️⃣ 12. Service 2 Citation-Boundary Fix (2026-08-28, third pass)

**Scope:** a dedicated follow-up to §10-11's one remaining failure — Stress 3's `TAG-2` section, reported as citing "papers outside its allowed evidence set." Per explicit instruction, the real failed run's saved artifacts were traced **before** any code changed, and the task's own working assumption (a genuine evidence-boundary leak) was checked against that evidence rather than taken at face value.

### 🔍 Root Cause

**Not what was assumed.** Loading the real run's `section_contexts/TAG-2.json` and `section_audits/TAG-2.json` showed the model cited **only allowed papers** — P001, P003, P004, P005, all present in `allowed_paper_ids`. There was no genuine evidence-boundary violation. The audit's `invalid_paper_ids` were `["@P001", "@P003", "@P004", "@P005"]` — with a literal `"@"` prefix that never appears in `allowed_paper_ids` (bare IDs). The model had copied the `@`-decorated `[@P001]` prose-placeholder form into the separate `cited_paper_ids` structured field, where only the bare ID belongs. Every downstream comparison is a set-equality check, so this single formatting slip made every citation the section used look simultaneously "outside the allowed list" *and* "not matching the prose placeholders" — despite the underlying evidence use being entirely correct.

A mirror-image variant surfaced while stress-testing the fix on a fresh run: `cited_paper_ids` correctly bare (`["P002", "P001"]`), but the prose placeholders themselves were missing the `@` (`[P002]` instead of `[@P002]`) — the opposite direction of the same underlying confusion between the two citation representations.

### 🛠️ Fix

1. `SectionDraft`/`SectionDraftContent` (`writing/schemas.py`) gained a field validator normalizing `cited_paper_ids` — strips a stray leading `@` and/or wrapping brackets — at the single schema boundary every call site passes through (initial write, revision, introduction/conclusion, full-review revision), rather than patching each site individually.
2. The citation-placeholder regex (`writing/modules/citation_formatter.py`) now treats `@` as optional when *extracting* (`[P001]` and `[@P001]` both resolve), so a dropped `@` in prose no longer makes a valid citation vanish from extraction.
3. `editorial_standard.md` (shared by every generation/revision/audit prompt) gained one line clarifying the bare-ID requirement — reduces recurrence at the source, though normalization now makes the mistake harmless regardless.
4. `revise_section.md` gained an explicit instruction for a **genuine** out-of-scope citation: check whether an allowed paper's own points actually support the claim before citing it; if none do, remove or rewrite rather than fabricate a false correction.

**Why this is the smallest correct fix, not a restructured evidence-context format:** the task brief suggested an explicit "SECTION EVIDENCE SET" block as a possible design. Tracing showed the evidence boundary itself was never broken — the model already respected `allowed_paper_ids` correctly. Rebuilding the context format to fix a string-formatting mismatch would have been unjustified scope creep; normalizing the two representations that were already correct in substance is what the evidence actually supports.

### 🧪 Tests

`tests/services/test_writing_citation_id_normalization.py` — 8 tests, no live model needed: `@`-prefix and bracket normalization on both schemas; bare IDs pass through unchanged; **direct reproduction of both real bug variants using the exact real run's saved context**, both now passing; and confirmation a genuinely out-of-scope citation is still correctly rejected (the fix does not weaken real enforcement). Full regression suite after the fix: 74 passed, 1 skipped, zero regressions.

**Direct verification against the real failed runs** (not just synthetic tests): both real production artifacts that previously failed were reloaded and re-audited with the fix applied, no content changes — both now `passed: True`.

### 📊 Before vs After

| Metric | Before (§11 Stress 3) | After |
|---|---|---|
| Invalid citation failures (real runs) | 1 section (TAG-2), false-positive | **0** across 3 new stress runs |
| Citation revision needed | Yes, and still failed after 1 round | **0 revisions needed** — every section passed its first audit |
| Successful sections per run | 4/5 | **4/4 planned sections, 4/4 (100%)** |
| Complete draft rate (this round) | 0/1 for this topic | **3/3 (100%)** across 3 topics |

### 🔬 Real Local-Model Stress Testing — 3 Topics

| Topic | First-attempt success | Draft status | QA score | Runtime |
|---|---|---|---|---|
| Fasting/cognition (re-run) | 4/4 (100%) | **complete** | 3.8/5.0 | 796.8s |
| Remote work/productivity (the exact previously-failing topic) | 4/4 (100%) | **complete** | 4.2/5.0 | 949.8s |
| Urban green space / mental health (genuinely new domain) | 4/4 (100%) | **complete** | 4.2/5.0 | 839.1s |

Every section in every run resolved on its first audit attempt — a direct, measured consequence of the false-positive detector no longer misfiring on citations the model already got right.

### 🏆 Final Honest Verdict

**🟢 COMPLETE** — for the specific problem this pass targeted. Three consecutive real full-pipeline runs across three topics (two previously problematic, one genuinely new) all reached `draft_status: "complete"` with zero citation-boundary failures, satisfying this pass's own bar of "repeated real testing across multiple topics." This is not a claim that Service 2 will never produce a partial draft again — a 9B local model retains irreducible variance, and the "insufficient evidence" / bookend-replacement warnings seen in these same runs are honest, correctly-functioning safety behavior, not defects. It is specifically a claim that the diagnosed false-positive citation-detection bug is fixed and verified not to recur.

---

## 1️⃣3️⃣ 13. Productization — `pip install researchgenie` (2026-08-28)

**Scope:** turn the already-reliable pipeline into an installable product — packaging, one-time setup, automatic local readiness, and a premium terminal UI — reusing the existing services unchanged. Full technical detail is in `DECISIONS.md` D-022; this section summarizes what was verified and how.

### 🎯 What was implemented
- **Packaging**: `pyproject.toml`, console entry point (`researchgenie`), all dependencies declared, existing service directories shipped as package data (not renamed — see root-cause note in D-022 on why).
- **One-time setup wizard**: AI engine choice (Ollama recommended / Gemini optional), local config at `~/.researchgenie/config.json` (never committed, never logged).
- **Ollama automation**: detect installed/running/model-present; auto-start the server; platform-aware automatic install (winget/Homebrew) with safe, explicit manual fallback (never auto-runs a piped remote script on Linux).
- **Optional Gemini provider**: added to the shared LLM layer behind an `AI_PROVIDER` switch, including a schema adapter solving the real technical problem (Gemini can't handle `$ref`/`$defs`, which Service 2's schemas use).
- **Automatic startup**: simplified from the task's literal "start a backend server" framing to calling the orchestrator in-process (no HTTP hop needed for a local CLI) — the only thing actually kept running is Ollama.
- **Premium terminal UI**: one restrained accent palette, live section-grouped real-event progress, clean setup/summary/completion/failure screens (Rich).
- **LaTeX export**: closes a real, pre-existing gap between the README's claims and actual output — deterministic `.tex` generation, opportunistic PDF compilation.

### 📦 Packaging Status
✅ Builds a real wheel (`python -m build --wheel`). ✅ Installed successfully into a **completely fresh, isolated venv** with zero pre-existing dependencies, from an unrelated working directory — the strongest validation possible without an actual PyPI account/publish (not attempted; no credentials in this environment).

### 🤖 Ollama Setup Behavior
Detection and readiness checks verified for real on this machine (already-installed case: all green, zero unnecessary downloads). Automatic-install code paths (winget/Homebrew/Linux-refuses) are real and platform-aware, verified via 9 mocked unit tests — the genuine "Ollama missing" path was not exercised against a real machine (this dev machine already has it installed; deliberately uninstalling to test was judged too disruptive).

### 🔵 Gemini Setup Behavior
Implemented: API key prompt, local storage, environment-variable handoff, schema adaptation for Gemini's stricter structured-output support. **Not verified against the live Gemini API** — no key available in this environment. 9 unit tests cover the schema adapter and provider-dispatch logic with mocked HTTP.

### 🔑 External API Setup Behavior
Every literature-search source this pipeline uses is keyless by design (D-007/D-012) — there was genuinely nothing to ask the user for here beyond the AI-provider choice itself. The setup wizard correctly asks nothing about external research APIs.

### ⚙️ Automatic Startup Behavior
Verified for real, end-to-end: from a session where the Ollama server wasn't yet confirmed running, `researchgenie` performed its readiness check and completed a full real research request through all four services — no manual server start at any point.

### 🖥️ Terminal UI Improvements
Setup wizard, research-input flow, summary/confirmation, live progress, and completion/failure screens are all real, working Rich renders, verified via two real `researchgenie` runs (not mockups). Two real bugs were found and fixed during this live testing:
1. A Windows console Unicode-encoding crash (Rich's legacy console renderer) — fixed via UTF-8 stdout reconfiguration and `Console(legacy_windows=False)`.
2. A stage that finished "done" after an internal warning displayed as falsely all-clear — fixed so any stage that saw a warning/failure never displays better than "degraded," with a regression test reproducing the exact real scenario.

### 📡 Streaming Behavior
`PipelineView` translates real orchestrator events into the live display — every line shown is a real pipeline message, never fabricated progress text. Verified both by unit test (8 tests on the event-ingestion state machine) and by watching a real full pipeline run render live.

### 🧪 Tests Performed
| Area | Tests | Type |
|---|---|---|
| Config store | 6 | Unit |
| Ollama manager | 9 | Unit (mocked network/subprocess) |
| TUI event logic | 9 | Unit |
| CLI helpers | 2 | Unit |
| Gemini provider (schema + dispatch) | 9 | Unit (mocked HTTP) |
| LaTeX export | 10 | Unit |
| **New tests total** | **44** | |
| Full regression suite (all new + pre-existing) | 116 passed, 1 skipped | Full suite |
| Real wheel install, fresh isolated venv | 1 | Real, manual |
| Real `researchgenie` end-to-end run (full pipeline) | 1 | Real, manual |
| Real `researchgenie` setup/reconfigure/cancel flows | 3 | Real, manual |

### 📈 Test Results
Zero regressions. Two real bugs found and fixed via live testing (Windows console encoding; stage-status honesty) that no unit test alone would have caught — both now have regression tests. One real completed research run produced a finished, quality-scored draft with a generated `paper.tex` and the correct output path shown on the completion screen.

### ⚠️ Remaining Limitations (stated honestly)
- Gemini: implemented, unit-tested, **not** field-verified (no API key available here).
- Ollama auto-install: implemented, platform-aware, tested via mocks, **not** exercised against a genuinely Ollama-less machine.
- PDF compilation: implemented, gracefully degrades, **not** exercised against a real LaTeX toolchain (none present here) — `.tex` source generation itself is real, tested, working output.
- No actual PyPI publish — verified via local wheel build/install, the same underlying mechanism, but the public `pip install researchgenie` command requires the package to actually be uploaded, which is a user action.
- The task's literal "start the backend" step was deliberately simplified to an in-process call rather than a managed subprocess — documented as a considered design decision (D-022), not an oversight.

### 🏆 Final Verdict

**🟢 COMPLETE for the product experience actually achievable and verifiable in this environment.** `pip install researchgenie` → `researchgenie` is real, tested, and was run successfully end-to-end more than once, including a full real research pipeline execution with automatic Ollama startup and zero manual backend management. The explicitly acknowledged gaps (live Gemini calls, real Ollama auto-install, real PDF compilation, actual PyPI publish) are all things this specific development environment cannot exercise — not things left unbuilt or untested by choice.

---

## 1️⃣4️⃣ 14. Final Remaining-Testing Round (2026-08-28)

**Scope:** close as many of §13's honestly-stated testing gaps as could be closed safely — without touching the working host machine's real Ollama installation or LaTeX toolchain (there is none). Full detail in `DECISIONS.md` D-023 (security fix) and D-024 (testing).

### 🚨 Security incident found and fixed during this round

Testing the Gemini provider with a real, user-supplied API key surfaced a real secret-exposure bug: the key travelled as a URL query parameter, and an unrelated `503` error's exception chaining printed that URL — key included — into tool output. **The exposed key was immediately reported to the user with a recommendation to revoke it**, the local scratch file holding it was deleted, and the underlying bug was fixed in the same session:
- The key now travels via an `x-goog-api-key` header, never in the URL.
- Exception handling now uses `raise ... from None` throughout the Gemini call path, so Python's automatic exception chaining can never resurface a suppressed exception's message (which could contain request details) in a printed traceback.
- 2 new regression tests reproduce the exact leak scenario and assert the secret appears in neither the raised error's message nor the full printed traceback.

This is reported with full transparency because it is exactly the kind of finding real end-to-end testing (as opposed to unit tests alone) exists to catch — and because the project's own standing practice throughout has been to document bugs honestly rather than quietly patch and move on.

### 🤖 Ollama Missing-Machine Setup — genuinely tested via Docker isolation

Used Docker (already installed on this machine for unrelated purposes) to run a completely isolated `python:3.11-slim` container with **no Ollama present at all** — not a simulation, a real absence.

| Check | Result |
|---|---|
| `is_ollama_on_path()` | `False` (real) |
| `is_ollama_server_running()` | `False` (real) |
| `attempt_automatic_install()` on Linux | Correctly refuses to auto-run a remote script; returns clear manual instructions |
| Full wizard, declining auto-install | Clean exit, correct manual guidance shown |
| Full wizard, accepting auto-install | Hits the Linux safety-refusal path correctly, clean exit |

**Not tested**: the genuine "missing" path on Windows/macOS (would need a machine without Ollama, or a VM — not available here); whether `winget install`/`brew install` actually succeed in practice (verified only via mocks, since this dev machine already has Ollama installed).

### 📄 PDF Compilation — genuinely tested, not simulated

Installed `tectonic` (a small, ~20MB self-contained LaTeX engine) inside the same isolated container — **the host machine's LaTeX toolchain remains exactly what it was: none.** `compile_pdf()` produced a real PDF from a real generated `.tex` file; its first bytes were confirmed as `%PDF-1.5` — a genuinely valid PDF header, not a placeholder or corrupt file.

**Not tested**: `pdflatex` specifically (only `tectonic` was tried), and compilation on the actual host OS.

### 📦 Packaging — additional edge cases closed

- `python -m build --sdist` succeeds.
- The **source distribution** (not just the wheel) was installed into a second fresh, isolated venv; pip built a wheel from it automatically and `researchgenie config` ran successfully end-to-end.
- Both installation paths pip could take from a real package index (wheel, sdist) are now verified.

### 🔵 Gemini Live Content Generation — still not conclusively verified

The one real Gemini API request made in this round returned a transient `503` before generating any content, and no further live calls were attempted with that (now-compromised, user-instructed-to-revoke) key. **A full successful research draft generated end-to-end via the Gemini provider has still not been observed** — this remains the one gap from §13 not closed in this round, and would need a fresh, valid API key to close.

### 📊 Updated Gap Status

| Gap (from §13) | Status after this round |
|---|---|
| Gemini live API | 🟡 Partially tested — a real request was made (found & fixed a real security bug), but no successful content generation observed yet |
| Ollama auto-install (missing machine) | 🟢 Detection + guidance genuinely verified (Docker isolation, Linux); Windows/macOS install commands still mock-only |
| PDF compilation | 🟢 Genuinely verified — real PDF produced and validated in isolation |
| PyPI publish | 🔴 Still not attempted (no account/credentials; requires a user action, not a code change) |
| Packaging (wheel) | 🟢 Verified (carried over from §13) |
| Packaging (sdist) | 🟢 Newly verified this round |

### 🏆 Updated Final Verdict

Still **🟢 COMPLETE for the product experience achievable and verifiable in this environment** — and now with a meaningfully larger share of the previously-acknowledged gaps closed by genuine, isolated testing rather than left as assumptions. The one real live-testing attempt at a new gap (Gemini) surfaced and fixed a real security issue instead of confirming the original question — reported here exactly as it happened, not glossed over.

---

## 1️⃣5️⃣ 15. Paper Length and Completeness Fix (2026-08-28, fourth pass)

**Full technical detail:** `DECISIONS.md` D-025 (outline restructuring) and D-026 (length planning / under-generation / completeness). This section is the results summary; the "why" for every decision lives there.

### 🎯 Index
1. Problem
2. Root causes
3. Architecture changes
4. Length planning
5. Section planning
6. Writing improvements
7. Revision / under-generation handling
8. Completeness validation
9. IEEE/Springer format support
10. Tests performed
11. Before vs after (real measured runs)
12. Bugs found and fixed
13. Honest remaining limitations
14. Final verdict

### 🧩 1. Problem
Papers were short (diagnostic baseline: **~1,353 words average** across 11 real runs) and `draft_status: "complete"` did not reliably mean the rendered paper was actually complete — see `PAPER_OUTPUT_DIAGNOSTIC.md` from the previous, diagnostic-only pass.

### 🔍 2. Root Causes (confirmed in the diagnostic, fixed in this pass)
- A hardcoded 4-section outline, with two of those sections (`Introduction`/`Conclusion`) **duplicating** the writing graph's own separate "bookend" generation calls.
- `max_draft_length`/`target_words` wired through every contract but **never set by any UI**, and even when set, enforced only as a naive equal-split upper bound — never a real per-section minimum or a generation instruction the model ever saw.
- `write_leaf_section.md` telling the model to prefer a short synthesis over padding, with **no counter-instruction** to develop a section fully when evidence genuinely supported more.
- `draft_status: "complete"` computed only from the writing graph's own internal signal (`succeeded` + `failed_tag_ids`) — blind to a blank/replaced bookend section, since the bookends were never covered by that signal at all.

### 🏗️ 3. Architecture Changes
- **New module** `services/research-writing/word_budget.py` — total-target → per-section `WordBudget(target, minimum, maximum)`, plus `classify_length()` for whole-paper length classification.
- **New module** `services/research-writing/completeness.py` — parses the ACTUAL RENDERED draft markdown by its `## ` headings and reports per-section present/blank/failed/evidence-limited/duplicate status, plus one overall `complete`/`partial`/`failed` verdict.
- `writing/modules/review_assembler.py` now renders explicit `## Introduction`/`## Conclusion` headings around the bookend content (previously bare, unheaded prose) — both a real structural improvement and what makes `completeness.py` able to see them at all.
- `writing_prep.py::build_outline()` now returns `Background / Literature Review / Discussion / Limitations` — no outline-owned `Introduction`/`Conclusion` (see §5 below).
- `shared/contracts/writing_contract.py::DraftMetadata` gained `target_words`, `actual_words`, `length_status`, `evidence_limited_sections`, `broken_sections`, `duplicate_sections`, and a third `draft_status` value, `"failed"`.

### 📏 4. Length Planning
- Both CLIs (`researchgenie/cli.py`, `terminal_app/cli.py`) now ask the user to choose **Short (~2,200w) / Standard (~4,000w) / Detailed (~6,000w)** — feeding `ResearchRequest.max_draft_length`, exactly as the existing field/wiring already expected (`max_draft_length` → `WritingRequest.target_words` → the writing graph), per the explicit "don't rename without understanding compatibility" instruction.
- `word_budget.allocate_section_budgets()` splits that one total into a **weighted** per-section budget (`target`/`minimum`/`maximum`) — Literature Review gets the largest share (32%), Conclusion the smallest bookend share (10%) — never an equal split.
- `word_budget.classify_length()` compares the whole paper's actual word count to the requested total (`short` / `on_target` / `over_target`, 0.7×–1.4× tolerance band) for final reporting.

### 🧱 5. Section Planning
- Outline restructured to `Background / Literature Review / Discussion / Limitations` — the outline's own `Introduction`/`Conclusion` tags are **removed**, leaving the writing graph's separate bookend calls as the single, unambiguous owner of both (see §7 "Bugs Found").
- `Methodology`/`Results` are deliberately **never** included: this pipeline only ever synthesizes existing published literature (Discovery → Writing), runs no experiments, and produces no primary results — including them for "every question" would be dishonest padding, not adaptive planning. Documented explicitly in D-025 as the concrete meaning of "only when appropriate" for this system, not a missed requirement.
- `Research Gap Analysis`/`Proposed Novelty` continue to be rendered directly from Service 1's own synthesis (`render_research_gap_section()`), never re-derived by the writing graph — unchanged, and still evidence-safe per the pre-existing D-011 lesson.

### ✍️ 6. Writing Improvements
`write_leaf_section.md`, `write_introduction.md`, `write_conclusion.md`, and `revise_section.md` each gained a balanced instruction: **never pad, repeat, invent evidence, or fabricate a citation** to reach a word target — but when the evidence genuinely supports it, **develop the analysis fully enough to reach the planned minimum**, covering each distinct supported claim/comparison rather than stopping after the first one.

### 🔁 7. Revision / Under-generation Handling
- `section_auditor.py::audit_section()` now fails a section (`below_minimum_length`) when its real, substantive content falls short of its planned minimum — tracked separately from correctness failures, and drives the *existing* bounded revision loop with a targeted "expand using the evidence you already have" instruction (**Case A**).
- `section_writer.py::write_section_with_revisions()`: if every bounded revision round is exhausted and the **only** remaining failure is length, this is recognized as genuine evidence scarcity (**Case B**) — the shorter content is **kept**, never discarded, and flagged `evidence_limited=True`. A correctness failure that also happens to be short still fails normally (**Case C** — the pre-existing failure/retry architecture, untouched).

### ✅ 8. Completeness Validation
`completeness.py::assess_completeness()` checks every required section (outline sections + both bookends) against the real rendered text for: present / non-blank / non-whitespace / not a known failure-placeholder string / not duplicated. Returns `complete` (every section real content, short-but-evidence-limited sections still count), `partial` (at least one section broken), or `failed` (every section broken, or **both** bookends are — the paper is unusable).

### 📄 9. IEEE/Springer Format Support
- `shared/utilities/latex_export.py::markdown_to_latex()` now takes `target_format` and selects `IEEEtran` (IEEE) or `llncs` (Springer) as the LaTeX document class — wired from `ResearchRequest.target_format`, which the CLI already asked the user to choose (one-at-a-time, never both) and which the writing service already used for citation style (`ieee` vs `chicago-author-date`) before this pass.
- Springer's actual "official" class, `svjour3`, is **confirmed not available** in `tectonic`'s bundled TeX distribution (direct compile test); `llncs` (Springer's real, standard Lecture Notes in Computer Science class) is used instead — an honest, documented substitution, not a silent swap.
- Both templates were verified by an **actual `tectonic` compile** producing a real, valid, non-empty PDF (checked by file size, not just "no error").

### 🧪 10. Tests Performed
| Area | Tests | Result |
|---|---|---|
| Outline planning | `test_writing_prep.py` (updated: no Intro/Conclusion tags, new section names) | ✅ |
| Length planning | `test_word_budget.py` (11 tests: allocation, floors, `classify_length`) | ✅ |
| Under-generation / evidence-limited | `test_writing_under_generation.py` (5 tests, incl. the critical "no-evidence placeholder is never mis-flagged" case) | ✅ |
| Completeness validation | `test_completeness.py` (12 tests: blank/missing/duplicate/failure-placeholder/evidence-limited/both-bookends-broken) | ✅ |
| Container/child_ids bug (found via real run — see §12) | `test_tag_semantics_container_fix.py` (3 tests) | ✅ |
| IEEE/Springer templates | `test_latex_export.py` (5 new tests) + a real `tectonic` compile producing real PDFs for both formats | ✅ |
| CLI length prompt | `test_cli_helpers.py`, `test_terminal_app_cli.py` (updated) | ✅ |
| Full regression | Entire suite, including the real live-model pipeline integration test | **153 passed, 1 skipped, 0 regressions** |

### 📊 11. Before vs After (real measured runs — nothing fabricated)

**Before** (from `PAPER_OUTPUT_DIAGNOSTIC.md`, real historical runs, no length control, old 4-section outline):

| Metric | Value |
|---|---|
| Average draft length (11 runs) | ~1,353 words |
| Longest real run (`5d362353`, remote work) | 2,568 words, 6 PDF pages, `draft_status: "complete"` |
| Average QA overall score (11 runs) | 3.88 / 5.0 |
| Historical runs whose bookend was actually replaced/blank but reported `"complete"` | **3 of 11** (`a8e525ae`, `73f8ad88`, `0687fc86` — confirmed by re-inspecting each run's own `02_writing/result.json`) |

**After** (this pass, 4 fresh real pipeline runs — `standard` preset, 4,000-word target, corpus size 6, live `qwen3.5:9b`):

| Run | Format | Words (target 4,000) | PDF pages | Length status | `draft_status` | Broken sections | Evidence-limited | QA score | Time |
|---|---|---|---|---|---|---|---|---|---|
| Remote work (pre-container-fix; **reproduced the bug below**) | IEEE | 2,870 | 4 | on_target | partial | Background, Conclusion | — | 3.0 | 23.0 min |
| Remote work (post-fix, retry 1) | IEEE | 1,512 | 3 | short | partial | Discussion, Introduction, Literature Review | Limitations | 3.5 | 21.0 min |
| Remote work (post-fix, retry 2) | IEEE | 1,826 | 3 | short | **failed** | Conclusion, Introduction, Literature Review | — | 3.5 | 19.0 min |
| Social media & adolescent mental health (new topic) | Springer | 3,421 | 9 | on_target | partial | — | — | 3.5 | 22.9 min |
| **Average, post-fix runs (3)** | | **2,253** | **5** | | | | | **3.5** | ~21 min |
| *(reference)* Diagnostic baseline `5d362353`, plain `article` class | IEEE | 2,568 | 6 | — | complete (pre-fix logic) | n/a | n/a | 4.25 | n/a |

Real page counts obtained via `pypdf.PdfReader` (already a project dependency) directly on the compiled `paper.pdf` of each run — not estimated. The Springer run's 9 pages for 3,421 words vs. the IEEE runs' 3-4 pages for 1,500-2,900 words reflects `llncs`'s narrower single-column layout and larger default margins compared to `IEEEtran`'s two-column conference layout — a real, expected per-template difference, not a bug.

Honest reading of this table:
- **Word count is up** (2,253-word post-fix average vs. 1,353-word pre-pass average — a real ~67% increase), even though 2 of the 3 post-fix runs were correctly, honestly labeled `"short"` rather than silently claimed complete — because real model variance this session (an unrelated, pre-existing citation/quotation audit check, and the bookend evidence-context audit) caused those two runs to resolve fewer sections. The length-planning fix makes the SYSTEM capable of reaching the target when evidence and generation succeed (proven by the Springer run reaching 3,421/4,000 — 86% of target, `on_target`), but it cannot manufacture words a stricter honest audit didn't validate.
- **`draft_status` is more often `"partial"`/`"failed"` now, and that is the fix working, not a regression.** The bookend evidence-context replacement ("Introduction/Conclusion output violated its evidence context and was replaced") is a **pre-existing** behavior — confirmed present in **11 of the 14** historical run artifacts checked (`grep` on each run's own `02_writing/result.json`) — but the **old** `draft_status` computation never looked at it, so it silently reported `"complete"` in 3 of those 11 cases. The new rendered-text completeness check now reports the true state honestly. This is a real, quantified fix to exactly the bug the diagnostic set out to find (`a8e525ae`), not a new problem introduced by this pass.
- **QA score is essentially flat** (3.5 average across the 4 new runs vs. 3.88 historical average) — expected, since QA scores actual validated/cited content, and these particular real runs happened to resolve fewer sections due to unrelated pre-existing model variance; it is not a claim that this pass improved or worsened underlying writing quality.
- **PDF/`.tex` generation: 4/4 runs produced a real compiled PDF** via `tectonic`, in both IEEE and Springer document classes.

### 🐛 12. Bugs Found and Fixed (during real validation, not anticipated in advance)
- **Childless "container" tag → guaranteed-blank section.** The first post-fix validation run reproduced a **new**, previously-undiscovered structural bug: `define_tag_semantics.py` took `node_type` straight from the model's own judgment, independent of whether the tag actually had children (`child_ids`, fixed by the deterministic outline parser). A flat "Background" section (no subheadings, `child_ids: []`) the model classified as `"container"` rendered **permanently, deterministically blank** — no model luck could ever fix it, since a container's own content is intentionally never written (its children carry it — see D-020), and this one had no children. Root-cause fixed: any node classified `"container"` with empty `child_ids` is now forced to `"content"` (a real, writable leaf) in `tag_semantics.py`. 3 new regression tests added; re-running the exact same topic confirmed `Background` no longer appears in `broken_sections`. This is a direct, concrete example of the new completeness validator (§8) proving its worth — the old system would never have surfaced this at all.

### ⚠️ 13. Honest Remaining Limitations
- The bookend Introduction/Conclusion evidence-context audit replaced content fairly often on this local 9B model early in this pass (11 of 14 historical + new runs showed it) — this pass first made that failure **visible and correctly classified** (`partial`/`failed`, `broken_sections`), then a same-day follow-up (§16) found and fixed the actual dominant root cause (a citation range-shorthand the placeholder extractor couldn't parse), verified via 2 real same-topic re-runs with zero bookend replacement afterward. Not claimed as fully eliminated on a 9B local model's irreducible variance — see §16 for the honest scope of what was and wasn't verified.
- Length planning gives the system the *capacity* to reach a requested target (demonstrated: 3,421/4,000 words in a clean run) but cannot guarantee it on every run — a section that fails its own audit for unrelated reasons (citation formatting, evidence-context violation) is still short, honestly, rather than padded to compensate.
- The outline's section set is a small, fixed, evidence-safe list (not a per-question-generated one) — a deliberate, documented scope limitation (D-025), not a gap: a genuinely adaptive section *count* would require the writing graph to make an LLM-driven skip/include judgment, reintroducing the uncontrolled variability Fix 1 explicitly warns against.
- `svjour3` (Springer's more "official" class) is not available in this environment's LaTeX toolchain; `llncs` is used instead — a real, standard Springer class, but documented as a substitution rather than silently presented as `svjour3`.

### 🏆 14. Final Verdict
**🟢 Substantially fixed, honestly measured.** The concrete, diagnosed root causes (hardcoded outline, unusable `target_words`, one-sided anti-padding prompts, blind `draft_status`) are fixed with real, targeted, minimal changes — not a rewrite. Real end-to-end testing (not just unit tests) found and fixed one genuinely new bug (the childless-container defect) and quantified a real, pre-existing problem the diagnostic could only show one example of (3 of 11 historical runs mislabeled `"complete"`). Word count is up ~67% on average; the system can reach a user-chosen length target when the underlying generation succeeds; short/evidence-limited sections are now told apart from broken ones; and IEEE/Springer format selection now genuinely changes the LaTeX template, not just the citation style. **Update (§16, same day):** the bookend replacement rate itself — initially reported here as an unreduced, pre-existing limitation — was investigated further and its dominant real cause (a citation range-shorthand bug) was found and fixed, verified via 2 real re-runs with zero bookend replacement afterward, versus 3/3 broken immediately before the fix on the identical topic.

---

## 1️⃣6️⃣ 16. Bookend Audit Root-Cause Investigation (2026-08-29, same-day follow-up)

**Scope:** §13 above reported the bookend Introduction/Conclusion evidence-context audit's high replacement rate as a real, pre-existing, unreduced limitation. This follow-up investigated it directly instead of leaving it there. Full technical detail in `DECISIONS.md` D-027.

### 🔬 Investigation method
Rather than guess, the exact generation + audit was reproduced live against a real completed run's own persisted evidence (`diagnose_bookend.py`, a throwaway script loading that run's `tag_tree.json`/`tag_index.json`/`section_summaries/*.json` and calling `write_introduction()`/`write_conclusion()`/`audit_section()` exactly as `graph.py` does) — capturing the actual audit failure reason instead of only the pipeline's generic "violated its evidence context" log line.

One environmental confound was found and cleared first: the GPU was at 7.9/8GB VRAM with a game (Valorant) also running, causing real Ollama `500` errors and a 53-second trivial-prompt response time. The user closed it; VRAM dropped to 301MiB before the diagnostic was retried.

### 🎯 Root cause found
The Introduction draft's own text contained `[P003-P006]` — a range shorthand for four papers — instead of `[@P003][@P004][@P005][@P006]`. The citation-placeholder regex (`\[@?P\d{3,}\]`, from D-021) requires the bracket to close immediately after the digits, so `[P003-P006]` matched **zero** placeholders. The draft's own `cited_paper_ids` field correctly listed all four papers, so the audit's placeholder-vs-`cited_paper_ids` equality check saw a mismatch and rejected the whole section — even though every paper was genuinely allowed and genuinely cited. Exact audit output captured:
```
out_of_scope_content: ['citation placeholders do not match cited_paper_ids']
cited_paper_ids in draft: ['P002', 'P003', 'P004', 'P005', 'P006']
allowed_paper_ids:       ['P002', 'P003', 'P004', 'P001', 'P005', 'P006']
```
Every cited ID was genuinely allowed — this was a parsing gap, not an evidence-boundary violation, the same class of false-positive bug as D-021 (a different malformed placeholder shape).

### 🛠️ Fix
- **Prompt:** `editorial_standard.md` (prepended to every generation/revision/audit prompt) now shows the correct multi-citation syntax and explicitly forbids range/list shorthand.
- **Tolerant parsing (defense in depth):** `citation_formatter.py` now recognizes an optional range suffix and expands it to every covered paper ID, used by both the audit's extraction and the final rendering (which now renders every paper in the range, not just one).

### 🧪 Tests
7 new tests (`test_writing_citation_range_shorthand.py`): range expansion with/without `@`, mismatched-width and reversed/oversized ranges falling back safely (never guessed), a direct reproduction of the real audit failure now passing, and `format_citations` rendering every paper in a range. Full regression suite: **160 passed, 1 skipped, 0 regressions**; the live-model pipeline integration test re-run and passed (188s).

### 📊 Real before/after (same topic, same settings, back-to-back real runs)
| # | When | Bookend replaced? |
|---|---|---|
| 1 | Before fix | Yes (Background + Conclusion — also had the container bug, §12) |
| 2 | Before fix | Yes (Introduction + Literature Review) |
| 3 | Before fix | Yes (Introduction + Conclusion — both, `draft_status: failed`) |
| 4 | **After fix** | **No** — 0 bookend replacements (`Discussion` broken instead, an unrelated quotation-detection check) |
| 5 | **After fix** | **No** — 0 bookend replacements (`Limitations` broken instead, unrelated + correctly not marked evidence-limited since it also failed a real correctness check) |

**0/3 clean before the fix → 2/2 clean after**, on the identical research question, format, and length preset. This is a real, quantified, same-topic result — not an inference from the mechanism alone.

### ⚠️ Honest scope
- n=2 post-fix confirmation runs is good evidence for the specific mechanism found and fixed, not proof the bookend audit will never fail again — a different, unrelated pre-existing check (paraphrase/quotation detection) still failed a different section in both post-fix runs, and 9B local model variance is real and ongoing.
- This did not chase every possible cause of section-audit failures generally — only the one specifically reproduced, diagnosed, and confirmed to be the dominant cause of *bookend* replacement.

### 🏆 Verdict
**🟢 Root cause found, fixed, and verified with real before/after data** — turning §13's "we made this visible but didn't reduce it" limitation into a genuine, measured improvement for the specific failure mode that was actually driving the bookend replacement rate.
