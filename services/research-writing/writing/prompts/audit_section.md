Audit the supplied section against its exact structured writing context. Do not rewrite it.

Evaluate in this order:

1. **Support:** identify factual or interpretive claims that cannot be traced to the allowed
   points, citations attached to claims they do not support, causal inflation, altered
   populations or conditions, and certainty stronger than the evidence.
2. **Balance:** identify omitted important contradictory or limiting evidence available in
   the context, false consensus, and alternative explanations dismissed without support.
3. **Scope:** identify sibling-topic leakage, use of prohibited topics, over-broad framing,
   and duplicated parent or child detail.
4. **Synthesis:** identify paper-by-paper narration, comparisons that ignore meaningful
   methodological differences, unexplained contradictions, and paragraphs that report facts
   without an analytical inference.
5. **Exposition:** identify broken claim-evidence-interpretation flow, vague referents,
   inconsistent terminology, generic openings, unnecessary jargon, repetition, and
   transitions that announce sequence rather than scientific logic.

Treat allowed paper and point lists as hard limits. Do not penalize a section for omitting a
claim that the supplied evidence cannot support. Map findings to the output schema as follows:

- unsupported, inflated, or miscalibrated claims -> `unsupported_claims`;
- sibling leakage, prohibited topics, or over-broad framing -> `out_of_scope_content`;
- cited papers outside the allowlist -> `invalid_paper_ids`;
- omitted contradictory, limiting, or otherwise essential supplied evidence ->
  `missing_key_points`;
- repeated parent or child material -> `duplicated_child_content`;
- synthesis, paragraph logic, terminology, clarity, jargon, repetition, and transition
  problems -> precise `revision_instructions` only, unless they also meet a category above.

Every reported issue must have a precise, executable revision instruction that can be
completed inside the existing evidence boundary. Pass only when no substantive issue remains.
