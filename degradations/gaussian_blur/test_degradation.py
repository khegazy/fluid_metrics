"""Tests specific to the gaussian_blur degradation.

The contract every operator satisfies -- shape preservation, the declared severity
direction, reproducibility from the seed -- is checked over the whole registry in
``tests/test_degradation_contract.py`` and is not repeated here.

What is tested here is what the card claims: the worked example in its Intuition section,
the exact preservation of the spatial mean, and the monotone attenuation in wavenumber
that separates this kernel from the windowed ones.
"""

from __future__ import annotations

import numpy as np

from fmeval.context import FieldContext
from fmeval.data.base import GridSpec

from .degradation import gaussian_blur

FIELD = np.array([[[0.0, 0.0, 0.0, 0.0],
                   [0.0, 1.0, 1.0, 0.0],
                   [0.0, 1.0, 1.0, 0.0],
                   [0.0, 0.0, 0.0, 0.0]]])


def _ctx(shape):
    """A minimal context; this operator uses only the grid's dimensionality."""
    return FieldContext(
        field="vorticity",
        grid=GridSpec(shape=shape, spacing=(1.0,) * len(shape), periodic=(True,) * len(shape)),
        frame_index=0,
        time=0.0,
        fluctuation_rms=1.0,
        rng=np.random.default_rng(0),
    )


def test_worked_example_from_the_card():
    """The 4x4 numbers printed in the card's Intuition section, to two decimals."""
    out = gaussian_blur(FIELD, 1.0, ctx=_ctx((4, 4)))
    expected = np.array([[0.13, 0.23, 0.23, 0.13],
                         [0.23, 0.42, 0.42, 0.23],
                         [0.23, 0.42, 0.42, 0.23],
                         [0.13, 0.23, 0.23, 0.13]])
    assert np.allclose(out[0], expected, atol=0.005)


def test_the_spatial_mean_is_preserved_exactly():
    """The card's claim that nothing is added or removed, only redistributed.

    This is what separates a smoothing operator from a filter that deletes a component:
    the high-pass operators had to be written carefully to keep this property, and this
    one gets it from the kernel being positive and normalised.
    """
    for severity in (0.5, 1.0, 4.0):
        out = gaussian_blur(FIELD, severity, ctx=_ctx((4, 4)))
        assert np.isclose(out.mean(), FIELD.mean())


def test_attenuation_is_monotone_in_wavenumber():
    """Every mode is damped and none amplified, which the box kernel cannot claim.

    A single sinusoid at each resolvable wavenumber, blurred, must come back with its
    amplitude reduced -- and reduced more at higher wavenumber.
    """
    n = 64
    x = np.arange(n)
    amplitudes = []
    for k in (1, 2, 4, 8):
        wave = np.sin(2 * np.pi * k * x / n)[None, :, None] * np.ones((1, n, n))
        out = gaussian_blur(wave, 2.0, ctx=_ctx((n, n)))
        amplitudes.append(np.abs(out).max())
    assert all(a < 1.0 for a in amplitudes), amplitudes
    assert amplitudes == sorted(amplitudes, reverse=True), amplitudes


def test_a_wider_kernel_removes_more():
    """The declared severity direction, in its simplest form."""
    weak = gaussian_blur(FIELD, 0.5, ctx=_ctx((4, 4)))
    strong = gaussian_blur(FIELD, 2.0, ctx=_ctx((4, 4)))
    assert np.abs(strong - FIELD).sum() > np.abs(weak - FIELD).sum()
