"""Tests specific to root mean squared error.

The registry-wide contract is checked in ``tests/test_metric_contract.py``. What is
tested here is what the card claims: the worked example in its Intuition section, its
exact relationship to mean squared error, and the consequence of that square root for the
declared reduction.
"""

from __future__ import annotations

import numpy as np

from ..mse.metric import mse
from .metric import rmse, rmse_map

REFERENCE = np.array([[[0.0, 0.0, 0.0, 0.0],
                       [0.0, 1.0, 1.0, 0.0],
                       [0.0, 1.0, 1.0, 0.0],
                       [0.0, 0.0, 0.0, 0.0]]])

SHIFTED = np.array([[[0.0, 0.0, 0.0, 0.0],
                     [0.0, 0.0, 1.0, 1.0],
                     [0.0, 0.0, 1.0, 1.0],
                     [0.0, 0.0, 0.0, 0.0]]])

HALF_AMPLITUDE = np.array([[[0.0, 0.0, 0.0, 0.0],
                            [0.0, 0.5, 0.5, 0.0],
                            [0.0, 0.5, 0.5, 0.0],
                            [0.0, 0.0, 0.0, 0.0]]])


def test_worked_example_from_the_card():
    """Four of sixteen cells wrong by one gives sqrt(4/16) = 0.5; by a half, 0.25."""
    assert rmse(REFERENCE, SHIFTED) == 0.5
    assert rmse(REFERENCE, HALF_AMPLITUDE) == 0.25


def test_it_is_exactly_the_square_root_of_mse():
    """The card's claim that the two orderings can never disagree.

    A square root is monotone, so any ranking of candidates by RMSE is the same ranking
    MSE gives. The two differ in scale, never in order.
    """
    for candidate in (SHIFTED, HALF_AMPLITUDE):
        assert rmse(REFERENCE, candidate) == np.sqrt(mse(REFERENCE, candidate))


def test_a_one_cell_shift_costs_twice_a_halved_amplitude():
    """The same comparison as the other controls: four times for MSE, two here.

    Taking the square root pulls the quadratic penalty back to a linear-looking ratio on
    these fields, which is why RMSE reads like MAE while ordering like MSE.
    """
    assert rmse(REFERENCE, SHIFTED) == 2.0 * rmse(REFERENCE, HALF_AMPLITUDE)


def test_the_map_does_not_average_to_the_metric():
    """The reduction is sqrt_mean, and this test is why it must be declared.

    The stored per-cell map is the squared error. Averaging it gives MSE, not RMSE, so a
    consumer that assumed every map averages to its metric would be silently wrong here.
    """
    mean_of_map = rmse_map(REFERENCE, SHIFTED).mean()
    assert mean_of_map == mse(REFERENCE, SHIFTED)
    assert mean_of_map != rmse(REFERENCE, SHIFTED)
    assert np.sqrt(mean_of_map) == rmse(REFERENCE, SHIFTED)
