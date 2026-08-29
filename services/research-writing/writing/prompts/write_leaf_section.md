Write only the requested literature-review section in the supplied `output_language`.

### Evidence boundary

Use `direct_points` as the section's primary evidence. Use `ancestor_context` only to
establish indispensable background, never as a substitute for section-specific evidence.
Do not use sibling topics, `prohibited_topics`, outside knowledge, or any paper or point
outside the allowlists. Preserve the supplied distinctions among content type, stance, and
certainty. Do not quote sources or cite page numbers.

### Section argument

Infer the section's analytical task from its title, complete outline path, and evidence.
Develop a coherent answer rather than a catalogue of papers. Organize paragraphs around one
or more evidence-backed dimensions, such as consensus versus disagreement, mechanism,
method, population, context, scale, or boundary condition. Use multiple dimensions only when
the evidence genuinely supports them. When evidence is sparse, prefer a short single-axis
synthesis to padding or an invented comparison. Compare papers within supported dimensions
and explain why differences matter. Do not invent a reason for disagreement when the
supplied points do not establish one; state the unresolved contrast instead.

Open with the section's substantive problem or best-supported synthesis, not a generic
importance claim. Conclude with the inference that the evidence warrants and, only when
supported, the precise unresolved issue that motivates the next topic. Do not add a heading,
repeat the section title, or refer to yourself, the prompt, the evidence list, or "this
section".

Render citations only as supplied `[@P001]` placeholders. Place each placeholder next to the
claim it supports and keep it synchronized with `cited_paper_ids`. Return polished prose, a
compact child-safe analytical summary, and complete `cited_paper_ids` and `used_point_ids`.

### Planned length

If `target_words` (with `min_words`/`max_words`) is present in the supplied context, it is
this section's planned scope within the overall paper — not a strict rule to hit exactly, but
a real target. Never pad, repeat a claim, invent evidence, or fabricate a citation to reach
it. But when the supplied evidence genuinely supports it, develop the analysis fully enough to
reach at least `min_words`: cover each distinct supported claim or comparison the evidence
allows, with its reasoning and significance, rather than stopping after the first one or two
sentences once the section's core point has been stated. If the evidence is too thin to
reasonably reach `min_words` without repetition or invention, write only what is genuinely
supported — a shorter, fully evidence-grounded section is always correct over a padded one.
