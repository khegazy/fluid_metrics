"""The degradation contract, parametrized over the whole registry, plus ladder mechanics.

The highest-value check here is ``test_declared_direction_is_true``: it *verifies* the
declared ``severity_direction`` by measuring that damage actually rises with level. A
reversed severity list would otherwise silently invert every Spearman computed from that
axis, and nothing else in the pipeline would notice.
"""

from __future__ import annotations

import numpy as np
import pytest

from degradations import registry as deg
from fmeval.context import FieldContext, derive_rng, fluctuation_rms
from fmeval.data.base import Frame, GridSpec
from fmeval.ladder import (
    REFERENCE_RUNG,
    Rung,
    apply_rung,
    build_ladder,
    ladder_axes,
    ordinal_axes,
)
from fmeval.calibration import calibrate_field
from tests.conftest import synthetic_field

#: Grid for the calibrated operators. Larger and with a red spectrum, because a calibrated
#: severity is a fraction of a measured property: on a small broadband field the characteristic
#: scale is a couple of cells, every scale fraction rounds to a no-op, and the direction test
#: would pass vacuously while checking nothing.
CALIBRATION_SHAPE = (64, 48)

SHAPE = (32, 16)  # non-square, and divisible by the coarsening factors under test


def grid(shape: tuple[int, ...] = SHAPE) -> GridSpec:
    n = len(shape)
    return GridSpec(tuple(shape), (1.0,) * n, (True,) * n, ("x", "y", "z")[:n],
                    (0.0,) * n)


def ctx_for(x: np.ndarray, seed: int = 0, label: str = "t") -> FieldContext:
    """Context matching the array actually passed in, not a fixed shape."""
    return FieldContext(
        field="vorticity",
        grid=grid(x.shape[1:]),
        frame_index=0,
        time=0.0,
        fluctuation_rms=fluctuation_rms(x),
        rng=derive_rng(seed, label, 0, "vorticity"),
    )


def smooth_field(shape: tuple[int, ...] = CALIBRATION_SHAPE) -> np.ndarray:
    """A field with a decaying spectrum, so it has a characteristic scale to calibrate against."""
    rng = np.random.default_rng(7)
    noise = rng.standard_normal((1, *shape))
    axes = np.meshgrid(*[np.fft.fftfreq(n) * n for n in shape], indexing="ij")
    k = np.sqrt(sum(a ** 2 for a in axes))
    transfer = 1.0 / (1.0 + k ** 2)
    return np.real(np.fft.ifftn(np.fft.fftn(noise[0]) * transfer))[None]


def resolve_for(spec: deg.DegradationSpec, x: np.ndarray, severity: float) -> float:
    """Turn a config-facing severity into the value the operator actually receives.

    Calibrated operators take an absolute cutoff or width while their config severity is a
    fraction, so a test that passes the config number straight to the function is testing a
    different quantity than the one whose direction is declared.
    """
    if spec.calibration is None:
        return severity
    measured = calibrate_field([x], grid(x.shape[1:]), "vorticity")
    if spec.calibration == "scale":
        return measured.length_for_scale_fraction(severity)
    side = "above" if spec.calibration == "energy_above" else "below"
    return measured.cutoff_removing_energy(severity, side)


def call(spec: deg.DegradationSpec, x: np.ndarray, severity: float, **kw) -> np.ndarray:
    """Apply an operator to ``x`` at a config-facing severity, resolving it if calibrated."""
    return call_absolute(spec, x, resolve_for(spec, x, severity), **kw)


def call_absolute(spec: deg.DegradationSpec, x: np.ndarray, severity: float,
                  **kw) -> np.ndarray:
    """Apply an operator at a severity already in its own units.

    Used by the tests that are about a filter's spectral behaviour rather than about the
    ladder, where a wavenumber is the meaningful thing to state.
    """
    kwargs = dict(spec.defaults)
    kwargs.update(kw)
    if spec.takes_ctx:
        kwargs["ctx"] = ctx_for(x)
    return spec.fn(x, severity, **kwargs)


def calibration_for(frame, fields: list[str]):
    """A Calibration covering ``fields``, for the tests that apply a calibrated operator."""
    from fmeval.calibration import Calibration

    return Calibration(
        {name: calibrate_field([frame.fields[name]], frame.grid, name) for name in fields}
    )


#: Severities that meaningfully exercise each operator, in increasing-damage order.
LADDERS: dict[str, list[float]] = {
    "identity": [0],
    # The calibrated operators take their severities in config units -- a fraction of the
    # characteristic scale, or of the energy to remove -- and `call` resolves them.
    "gaussian_blur": [0.02, 0.06, 0.15, 0.30],
    "box_blur": [0.06, 0.15, 0.30],
    "median_blur": [0.06, 0.15, 0.30],
    "disk_blur": [0.06, 0.15, 0.30],
    "epanechnikov_blur": [0.06, 0.15, 0.30],
    "lowpass_ideal": [0.05, 0.20, 0.45],
    "lowpass_butterworth": [0.05, 0.20, 0.45],
    "highpass_ideal": [0.45, 0.70, 0.90],
    "highpass_butterworth": [0.45, 0.70, 0.90],
    "band_attenuate": [0.8, 0.4, 0.0],
    "translate": [1, 2, 4],
    "translate_subpixel": [0.25, 0.5, 1.0],
    "coarsen": [2, 4, 8],
    "subsample": [2, 4, 8],
    "additive_noise": [0.01, 0.1, 0.5],
    "multiplicative_noise": [0.01, 0.1, 0.5],
    "gaussian_impostor": [0],
    "random_large_translation": [0, 1, 2],   # draw indices, not damage levels
    "gain": [0.05, 0.2, 0.5],
    "bias": [0.05, 0.2, 0.5],
}


@pytest.fixture(params=sorted(deg.available()))
def spec(request) -> deg.DegradationSpec:
    return deg.get(request.param)


def test_no_import_errors():
    assert deg.discover() == {}


def test_every_operator_has_a_test_ladder(spec):
    """A new operator must be added to LADDERS, or it escapes every check below."""
    assert spec.name in LADDERS, f"add {spec.name!r} to LADDERS in this file"


def test_preserves_shape_and_dtype(spec):
    x = synthetic_field(SHAPE, 2, seed=0)
    out = call(spec, x, LADDERS[spec.name][-1])
    assert out.shape == x.shape
    assert np.asarray(out).dtype == np.float64
    assert np.isfinite(out).all(), f"{spec.name} produced non-finite values"


def test_zero_severity_is_a_passthrough(spec):
    """Level 0 must be a no-op, or pairwise metrics do not return 0 on the clean rung."""
    if spec.name in {"gaussian_impostor", "random_large_translation", "band_attenuate",
                     "lowpass_ideal", "lowpass_butterworth", "highpass_ideal",
                     "highpass_butterworth", "median_blur"}:
        pytest.skip("severity 0 is not a no-op for this operator")
    x = synthetic_field(SHAPE, 1, seed=0)
    assert np.allclose(call(spec, x, 0), x, rtol=0, atol=1e-15)


def test_declared_direction_is_true(spec):
    """Verify severity_direction by measuring that damage rises with level.

    A reversed list inverts the Spearman for that axis, silently.
    """
    if not spec.ordinal or spec.name == "identity":
        pytest.skip("not on a monotone axis")
    x = (smooth_field() if spec.calibration
         else synthetic_field(SHAPE, 1, seed=0, noise=0.02))
    severities = spec.sort_severities(LADDERS[spec.name])
    damage = [float(((x - call(spec, x, s)) ** 2).mean()) for s in severities]
    assert damage[-1] > 0, (
        f"{spec.name}: the harshest test severity does nothing, so this test proves nothing; "
        "the entry in LADDERS is too mild for the field it is applied to"
    )
    assert damage == sorted(damage), (
        f"{spec.name}: damage {damage} is not increasing across sorted severities "
        f"{severities}; severity_direction={spec.severity_direction!r} may be wrong"
    )


def test_sort_severities_orders_by_damage(spec):
    """Config order must not matter: the builder sorts into increasing-damage order."""
    given = LADDERS[spec.name]
    assert spec.sort_severities(list(reversed(given))) == spec.sort_severities(given)


def test_deterministic_operators_are_reproducible(spec):
    if spec.stochastic:
        pytest.skip("stochastic")
    x = synthetic_field(SHAPE, 1, seed=0)
    s = LADDERS[spec.name][-1]
    assert np.array_equal(call(spec, x, s), call(spec, x, s))


def test_stochastic_operators_are_seed_reproducible(spec):
    if not spec.stochastic:
        pytest.skip("deterministic")
    x = synthetic_field(SHAPE, 1, seed=0)
    s = LADDERS[spec.name][-1]
    kw = dict(spec.defaults)

    def run(seed, frame_index, field):
        c = FieldContext("vorticity", grid(), frame_index, 0.0, fluctuation_rms(x),
                         derive_rng(seed, "lbl", frame_index, field))
        return spec.fn(x, s, **{**kw, "ctx": c})

    assert np.array_equal(run(7, 0, "vorticity"), run(7, 0, "vorticity"))
    assert not np.array_equal(run(7, 0, "vorticity"), run(7, 1, "vorticity"))
    assert not np.array_equal(run(7, 0, "vorticity"), run(7, 0, "density"))
    assert not np.array_equal(run(7, 0, "vorticity"), run(8, 0, "vorticity"))


# --- operator-specific properties ---------------------------------------------------


def test_translate_is_periodic():
    x = synthetic_field(SHAPE, 1, seed=0)
    s = deg.get("translate")
    assert np.array_equal(call(s, x, SHAPE[0], axis="x"), x)


def test_translate_moves_the_declared_axis():
    """axis='x' must move axis -2 on a 2D grid, not axis -1."""
    x = synthetic_field(SHAPE, 1, seed=0)
    s = deg.get("translate")
    assert np.array_equal(call(s, x, 3, axis="x"), np.roll(x, 3, axis=-2))
    assert np.array_equal(call(s, x, 3, axis="y"), np.roll(x, 3, axis=-1))


def test_subpixel_translate_matches_roll_at_integer_distance():
    """The sub-pixel operator must agree with the exact one where both are defined."""
    x = synthetic_field(SHAPE, 1, seed=0)
    s = deg.get("translate_subpixel")
    for d in (1, 2, 5):
        assert np.allclose(call(s, x, d, axis="x"), np.roll(x, d, axis=-2), atol=1e-10)


def test_subpixel_translate_resolves_below_one_cell():
    """The whole point: sub-cell displacement must be distinguishable from 0 and from 1."""
    x = synthetic_field(SHAPE, 1, seed=0)
    s = deg.get("translate_subpixel")
    half = call(s, x, 0.5, axis="x")
    assert not np.allclose(half, x)
    assert not np.allclose(half, np.roll(x, 1, axis=-2))


def test_impostor_preserves_the_spectrum_exactly():
    """IN-4's defining property: identical |X_k|, hence identical E(k)."""
    x = synthetic_field((32, 32), 1, seed=0, noise=0.3)
    y = call(deg.get("gaussian_impostor"), x, 0)
    assert np.allclose(np.abs(np.fft.fftn(x[0])), np.abs(np.fft.fftn(y[0])), rtol=1e-8)


def _flatness(a: np.ndarray) -> float:
    f = a - a.mean()
    return float((f**4).mean() / (f**2).mean() ** 2)


def test_impostor_is_real_and_gaussian():
    """Hermitian symmetry must hold, and the result must actually be Gaussian.

    A hand-drawn-phase implementation fails both: ``irfftn`` silently discards imaginary
    parts and the flatness lands far from 3 (an earlier attempt gave 47.9).

    Flatness is a fourth moment and noisy on one realisation -- measured spread on a 64^2
    grid is 2.9 +/- 0.2 across seeds -- so the tight assertion is on the mean over several
    seeds, with a loose per-seed bound that still separates 3 from a broken 48.
    """
    spec = deg.get("gaussian_impostor")
    # Strongly intermittent: sparse spikes on a smooth background.
    x = synthetic_field((64, 64), 1, seed=0, noise=0.0)
    x[0, ::16, ::16] += 20.0
    assert _flatness(x[0]) > 50, "test field is not intermittent enough to discriminate"

    g = grid((64, 64))
    values = []
    for seed in range(8):
        c = FieldContext("v", g, 0, 0.0, fluctuation_rms(x),
                         derive_rng(seed, "impostor", 0, "v"))
        y = spec.fn(x, 0, ctx=c, **spec.defaults)
        assert np.isrealobj(y) and np.isfinite(y).all()
        f = _flatness(y[0])
        assert f < 10, (
            f"impostor flatness {f:.2f} is nowhere near Gaussian; the phase construction "
            "is probably violating Hermitian symmetry"
        )
        values.append(f)
    assert float(np.mean(values)) == pytest.approx(3.0, abs=0.3)


def test_impostor_matches_moments():
    x = synthetic_field((32, 32), 1, seed=0, noise=0.3)
    y = call(deg.get("gaussian_impostor"), x, 0)
    assert y.mean() == pytest.approx(x.mean(), rel=1e-9)
    assert y.std() == pytest.approx(x.std(), rel=1e-9)


def test_random_large_translation_preserves_every_statistic():
    """It is a roll, so it is a perfect statistical twin -- that is the whole point."""
    x = synthetic_field((32, 32), 1, seed=0, noise=0.3)
    y = call(deg.get("random_large_translation"), x, 0)
    assert sorted(y.ravel().tolist()) == pytest.approx(sorted(x.ravel().tolist()))
    assert y.mean() == pytest.approx(x.mean(), rel=1e-12)
    assert y.std() == pytest.approx(x.std(), rel=1e-12)
    assert _flatness(y[0]) == pytest.approx(_flatness(x[0]), rel=1e-12)
    assert np.allclose(np.abs(np.fft.fftn(y[0])), np.abs(np.fft.fftn(x[0])), rtol=1e-8)


def _draws(x, n=8, shape=None):
    spec = deg.get("random_large_translation")
    g = grid(shape or x.shape[1:])
    return [
        spec.fn(x, 0, ctx=FieldContext("v", g, 0, 0.0, fluctuation_rms(x),
                                       derive_rng(seed, "unc", 0, "v")))
        for seed in range(n)
    ]


def test_random_large_translation_always_moves_by_at_least_a_quarter_domain():
    """The guarantee the operator makes: offsets come from the middle half of each axis."""
    x = np.arange(64 * 64, dtype=float).reshape(1, 64, 64)  # every cell distinguishable
    for y in _draws(x, shape=(64, 64)):
        # Recover the offset from where the original first element ended up.
        idx = int(np.argwhere(y[0] == 0.0)[0][0])
        assert 16 <= idx <= 48, f"offset {idx} is outside the middle half"


def test_random_large_translation_decorrelates_a_broadband_field():
    """Averaged over draws it reaches the uncorrelated limit on a realistic field.

    Deliberately broadband. A field dominated by one large-scale mode is a known bad case
    -- see the caveat in the operator docstring -- and the median over draws, not any
    single draw, is what the anchor uses.
    """
    rng = np.random.default_rng(0)
    x = synthetic_field((64, 64), 1, seed=0, noise=1.0)
    x += 0.5 * rng.standard_normal(x.shape)
    corrs = [abs(float(np.corrcoef(x.ravel(), y.ravel())[0, 1])) for y in _draws(x)]
    assert float(np.median(corrs)) < 0.2, f"median |corr| over draws is {corrs}"


def test_random_large_translation_is_not_ordinal():
    """It is a reference measurement defining D = 1, not a rung on a monotone axis."""
    assert deg.get("random_large_translation").ordinal is False


def test_impostor_is_not_ordinal():
    """The canary must be excluded from rank correlation by declaration."""
    assert deg.get("gaussian_impostor").ordinal is False


def test_lowpass_then_highpass_reconstructs():
    """Ideal filters at a shared cutoff partition the spectrum, up to two shared modes.

    Both keep the cutoff band |k| == c, and the high-pass additionally keeps k = 0 on
    purpose (see highpass_ideal), so each is counted twice and subtracted once.
    """
    from degradations.spectral import _apply_filter, _wavenumber_magnitude

    x = synthetic_field((32, 32), 1, seed=0, noise=0.3)
    lo = call_absolute(deg.get("lowpass_ideal"), x, 8)
    hi = call_absolute(deg.get("highpass_ideal"), x, 8)
    k = _wavenumber_magnitude((32, 32))
    overlap = _apply_filter(x, (k == 8).astype(float))
    mean = np.full_like(x, x.mean())
    assert np.allclose(lo + hi - overlap - mean, x, atol=1e-10)


def test_gain_preserves_the_mean_and_moves_only_amplitude():
    x = synthetic_field(SHAPE, 1, seed=0)
    y = call(deg.get("gain"), x, 0.5)
    assert y.mean() == pytest.approx(x.mean(), rel=1e-12)
    fluct_x, fluct_y = x - x.mean(), y - y.mean()
    assert np.allclose(fluct_y, 1.5 * fluct_x)


def test_bias_shifts_the_mean_only():
    x = synthetic_field(SHAPE, 1, seed=0)
    y = call(deg.get("bias"), x, 0.25)
    assert np.allclose(y - x, 0.25 * fluctuation_rms(x))


def test_coarsen_is_conservative_and_subsample_is_not():
    x = synthetic_field((32, 16), 1, seed=0, noise=0.3)
    co = call(deg.get("coarsen"), x, 4)
    su = call(deg.get("subsample"), x, 4)
    assert co.mean() == pytest.approx(x.mean(), abs=1e-12)
    assert not np.allclose(co, su)


# --- ladder construction --------------------------------------------------------------


def test_build_ladder_expands_entries():
    rungs = build_ladder({"gaussian_blur": {"severities": [1.0, 2.0]}})
    assert [r.variant_label for r in rungs] == [
        "reference", "gaussian_blur_l1", "gaussian_blur_l2"
    ]
    assert [r.level for r in rungs] == [0, 1, 2]
    assert [r.severity for r in rungs] == [0.0, 1.0, 2.0]


def test_build_ladder_sorts_decreasing_direction_correctly():
    """A decreasing-direction list is worst-last after sorting, however it was written.

    ``band_attenuate`` is the example because its severity is the fraction *retained*, so
    smaller is worse. The spectral filters used to be the example, but their severity is now
    the fraction of energy removed, which rises with damage like everything else.
    """
    assert deg.get("band_attenuate").severity_direction == "decreasing"
    for given in ([0.8, 0.5, 0.2, 0.0], [0.0, 0.2, 0.5, 0.8]):
        rungs = build_ladder({"band_attenuate": {"severities": given}},
                             include_reference=False)
        assert [r.severity for r in rungs] == [0.8, 0.5, 0.2, 0.0]
        assert [r.level for r in rungs] == [1, 2, 3, 4]


def test_build_ladder_supports_two_instances_of_one_operator():
    cfg = {
        "translate_x": {"op": "translate", "severities": [1, 2], "options": {"axis": "x"}},
        "translate_y": {"op": "translate", "severities": [1, 2], "options": {"axis": "y"}},
    }
    rungs = build_ladder(cfg, include_reference=False)
    assert ladder_axes(rungs) == ["translate_x", "translate_y"]
    assert {r.op for r in rungs} == {"translate"}


def test_build_ladder_honours_enabled_only_and_skip():
    cfg = {
        "gaussian_blur": {"severities": [1]},
        "median_blur": {"severities": [3], "enabled": False},
        "coarsen": {"severities": [2]},
    }
    assert ladder_axes(build_ladder(cfg)) == ["gaussian_blur", "coarsen"]
    assert ladder_axes(build_ladder(cfg, only=["coarsen"])) == ["coarsen"]
    assert ladder_axes(build_ladder(cfg, skip=["coarsen"])) == ["gaussian_blur"]


def test_ordinal_axes_excludes_the_canary():
    cfg = {
        "gaussian_blur": {"severities": [1, 2]},
        "gaussian_impostor": {"severities": [0]},
    }
    rungs = build_ladder(cfg)
    assert ladder_axes(rungs) == ["gaussian_blur", "gaussian_impostor"]
    assert ordinal_axes(rungs) == ["gaussian_blur"]


def test_build_ladder_rejects_malformed_entries():
    with pytest.raises(ValueError, match="no 'severities'"):
        build_ladder({"gaussian_blur": {}})
    with pytest.raises(ValueError, match="unexpected keys"):
        build_ladder({"gaussian_blur": {"severities": [1], "typo": 3}})
    with pytest.raises(KeyError, match="unknown degradation"):
        build_ladder({"nope": {"severities": [1]}})


# --- applying rungs to frames ---------------------------------------------------------


def _frame() -> Frame:
    g = grid()
    return Frame(
        index=3,
        time=1.5,
        fields={
            "density": 1.0 + 1e-3 * synthetic_field(SHAPE, 1, seed=1),
            "velocity": 0.04 * synthetic_field(SHAPE, 2, seed=2),
        },
        grid=g,
    )


def test_apply_reference_rung_returns_the_originals():
    frame = _frame()
    out, _, _ = apply_rung(REFERENCE_RUNG, frame, ["density", "velocity"], seed=0)
    for name, arr in out.items():
        assert arr is frame.fields[name]


def test_apply_rung_degrades_every_requested_field():
    frame = _frame()
    rung = build_ladder({"gaussian_blur": {"severities": [0.3]}},
                        include_reference=False)[0]
    out, resolved, _ = apply_rung(
        rung, frame, ["density", "velocity"], seed=0,
        calibration=calibration_for(frame, ["density", "velocity"]),
    )
    assert set(out) == {"density", "velocity"}
    assert set(resolved) == {"density", "velocity"}
    for name, arr in out.items():
        assert arr.shape == frame.fields[name].shape
        assert not np.allclose(arr, frame.fields[name])


def test_apply_rung_is_invariant_to_frame_iteration_order():
    """Seeding from content, not call order, is what makes parallelisation safe later."""
    frame = _frame()
    rung = build_ladder({"additive_noise": {"severities": [0.1]}},
                        include_reference=False)[0]
    first = apply_rung(rung, frame, ["density"], seed=11)[0]["density"]
    _ = apply_rung(rung, frame, ["velocity"], seed=11)  # advance nothing
    again = apply_rung(rung, frame, ["density"], seed=11)[0]["density"]
    assert np.array_equal(first, again)


def test_noise_scales_with_the_reference_rms_not_the_raw_rms():
    """Density is 1.0 +/- 1e-3: scaling by the raw RMS would be pure destruction."""
    frame = _frame()
    rung = build_ladder({"additive_noise": {"severities": [0.1]}},
                        include_reference=False)[0]
    rms = fluctuation_rms(frame["density"])
    out = apply_rung(rung, frame, ["density"], seed=0,
                     reference_rms={"density": rms})[0]["density"]
    perturbation = np.abs(out - frame["density"]).mean()
    assert perturbation < 0.5 * frame["density"].mean(), "noise swamped the signal"
    assert perturbation == pytest.approx(0.1 * rms * np.sqrt(2 / np.pi), rel=0.25)


def test_highpass_preserves_the_spatial_mean():
    """Removing k=0 would swamp the ladder on any field with a large mean.

    Density is 1.0 with fluctuations of order 1e-4. Before the mean was preserved, every
    high-pass rung gave an identical damage 2.7e7 times the unrelated-field level, so the
    axis carried no ordering and its rank correlation collapsed to 0.10.
    """
    x = 1.0 + 1e-3 * synthetic_field((32, 32), 1, seed=0, noise=0.3)
    for name in ("highpass_ideal", "highpass_butterworth"):
        for cutoff in (2, 4, 8):
            y = call_absolute(deg.get(name), x, cutoff)
            assert y.mean() == pytest.approx(x.mean(), rel=1e-10), name


def test_highpass_ladder_is_monotone_on_a_field_with_a_large_mean():
    """Monotone, and on the scale of the fluctuation rather than of the mean."""
    x = 1.0 + 1e-3 * synthetic_field((32, 32), 1, seed=0, noise=0.3)
    spec = deg.get("highpass_ideal")
    damage = [float(((x - call_absolute(spec, x, c)) ** 2).mean())
              for c in (2, 4, 8, 16)]
    assert damage == sorted(damage), f"high-pass ladder is not monotone: {damage}"
    assert damage[-1] > 1.5 * damage[0], f"ladder has little dynamic range: {damage}"
    # The decisive check: before the fix every rung sat ~1e7 times the fluctuation
    # variance, because the mean was being deleted.
    variance = float(np.var(x))
    assert damage[-1] < variance, (
        f"damage {damage[-1]:.3e} exceeds the fluctuation variance {variance:.3e}; "
        "the filter is probably removing the spatial mean"
    )
