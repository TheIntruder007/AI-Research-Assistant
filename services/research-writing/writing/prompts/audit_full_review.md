Audit the complete review against its review question, audited section summaries, and
supplied section content. Do not rewrite it.

Assess whether the article functions as one authoritative and balanced synthesis:

- the introduction defines the actual scope, central problem, and organizing logic of the
  completed body without unsupported framing;
- each section has a distinct analytical purpose and advances the review question;
- parent-child transitions express scientific relationships rather than a table of contents;
- terminology, causal language, evidence strength, and treatment of the same paper remain
  consistent across sections;
- consensus and disagreement are represented fairly, with credible contrary evidence and
  boundary conditions neither hidden nor exaggerated;
- repetition is removed unless a concept is deliberately advanced at a new analytical level;
- the conclusion answers the review question, distinguishes established, conditional, and
  unknown claims, and derives any outlook from body-supported gaps;
- the prose remains accessible to scientists outside the immediate specialty and avoids
  jargon, hype, generic importance claims, and paper-by-paper narration.

Do not request new literature, data, or outline headings. Return targeted revision
instructions that identify the affected section and the exact intellectual repair. Pass only
when no substantive coherence, balance, support, or exposition issue remains.

Optionally return a visual recommendation when a figure or table would materially clarify
evidence already present in one section. Do not generate an image, table, Markdown image
link, or fabricated data. A visual is justified only when it compresses a real comparison,
mechanism, taxonomy, sequence, or evidence boundary better than prose.

Each recommendation must use a `tag_id` from the supplied section summaries and include:

- `visual_type`: `figure` or `table`;
- a self-contained production `prompt` specifying the analytical message, elements,
  relationships, labels, ordering, and exclusions needed for later human creation;
- a concise, publication-ready `caption` that states what the visual shows without making a
  stronger claim than the evidence;
- `placement_after`: one exact sentence copied from that tag's supplied section content;
- one or more `source_point_ids` already used by that section.

For a table, define meaningful rows, columns, comparison axes, and how missing or
non-comparable evidence should be represented. Recommend no decorative visuals. Visual
recommendations are optional enhancements: they are not semantic issues, must not enter
`revision_instructions`, and must not make an otherwise sound review fail.
