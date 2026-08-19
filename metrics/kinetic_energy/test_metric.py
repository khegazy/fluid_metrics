"""Tests specific to kinetic energy.

The registry-wide contract is checked in ``tests/test_metric_contract.py``. What is tested
here is what the card claims: the worked example, the summing of velocity components, and
the degeneracy that makes this a tripwire rather than a verdict.
"""

from __future__ import annotations

import numpy as np

from .metric import kinetic_energy

# A 4x4 two-component velocity field: u = 1 everywhere, v = 0 everywhere.
UNIFORM = np.stack([np.ones((4, 4)), np.zeros((4, 4))])


def test_worked_example_from_the_card():
    """A unit velocity in one component everywhere gives 0.5 * 1."""
    assert kinetic_energy(UNIFORM) == 0.5


def test_components_are_summed_before_averaging():
    """Both components moving at unit speed carries twice the energy of one."""
    both = np.stack([np.ones((4, 4)), np.ones((4, 4))])
    assert kinetic_energy(both) == 2.0 * kinetic_energy(UNIFORM)


def test_direction_does_not_matter():
    """Only the speed enters, so reversing the flow leaves the energy unchanged."""
    assert kinetic_energy(-UNIFORM) == kinetic_energy(UNIFORM)


def test_many_different_fields_share_one_value():
    """The card's reason for calling this a tripwire.

    A uniform flow and one with the same total energy piled into a quarter of the domain
    are indistinguishable here, though they are entirely different flows.
    """
    concentrated = np.zeros_like(UNIFORM)
    concentrated[0, :2, :] = np.sqrt(2.0)   # half the domain, at the speed that matches
    assert np.isclose(kinetic_energy(concentrated), kinetic_energy(UNIFORM))


def test_it_scales_quadratically_with_the_field():
    """Doubling every velocity quadruples the energy."""
    assert kinetic_energy(2.0 * UNIFORM) == 4.0 * kinetic_energy(UNIFORM)
