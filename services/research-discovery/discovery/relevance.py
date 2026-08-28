"""Deterministic relevance screening for Research Discovery candidate papers.

Root cause this addresses (see DECISIONS.md D-018): the original rank()
function had no signal at all comparing a candidate paper to the actual
research question — it scored purely on abstract presence, citation count,
recency, and the paper's position in the search engine's own results. A
paper could rank highly purely by being recent/well-cited/abstract-bearing
even if it shared nothing topically with the question, because query
generation deliberately favors recall over precision ("broad terms beat
narrow exact phrases" — see analysis.py's QUERYGEN_SYSTEM) and no downstream
step ever re-checked the results against the question.

This module is the missing check: a fast, deterministic (no extra LLM call)
hard relevance gate, plus a relevance score that dominates ranking among
papers that pass it. Deterministic by design — a token/phrase-overlap check
is cheap and, per the project's own hardware constraints, sufficient to
catch the failure mode actually observed (zero topical overlap), without
adding another slow local-model call to every candidate paper.

Known limitation, documented rather than hidden: pure token/phrase overlap
cannot distinguish two genuinely different meanings that happen to share a
word (e.g. "fasting" in a religious-practice paper vs. a metabolic-health
paper) — closing that gap fully would need embeddings or an LLM judgment
call per candidate, which is deliberately out of scope here per the
project's "don't require expensive LLM calls if deterministic checks are
sufficient" rule. What this module guarantees is narrower and matches the
actual bug: a paper sharing *no* meaningful terms or phrases with the
research topic can no longer enter the corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Paper

# Generic / academic-boilerplate words that appear in almost any research
# question or paper and therefore carry no topic-discriminating signal.
_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "for", "and", "or", "to", "with", "from",
    "by", "is", "are", "was", "were", "be", "been", "being", "this", "that",
    "these", "those", "as", "at", "it", "its", "their", "our", "we", "study",
    "studies", "research", "effect", "effects", "analysis", "review", "paper",
    "using", "use", "based", "approach", "among", "between", "across", "new",
    "novel", "toward", "towards", "role", "impact", "impacts", "investigating",
    "investigation", "examining", "examination", "assessment", "evaluating",
    "evaluation", "understanding", "exploring", "exploration", "what", "how",
    "does", "do", "can", "into", "about", "related", "relationship",
}

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]{2,}")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _significant_unigrams(text: str) -> set[str]:
    return {t for t in _tokens(text) if t not in _STOPWORDS and len(t) > 3}


def _bigrams(text: str) -> set[str]:
    toks = _tokens(text)
    return {
        f"{a} {b}" for a, b in zip(toks, toks[1:])
        if a not in _STOPWORDS and b not in _STOPWORDS
    }


@dataclass
class TopicProfile:
    """The topic a paper is screened against: everything we know about what
    the researcher is actually asking for, before any single paper is read."""
    unigrams: set[str] = field(default_factory=set)
    bigrams: set[str] = field(default_factory=set)
    # The most authoritative terms — explicit user-supplied keywords and the
    # LLM's own distilled keyword_query — weighted more heavily than terms
    # that only appear in the raw, more loosely worded research question.
    priority_unigrams: set[str] = field(default_factory=set)


def build_topic_profile(
    question: str, keyword_query: str = "", keywords: list[str] | None = None,
) -> TopicProfile:
    keywords = keywords or []
    keyword_text = " ".join(keywords)
    all_text = " ".join([question, keyword_query, keyword_text])
    priority_text = " ".join([keyword_query, keyword_text])
    return TopicProfile(
        unigrams=_significant_unigrams(all_text),
        bigrams=_bigrams(all_text),
        priority_unigrams=_significant_unigrams(priority_text),
    )


# Below this score, and with no shared meaningful phrase, a paper is rejected
# outright rather than merely ranked low — this is the hard gate.
HARD_REJECT_THRESHOLD = 0.12
_BIGRAM_BONUS = 0.35       # a shared meaningful two-word phrase is a strong signal
_MAX_BIGRAM_BONUS_HITS = 2
_PRIORITY_BONUS_WEIGHT = 0.15


@dataclass
class RelevanceResult:
    score: float
    decision: str  # "accepted" | "rejected"
    reason: str
    matched_terms: list[str]

    def to_dict(self, paper_id: int) -> dict:
        return {
            "paper_id": paper_id,
            "relevance_score": self.score,
            "decision": self.decision,
            "reason": self.reason,
        }


def score_paper(paper: Paper, profile: TopicProfile) -> RelevanceResult:
    if not profile.unigrams:
        # Degenerate/empty topic profile (e.g. an extremely short question) —
        # there is nothing to screen against, so don't block the pipeline.
        return RelevanceResult(1.0, "accepted", "No topic terms available to screen against.", [])

    text = f"{paper.title} {paper.abstract or ''} {paper.venue or ''}"
    paper_unigrams = _significant_unigrams(text)
    paper_bigrams = _bigrams(text)

    matched_unigrams = profile.unigrams & paper_unigrams
    matched_priority = profile.priority_unigrams & paper_unigrams
    matched_bigrams = profile.bigrams & paper_bigrams

    score = len(matched_unigrams) / len(profile.unigrams)
    score += min(len(matched_bigrams), _MAX_BIGRAM_BONUS_HITS) * _BIGRAM_BONUS
    if profile.priority_unigrams:
        score += (len(matched_priority) / len(profile.priority_unigrams)) * _PRIORITY_BONUS_WEIGHT
    score = min(round(score, 3), 1.0)

    matched_terms = sorted(matched_bigrams) + sorted(matched_unigrams)

    if score < HARD_REJECT_THRESHOLD and not matched_bigrams:
        reason = "Shares no meaningful terms or phrases with the research topic."
        return RelevanceResult(score, "rejected", reason, matched_terms)

    reason = f"Overlaps the research topic on: {', '.join(matched_terms[:6]) or 'general terms'}."
    return RelevanceResult(score, "accepted", reason, matched_terms)


def screen_papers(papers: list[Paper], profile: TopicProfile) -> tuple[list[Paper], list[Paper]]:
    """Scores every paper against the topic profile, writes the result onto
    each Paper (relevance_score/relevance_decision/relevance_reason), and
    returns (accepted, rejected)."""
    accepted, rejected = [], []
    for p in papers:
        result = score_paper(p, profile)
        p.relevance_score = result.score
        p.relevance_decision = result.decision
        p.relevance_reason = result.reason
        (accepted if result.decision == "accepted" else rejected).append(p)
    return accepted, rejected
