"""Tests specific to mean absolute error.

The contract every metric satisfies -- zero on identical fields, symmetry, the pointwise
map reducing to the scalar -- is checked over the whole registry in
``tests/test_metric_contract.py`` and is not repeated here.

What is tested here is what the card claims: the worked example in its Intuition section,
and the linear response to displacement that separates it from MSE.
"""

from __future__ import annotations

import numpy as np

from .metric import mae, mae_map

# The same 4x4 feature the MSE card uses, so the two cards can be read against each other.
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
    """The two numbers quoted in the card's Intuition section.

    Four of sixteen cells differ by one when the feature moves, so the mean absolute
    error is 4/16. Four cells differ by a half when the amplitude is halved, so it is
    4*0.5/16.
    """
    assert mae(REFERENCE, SHIFTED) == 0.25
    assert mae(REFERENCE, HALF_AMPLITUDE) == 0.125


def test_a_one_cell_shift_costs_twice_a_halved_amplitude():
    """The same comparison the MSE card makes, where MSE gives four times rather than two.

    Both metrics prefer the damped candidate to the displaced one. They disagree by how
    much, and that factor is the whole practical difference between them.
    """
    assert mae(REFERENCE, SHIFTED) == 2.0 * mae(REFERENCE, HALF_AMPLITUDE)


def test_response_to_a_small_displacement_is_linear():
    """MAE ~ delta <|df/dx|> for a displacement below the scale of variation.

    Halving the displacement should halve the error, where MSE quarters it. Checked on a
    smooth sinusoid, where the sub-cell displacement is exact and the derivative bounded.
    """
    x = np.linspace(0.0, 2.0 * np.pi, 256, endpoint=False)
    reference = np.sin(x)[None, :]
    errors = [mae(reference, np.sin(x + d)[None, :]) for d in (0.02, 0.01, 0.005)]
    ratios = [errors[i] / errors[i + 1] for i in range(len(errors) - 1)]
    assert all(abs(r - 2.0) < 0.05 for r in ratios), ratios


def test_the_error_map_shows_two_lobes_for_a_displaced_feature():
    """The double penalty as a picture: error where the feature is not, and where it is."""
    error = mae_map(REFERENCE, SHIFTED)
    assert np.all(error[1:3, 1] == 1.0)          # where the feature should be and is not
    assert np.all(error[1:3, 3] == 1.0)          # where it is and should not be
    assert np.all(error[1:3, 2] == 0.0)          # where they overlap, no error at all


def test_it_is_blind_to_where_the_error_sits():
    """Two candidates wrong by the same amount in different places score identically."""
    reference = np.zeros((1, 4, 4))
    corner = reference.copy()
    corner[0, 0, 0] = 1.0
    middle = reference.copy()
    middle[0, 2, 2] = 1.0
    assert mae(reference, corner) == mae(reference, middle)
