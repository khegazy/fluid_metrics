"""Tests for this bundle's degradation.

The contract every degradation must satisfy -- shape and dtype preserved, severity zero
being a no-op where that is meant to hold, the declared severity direction actually being
true -- is checked for the whole registry in ``tests/test_degradation_contract.py``. Do
not repeat it here. Test what is specific to this operator: the property that makes it
the degradation it claims to be.
"""

from __future__ import annotations

import numpy as np

from .degradation import template_degradation


def test_it_changes_the_field_at_a_real_severity():
    raise NotImplementedError("TODO(fill)")
