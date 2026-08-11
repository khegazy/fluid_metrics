"""Failure-mode tests: what the harness does when a run leaves the well-trodden path.

Every test here was written after reproducing the behaviour it describes, either on the
real 256^2 trajectory or through the real pipeline on synthetic frames. Each one asks the
same question the rest of the suite asks -- *does a wrong number look wrong?* -- but on
inputs the existing tests do not reach: a metric that is invariant to the operator the
D = 1 anchor is built from, a metric that improves as damage rises, an analysis grid that
the configured ladder does not fit on.

**Several of these are marked ``xfail(strict=True)``.** They describe defects that are
reproduced and written up in ``issues/``, not aspirations. Strict is deliberate: when
someone fixes the underlying problem the test starts passing, strict mode turns that into
a failure, and the fixer is forced to come here and remove the marker. Each marker names
the issue file carrying the measurement.

The tests themselves assert the *property*, never the current number, so they survive a
fix that changes magnitudes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from degradations import registry as deg_registry
from fmeval import analysis as an
from fmeval.data.base import GridSpec, Trajectory
from fmeval.ladder import Rung, apply_rung, build_ladder
from fmeval.pipeline import DatasetInfo, MapRequest, run
from metrics import registry as metric_registry
from tests.conftest import synthetic_field
from tests.test_analysis import make_frame

# --- scaffolding ---------------------------------------------------------------------

#: Deliberately non-square, and divisible by 2 twice, so a coarsening ladder can be run
#: against it without the shape itself being the reason something fails.
SHAPE: tuple[int, int] = (16, 8)


class SyntheticTrajectory(Trajectory):
    """A four-frame in-memory trajectory, so pipeline tests need no files and no CFS."""

    def __init__(self, shape: tuple[int, ...] = SHAPE, n_frames: int = 4) -> None:
        self._shape = shape
        self._n = n_frames
        self._grid = GridSpec(
            tuple(shape), (1.0,) * len(shape), (True,) * len(shape),
            ("x", "y", "z")[: len(shape)], (0.0,) * len(shape),
        )

    @property
    def fields(self) -> tuple[str, ...]:
        return ("density",)

    @property
    def times(self) -> np.ndarray:
        return np.arange(self._n, dtype=np.float64)

    @property
    def grid(self) -> GridSpec:
        return self._grid

    @property
    def meta(self) -> dict:
        return {"format": "synthetic"}

    def read_frame(self, t: int, fields):
        # Density-like: 1.0 with small fluctuations, matching the real data's scale, so
        # relative-severity operators behave as they do on the real thing.
        return {"density": 1.0 + 1e-3 * synthetic_field(self._shape, 1, seed=t)}


@pytest.fixture
def temporary_metric():
    """Register a metric for one test and remove it again.

    Metrics must not be registered at module import: ``test_metric_contract`` parametrizes
    its fixtures over the registry at collection time, so a probe metric left behind would
    be silently held to the whole metric contract and would change another file's test IDs.
    """
    added: list[str] = []

    def _register(**kwargs):
        def _decorate(fn):
            name = kwargs.get("name") or fn.__name__
            added.append(name)
            return metric_registry.metric(**kwargs)(fn)

        return _decorate

    yield _register
    for name in added:
        metric_registry.REGISTRY.pop(name, None)


@pytest.fixture
def temporary_degradation():
    """Register a degradation for one test and remove it again. See `temporary_metric`."""
    added: list[str] = []

    def _register(**kwargs):
        def _decorate(fn):
            added.append(kwargs.get("name") or fn.__name__)
            return deg_registry.degradation(**kwargs)(fn)

        return _decorate

    yield _register
    for name in added:
        deg_registry.REGISTRY.pop(name, None)


def _frame_with_anchor(anchor_values: list[float], **kwargs) -> pd.DataFrame:
    """A result frame whose ``uncorrelated`` anchor takes the given values."""
    axes = dict(kwargs.pop("axes", {}))
    axes["uncorrelated"] = anchor_values
    return make_frame(axes=axes, **kwargs)


# --- the D = 1 anchor ------------------------------------------------------------------
#
# The anchor is built by translating the reference (`random_large_translation`). That is
# exact and cheap for a pointwise metric, and it is *empty* for any metric invariant to
# translation -- which is most of the position-tolerant family this project exists to
# develop: spectra (BD-1), two-point correlations (BD-2), increment PDFs (OT-5, PS-4).


@pytest.mark.xfail(
    strict=True,
    reason="issues/032: the median-based scale collapses to round-off, so the guard "
           "does not fire; a max-based scale would",
)
def test_degeneracy_guard_fires_when_most_rungs_are_round_off():
    """A metric whose anchor is round-off must be reported as having no dynamic range.

    ``normalisation`` guards against a vanishing span with
    ``abs(span) < 1e-12 * median(|value|)``. The median is taken over *every* row of the
    group, so when most rungs are round-off the scale collapses to round-off too and the
    guard compares noise against noise. It is defeated in exactly the case it exists for.

    See issues/032-translation-invariant-anchor.md for the measurement on real data.
    """
    # One axis with genuine response (a blur, which a spectral metric does see) and three
    # axes at the float64 noise floor (translation, the impostor, and the anchor -- all of
    # which preserve the amplitude spectrum exactly).
    df = make_frame(
        n_frames=6,
        axes={
            "gaussian_blur": [1e-1, 3e-1],
            "translate_x": [1.1e-16, 1.3e-16, 0.9e-16],
            "gaussian_impostor": [1.8e-16],
            "uncorrelated": [1.5e-16, 1.5e-16, 1.5e-16],
        },
    )
    norm = an.normalisation(df)
    row = norm.iloc[0]

    assert bool(row["degenerate"]), (
        f"span={row['span']:.3e} against a genuine response of "
        f"{df['value'].max():.3e} was not marked degenerate; the damage column is a "
        "ratio of round-off and will be read as a measurement"
    )


@pytest.mark.xfail(
    strict=True,
    reason="issues/032: nothing checks that the anchor operator actually moves the "
           "metric, so `anchor_source` reads 'uncorrelated' as if it were measured",
)
def test_damage_is_not_reported_against_an_anchor_the_metric_cannot_see():
    """Damage must be withheld when the anchor is indistinguishable from clean.

    Measured on the real trajectory (t = 5000..6000, vorticity) with a radially averaged
    energy-spectrum metric of the BD-1 family:

        clean value             0.0
        uncorrelated anchor     1.5e-16      <- the whole D = 1 scale
        gaussian_impostor       1.8e-16      -> reported damage 1.17
        translate_x = 4         1.3e-16      -> reported damage 0.86

    The reported impostor damage of 1.17 says "worse than two unrelated fields". The truth
    is that the metric cannot separate any of them. Read by the rule AGENTS.md gives for
    the canary column, a colleague concludes the spectral metric passes IN-4 -- the exact
    inversion the canary exists to prevent.
    """
    df = make_frame(
        n_frames=6,
        axes={
            "gaussian_blur": [1e-1, 3e-1],
            "gaussian_impostor": [1.8e-16],
            "uncorrelated": [1.5e-16, 1.5e-16, 1.5e-16],
        },
    )
    norm = an.normalisation(df)
    probes = an.probe_summary(df, norm)
    damage = float(probes["gaussian_impostor_damage"].iloc[0])

    assert not np.isfinite(damage), (
        f"impostor damage reported as {damage:.3f} against an anchor of "
        f"{norm['value_uncorrelated'].iloc[0]:.3e}, which is round-off. A damage score "
        "computed from an anchor the metric cannot see must be NaN, not a number."
    )


# --- rank correlation ------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="issues/033: summarise_axes has no dynamic-range guard, so it reports a "
           "Spearman computed from float64 summation-order noise",
)
def test_rank_correlation_is_withheld_when_the_variation_is_round_off():
    """A rank correlation over values that differ only in the last ulp is not a signal.

    Reproduced end to end: ``evaluate.py metrics=[enstrophy]`` with a translation-only
    ladder on the dev trajectory. ``np.roll`` cannot change enstrophy, but it does change
    the pairwise-summation order inside ``np.mean``, so the five rungs differ by a relative
    1.6e-16. The run folder then reports ``rho_min = 0.707`` on ``worst_axis =
    translate_x`` -- a number that is entirely round-off, printed in the monotonicity
    heatmap next to genuine correlations and indistinguishable from them.

    The ``degenerate`` flag catches the *damage* column in that particular run, but not
    ``rho``, which is what the heatmap and the acceptance threshold both read.
    """
    rng = np.random.default_rng(0)
    rows = []
    for frame in range(8):
        base = 3.7
        for level in range(5):
            # Values identical to within float64 round-off, ordered arbitrarily.
            value = base * (1.0 + rng.standard_normal() * 2e-16)
            rows.append(
                {
                    "dataset": "d", "metric": "enstrophy", "field": "vorticity",
                    "degradation": "identity" if level == 0 else "translate_x",
                    "degradation_family": "identity" if level == 0 else "geometric",
                    "level": level, "severity": float(level), "frame_index": frame,
                    "value": base if level == 0 else value, "wall_time_s": 1e-4,
                }
            )
    df = pd.DataFrame(rows)
    axes = an.summarise_axes(df, n_bootstrap=0)
    rho = float(axes.loc[axes["degradation"] == "translate_x", "rho"].iloc[0])

    assert not np.isfinite(rho), (
        f"rho={rho:.3f} reported for an axis whose values span a relative 2e-16. A "
        "correlation over round-off must be NaN, or it will be read as a real response."
    )


@pytest.mark.xfail(
    strict=True,
    reason="issues/034: report_card calls groupby.idxmin() on rho without guarding the "
           "all-NA case",
)
def test_report_card_survives_an_all_nan_rank_correlation():
    """A metric constant on every ordinal axis must produce a card, not an exception.

    ``report_card`` takes ``ordinal.groupby(keys)['rho'].idxmin()``. When every ordinal
    axis has an undefined correlation -- which happens whenever a metric is exactly
    invariant to every operator in the ladder, e.g. a single-field invariant against a
    translation-only ladder -- pandas raises ``ValueError: Encountered all NA values``.

    The failure is fatal rather than cosmetic: ``build_context`` computes the card before
    any renderer runs, so it takes down the whole report rather than costing one figure,
    and it happens *after* the expensive evaluation has already been paid for.
    """
    rows = []
    for frame in range(6):
        for degradation, levels in (("identity", [0]), ("translate_x", [1, 2, 3]),
                                    ("uncorrelated", [1, 2])):
            for level in levels:
                rows.append(
                    {
                        "dataset": "d", "metric": "enstrophy", "field": "vorticity",
                        "degradation": degradation,
                        "degradation_family": (
                            "identity" if degradation == "identity" else "geometric"),
                        "level": level, "severity": float(level),
                        "frame_index": frame, "value": 1.0, "wall_time_s": 1e-4,
                    }
                )
    df = pd.DataFrame(rows)
    norm = an.normalisation(df)
    axes = an.summarise_axes(df, norm=norm, n_bootstrap=0)
    probes = an.probe_summary(df, norm)

    card = an.report_card(axes, probes, norm)   # must not raise
    assert len(card) == 1
    assert not np.isfinite(card["rho_min"].iloc[0])


# --- direction ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="issues/035: analysis.py never reads MetricSpec.higher_is_better, so every "
           "ordering statistic assumes the value rises with damage",
)
def test_a_similarity_metric_is_scored_in_its_own_direction():
    """A metric where *larger is better* must not be scored as non-monotone.

    ``higher_is_better`` is declared on every metric and consumed nowhere in
    ``fmeval/analysis.py``. Three statistics hardcode "damage makes the value rise":

    * ``_monotone_fraction`` requires ``diff(value) > 0``;
    * ``_min_adjacent_auc`` calls ``mannwhitneyu(..., alternative='greater')``;
    * ``_threshold_level`` takes the first level with ``median >= clean + f * span``.

    Measured on a synthetic axis that falls perfectly from 1.0 to 0.2 -- the shape of any
    correlation-, SSIM- or skill-score-style metric, and of PS-2/PS-3 when they arrive:

        rho                    -1.0   (perfectly ordered, reported as anti-correlated)
        monotone_fraction       0.0   (it is monotone on every frame)
        separability_auc_min    0.0   (adjacent rungs are perfectly separable)
        saturation_level        1.0   (fires at rung 1, meaninglessly)

    Every one of those then trips a configured threshold, so a correct metric arrives in
    the report card flagged on three criteria at once.
    """
    rows = []
    for frame in range(8):
        for level, value in enumerate([1.0, 0.8, 0.6, 0.4, 0.2]):
            rows.append(
                {
                    "dataset": "d", "metric": "similarity", "field": "v",
                    "degradation": "identity" if level == 0 else "gaussian_blur",
                    "degradation_family": (
                        "identity" if level == 0 else "smoothing"),
                    "level": level, "severity": float(level), "frame_index": frame,
                    # A small per-frame offset, so the ranks are well defined.
                    "value": value + 0.001 * frame, "wall_time_s": 1e-4,
                }
            )
        rows.append(
            {
                "dataset": "d", "metric": "similarity", "field": "v",
                "degradation": "uncorrelated", "degradation_family": "geometric",
                "level": 1, "severity": 0.0, "frame_index": frame,
                "value": 0.0, "wall_time_s": 1e-4,
            }
        )
    df = pd.DataFrame(rows)
    norm = an.normalisation(df)
    axes = an.summarise_axes(df, norm=norm, n_bootstrap=0)
    blur = axes[axes["degradation"] == "gaussian_blur"].iloc[0]

    assert blur["monotone_fraction"] == pytest.approx(1.0), (
        f"monotone_fraction={blur['monotone_fraction']} for an axis that is perfectly "
        "ordered on every frame, because the ordering test assumes the value rises"
    )
    assert blur["separability_auc_min"] >= 0.9, (
        f"separability_auc_min={blur['separability_auc_min']} for perfectly separated "
        "rungs, because the Mann-Whitney alternative is hardcoded to 'greater'"
    )


# --- the degradation contract ------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="issues/036: apply_rung never reads DegradationSpec.whole_frame",
)
def test_whole_frame_degradation_receives_the_field_dict(temporary_degradation):
    """``whole_frame=True`` is documented and does nothing.

    Both ``degradations/registry.py`` and AGENTS.md section 4 say an operator needing
    cross-field access declares ``whole_frame=True`` and then receives the whole
    ``dict[str, ndarray]``. ``fmeval/ladder.py::apply_rung`` does not mention
    ``whole_frame`` anywhere: it always calls ``spec.fn(source, severity, ...)`` with a
    single array.

    No shipped operator declares it, so nothing is broken today. It is a trap laid for the
    next contributor: the operators that most need it are the physically interesting ones
    -- a Leray projection (issue 024), a rotation that must rotate velocity components
    (issue 015), a density-weighted remap (issue 016) -- and each would receive an array
    where it expected a dict, with a message pointing at numpy rather than at the
    declaration that was ignored.
    """

    @temporary_degradation(name="_probe_whole_frame", family="pointwise",
                           whole_frame=True)
    def _probe_whole_frame(fields, severity, *, ctx):
        """Returns its input unchanged; fails loudly if it is not a mapping."""
        assert isinstance(fields, dict), (
            f"declared whole_frame=True but received {type(fields).__name__}"
        )
        return dict(fields)

    frame = SyntheticTrajectory().frame(1, ["density"])
    # Built through build_ladder rather than the Rung constructor, so this test keeps
    # testing whole_frame rather than turning into a signature check whenever a field is
    # added to Rung.
    rung = build_ladder(
        {"probe": {"op": "_probe_whole_frame", "severities": [1.0]}},
        include_reference=False,
    )[0]

    out = apply_rung(rung, frame, ["density"], seed=0)
    assert set(out) == {"density"}


# --- the analysis grid as a size knob ------------------------------------------------------
#
# `analysis_grid.resolution` is documented in CLAUDE.md and AGENTS.md as one of the two
# size knobs. Nothing checks the configured ladder against the grid it will run on.


@pytest.mark.parametrize(
    "resolution",
    [
        32,
        pytest.param(8, marks=pytest.mark.xfail(
            strict=True,
            reason="issues/037: the ladder is never validated against the analysis "
                   "grid, so coarsen severity 16 on an 8-cell grid aborts the run "
                   "mid-frame",
        )),
    ],
)
def test_the_default_ladder_runs_at_every_analysis_resolution(resolution):
    """Turning down the analysis grid must not abort the run.

    Reproduced with the real command:

        evaluate.py metrics=[mse] dataset=kinet_re5e4_dev analysis_grid.resolution=8

    which dies partway through the first frame with

        ValueError: factor 16 does not divide grid (8, 8)

    from ``coarsen`` at severity 16, since the default ladder coarsens by up to 16 and the
    analysis grid is 8 cells across. Two things make this worth fixing rather than
    documenting: the error names the operator but not the knob that caused it, and it is
    raised inside the frame loop, so the I/O for a long trajectory is paid before the run
    fails.

    The ladder is knowable before the first frame is read; a pre-flight check against the
    analysis grid would turn this into one message at startup.
    """
    ladder = build_ladder(
        {"coarsen": {"severities": [2, 4, 8, 16]},
         "gaussian_blur": {"severities": [1.0, 2.0]}}
    )
    metric_registry.discover()
    deg_registry.discover()

    # 32x16 native: every configured coarsening factor fits at the native resolution, so
    # the only thing under test is what the analysis grid does to the ladder.
    result = run(
        SyntheticTrajectory((32, 16)), [metric_registry.get("mse")], ladder,
        fields=["density"], dataset=DatasetInfo(name="synthetic"), seed=0,
        analysis_resolution=resolution,
    )
    assert len(result.rows) > 0


@pytest.mark.xfail(
    strict=True,
    reason="issues/037: a severity the analysis grid cannot express becomes an exact "
           "no-op rung and is still counted and correlated as a rung",
)
def test_a_rung_the_grid_cannot_express_is_not_counted_as_a_rung():
    """A severity that the analysis grid turns into the identity must not be a rung.

    ``translate_x`` runs to 16 cells in the shipped ladder, and ``analysis_grid.resolution``
    is a documented knob. On a periodic 16-cell axis ``np.roll(x, 16)`` is exactly ``x``,
    so that rung reproduces the reference bit for bit: MSE is 0.0 there, identical to level
    0, and the axis is reported with ``n_levels = 5`` while carrying four.

    The same class of failure was reproduced on the real data through the spectral axes
    before the issue-030 calibration work began:

        evaluate.py metrics=[mse] dataset=kinet_re5e4_dev analysis_grid.resolution=32 \\
            'degradation.skip=[coarsen]'

    gave MSE medians of 0.0, 0.0, 0.0, 3.2e-6 across low-pass cutoffs 64, 32, 16, 8 -- the
    largest |k| a 32-cell grid can represent is about 22.6, so three of the four rungs were
    the same experiment run three times. Calibrating spectral severities against the
    measured spectrum fixes that instance; it does not fix the general case, because
    ``translate``, ``coarsen`` and ``box_blur`` severities remain absolute cell counts by
    design and can still exceed what the analysis grid can express.

    The property asserted here is the general one: an ordinal axis must not contain a rung
    that is bit-for-bit identical to the reference.
    """
    metric_registry.discover()
    deg_registry.discover()
    ladder = build_ladder(
        {"translate_x": {"op": "translate", "severities": [1, 2, 4, 8, 16],
                         "options": {"axis": "x"}}}
    )
    result = run(
        SyntheticTrajectory((16, 8)), [metric_registry.get("mse")], ladder,
        fields=["density"], dataset=DatasetInfo(name="synthetic"), seed=0,
    )
    rows = result.rows[result.rows["degradation"] == "translate_x"]
    per_level = rows.groupby(["level", "severity"], observed=True)["value"].median()
    no_ops = per_level[per_level == 0.0]

    assert no_ops.empty, (
        f"rung(s) {list(no_ops.index)} of translate_x reproduce the reference exactly on "
        f"a 16-cell axis, yet the axis is reported with n_levels={len(per_level)} and its "
        "Spearman is computed over a ladder containing an exact tie with level 0"
    )


# --- the report request --------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="issues/038: MapRequest.frames is indexed without a bounds check",
)
def test_a_map_frame_position_outside_the_selection_is_reported_clearly():
    """An out-of-range error-map position must name the config key, not numpy's axis 0.

    ``report.error_map.frames`` holds positions *within the selected frames*, so what is
    valid depends on ``dataset.time.reduction`` and on the trajectory length. Raising
    ``dataset.time.reduction`` far enough shrinks the selection under a configured
    position, and ``pipeline.run`` then fails with

        IndexError: index 7 is out of bounds for axis 0 with size 4

    which names neither ``report.error_map.frames`` nor the reduction that shrank the
    selection. The check costs one line and the alternative costs a debugging session.
    """
    metric_registry.discover()
    deg_registry.discover()
    ladder = build_ladder({"gaussian_blur": {"severities": [1.0, 2.0]}})

    with pytest.raises(ValueError, match="error_map|frames"):
        run(
            SyntheticTrajectory(n_frames=4), [metric_registry.get("mse")], ladder,
            fields=["density"], dataset=DatasetInfo(name="synthetic"), seed=0,
            maps=MapRequest(enabled=True, frames=[0, 7]),
        )


# --- the report renderers ---------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="issues/039: displacement_response sets a log x-scale before checking that "
           "it has any finite data to draw",
)
def test_the_displacement_figure_declines_rather_than_crashes_without_damage():
    """A degenerate metric must skip the displacement figure, not error on it.

    AGENTS.md section 3 states that a single-field metric legitimately has no dynamic
    range and that ``rho = -1`` there "is correct, not a bug you should try to fix". The
    report does not honour its own rule: with the damage column all-NaN,
    ``displacement_response`` plots nothing, matplotlib finds no positive data for the log
    axis it has already set, and the renderer raises

        ValueError: Data cannot be log-scaled because all values are <= 0

    Reproduced with ``make_report.py`` on a real ``metrics=[enstrophy]`` run folder:
    ``error 1 · ok 7 · skipped 6``. The driver catches it, so the run survives -- but a
    documented-correct configuration produces an error in the manifest, and the renderer
    contract in AGENTS.md section 6 is explicit that unavailability is declared with
    ``ctx.require`` rather than raised.
    """
    from fmeval.io import RunFolder, write_config, write_results, write_run_meta
    from fmeval.report.driver import build_context, render

    import tempfile
    from pathlib import Path

    # A metric that cannot tell the anchor from clean: span = 0, so damage is all NaN.
    df = _frame_with_anchor(
        [1.0, 1.0, 1.0], metric="enstrophy", field="vorticity", n_frames=8,
        axes={"translate_x": [1.0, 1.0, 1.0, 1.0]},
    )
    with tempfile.TemporaryDirectory() as tmp:
        folder = RunFolder(Path(tmp) / "enstrophy_1").create()
        write_results(folder, df)
        digest = write_config(folder, {"metrics": ["enstrophy"], "seed": 1}, [])
        write_run_meta(folder, run_id=1, config_hash=digest, metric="enstrophy",
                       dataset="synthetic", n_frames=8, fields=["vorticity"],
                       analysis_grid=16, ladder_axes=["translate_x"], n_rungs=6, seed=1,
                       command="evaluate.py metrics=[enstrophy]")
        ctx = build_context(folder, thresholds={}, bootstrap=0)
        rendered = render(folder, ctx, formats=("png",))

    errored = [(r.name, r.reason) for r in rendered if r.status == "error"]
    assert not errored, (
        f"renderer(s) raised on a metric with no dynamic range: {errored}. "
        "AGENTS.md section 6 requires unavailability to be declared with ctx.require."
    )
