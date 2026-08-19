"""Tests specific to mean squared error.

The contract every metric must satisfy -- zero on identical fields, symmetry, the
pointwise map reducing to the scalar -- is checked over the whole registry in
``tests/test_metric_contract.py`` and is not repeated here.

What is tested here is the behaviour the card claims: the worked example printed in the
card's Intuition section, and the quadratic response to displacement that makes MSE
tolerant of small shifts and severe about larger ones. Keeping those in a test is what
stops the prose drifting away from the code.
"""

from __future__ import annotations

import numpy as np

from .metric import mse, mse_map

# A sharp feature on a 4x4 grid, and two ways of getting it wrong: moving it by one cell,
# and halving its amplitude where it stands. These exact arrays appear in card.md.
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

    Four of sixteen cells differ by one when the feature moves, so the mean squared error
    is 4/16. Four cells differ by a half when the amplitude is halved, so it is 4*0.25/16.
    """
    assert mse(REFERENCE, SHIFTED) == 0.25
    assert mse(REFERENCE, HALF_AMPLITUDE) == 0.0625


def test_a_one_cell_shift_costs_four_times_a_halved_amplitude():
    """The claim the card makes about what MSE prioritises, stated as a ratio.

    This is the double penalty in its smallest form: the displaced candidate has the
    feature's shape and amplitude exactly right and is punished four times as hard as one
    that keeps the position and gets the amplitude badly wrong.
    """
    assert mse(REFERENCE, SHIFTED) == 4.0 * mse(REFERENCE, HALF_AMPLITUDE)


def test_the_error_map_shows_two_lobes_for_a_displaced_feature():
    """The double penalty as a picture: error where the feature is not, and where it is."""
    error = mse_map(REFERENCE, SHIFTED)
    missing = error[1:3, 1]     # where the feature should be and is not
    spurious = error[1:3, 3]    # where it is and should not be
    overlap = error[1:3, 2]     # where the two agree, and the error vanishes
    assert np.all(missing == 1.0)
    assert np.all(spurious == 1.0)
    assert np.all(overlap == 0.0), "the overlapping column should carry no error at all"


def test_response_to_a_small_displacement_is_quadratic():
    """MSE ~ delta^2 <(df/dx)^2> for a displacement below the scale of variation.

    Halving the displacement should quarter the error. Checked on a smooth sinusoid,
    where the sub-cell displacement is exact rather than approximated by a shift, and
    where the derivative is bounded so the expansion in the card's Definition holds.
    """
    x = np.linspace(0.0, 2.0 * np.pi, 256, endpoint=False)
    reference = np.sin(x)[None, :]
    errors = [mse(reference, np.sin(x + d)[None, :]) for d in (0.02, 0.01, 0.005)]
    ratios = [errors[i] / errors[i + 1] for i in range(len(errors) - 1)]
    assert all(abs(r - 4.0) < 0.05 for r in ratios), ratios


def test_it_is_blind_to_where_the_error_sits():
    """Two candidates wrong in the same amount at different places score identically.

    This is the sentence in the card's Intuition about what MSE ignores, made into a
    test: the metric sees a bag of per-cell differences and nothing about their
    arrangement, which is exactly the information a displaced shock lives in.
    """
    reference = np.zeros((1, 4, 4))
    corner = reference.copy()
    corner[0, 0, 0] = 1.0
    middle = reference.copy()
    middle[0, 2, 2] = 1.0
    assert mse(reference, corner) == mse(reference, middle)
