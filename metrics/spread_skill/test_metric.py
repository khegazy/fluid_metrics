"""Spread-to-skill ratio, and the estimator mistake it exists to avoid.

The single most important test in this file is
``test_uses_the_fortin_estimator_not_the_mean_of_spreads``. Fortin and colleagues (2014)
show that averaging per-cell spreads instead of taking the square root of the average
variance biases the spread low, and that the bias is large enough to flip an operational
verdict from "underdispersed" to "excellent agreement". Both forms are one line, both
look reasonable, and only one is right -- so it is pinned by a test whose numbers differ
by a factor of sqrt(2), not by a comment.

The ratio is reported raw, as the literature reports it: it is calibrated at one and
wrong in both directions. Nothing here transforms it into a monotone error, because that
would be reporting a different quantity than the one the name promises.
"""

from __future__ import annotations

import numpy as np
import pytest

from metrics.spread_skill.metric import spread_skill


def test_worked_example_from_the_card():
    """Three members at -1, 0, 1 against a reference of 2, on a single cell.

    The sample variance is 1, so the raw spread is 1. With three members the
    finite-ensemble factor is sqrt(4/3), giving a corrected spread of 1.1547. The
    ensemble mean is 0 against a reference of 2, so the skill is 2 and the ratio is
    0.5774: the ensemble is far less uncertain than its error warrants, which is
    overconfidence.
    """
    reference = np.full((1, 1, 1), 2.0)
    members = np.array([-1.0, 0.0, 1.0]).reshape(3, 1, 1, 1)
    expected = 1.0 * np.sqrt(4.0 / 3.0) / 2.0
    assert spread_skill(reference, members) == pytest.approx(expected)
    assert spread_skill(reference, members) == pytest.approx(0.57735, abs=1e-5)


def test_uses_the_fortin_estimator_not_the_mean_of_spreads():
    """Square root of the mean variance, never the mean of the per-cell spreads.

    Two cells: one where the members agree exactly (variance 0) and one where they are
    -6, 0, 6 (variance 36). The correct spread is sqrt((0 + 36)/2) = 4.2426; the naive
    average of per-cell spreads is (0 + 6)/2 = 3, low by a factor of sqrt(2). Swapping
    the implementation for the naive form turns this assertion red, which was checked by
    doing exactly that while writing it.
    """
    members = np.zeros((3, 1, 2, 1))
    members[:, 0, 0, 0] = [0.0, 0.0, 0.0]
    members[:, 0, 1, 0] = [-6.0, 0.0, 6.0]
    # Ensemble mean is zero at both cells, so a reference of 2 gives a skill of exactly 2.
    reference = np.full((1, 2, 1), 2.0)

    correction = np.sqrt(4.0 / 3.0)  # three members
    fortin = np.sqrt(np.mean([0.0, 36.0]))  # 4.2426
    naive = np.mean([0.0, 6.0])             # 3.0, low by sqrt(2)
    assert fortin != pytest.approx(naive)

    assert spread_skill(reference, members) == pytest.approx(fortin * correction / 2.0)
    assert spread_skill(reference, members) != pytest.approx(naive * correction / 2.0)


def test_uses_the_unbiased_variance():
    """Sample variance with ddof=1: the population form biases the spread low.

    Two members at -1 and 1. The ddof=1 variance is 2 and the population variance would
    be 1, so this distinguishes them by a factor of sqrt(2). Mean is 0 against a
    reference of 1, so the skill is 1, and the two-member correction is sqrt(3/2).
    """
    reference = np.full((1, 1, 1), 1.0)
    members = np.array([-1.0, 1.0]).reshape(2, 1, 1, 1)
    unbiased = np.sqrt(2.0) * np.sqrt(3.0 / 2.0)
    population = np.sqrt(1.0) * np.sqrt(3.0 / 2.0)
    assert spread_skill(reference, members) == pytest.approx(unbiased)
    assert spread_skill(reference, members) != pytest.approx(population)


def test_is_one_for_an_exchangeable_ensemble():
    """The calibrated case, at the size where the finite-ensemble factor matters.

    For a reference drawn from the same process as the members, the expected squared
    error of the ensemble mean exceeds the ensemble variance by (N+1)/N, so the raw
    ratio approaches sqrt(N/(N+1)) rather than exactly one. The metric applies that
    correction, so a well-calibrated ensemble reads one at any ensemble size -- which is
    what makes the number comparable between a 4-member and a 50-member run.
    """
    rng = np.random.default_rng(0)
    for n_members in (4, 40):
        base = rng.standard_normal((1, 40, 40))
        reference = base + rng.standard_normal((1, 40, 40))
        members = base[None] + rng.standard_normal((n_members, 1, 40, 40))
        assert spread_skill(reference, members) == pytest.approx(1.0, abs=0.08), n_members


def test_underdispersion_reads_below_one():
    rng = np.random.default_rng(1)
    base = rng.standard_normal((1, 32, 32))
    reference = base + rng.standard_normal((1, 32, 32))
    members = base[None] + rng.standard_normal((24, 1, 32, 32))
    mean = members.mean(axis=0, keepdims=True)
    assert spread_skill(reference, mean + 0.3 * (members - mean)) < 0.6


def test_overdispersion_reads_above_one():
    rng = np.random.default_rng(2)
    base = rng.standard_normal((1, 32, 32))
    reference = base + rng.standard_normal((1, 32, 32))
    members = base[None] + rng.standard_normal((24, 1, 32, 32))
    mean = members.mean(axis=0, keepdims=True)
    assert spread_skill(reference, mean + 3.0 * (members - mean)) > 1.8


def test_is_monotone_in_the_inflation_factor():
    """The ratio itself is monotone in dispersion; it is *damage* that is U-shaped."""
    rng = np.random.default_rng(3)
    base = rng.standard_normal((1, 24, 24))
    reference = base + rng.standard_normal((1, 24, 24))
    members = base[None] + rng.standard_normal((16, 1, 24, 24))
    mean = members.mean(axis=0, keepdims=True)
    values = [
        spread_skill(reference, mean + f * (members - mean))
        for f in (0.25, 0.5, 1.0, 2.0, 4.0)
    ]
    assert values == sorted(values), values


def test_zero_spread_is_zero_not_a_division_error():
    """An ensemble that has collapsed is maximally overconfident, and reads zero."""
    reference = np.ones((1, 4, 4))
    members = np.repeat(np.zeros((1, 4, 4))[None], 5, axis=0)
    with np.errstate(divide="raise", invalid="raise"):
        assert spread_skill(reference, members) == 0.0


def test_a_perfect_ensemble_mean_with_spread_is_not_finite_nonsense():
    """Zero skill with non-zero spread: infinitely overdispersed, reported as inf.

    Returning a large finite number instead would be a silent lie, and returning NaN
    would drop the point from every rank correlation without saying why.
    """
    reference = np.zeros((1, 1, 1))
    members = np.array([-1.0, 0.0, 1.0]).reshape(3, 1, 1, 1)
    with np.errstate(divide="raise", invalid="raise"):
        assert np.isinf(spread_skill(reference, members))


def test_needs_at_least_two_members():
    """A single member has no spread to speak of, and the ddof=1 variance is undefined."""
    with pytest.raises(ValueError, match="two"):
        spread_skill(np.zeros((1, 4, 4)), np.zeros((1, 1, 4, 4)))


def test_rejects_members_without_a_member_axis():
    with pytest.raises(ValueError):
        spread_skill(np.zeros((1, 4, 4)), np.zeros((1, 4, 4)))
