"""Tests for this bundle's metric.

At least one test must have an expected value you worked out by hand rather than copied
from a run: a test that asserts the code does what the code does will pass through any
mistake. Keep the inputs small, because this same example goes into the ``## Intuition``
section of the card, where four-by-four fields are readable and thirty-two-by-thirty-two
are not.

The contract tests that every metric must satisfy -- symmetry, zero on identical fields,
the pointwise map reducing to the scalar -- live in ``tests/test_metric_contract.py`` and
run automatically over the registry. Do not repeat them here; test what is specific to
this metric.
"""

from __future__ import annotations

import numpy as np

from .metric import template_metric


def test_identical_fields_score_zero():
    field = np.array([[[0.0, 1.0], [1.0, 0.0]]])
    assert template_metric(field, field) == 0.0


def test_worked_example_matches_the_card():
    """The example printed in the card's Intuition section, computed here.

    Keeping it in a test is what stops the card's numbers drifting away from the code.
    """
    raise NotImplementedError("TODO(fill)")
