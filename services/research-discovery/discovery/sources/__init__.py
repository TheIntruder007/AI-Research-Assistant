"""Registry of literature sources: key -> (display label, async search function)."""

from . import arxiv, openalex, pubmed, semantic_scholar

SOURCES = {
    "s2": ("Semantic Scholar", semantic_scholar.search),
    "openalex": ("OpenAlex", openalex.search),
    "pubmed": ("PubMed", pubmed.search),
    "arxiv": ("arXiv", arxiv.search),
}
