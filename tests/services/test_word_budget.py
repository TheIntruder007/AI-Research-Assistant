"""Tests for the deterministic word-budget allocation (DECISIONS.md D-025)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-writing"))

from word_budget import (  # noqa: E402
    LENGTH_PRESETS, SECTION_WEIGHTS, allocate_section_budgets, classify_length,
)


def test_none_total_returns_no_budgets_preserving_old_behavior():
    assert allocate_section_budgets(None) == {}
    assert allocate_section_budgets(0) == {}


def test_budgets_cover_every_section_role():
    budgets = allocate_section_budgets(4000)
    assert set(budgets) == set(SECTION_WEIGHTS)


def test_budget_targets_sum_close_to_the_total():
    total = 4000
    budgets = allocate_section_budgets(total)
    summed = sum(b.target for b in budgets.values())
    # Rounding per section means this won't be exact, but should be close.
    assert abs(summed - total) < total * 0.05


def test_literature_review_gets_the_largest_share():
    budgets = allocate_section_budgets(4000)
    lit_review = budgets["Literature Review"].target
    for role, budget in budgets.items():
        if role != "Literature Review":
            assert budget.target <= lit_review


def test_minimum_is_below_target_and_maximum_is_above():
    budgets = allocate_section_budgets(4000)
    for budget in budgets.values():
        assert budget.minimum < budget.target < budget.maximum


def test_small_total_still_produces_a_sane_floor_not_near_zero():
    budgets = allocate_section_budgets(200)  # deliberately tiny
    for budget in budgets.values():
        assert budget.target >= 40


def test_length_presets_are_ordered_short_to_detailed():
    assert LENGTH_PRESETS["short"] < LENGTH_PRESETS["standard"] < LENGTH_PRESETS["detailed"]


def test_classify_length_returns_none_without_a_target():
    assert classify_length(4000, None) is None
    assert classify_length(4000, 0) is None


def test_classify_length_on_target_for_a_close_match():
    assert classify_length(4000, 4000) == "on_target"
    assert classify_length(3800, 4000) == "on_target"


def test_classify_length_short_when_well_under_target():
    assert classify_length(2000, 4000) == "short"


def test_classify_length_over_target_when_well_over():
    assert classify_length(6500, 4000) == "over_target"
