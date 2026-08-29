Write the review conclusion in the supplied `output_language` only from audited section
summaries.

Answer the review question directly. Synthesize the body into three levels where the
evidence permits: what is robustly supported, what remains conditional or contested, and
what cannot yet be concluded. Explain the main boundary conditions or sources of uncertainty
without repeating each section in order.

End with a disciplined outlook, not a generic wish list. Derive priorities only from
limitations, contradictions, or future directions already present in the summaries. Rank or
connect those priorities by the bottleneck they would resolve, and formulate unresolved
issues as answerable scientific questions when the evidence supports doing so. Separate
evidence-backed implications from speculation and do not promise breakthroughs.

Introduce no new paper, point, mechanism, example, recommendation, or factual claim. Do not
quote sources, cite page numbers, use headings, or mention "this review". Render citations
only as supplied `[@P001]` placeholders. Return polished prose and complete
`cited_paper_ids` and `used_point_ids`.

If `target_words`/`min_words` is present in the supplied context, use it as this section's
planned scope — develop the three-level synthesis above fully enough to reach it when the
summaries genuinely support that much content, but never pad, repeat, or introduce anything
not already present in the summaries to reach a word count.

If `introduction_already_written` is present, it is this review's actual, already-published
Introduction — the reader has just read it. Do not restate its sentences, its framing of the
problem, or its specific claims/statistics in similar words: that is the Introduction's job,
not the Conclusion's. The Conclusion's distinct job is the retrospective judgment the
Introduction could not yet make — what the completed body actually established, what remains
contested, and what still cannot be concluded. If a fact from the Introduction is genuinely
needed to state a final judgment, reference its significance rather than re-describing it.
A conclusion that could be produced without ever having read the body sections has failed
this task, regardless of word count.
