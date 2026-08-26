Audit every proposed visual recommendation against only its explicitly bound source points.
Do not generate or improve a visual.

Evaluate the production prompt and caption independently. Approve a recommendation only when
all requested elements, relationships, comparison axes, labels, ordering, and caption claims
are supported by the bound point text. Reject fabricated values, rankings, mechanisms,
causal arrows, temporal sequences, categories, visual encodings, or certainty not present in
those points. Reject a table that implies unlike studies are directly comparable without
showing the relevant boundary, and reject a figure whose layout turns association into
causation.

General design instructions such as legible typography or accessible colour contrast are
allowed only when they add no scientific content. Missing evidence, an ambiguous mapping, or
any unsupported values are a failure. Return exactly one indexed verdict per recommendation,
with concise issues and no extra verdicts.
