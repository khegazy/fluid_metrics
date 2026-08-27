"""Ensemble-mean RMSE: the deterministic control for the probabilistic family.

Its job is to be boring in a specific way. It collapses the ensemble to its mean and
scores that with the existing RMSE, so it sees accuracy and is blind to dispersion --
which is exactly what makes it the right thing to read CRPS against. The test that earns
its place here is the one showing that blindness explicitly.
"""

from __future__ import annotations

import numpy as np
import pytest

from metrics.ensemble_mean_rmse.metric import ensemble_mean_rmse
from metrics.rmse.metric import rmse


def test_worked_example_from_the_card():
    """Two members at 0 and 4 against a reference of 1, on a 2x2 field.

    The ensemble mean is 2 everywhere, the error is 1 everywhere, so the RMSE is 1.
    """
    reference = np.ones((1, 2, 2))
    members = np.stack([np.zeros((1, 2, 2)), np.full((1, 2, 2), 4.0)])
    assert ensemble_mean_rmse(reference, members) == pytest.approx(1.0)


def test_equals_rmse_of_the_member_mean():
    """The definition, checked against this repository's own RMSE.

    Also the test that catches an axis slip: averaging over channels instead of members
    would still return a number of the right order.
    """
    rng = np.random.default_rng(0)
    reference = rng.standard_normal((2, 8, 4))
    members = rng.standard_normal((6, 2, 8, 4))
    assert ensemble_mean_rmse(reference, members) == pytest.approx(
        rmse(reference, members.mean(axis=0)), rel=1e-12
    )


def test_single_member_equals_rmse():
    rng = np.random.default_rng(1)
    reference = rng.standard_normal((1, 6, 4))
    member = rng.standard_normal((1, 6, 4))
    assert ensemble_mean_rmse(reference, member[None]) == pytest.approx(
        rmse(reference, member), rel=1e-12
    )


def test_is_zero_when_the_mean_is_the_reference():
    reference = np.linspace(0, 1, 24).reshape(1, 6, 4)
    members = np.stack([reference - 0.5, reference + 0.5])
    assert ensemble_mean_rmse(reference, members) == pytest.approx(0.0, abs=1e-12)


def test_is_blind_to_dispersion_about_a_fixed_mean():
    """The control's defining property: inflating the spread leaves it unchanged.

    This is what separates it from CRPS and from the spread-to-skill ratio. A panel that
    reported only this number could not tell a confident ensemble from a vague one.
    """
    rng = np.random.default_rng(2)
    reference = rng.standard_normal((1, 10, 6))
    members = rng.standard_normal((12, 1, 10, 6))
    mean = members.mean(axis=0, keepdims=True)
    baseline = ensemble_mean_rmse(reference, members)
    for factor in (0.1, 0.5, 2.0, 5.0):
        widened = mean + factor * (members - mean)
        assert ensemble_mean_rmse(reference, widened) == pytest.approx(baseline, rel=1e-12)


def test_increases_monotonically_with_bias():
    rng = np.random.default_rng(3)
    reference = rng.standard_normal((1, 12, 8))
    members = rng.standard_normal((10, 1, 12, 8))
    values = [ensemble_mean_rmse(reference, members + b) for b in (0.0, 0.25, 0.5, 1.0)]
    assert values == sorted(values), values


def test_rejects_members_without_a_member_axis():
    with pytest.raises(ValueError):
        ensemble_mean_rmse(np.zeros((1, 4, 4)), np.zeros((1, 4, 4)))


def test_rejects_an_empty_ensemble():
    with pytest.raises(ValueError):
        ensemble_mean_rmse(np.zeros((1, 4, 4)), np.zeros((0, 1, 4, 4)))
