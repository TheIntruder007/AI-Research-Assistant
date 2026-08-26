Define the semantics of an immutable, user-authored literature-review outline.

Return exactly one semantic record for every supplied tag, in order. Never create, delete,
merge, rename, reorder, or renumber tags. `TAG-ROOT` (the first tag) MUST always have
node_type `root` — never `container`, `content`, or `mixed`. No other tag may use `root`.

When `outline_context` is supplied, treat its bullets and numbered notes as semantic
guidance for the nearest preceding Markdown heading. These notes refine inclusion and
exclusion boundaries but never create, remove, rename, or reorder structural tags.

Interpret each heading from the review question and its complete outline path. Give every tag
a distinct intellectual role: specify the scientific question, object, process, comparison,
scale, or boundary it owns and how it differs from its siblings. A parent scope must cover
all child scopes without collapsing their distinctions. Preserve container tags even when
they will not receive detailed prose.

For each tag provide:

- a concise normalized label using stable scientific terminology;
- a path-aware description of the tag's analytical purpose, not merely a paraphrase of its
  title;
- concrete `include_when` rules describing evidence that belongs;
- concrete `exclude_when` rules that separate near-neighbour and sibling material;
- the correct node type: `root`, `container`, `content`, or `mixed`.

Do not add domain facts absent from the review question and outline. The definitions should
make later evidence assignment reproducible and minimize overlap between branches.
