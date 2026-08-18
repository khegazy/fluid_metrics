"""Can the harness carry the metrics that come next?

The existing contract tests hold the *registered* metrics to their declarations. This file
asks the complementary question: if a colleague sits down tomorrow and implements the
first-wave candidates from CLAUDE.md -- NM-2, BD-1, PS-4 -- does the harness carry them
without a code change, and does the acceptance protocol behave the way the documentation
says it will?

Every metric here is registered for the duration of one test and removed again. They are
deliberately *not* contributions to ``metrics/``: the point is to exercise the extension
surface as an outside contributor meets it, not to grow the panel. A metric that graduates
belongs in ``metrics/`` as its own bundle, with the card that bundle requires.

Two of these tests are the interesting ones scientifically:

* ``test_h_minus_one_is_more_displacement_tolerant_than_the_l2_baseline`` checks that the
  harness can actually *demonstrate* the central claim -- that a negative-Sobolev norm
  beats L2 on the double penalty -- rather than merely hosting both.
* ``test_the_impostor_is_scored_perfectly_by_a_spectrum_only_metric`` checks the IN-4
  canary against the class of metric AGENTS.md says it is aimed at.
"""

from __future__ import annotations

import numpy as np
import pytest

from degradations import registry as deg_registry
from fmeval import analysis as an
from fmeval.context import FieldContext, derive_rng, fluctuation_rms
from fmeval.data.base import GridSpec, TimeSelection
from fmeval.ladder import build_ladder
from fmeval.pipeline import DatasetInfo, run
from metrics import registry as metric_registry
from tests.conftest import synthetic_field
from tests.test_robustness import SyntheticTrajectory, temporary_metric  # noqa: F401

SHAPE: tuple[int, int] = (32, 16)  # non-square; large enough for a spectral ladder


def grid_for(shape: tuple[int, ...]) -> GridSpec:
    n = len(shape)
    return GridSpec(tuple(shape), (1.0,) * n, (True,) * n, ("x", "y", "z")[:n],
                    (0.0,) * n)


def ctx_for(x: np.ndarray, *, field: str = "vorticity", seed: int = 0) -> FieldContext:
    return FieldContext(
        field=field, grid=grid_for(x.shape[1:]), frame_index=0, time=0.0,
        fluctuation_rms=fluctuation_rms(x),
        rng=derive_rng(seed, "capability", 0, field),
    )


# --- reference implementations of first-wave candidates -----------------------------------
#
# Kept as plain functions so each test can register whichever it needs. Both are standard
# textbook definitions rather than novel constructions.


def h_minus_one(reference: np.ndarray, candidate: np.ndarray, *, ctx) -> float:
    """Homogeneous negative Sobolev norm ``||r - c||_{H^-1}`` of the difference.

    The NM-2 candidate. In Fourier space the homogeneous H^s norm of a periodic field is
    ``(sum_k |k|^{2s} |f_k|^2)^{1/2}``; at s = -1 the ``|k|^{-1}`` weight makes the norm
    insensitive to a displacement in proportion to how large the displaced structure is,
    which is what makes it a candidate cure for the double penalty. Standard definition;
    see e.g. Peyre (2018), ESAIM:COCV 24(4), 1489, Eq. (1.2) for the H^-1 / Wasserstein
    linearisation this is the norm half of.

    The ``k = 0`` mode is excluded because the homogeneous norm is undefined there; that
    makes the quantity blind to a uniform offset, which is a property of the norm rather
    than of this implementation.
    """
    difference = reference - candidate
    spatial = tuple(range(1, difference.ndim))
    spectrum = np.fft.fftn(difference, axes=spatial)
    wavenumbers = [
        2 * np.pi * np.fft.fftfreq(n, d=dx)
        for n, dx in zip(ctx.grid.shape, ctx.grid.spacing)
    ]
    k_squared = sum(g**2 for g in np.meshgrid(*wavenumbers, indexing="ij"))
    weight = np.zeros_like(k_squared)
    nonzero = k_squared > 0
    weight[nonzero] = 1.0 / k_squared[nonzero]
    n_cells = int(np.prod(ctx.grid.shape))
    return float(np.sqrt((np.abs(spectrum) ** 2 * weight).sum()) / n_cells)


def radial_energy_spectrum(x: np.ndarray) -> np.ndarray:
    """Energy in each integer wavenumber shell, summed over channels.

    A function of ``|F(x)|`` alone: invariant to every phase, and therefore to translation.
    """
    axes = np.meshgrid(
        *[np.fft.fftfreq(n) * n for n in x.shape[1:]], indexing="ij"
    )
    shells = np.sqrt(sum(a**2 for a in axes)).astype(int).ravel()
    n_shells = int(shells.max()) + 1
    out = np.zeros(n_shells)
    for channel in range(x.shape[0]):
        power = (np.abs(np.fft.fftn(x[channel])) ** 2).ravel()
        out += np.bincount(shells, power, minlength=n_shells)
    return out


def spectrum_distance(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Relative L1 distance between radial energy spectra: the BD-1 shape of metric."""
    r = radial_energy_spectrum(reference)
    c = radial_energy_spectrum(candidate)
    return float(np.abs(r - c).sum() / (r.sum() + 1e-300))


# --- the extension surface -----------------------------------------------------------------


def test_a_ctx_using_pairwise_metric_needs_no_harness_change(temporary_metric):
    """NM-2 registers, discovers its ctx, and runs through the pipeline as documented.

    The whole claim of the registry is that a metric is one decorated function and no edit
    anywhere else. This exercises that for the first-wave candidate that actually needs
    ``ctx`` -- it must read the grid spacing to build wavenumbers, so it cannot be written
    as the two-line ``mae(a, b)`` the simplest path covers.
    """
    temporary_metric(name="_h_minus_one", arity="pairwise",
                     fields=("*",), units="field", symmetric=True)(h_minus_one)
    spec = metric_registry.get("_h_minus_one")

    assert spec.takes_ctx, "ctx was not detected from the signature"
    assert spec.units == "field"

    ladder = build_ladder({"gaussian_blur": {"severities": [1.0, 2.0]}})
    result = run(SyntheticTrajectory(), [spec], ladder, fields=["density"],
                 dataset=DatasetInfo(name="synthetic"), seed=0)

    assert len(result.rows) > 0
    reference_rows = result.rows[result.rows["level"] == 0]
    assert np.allclose(reference_rows["value"], 0.0), (
        "a pairwise metric must return exactly 0 on the reference severity level"
    )


def test_a_vector_returning_metric_expands_into_one_row_per_component(temporary_metric):
    """``returns="vector"`` works end to end, which issue 012 leaves open.

    Issue 012 lists vector-valued metrics as deferred functionality. The *pipeline* half is
    already there: ``_emit`` ravels the return value and writes one row per component with
    the index in the ``component`` column. Recording that here means the remaining work is
    scoped to the report layer rather than rediscovered from scratch.

    An energy spectrum is the natural first such metric, and it is also the BD-1 candidate,
    so this doubles as a check that the shape of that metric is expressible.
    """
    n_shells = [0]

    @temporary_metric(name="_spectrum_profile", arity="pairwise",
                      fields=("*",), returns="vector", units="dimensionless")
    def _spectrum_profile(reference, candidate):
        """Per-shell energy difference: one number per wavenumber shell."""
        out = radial_energy_spectrum(reference) - radial_energy_spectrum(candidate)
        n_shells[0] = len(out)
        return out

    ladder = build_ladder({"gaussian_blur": {"severities": [1.0, 2.0]}})
    result = run(SyntheticTrajectory(), [metric_registry.get("_spectrum_profile")],
                 ladder, fields=["density"], dataset=DatasetInfo(name="synthetic"),
                 seed=0)

    components = result.rows["component"].astype(str).unique()
    assert len(components) == n_shells[0] > 1, (
        f"expected one row per shell, got components {sorted(components)}"
    )
    assert result.rows["value"].notna().all()


def test_a_new_degradation_inherits_the_whole_contract(temporary_degradation_local):
    """A degradation is one decorated function, and the ladder machinery picks it up.

    The counterpart of the metric test above, for the other open extension surface. What is
    checked here is only that registration, discovery, sorting and application work; the
    substantive checks (direction verification, seed reproducibility) live in
    ``test_degradation_contract.py`` and are parametrized over the registry, which is where
    a real operator would meet them.
    """

    @temporary_degradation_local(name="_probe_quantise", family="pointwise",
                                 severity_name="levels", severity_units="",
                                 severity_direction="decreasing")
    def _probe_quantise(x, severity, *, ctx):
        """Quantise the fluctuation to ``severity`` levels: fewer levels is worse."""
        if severity <= 0:
            return x
        spatial = tuple(range(1, x.ndim))
        mean = x.mean(axis=spatial, keepdims=True)
        fluctuation = x - mean
        scale = np.abs(fluctuation).max() or 1.0
        step = 2.0 * scale / severity
        return mean + np.round(fluctuation / step) * step

    severity_levels = build_ladder({"quantise": {"op": "_probe_quantise",
                                       "severities": [4, 16, 64]}},
                         include_reference=False)

    # `decreasing` means a smaller value is worse, so the mildest severity level must be the largest.
    assert [r.severity for r in severity_levels] == [64.0, 16.0, 4.0], (
        "sort_severities did not order a decreasing-direction ladder by increasing damage"
    )

    field = synthetic_field(SHAPE, 1, seed=0)
    spec = deg_registry.get("_probe_quantise")
    damage = [
        float(np.mean((field - spec.fn(field, r.severity, ctx=ctx_for(field))) ** 2))
        for r in severity_levels
    ]
    assert damage == sorted(damage), (
        f"damage {damage} is not increasing across severity_levels {[r.severity for r in severity_levels]}; "
        "severity_direction='decreasing' would be wrong"
    )


@pytest.fixture
def temporary_degradation_local():
    """Register a degradation for one test and remove it again."""
    added: list[str] = []

    def _register(**kwargs):
        def _decorate(fn):
            added.append(kwargs.get("name") or fn.__name__)
            return deg_registry.degradation(**kwargs)(fn)

        return _decorate

    yield _register
    for name in added:
        deg_registry.REGISTRY.pop(name, None)


# --- the protocol's own claims ---------------------------------------------------------------


def test_the_impostor_preserves_the_radial_energy_spectrum():
    """IN-4's construction does what its docstring claims, on a non-square grid.

    ``gaussian_impostor`` says it "keeps ``|X_k|`` exactly -- hence the energy spectrum,
    the two-point correlation, and every isotropic spectral diagnostic". The existing
    contract test checks the per-mode amplitudes with ``match_moments`` off. This checks
    the *radial* spectrum with ``match_moments`` on, which is the default and the form the
    ladder actually runs, because the moment restoration rescales the field and could in
    principle disturb what the construction is for.

    Measured on the real 256^2 vorticity field at t = 5000: relative L1 error between the
    radial spectra is 1.6e-16 with match_moments on and 1.5e-16 with it off, i.e. exact.
    """
    deg_registry.discover()
    field = synthetic_field(SHAPE, 1, seed=0)
    spec = deg_registry.get("gaussian_impostor")

    for match_moments in (True, False):
        impostor = spec.fn(field, 0, ctx=ctx_for(field), match_moments=match_moments)
        before = radial_energy_spectrum(field)
        after = radial_energy_spectrum(impostor)
        error = float(np.abs(after - before).sum() / before.sum())
        assert error < 1e-10, (
            f"match_moments={match_moments}: radial spectrum changed by a relative "
            f"{error:.2e}; the canary's whole construction is that it does not"
        )


def test_the_impostor_is_scored_perfectly_by_a_spectrum_only_metric(temporary_metric):
    """The IN-4 canary must catch the class of metric it is aimed at.

    AGENTS.md, "Traps that have already caught someone": the canary "is aimed at
    quantities that are functions of ``|F(f)|`` alone -- an energy spectrum (BD-1), a
    two-point correlation (BD-2) -- which score it *perfectly*". This is the direct test of
    that claim, and it passes at the level of the raw metric value: a spectrum-only metric
    really cannot tell the impostor from the reference.

    What the *report* then does with that value is a separate matter, and it is broken --
    see ``test_damage_is_not_reported_against_an_anchor_the_metric_cannot_see`` in
    ``tests/test_robustness.py``. The two tests together locate the problem
    precisely: the canary construction is sound, the normalisation it is read through is
    not.
    """
    deg_registry.discover()
    field = synthetic_field(SHAPE, 1, seed=0)
    impostor = deg_registry.get("gaussian_impostor").fn(
        field, 0, ctx=ctx_for(field), match_moments=True
    )
    blurred = deg_registry.get("gaussian_blur").fn(field, 2.0, ctx=ctx_for(field))

    on_impostor = spectrum_distance(field, impostor)
    on_blur = spectrum_distance(field, blurred)

    assert on_impostor < 1e-10, (
        f"a |F(f)|-only metric scored the impostor at {on_impostor:.2e}; the canary is "
        "supposed to be invisible to it"
    )
    assert on_blur > 1e-3, (
        f"the same metric scored a sigma=2 blur at {on_blur:.2e}, so it is not simply "
        "insensitive to everything"
    )


@pytest.mark.data
def test_h_minus_one_is_more_displacement_tolerant_than_the_l2_baseline(temporary_metric):
    """The harness can demonstrate the project's central claim, not merely host it.

    CLAUDE.md frames the double penalty as the pathology every metric here exists to
    address, and lists NM-2 as a first-wave candidate. The check is that the harness's own
    machinery -- the translation ladder, the measured anchor, the damage score -- shows
    NM-2 climbing more slowly than L2 under pure displacement. If it did not, the ladder or
    the normalisation would be wrong, because the analytic answer is not in doubt: the
    ``|k|^-1`` weight suppresses exactly the high wavenumbers a small shift excites.

    Measured through the real pipeline on the 256^2 production trajectory
    (t = 5000..6000, vorticity), damage relative to the unrelated-field anchor:

        displacement   1 cell   4 cells   16 cells
        mse             0.028     0.233      0.517
        h_minus_one     0.018     0.069      0.237

    The gap widens with distance, which is the double penalty being softened rather than
    merely rescaled -- so the ordering is a property, not a normalisation artefact, and
    that is what is asserted here.

    **Marked ``data``, and it has to be.** The result is a statement about a broadband
    turbulent field, not about H^-1 in the abstract: which of the two grows faster under a
    shift depends on where the field keeps its energy. On the conftest synthetic field --
    two sine modes on a 32-cell grid, where one cell is 3% of the domain and there is
    almost no small-scale content for the ``|k|^-1`` weight to suppress -- the ordering
    reverses (H^-1 damage 0.22 against L2's 0.09 at one cell). Pinning this on a synthetic
    fixture would mean tuning the fixture until it agreed, which is the opposite of
    evidence.
    """
    from pathlib import Path

    from fmeval.data.kinet_raw import KinetRawTrajectory
    from fmeval.derived import recompute_frame

    path = Path(
        "datasets/kinet/doubly_periodic/weakly_compressible_isoT_fluids/"
        "sys_Re-5e4_Ma-1en1/D2Q9_shape-256-256_T-10000_H-dc804f.h5"
    )
    if not path.exists():
        pytest.skip(f"production trajectory not readable at {path}")

    temporary_metric(name="_h_minus_one", arity="pairwise",
                     fields=("*",), units="field", symmetric=True)(h_minus_one)
    metric_registry.discover()
    deg_registry.discover()

    class _Recomputing:
        """The wrapper evaluate.py applies, so vorticity is our spectral curl."""

        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def __len__(self):
            return len(self._inner)

        def frame(self, t, fields):
            return recompute_frame(self._inner.frame(t, fields))

    specs = [metric_registry.get("mse"), metric_registry.get("_h_minus_one")]
    severity_levels = build_ladder({
        "translate_x": {"op": "translate", "severities": [1, 2, 4],
                        "options": {"axis": "x"}},
        "uncorrelated": {"op": "random_large_translation", "severities": [0, 1, 2]},
    })
    trajectory = _Recomputing(KinetRawTrajectory(path))
    try:
        result = run(
            trajectory, specs, severity_levels, fields=["velocity", "vorticity"],
            # Developed flow: the dev trajectory is the first 100 solver steps and is
            # explicitly not physically representative.
            selection=TimeSelection(start=5000, stop=6001, reduction=250),
            dataset=DatasetInfo(name="kinet_re5e4"), seed=0,
        )
    finally:
        trajectory.close()
    result.rows = result.rows[result.rows["field"] == "vorticity"]

    norm = an.normalisation(result.rows)
    assert not norm["degenerate"].any(), (
        "the translation anchor is degenerate for one of these metrics, so the "
        "comparison below would be a ratio of round-off"
    )
    scored = an.add_damage(result.rows, norm)
    translation = scored[scored["degradation"] == "translate_x"]
    damage = translation.groupby(["metric", "severity"], observed=True)["damage"].median()

    for severity in sorted(translation["severity"].unique()):
        l2 = damage[("mse", severity)]
        sobolev = damage[("_h_minus_one", severity)]
        assert sobolev < l2, (
            f"at a {severity:g}-cell displacement H^-1 damage {sobolev:.4f} is not below "
            f"L2 damage {l2:.4f}; the negative-Sobolev weight should suppress exactly the "
            "high wavenumbers a small shift excites"
        )

    widest = sorted(translation["severity"].unique())[-1]
    narrowest = sorted(translation["severity"].unique())[0]
    assert (damage[("mse", widest)] / damage[("_h_minus_one", widest)]
            > damage[("mse", narrowest)] / damage[("_h_minus_one", narrowest)]), (
        "the advantage does not grow with displacement, which would mean the two metrics "
        "differ by a constant factor rather than in position tolerance"
    )


def test_two_metrics_can_rank_identically_and_still_differ_in_magnitude(temporary_metric):
    """Rank correlation alone must not be allowed to prune a panel.

    AGENTS.md records this as an interpretive trap: MAE and MSE correlate at 0.995 across
    the ladder yet differ by 55x in displacement damage, "for ranking they are duplicates;
    as losses they are not". The redundancy table is built from
    ``cross_metric_correlation`` alone, so this is the test that the trap is real in the
    harness rather than only in the prose -- if a future change made the two agree in
    magnitude as well, the warning in the documentation would have quietly become false.
    """
    metric_registry.discover()
    deg_registry.discover()
    specs = [metric_registry.get("mae"), metric_registry.get("mse")]
    severity_levels = build_ladder({
        "gaussian_blur": {"severities": [0.5, 1.0, 2.0, 4.0]},
        "translate_x": {"op": "translate", "severities": [1, 2, 4],
                        "options": {"axis": "x"}},
        "uncorrelated": {"op": "random_large_translation", "severities": [0, 1, 2]},
    })
    result = run(SyntheticTrajectory(SHAPE), specs, severity_levels, fields=["density"],
                 dataset=DatasetInfo(name="synthetic"), seed=0)

    correlation = an.cross_metric_correlation(result.rows, field="density")
    rho = float(correlation.loc["mae", "mse"])
    assert rho > 0.9, f"MAE and MSE rank differently here (rho={rho:.3f})"

    norm = an.normalisation(result.rows)
    scored = an.add_damage(result.rows, norm)
    translation = scored[scored["degradation"] == "translate_x"]
    smallest = translation[translation["severity"] == translation["severity"].min()]
    by_metric = smallest.groupby("metric", observed=True)["damage"].median()
    ratio = float(by_metric["mse"] / by_metric["mae"])

    assert not np.isclose(ratio, 1.0, rtol=0.5), (
        f"MAE and MSE rank together (rho={rho:.3f}) and now also agree in magnitude "
        f"(ratio {ratio:.2f}); the documented warning that rank agreement does not imply "
        "interchangeability would no longer be supported by the code"
    )
