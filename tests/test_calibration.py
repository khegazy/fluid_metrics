"""Severity calibration: measuring a field's spectrum, and resolving severities against it.

These are the checks that keep a calibrated axis meaning what it claims. The one that matters
most is ``test_removing_energy_uses_the_declared_side``: with the sides swapped, a request to
remove 5% of the energy resolves to the wavenumber *holding* 5% of it and removes the other 95%,
which inverts the axis while leaving every number plausible.
"""

from __future__ import annotations

import numpy as np
import pytest

from fmeval.calibration import DRIFT_WARN, calibrate, calibrate_field
from fmeval.data.base import GridSpec
from fmeval.ladder import build_ladder, resolve_severity

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
    """The measurement must localise energy where it actually is.

    Note the curve is indexed by position in the list of distinct magnitudes, not by wavenumber,
    so it is read through the accessors rather than by integer index.
    """
    cal = calibrate_field([band_limited(8.0)], grid(), "vorticity")
    assert cal.energy_removed(8.0, "below") == pytest.approx(1.0, abs=1e-12)
    assert cal.energy_removed(8.0, "above") == pytest.approx(0.0, abs=1e-12)
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
    severity_level = build_ladder({"translate_x": {"op": "translate", "severities": [4]}},
                        include_reference=False)[0]
    assert resolve_severity(severity_level, "density", None) == 4.0


def test_a_calibrated_operator_without_a_calibration_fails_loudly():
    """Silently falling back would apply an energy fraction as if it were a wavenumber."""
    severity_level = build_ladder({"lowpass_ideal": {"severities": [0.3]}},
                        include_reference=False)[0]
    with pytest.raises(KeyError, match="no calibration was measured"):
        resolve_severity(severity_level, "density", None)


def test_the_same_config_severity_resolves_differently_per_field():
    """The whole point: one number, the same fraction of structure destroyed on each field."""
    cal = calibrate(
        {"density": [band_limited(2.0)], "vorticity": [band_limited(20.0)]},
        grid(), ["density", "vorticity"],
    )
    severity_level = build_ladder({"gaussian_blur": {"severities": [0.1]}},
                        include_reference=False)[0]
    on_density = resolve_severity(severity_level, "density", cal)
    on_vorticity = resolve_severity(severity_level, "vorticity", cal)
    assert on_density > 2 * on_vorticity, (
        "a smoother field must get a wider kernel from the same config number"
    )


# --- degenerate severity levels -----------------------------------------------------------------
#
# Detected by measurement, in the pipeline: two severity levels whose severities resolve to the same
# quantised operation produce a bitwise identical field and therefore an exactly equal
# energy_changed. See tests/test_pipeline.py for the end-to-end check; here we verify the
# property the detection relies on.


def test_two_cutoffs_inside_one_shell_are_the_same_experiment():
    """The premise of the duplicate detection, and the density case in miniature.

    Requests of 45% and 70% removal on a field whose energy lives below |k| = 1.5 both resolve
    inside the same gap between available magnitudes, so they select identical modes.
    """
    x = band_limited(2.0, seed=9)
    a = apply("highpass_ideal", [0.45], "density", x)
    b = apply("highpass_ideal", [0.55], "density", x)
    assert a.energy_changed["density"] == b.energy_changed["density"], (
        "two cutoffs selecting the same modes must give exactly equal measured effect, or the "
        "duplicate detection cannot see them"
    )


def test_two_widths_rounding_to_one_odd_window_are_the_same_experiment():
    x = band_limited(6.0, seed=10)
    cal_scale = calibrate_field([x], grid(), "vorticity").characteristic_scale
    # Two fractions whose widths differ by less than a cell either side of the same odd number.
    fractions = [3.0 / cal_scale, 3.4 / cal_scale]
    effects = [apply("box_blur", [f], "vorticity", x).energy_changed["vorticity"]
               for f in fractions]
    assert effects[0] == effects[1]


def test_distinct_experiments_do_not_collide():
    """The detection must not fold together severity levels that really differ."""
    x = band_limited(24.0, seed=11)
    effects = [apply("lowpass_ideal", [f], "vorticity", x).energy_changed["vorticity"]
               for f in (0.05, 0.2, 0.45)]
    assert len(set(effects)) == 3


def test_a_cutoff_quantises_to_an_available_magnitude():
    cal = calibrate_field([band_limited(20.0)], grid(), "vorticity")
    for cutoff in (1.2, 3.7, 9.9):
        snapped = cal.quantised_cutoff(cutoff)
        assert snapped <= cutoff
        assert snapped in set(cal.wavenumbers)


# --- the realised effect of a severity level ------------------------------------------------------


def _frame_of(field: str, array: np.ndarray):
    from fmeval.data.base import Frame

    return Frame(index=0, time=0.0, grid=grid(array.shape[1:]), fields={field: array})


def apply(label: str, severities: list[float], field: str, array: np.ndarray):
    """Apply the first severity level of a one-entry ladder, calibrating from the array itself."""
    from fmeval.calibration import Calibration
    from fmeval.ladder import apply_severity_level

    frame = _frame_of(field, array)
    severity_level = build_ladder({label: {"severities": severities}}, include_reference=False)[0]
    cal = Calibration({field: calibrate_field([array], frame.grid, field)})
    return apply_severity_level(severity_level, frame, [field], seed=0, calibration=cal)


def test_a_sharp_lowpass_removes_the_energy_it_was_asked_to():
    """Parseval: for a projection, the energy removed is exactly the requested fraction.

    This is the check that the requested and realised fractions agree when the spectrum is
    broad enough to resolve the request -- the case density does not satisfy.
    """
    x = band_limited(24.0, seed=3)
    applied = apply("lowpass_ideal", [0.3], "vorticity", x)
    assert applied.energy_removed["vorticity"] == pytest.approx(0.3, abs=0.06)
    # For an ideal filter the removed energy and the difference energy are the same thing.
    assert applied.energy_changed["vorticity"] == pytest.approx(
        applied.energy_removed["vorticity"], rel=1e-6
    )


def test_a_steep_spectrum_makes_the_realised_removal_miss_the_request():
    """The density case, and the reason this is measured rather than inferred from the severity.

    A sharp filter cannot cut inside a wavenumber shell. Where a field's energy is concentrated in
    a few shells the realised removal therefore lands wherever the nearest shell boundary puts it,
    which can be far from what was asked for in either direction, while the same request is met
    closely on a broadband field.
    """
    steep = apply("highpass_ideal", [0.45], "density", band_limited(2.0, seed=4))
    broad = apply("highpass_ideal", [0.45], "vorticity", band_limited(24.0, seed=4))

    steep_error = abs(steep.energy_removed["density"] - 0.45)
    broad_error = abs(broad.energy_removed["vorticity"] - 0.45)
    assert broad_error < 0.06, (
        f"a broadband field should meet the request closely, missed by {broad_error:.3f}"
    )
    assert steep_error > 5 * broad_error, (
        "a two-shell spectrum should miss the request by far more than a broadband one does; "
        f"missed by {steep_error:.3f} against {broad_error:.3f}"
    )


def test_a_translation_relocates_energy_rather_than_removing_it():
    """energy_removed near zero with energy_changed large is the signature, not a defect."""
    from fmeval.ladder import apply_severity_level

    x = band_limited(12.0, seed=5)
    frame = _frame_of("vorticity", x)
    severity_level = build_ladder({"translate_x": {"op": "translate", "severities": [6],
                                         "options": {"axis": "x"}}},
                        include_reference=False)[0]
    applied = apply_severity_level(severity_level, frame, ["vorticity"], seed=0)
    assert applied.energy_removed["vorticity"] == pytest.approx(0.0, abs=1e-10)
    assert applied.energy_changed["vorticity"] > 0.1


def test_additive_noise_adds_energy_so_the_removed_fraction_is_negative():
    from fmeval.ladder import apply_severity_level

    x = band_limited(12.0, seed=6)
    frame = _frame_of("vorticity", x)
    severity_level = build_ladder({"additive_noise": {"severities": [0.5]}},
                        include_reference=False)[0]
    applied = apply_severity_level(severity_level, frame, ["vorticity"], seed=0)
    assert applied.energy_removed["vorticity"] < 0
    assert applied.energy_changed["vorticity"] > 0


def test_the_reference_level_removes_and_changes_nothing():
    from fmeval.ladder import REFERENCE_LEVEL, apply_severity_level

    x = band_limited(12.0, seed=7)
    applied = apply_severity_level(
        REFERENCE_LEVEL, _frame_of("vorticity", x), ["vorticity"], seed=0
    )
    assert applied.energy_removed["vorticity"] == 0.0
    assert applied.energy_changed["vorticity"] == 0.0


def test_the_effect_is_measured_about_the_spatial_mean():
    """A large mean must not hide the effect, as it would if energies were taken about zero."""
    from fmeval.ladder import apply_severity_level

    fluctuation = band_limited(12.0, seed=8)
    frame_small = _frame_of("density", fluctuation)
    frame_large = _frame_of("density", fluctuation + 1000.0)
    severity_level = build_ladder({"lowpass_butterworth": {"severities": [0.3]}},
                        include_reference=False)[0]
    from fmeval.calibration import Calibration

    def removed(frame):
        cal = Calibration(
            {"density": calibrate_field([frame.fields["density"]], frame.grid, "density")}
        )
        return apply_severity_level(severity_level, frame, ["density"], seed=0,
                          calibration=cal).energy_removed["density"]

    assert removed(frame_large) == pytest.approx(removed(frame_small), rel=1e-6)
