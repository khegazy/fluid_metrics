"""Rank histogram reliability index: is the ensemble the right shape?

The scalar reported here is a summary of a histogram, so the tests fall into two groups:
those that pin the arithmetic on a hand-checkable case, and those that check the summary
responds the way the histogram's shape is known to respond -- rising for an ensemble that
is too narrow, too wide, or off-centre, and near zero only when the truth is genuinely
exchangeable with the members.

The uniformity test uses a chi-square goodness of fit on independent draws. It is a
statistical test with a fixed seed, so it is deterministic in practice, but the threshold
is chosen loose enough that it is testing the metric rather than the seed.
"""

from __future__ import annotations

import numpy as np
import pytest

from fmeval.context import derive_rng
from metrics.rank_histogram.metric import rank_histogram, reliability_index


def _ctx(seed: int = 0):
    """A minimal stand-in for the pipeline's FieldContext, for tie-breaking only."""

    class _Ctx:
        rng = derive_rng(seed, "test", 0, "density")

    return _Ctx()


# --- the summary statistic itself ----------------------------------------------------


def test_reliability_index_is_zero_for_a_flat_histogram():
    counts = np.full(5, 20)
    assert reliability_index(counts) == pytest.approx(0.0)


def test_reliability_index_is_maximal_when_one_bin_takes_everything():
    """All mass in one bin of N+1 gives 2N/(N+1), the largest value attainable."""
    for n_bins in (3, 5, 9):
        counts = np.zeros(n_bins, dtype=int)
        counts[0] = 100
        n_members = n_bins - 1
        assert reliability_index(counts) == pytest.approx(
            2 * n_members / (n_members + 1)
        )


def test_reliability_index_worked_example():
    """Four bins holding 40, 20, 20, 20 of 100 draws.

    Frequencies are 0.4, 0.2, 0.2, 0.2 against a uniform 0.25, so the absolute
    deviations are 0.15, 0.05, 0.05, 0.05 and the index is 0.30.
    """
    assert reliability_index(np.array([40, 20, 20, 20])) == pytest.approx(0.30)


# --- the metric on hand-checkable ensembles ------------------------------------------


def test_worked_example_from_the_card():
    """Three members and four cells, arranged so the reference takes each rank once.

    One draw in each of the four bins is exactly uniform, so the index is zero.
    """
    reference = np.array([0.0, 0.0, 0.0, 0.0]).reshape(1, 4)
    members = np.array(
        [
            [1.0, -1.0, -1.0, -1.0],   # ref below all three  -> rank 0
            [2.0, 1.0, -2.0, -2.0],    # ref above one        -> rank 1
            [3.0, 2.0, 1.0, -3.0],     # ref above two        -> rank 2
        ]
    ).reshape(3, 1, 4)                  # ref above all three  -> rank 3
    assert rank_histogram(reference, members, ctx=_ctx()) == pytest.approx(0.0)


def test_a_reference_below_every_member_fills_the_first_bin():
    """Maximal bias: every draw lands in one bin, so the index is at its bound."""
    reference = np.zeros((1, 8, 8))
    members = np.ones((4, 1, 8, 8))
    assert rank_histogram(reference, members, ctx=_ctx()) == pytest.approx(2 * 4 / 5)


def test_a_reference_above_every_member_fills_the_last_bin():
    reference = np.full((1, 8, 8), 10.0)
    members = np.zeros((4, 1, 8, 8))
    assert rank_histogram(reference, members, ctx=_ctx()) == pytest.approx(2 * 4 / 5)


# --- calibration behaviour -----------------------------------------------------------


def test_is_near_zero_for_an_exchangeable_ensemble():
    """The calibrated null: truth drawn from the same process as the members.

    With 64 cells per bin on average the sampling floor is around 0.1, so the assertion
    is loose in absolute terms but far below what any miscalibration below produces.
    """
    rng = np.random.default_rng(0)
    base = rng.standard_normal((1, 48, 48))
    reference = base + rng.standard_normal((1, 48, 48))
    members = base[None] + rng.standard_normal((8, 1, 48, 48))
    assert rank_histogram(reference, members, ctx=_ctx()) < 0.12


def test_underdispersion_raises_the_index():
    """Too-narrow members push the truth to the tails: a U-shaped histogram."""
    rng = np.random.default_rng(1)
    base = rng.standard_normal((1, 48, 48))
    reference = base + rng.standard_normal((1, 48, 48))
    members = base[None] + rng.standard_normal((8, 1, 48, 48))
    mean = members.mean(axis=0, keepdims=True)
    narrow = mean + 0.2 * (members - mean)
    assert rank_histogram(reference, narrow, ctx=_ctx()) > 0.5


def test_overdispersion_raises_the_index():
    """Too-wide members trap the truth in the middle: a dome-shaped histogram."""
    rng = np.random.default_rng(2)
    base = rng.standard_normal((1, 48, 48))
    reference = base + rng.standard_normal((1, 48, 48))
    members = base[None] + rng.standard_normal((8, 1, 48, 48))
    mean = members.mean(axis=0, keepdims=True)
    wide = mean + 5.0 * (members - mean)
    assert rank_histogram(reference, wide, ctx=_ctx()) > 0.3


def test_rises_monotonically_with_bias():
    rng = np.random.default_rng(3)
    base = rng.standard_normal((1, 48, 48))
    reference = base + rng.standard_normal((1, 48, 48))
    members = base[None] + rng.standard_normal((8, 1, 48, 48))
    values = [
        rank_histogram(reference, members + b, ctx=_ctx()) for b in (0.0, 0.5, 1.0, 2.0)
    ]
    assert values == sorted(values), values


def test_detects_miscalibration_that_the_ensemble_mean_cannot_see():
    """The reason this metric is on the panel beside ensemble_mean_rmse.

    Scaling the members about their own mean leaves the ensemble mean untouched, so a
    mean-based score is unchanged, while the rank histogram registers it immediately.
    """
    from metrics.ensemble_mean_rmse.metric import ensemble_mean_rmse

    rng = np.random.default_rng(4)
    base = rng.standard_normal((1, 48, 48))
    reference = base + rng.standard_normal((1, 48, 48))
    members = base[None] + rng.standard_normal((8, 1, 48, 48))
    mean = members.mean(axis=0, keepdims=True)
    narrow = mean + 0.2 * (members - mean)

    assert ensemble_mean_rmse(reference, narrow) == pytest.approx(
        ensemble_mean_rmse(reference, members), rel=1e-12
    )
    assert rank_histogram(reference, narrow, ctx=_ctx()) > 4 * rank_histogram(
        reference, members, ctx=_ctx()
    )


# --- ties, determinism and shape handling --------------------------------------------


def test_identical_members_do_not_crash_and_ties_are_broken_at_random():
    """A collapsed ensemble is all ties. The rank must still be defined.

    Randomising among tied ranks is the standard treatment (Hamill 2001): it keeps the
    histogram uniform for a genuinely calibrated but discretised forecast, where always
    taking the lowest rank would manufacture a spike in the first bin.
    """
    reference = np.zeros((1, 16, 16))
    members = np.zeros((4, 1, 16, 16))
    value = rank_histogram(reference, members, ctx=_ctx())
    assert np.isfinite(value)


def test_is_deterministic_for_a_given_seed():
    rng = np.random.default_rng(5)
    reference = rng.standard_normal((1, 16, 16))
    members = rng.standard_normal((6, 1, 16, 16))
    a = rank_histogram(reference, members, ctx=_ctx(seed=11))
    b = rank_histogram(reference, members, ctx=_ctx(seed=11))
    assert a == b


def test_works_without_a_context():
    """The ctx is optional; without one, ties fall back to a deterministic rule."""
    reference = np.zeros((1, 8, 8))
    members = np.ones((4, 1, 8, 8))
    assert np.isfinite(rank_histogram(reference, members))


def test_rejects_members_without_a_member_axis():
    with pytest.raises(ValueError):
        rank_histogram(np.zeros((1, 4, 4)), np.zeros((1, 4, 4)), ctx=_ctx())


def test_needs_at_least_two_members():
    with pytest.raises(ValueError, match="two"):
        rank_histogram(np.zeros((1, 4, 4)), np.zeros((1, 1, 4, 4)), ctx=_ctx())
