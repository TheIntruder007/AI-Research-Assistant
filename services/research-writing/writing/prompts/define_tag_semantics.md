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

### Ancestor/descendant ownership (not just sibling separation)

Every tag with children (including `TAG-ROOT`) must be written so its `include_when` does
NOT also cover what a child tag already owns. Restating the full review question as an
ancestor's `include_when` is wrong even when every piece of evidence is technically "relevant
to the question" — that is true of every tag in the tree by construction, so it gives no
assignment guidance and causes the same evidence to be claimed by both a parent and a child.

For every tag that has children:

- Write its `include_when` to cover ONLY evidence that is relevant to the parent's scope but
  does not fit any single child's more specific scope — genuine cross-cutting synthesis,
  definitional framing, or content spanning multiple children at once. If you cannot describe
  such content concretely, `include_when` may be a short list focused on that synthesis role
  rather than a restatement of the overall topic.
- Add at least one `exclude_when` entry per child stating that content matching that child's
  scope belongs to the child, not this tag (e.g. "Findings specific to the Literature Review's
  scope belong there, not here").

For a leaf/content tag, `exclude_when` must distinguish it from its siblings AND explicitly
state that anything broader belonging to an ancestor's synthesis role (rather than this tag's
specific domain) belongs to that ancestor instead — ownership is a two-way boundary.

The deepest matching tag always owns a given piece of evidence; an ancestor may only claim
evidence when no child's scope fits it at all.
