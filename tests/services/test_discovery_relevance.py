"""Unit tests for the Service 1 relevance gate (discovery/relevance.py).

See DECISIONS.md D-018 for the root-cause investigation this fixes: the
pipeline's rank() function had no signal at all comparing a candidate paper
to the actual research question, which is how an unrelated paper (an
asthma-management guideline) once entered a corpus for an intermittent
fasting / cognition query. These tests reproduce that exact scenario (Test
B) plus the other cases requested for this reliability pass.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-discovery"))

from discovery.models import Paper
from discovery.pipeline import rank
from discovery.relevance import build_topic_profile, score_paper, screen_papers

QUESTION = "Effects of intermittent fasting on cognitive performance"
KEYWORD_QUERY = "intermittent fasting cognitive performance"


def _profile(keywords=None):
    return build_topic_profile(QUESTION, KEYWORD_QUERY, keywords)


def test_a_clearly_relevant_paper_is_accepted():
    paper = Paper(
        title="Intermittent fasting and cognitive function in adults",
        abstract="A randomized trial of intermittent fasting effects on memory and "
                 "attention in healthy adults.",
    )
    result = score_paper(paper, _profile())
    assert result.decision == "accepted"
    assert result.score > 0.3


def test_b_clearly_unrelated_paper_is_rejected():
    """Reproduces the actual bug: an asthma-management guideline must not
    enter a fasting/cognition corpus."""
    paper = Paper(
        title="Asthma management guidelines in primary care",
        abstract="A review of inhaled corticosteroid protocols and stepwise "
                 "treatment escalation for pediatric and adult asthma patients.",
    )
    result = score_paper(paper, _profile())
    assert result.decision == "rejected"
    assert result.score < 0.12


def test_c_partially_related_paper_is_accepted_but_scored_lower_than_direct_hit():
    direct = Paper(
        title="Intermittent fasting and cognitive function in adults",
        abstract="Effects of intermittent fasting on cognitive performance and memory.",
    )
    partial = Paper(
        title="Intermittent fasting and metabolic health",
        abstract="Effects of intermittent fasting on insulin sensitivity and weight loss.",
    )
    direct_result = score_paper(direct, _profile())
    partial_result = score_paper(partial, _profile())
    assert partial_result.decision == "accepted"  # shares real topic terms, not junk
    assert partial_result.score < direct_result.score  # but clearly less on-topic


def test_d_ambiguous_single_keyword_paper_does_not_outrank_relevant_papers():
    relevant = Paper(
        title="Intermittent fasting and cognitive function in adults",
        abstract="A study of intermittent fasting's effects on cognitive performance.",
        citations=5, year=2023,
    )
    # Shares one surface word ("fasting") but addresses a completely different
    # research problem (a pre-surgical/clinical protocol, not diet or cognition).
    ambiguous = Paper(
        title="Preoperative fasting protocols and patient safety",
        abstract="Guidelines on fasting duration before elective surgery to reduce "
                 "aspiration risk during anesthesia.",
        citations=50, year=2024,  # deliberately "stronger" by every non-relevance signal
    )
    for p in (relevant, ambiguous):
        p.relevance_score = score_paper(p, _profile()).score
    ranked = rank([ambiguous, relevant], per_source_limit=40)
    assert ranked[0] is relevant, (
        "A higher-cited, more recent but topically ambiguous paper must not "
        "outrank the genuinely relevant one once relevance scoring is applied."
    )


def test_e_adversarial_keyword_overlap_alone_cannot_win_ranking():
    relevant = Paper(
        title="Intermittent fasting and cognitive performance in older adults",
        abstract="Intermittent fasting interventions improved cognitive performance "
                 "test scores relative to controls.",
    )
    adversarial = Paper(
        title="Fasting blood glucose performance monitoring in diabetic cohorts",
        abstract="Performance characteristics of continuous glucose monitors during "
                 "overnight fasting periods in diabetic patients.",
        citations=200, year=2025,
    )
    for p in (relevant, adversarial):
        p.relevance_score = score_paper(p, _profile()).score
    ranked = rank([adversarial, relevant], per_source_limit=40)
    assert ranked[0] is relevant


def test_screen_papers_splits_accepted_and_rejected_and_annotates_each_paper():
    relevant = Paper(title="Intermittent fasting and cognitive function in adults",
                     abstract="Fasting and cognitive performance outcomes.")
    unrelated = Paper(title="Asthma management guidelines in primary care",
                      abstract="Inhaled corticosteroid stepwise treatment protocols.")
    accepted, rejected = screen_papers([relevant, unrelated], _profile())
    assert accepted == [relevant]
    assert rejected == [unrelated]
    assert relevant.relevance_decision == "accepted"
    assert unrelated.relevance_decision == "rejected"
    assert unrelated.relevance_reason


def test_user_supplied_keywords_strengthen_the_topic_profile():
    paper = Paper(
        title="Time-restricted eating and working memory outcomes",
        abstract="A trial of time-restricted eating and its effect on working memory.",
    )
    # The raw question alone doesn't mention "time-restricted eating" or
    # "working memory" — user keywords should still let this paper score well.
    without_keywords = score_paper(paper, build_topic_profile(QUESTION, KEYWORD_QUERY))
    with_keywords = score_paper(
        paper, build_topic_profile(QUESTION, KEYWORD_QUERY,
                                   keywords=["time-restricted eating", "working memory"]),
    )
    assert with_keywords.score >= without_keywords.score


def test_degenerate_topic_profile_does_not_block_the_pipeline():
    paper = Paper(title="X", abstract=None)
    profile = build_topic_profile("", "", [])
    result = score_paper(paper, profile)
    assert result.decision == "accepted"
