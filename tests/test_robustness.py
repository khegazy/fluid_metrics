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
from fmeval.ladder import SeverityLevel, apply_severity_level, build_ladder
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


def test_degeneracy_guard_fires_when_most_levels_are_round_off():
    """A metric whose anchor is round-off must be reported as having no dynamic range.

    ``normalisation`` guards against a vanishing span with
    ``abs(span) < 1e-12 * median(|value|)``. The median is taken over *every* row of the
    group, so when most severity levels are round-off the scale collapses to round-off too and the
    guard compares noise against noise. It is defeated in exactly the case it exists for.

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


def test_rank_correlation_is_withheld_when_the_variation_is_round_off():
    """A rank correlation over values that differ only in the last ulp is not a signal.

    Reproduced end to end: ``evaluate.py metrics=[enstrophy]`` with a translation-only
    ladder on the dev trajectory. ``np.roll`` cannot change enstrophy, but it does change
    the pairwise-summation order inside ``np.mean``, so the five severity levels differ by a relative
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
        separability_auc_min    0.0   (adjacent severity levels are perfectly separable)
        saturation_level        1.0   (fires at severity level 1, meaninglessly)

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
        "severity levels, because the Mann-Whitney alternative is hardcoded to 'greater'"
    )


# --- the degradation contract ------------------------------------------------------------


def test_whole_frame_degradation_receives_the_field_dict(temporary_degradation):
    """``whole_frame=True`` is documented and does nothing.

    Both ``degradations/registry.py`` and AGENTS.md section 4 say an operator needing
    cross-field access declares ``whole_frame=True`` and then receives the whole
    ``dict[str, ndarray]``. ``fmeval/ladder.py::apply_severity_level`` does not mention
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
    # Built through build_ladder rather than the SeverityLevel constructor, so this test keeps
    # testing whole_frame rather than turning into a signature check whenever a field is
    # added to SeverityLevel.
    severity_level = build_ladder(
        {"probe": {"op": "_probe_whole_frame", "severities": [1.0]}},
        include_reference=False,
    )[0]

    applied = apply_severity_level(severity_level, frame, ["density"], seed=0)
    assert set(applied.fields) == {"density"}
    # The operator returned its input unchanged, so the harness must see that and say so
    # rather than counting the severity level as an experiment.
    assert "density" in applied.unchanged


# --- the analysis grid as a size knob ------------------------------------------------------
#
# `analysis_grid.resolution` is documented in CLAUDE.md and AGENTS.md as one of the two
# size knobs. Nothing checks the configured ladder against the grid it will run on.


@pytest.mark.parametrize(
    "resolution",
    [
        32,
        8,
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


def test_a_no_op_level_is_flagged_and_excluded_on_an_absolute_severity_axis():
    """The degenerate-severity level detector must cover uncalibrated operators too.

    Issue 030's calibration work added ``severity_degenerate``: a severity level that resolves to a
    severity at which the operator does nothing, or that repeats a milder severity level's
    experiment, is flagged in the result frame and dropped by ``summarise_axes`` before any
    acceptance statistic is computed. Scoring such a severity level would read as agreement in the
    rank correlation and would compare a distribution against itself in the separability.

    That work was driven by the *calibrated* spectral and smoothing axes. This checks the
    same guarantee on an axis whose severities stay absolute cell counts by design, where
    the no-op arises from the analysis grid rather than from the field's spectrum:
    ``translate_x`` runs to 16 cells in the shipped ladder, and on a periodic 16-cell axis
    ``np.roll(x, 16)`` is exactly ``x``. ``analysis_grid.resolution`` is a documented knob,
    so this configuration is reachable without editing the ladder at all.

    Measured here: level 5 records ``value = 0.0`` and ``energy_changed = 0.0``, is flagged,
    and is logged as "resolve[d] to a severity at which the operator leaves the field
    unchanged". Levels 1-4 are untouched. The detector is measurement-based rather than
    operator-declared, which is why it generalises to an operator that knows nothing about
    calibration -- and that generality is the thing worth pinning.
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
    by_level = rows.groupby(["level"], observed=True).agg(
        value=("value", "median"), flagged=("severity_degenerate", "max")
    )

    no_ops = by_level.index[by_level["value"] == 0.0].tolist()
    assert no_ops == [5], (
        f"expected only the 16-cell severity_level to be a no-op on a 16-cell axis, got {no_ops}"
    )
    assert bool(by_level.loc[5, "flagged"]), (
        "the 16-cell severity level reproduces the reference bit for bit but was not flagged "
        "severity_degenerate, so its exact tie with level 0 would be scored as agreement"
    )
    assert not by_level.loc[[1, 2, 3, 4], "flagged"].any(), (
        "a severity level that does real damage was flagged degenerate"
    )

    # And the exclusion actually reaches the acceptance statistics.
    axes = an.summarise_axes(result.rows, n_bootstrap=0)
    measured = int(axes.loc[axes["degradation"] == "translate_x", "n_levels"].iloc[0])
    assert measured == 4, (
        f"summarise_axes reports n_levels={measured}; the flagged severity_level was not dropped"
    )


# --- the report request --------------------------------------------------------------------


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
                       analysis_grid=16, ladder_axes=["translate_x"], n_severity_levels=6, seed=1,
                       command="evaluate.py metrics=[enstrophy]")
        ctx = build_context(folder, thresholds={}, bootstrap=0)
        rendered = render(folder, ctx, formats=("png",))

    errored = [(r.name, r.reason) for r in rendered if r.status == "error"]
    assert not errored, (
        f"renderer(s) raised on a metric with no dynamic range: {errored}. "
        "AGENTS.md section 6 requires unavailability to be declared with ctx.require."
    )
