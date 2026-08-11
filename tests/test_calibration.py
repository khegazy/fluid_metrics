"""Severity calibration: measuring a field's spectrum, and resolving severities against it.

These are the checks that keep a calibrated axis meaning what it claims. The one that matters
most is ``test_removing_energy_uses_the_declared_side``: with the sides swapped, a request to
remove 5% of the energy resolves to the wavenumber *holding* 5% of it and removes the other 95%,
which inverts the axis while leaving every number plausible.
"""

from __future__ import annotations

import numpy as np
import pytest

from degradations import registry as deg
from fmeval.calibration import DRIFT_WARN, calibrate, calibrate_field
from fmeval.data.base import GridSpec
from fmeval.ladder import Rung, build_ladder, degenerate_rungs, resolve_severity

SHAPE = (64, 48)  # non-square, so an axis mix-up in the wavenumber grid shows up


def grid(shape: tuple[int, ...] = SHAPE) -> GridSpec:
    n = len(shape)
    return GridSpec(tuple(shape), (1.0,) * n, (True,) * n, ("x", "y", "z")[:n], (0.0,) * n)


def band_limited(k_max: float, shape: tuple[int, ...] = SHAPE, *, seed: int = 0,
                 mean: float = 0.0) -> np.ndarray:
    """A field whose fluctuation energy lies entirely below ``k_max``."""
    rng = np.random.default_rng(seed)
    axes = np.meshgrid(*[np.fft.fftfreq(n) * n for n in shape], indexing="ij")
    k = np.sqrt(sum(a**2 for a in axes))
    spectrum = np.fft.fftn(rng.standard_normal(shape)) * (k <= k_max)
    return (mean + np.real(np.fft.ifftn(spectrum)))[None]


# --- measuring ------------------------------------------------------------------------


def test_cumulative_energy_reaches_one_and_is_monotone():
    c = calibrate_field([band_limited(8.0)], grid(), "vorticity").cumulative_energy
    assert c[-1] == pytest.approx(1.0)
    assert np.all(np.diff(c) >= -1e-12)


def test_a_band_limited_field_has_no_energy_above_its_band():
    """The measurement must localise energy where it actually is."""
    cal = calibrate_field([band_limited(8.0)], grid(), "vorticity")
    assert cal.cumulative_energy[8] == pytest.approx(1.0, abs=1e-12)
    assert cal.wavenumber_for_energy_fraction(0.999) <= 8.0


def test_the_spatial_mean_is_removed_before_measuring():
    """Otherwise a field like density, 1.0 with 1e-4 fluctuations, is all k=0.

    Left in, the k=0 spike dominates the spectrum and every energy fraction resolves to the
    same wavenumber, which is exactly the failure this module exists to prevent.
    """
    fluctuation = band_limited(8.0, seed=1)
    with_mean = fluctuation + 1000.0
    a = calibrate_field([fluctuation], grid(), "density")
    b = calibrate_field([with_mean], grid(), "density")
    # atol, not rtol alone: the k=0 bin is zero by construction in both, and subtracting a
    # mean of 1000 leaves a different round-off there (1e-35 against 1e-25). Both are zero.
    np.testing.assert_allclose(a.cumulative_energy, b.cumulative_energy,
                               rtol=1e-10, atol=1e-20)
    assert b.characteristic_scale == pytest.approx(a.characteristic_scale, rel=1e-12)


def test_a_smoother_field_has_a_larger_characteristic_scale():
    smooth = calibrate_field([band_limited(2.0)], grid(), "density")
    rough = calibrate_field([band_limited(20.0)], grid(), "vorticity")
    assert smooth.characteristic_scale > rough.characteristic_scale


def test_a_uniform_field_cannot_be_calibrated():
    """It has no spectrum, so failing loudly beats inventing a scale for it."""
    with pytest.raises(ValueError, match="no fluctuation energy"):
        calibrate_field([np.ones((1, *SHAPE))], grid(), "temperature")


def test_calibrate_skips_a_field_it_cannot_measure_rather_than_aborting():
    out = calibrate(
        {"density": [band_limited(4.0)], "temperature": [np.ones((1, *SHAPE))]},
        grid(), ["density", "temperature"],
    )
    assert "density" in out
    assert "temperature" not in out


def test_scale_spread_reports_drift_across_frames():
    """The diagnostic for whether one fixed calibration is defensible on a trajectory."""
    steady = calibrate_field([band_limited(8.0, seed=s) for s in range(4)], grid(), "v")
    assert steady.scale_spread < DRIFT_WARN

    drifting = calibrate_field(
        [band_limited(k, seed=2) for k in (2.0, 6.0, 18.0, 30.0)], grid(), "v"
    )
    assert drifting.scale_spread > DRIFT_WARN


# --- resolving ------------------------------------------------------------------------


def test_removing_energy_uses_the_declared_side():
    """A low-pass removes what is above its cutoff; a high-pass what is below.

    Swapping the two inverts the axis silently: "remove 5%" would resolve to the wavenumber
    holding 5% of the energy, and the filter would remove the other 95%.
    """
    cal = calibrate_field([band_limited(20.0)], grid(), "vorticity")
    low = cal.cutoff_removing_energy(0.05, "above")
    high = cal.cutoff_removing_energy(0.05, "below")
    assert low > high, "a mild low-pass cuts high, a mild high-pass cuts low"
    assert cal.energy_removed(low, "above") == pytest.approx(0.05, abs=0.05)
    assert cal.energy_removed(high, "below") == pytest.approx(0.05, abs=0.05)


def test_a_harsher_request_moves_a_lowpass_cutoff_down_and_a_highpass_cutoff_up():
    cal = calibrate_field([band_limited(20.0)], grid(), "vorticity")
    lows = [cal.cutoff_removing_energy(f, "above") for f in (0.05, 0.2, 0.5)]
    highs = [cal.cutoff_removing_energy(f, "below") for f in (0.5, 0.7, 0.9)]
    assert lows == sorted(lows, reverse=True)
    assert highs == sorted(highs)


def test_an_energy_fraction_outside_the_unit_interval_is_rejected():
    cal = calibrate_field([band_limited(8.0)], grid(), "v")
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        cal.wavenumber_for_energy_fraction(1.5)


def test_a_scale_fraction_resolves_to_a_length_in_cells():
    cal = calibrate_field([band_limited(4.0)], grid(), "density")
    assert cal.length_for_scale_fraction(0.25) == pytest.approx(
        0.25 * cal.characteristic_scale
    )


def test_an_absolute_operator_passes_its_severity_through_untouched():
    rung = build_ladder({"translate_x": {"op": "translate", "severities": [4]}},
                        include_reference=False)[0]
    assert resolve_severity(rung, "density", None) == 4.0


def test_a_calibrated_operator_without_a_calibration_fails_loudly():
    """Silently falling back would apply an energy fraction as if it were a wavenumber."""
    rung = build_ladder({"lowpass_ideal": {"severities": [0.3]}},
                        include_reference=False)[0]
    with pytest.raises(KeyError, match="no calibration was measured"):
        resolve_severity(rung, "density", None)


def test_the_same_config_severity_resolves_differently_per_field():
    """The whole point: one number, the same fraction of structure destroyed on each field."""
    cal = calibrate(
        {"density": [band_limited(2.0)], "vorticity": [band_limited(20.0)]},
        grid(), ["density", "vorticity"],
    )
    rung = build_ladder({"gaussian_blur": {"severities": [0.1]}},
                        include_reference=False)[0]
    on_density = resolve_severity(rung, "density", cal)
    on_vorticity = resolve_severity(rung, "vorticity", cal)
    assert on_density > 2 * on_vorticity, (
        "a smoother field must get a wider kernel from the same config number"
    )


# --- degenerate rungs -----------------------------------------------------------------


def test_rungs_that_round_onto_one_wavenumber_shell_are_flagged():
    """Density-like case: with the energy in a couple of shells, rungs collapse.

    Reporting the repeat as a distinct rung would let the rank correlation score a tie as
    agreement and make the separability compare a distribution against itself.
    """
    cal = calibrate({"density": [band_limited(2.0)]}, grid(), ["density"])
    rungs = build_ladder({"highpass_ideal": {"severities": [0.90, 0.95, 0.97, 0.99]}},
                         include_reference=False)
    flagged = degenerate_rungs(rungs, "density", cal)
    assert flagged.get("highpass_ideal"), (
        "four sharp-cutoff rungs cannot all be distinct on a field with a two-shell spectrum"
    )


def test_a_broadband_field_keeps_all_its_rungs():
    cal = calibrate({"vorticity": [band_limited(30.0)]}, grid(), ["vorticity"])
    rungs = build_ladder({"highpass_ideal": {"severities": [0.45, 0.70, 0.90, 0.97]}},
                         include_reference=False)
    assert degenerate_rungs(rungs, "vorticity", cal) == {}


def test_an_uncalibrated_axis_is_never_flagged():
    rungs = build_ladder({"translate_x": {"op": "translate", "severities": [1, 2, 4]}},
                         include_reference=False)
    assert degenerate_rungs(rungs, "density", None) == {}


def test_the_windowed_kernels_quantise_to_odd_widths():
    """An even window has no centre cell, so it displaces the field by half a cell."""
    for name in ("box_blur", "median_blur"):
        spec = deg.get(name)
        widths = [spec.quantise_severity(s) for s in (1.4, 2.0, 3.2, 4.9, 6.1)]
        assert all(w % 2 == 1 for w in widths), (name, widths)


def test_an_operator_with_no_quantisation_returns_the_severity_unchanged():
    assert deg.get("gaussian_blur").quantise_severity(3.7) == pytest.approx(3.7)
