"""Tests for this bundle's degradation.

The contract every degradation must satisfy -- shape and dtype preserved, severity zero
being a no-op where that is meant to hold, the declared severity direction actually being
true -- is checked for the whole registry in ``tests/test_degradation_contract.py``. Do
not repeat it here. Test what is specific to this operator: the property that makes it
the degradation it claims to be.
"""

from __future__ import annotations

import numpy as np
import pytest

from .degradation import spread_inflate


def _ensemble(n_members: int = 8, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n_members, 1, 8, 4))


def test_it_changes_the_field_at_a_real_severity():
    members = _ensemble()
    assert not np.allclose(spread_inflate(members, 1.0), members)


def test_it_leaves_the_ensemble_mean_exactly_where_it_was():
    """The property that makes this a calibration axis rather than an accuracy one.

    If the mean moved, every metric built on it would respond too, and a rise in a
    calibration metric could no longer be attributed to dispersion alone.
    """
    members = _ensemble()
    for severity in (0.5, 1.0, 4.0):
        assert spread_inflate(members, severity).mean(axis=0) == pytest.approx(
            members.mean(axis=0), rel=1e-12
        )


def test_severity_is_the_excess_dispersion():
    """Severity one doubles the spread; severity three quadruples it."""
    members = _ensemble()
    base = members.std(axis=0, ddof=1).mean()
    for severity, factor in ((1.0, 2.0), (3.0, 4.0)):
        widened = spread_inflate(members, severity).std(axis=0, ddof=1).mean()
        assert widened == pytest.approx(factor * base, rel=1e-12)


def test_it_is_monotone_in_severity():
    members = _ensemble()
    spreads = [
        spread_inflate(members, s).std(axis=0, ddof=1).mean()
        for s in (0.0, 0.5, 1.0, 2.0, 4.0)
    ]
    assert spreads == sorted(spreads)
