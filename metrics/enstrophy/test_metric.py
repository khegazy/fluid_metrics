"""Tests specific to enstrophy.

The registry-wide contract is checked in ``tests/test_metric_contract.py``. What is tested
here is what the card claims: the worked example in its Intuition section, the summing of
components, and the degeneracy that makes this a tripwire rather than a verdict.
"""

from __future__ import annotations

import numpy as np

from .metric import enstrophy

# A 4x4 vorticity field with four cells of unit vorticity, two of each sign.
FIELD = np.array([[[0.0, 0.0, 0.0, 0.0],
                   [0.0, 1.0, -1.0, 0.0],
                   [0.0, -1.0, 1.0, 0.0],
                   [0.0, 0.0, 0.0, 0.0]]])


def test_worked_example_from_the_card():
    """Four cells of unit magnitude out of sixteen, halved: 0.5 * 4/16."""
    assert enstrophy(FIELD) == 0.125


def test_sign_does_not_matter():
    """Squaring means clockwise and anticlockwise rotation contribute alike."""
    assert enstrophy(FIELD) == enstrophy(-FIELD)


def test_components_are_summed_before_averaging():
    """In 3D the three vorticity components add, rather than being averaged over."""
    three_d = np.concatenate([FIELD, FIELD, FIELD], axis=0)
    assert enstrophy(three_d) == 3.0 * enstrophy(FIELD)


def test_many_different_fields_share_one_value():
    """The card's reason for calling this a tripwire rather than a verdict.

    Moving all the vorticity into a corner, or reflecting it, leaves the number
    untouched. A metric that cannot tell these apart cannot certify a prediction; it can
    only notice when the total has moved.
    """
    moved = np.zeros_like(FIELD)
    moved[0, :2, :2] = np.array([[1.0, -1.0], [-1.0, 1.0]])
    assert enstrophy(moved) == enstrophy(FIELD)
    assert enstrophy(FIELD[:, ::-1, :]) == enstrophy(FIELD)


def test_smoothing_reduces_it():
    """Enstrophy lives at the small scales, so removing them lowers it.

    This is the drift the ladder is expected to expose, checked here in its simplest
    form: averaging neighbouring cells cannot raise the mean square.
    """
    smoothed = FIELD.copy()
    smoothed[0, 1:3, 1:3] = FIELD[0, 1:3, 1:3].mean()
    assert enstrophy(smoothed) < enstrophy(FIELD)
