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

from .degradation import spread_deflate


def _ensemble(n_members: int = 8, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n_members, 1, 8, 4))


def test_it_changes_the_field_at_a_real_severity():
    members = _ensemble()
    assert not np.allclose(spread_deflate(members, 0.5), members)


def test_it_leaves_the_ensemble_mean_exactly_where_it_was():
    members = _ensemble()
    for severity in (0.25, 0.5, 0.9):
        assert spread_deflate(members, severity).mean(axis=0) == pytest.approx(
            members.mean(axis=0), rel=1e-12
        )


def test_severity_is_the_fraction_of_spread_removed():
    """Severity 0.75 leaves a quarter of the dispersion."""
    members = _ensemble()
    base = members.std(axis=0, ddof=1).mean()
    narrowed = spread_deflate(members, 0.75).std(axis=0, ddof=1).mean()
    assert narrowed == pytest.approx(0.25 * base, rel=1e-12)


def test_full_severity_collapses_the_ensemble_onto_its_mean():
    """The limit case: a forecast claiming perfect certainty."""
    members = _ensemble()
    collapsed = spread_deflate(members, 1.0)
    assert collapsed.std(axis=0, ddof=1) == pytest.approx(0.0, abs=1e-12)
    assert collapsed[0] == pytest.approx(members.mean(axis=0), rel=1e-12)


def test_it_is_monotone_in_severity():
    members = _ensemble()
    spreads = [
        spread_deflate(members, s).std(axis=0, ddof=1).mean()
        for s in (0.0, 0.25, 0.5, 0.9)
    ]
    assert spreads == sorted(spreads, reverse=True)


def test_a_severity_outside_the_unit_interval_is_refused():
    """Severity is a fraction removed, so above one it would invert the ensemble."""
    members = _ensemble()
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        spread_deflate(members, 1.5)
