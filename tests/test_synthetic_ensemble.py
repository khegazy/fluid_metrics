"""The synthetic ensemble reader.

This dataset exists so probabilistic metrics have a case whose right answer is known in
closed form. That rests entirely on one property -- **exchangeability**: the reference is
drawn from the same process as every member, with the same dispersion, independently. It
is then statistically just one more member, so a calibrated ensemble is the null
hypothesis by construction: rank histograms are uniform, the spread-to-skill ratio is 1,
and CRPS matches the Gaussian closed form.

The tests below check that property directly, at the reader level, without involving any
metric. When a probabilistic metric later disagrees with its analytic target, this file is
what says whether the generator or the metric is at fault.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from fmeval.data.base import READERS
from fmeval.data.synthetic_ensemble import SyntheticEnsembleTrajectory

GRID = (16, 8)
N_MEMBERS = 12


@pytest.fixture
def traj() -> SyntheticEnsembleTrajectory:
    return SyntheticEnsembleTrajectory(
        grid=GRID, n_members=N_MEMBERS, n_frames=6, fields=("density",), sigma=0.2, seed=0
    )


# --- registration and the reader contract -------------------------------------------


def test_is_registered():
    assert READERS["synthetic_ensemble"] is SyntheticEnsembleTrajectory


def test_declares_itself_an_ensemble(traj):
    assert traj.is_ensemble is True


def test_frame_shapes(traj):
    frame = traj.frame(2, ["density"])
    assert frame.fields["density"].shape == (1, *GRID)
    assert frame.members["density"].shape == (N_MEMBERS, 1, *GRID)
    assert frame.members["density"].dtype == np.float64


def test_length_and_times(traj):
    assert len(traj) == 6
    assert traj.times.shape == (6,)


def test_grid_is_periodic_and_non_square(traj):
    assert traj.grid.shape == GRID
    assert traj.grid.periodic == (True, True)


def test_meta_records_ensemble_size(traj):
    assert traj.meta["n_members"] == N_MEMBERS
    assert traj.meta["format"] == "synthetic_ensemble"


def test_supports_multi_channel_fields():
    traj = SyntheticEnsembleTrajectory(
        grid=GRID, n_members=4, n_frames=2, fields=("density", "velocity"), seed=0
    )
    frame = traj.frame(0, ["density", "velocity"])
    assert frame.fields["velocity"].shape == (2, *GRID)
    assert frame.members["velocity"].shape == (4, 2, *GRID)


# --- reproducibility -----------------------------------------------------------------


def test_is_reproducible_from_the_seed(traj):
    other = SyntheticEnsembleTrajectory(
        grid=GRID, n_members=N_MEMBERS, n_frames=6, fields=("density",), sigma=0.2, seed=0
    )
    a, b = traj.frame(3, ["density"]), other.frame(3, ["density"])
    assert np.array_equal(a.fields["density"], b.fields["density"])
    assert np.array_equal(a.members["density"], b.members["density"])


def test_a_different_seed_gives_different_draws(traj):
    other = SyntheticEnsembleTrajectory(
        grid=GRID, n_members=N_MEMBERS, n_frames=6, fields=("density",), sigma=0.2, seed=1
    )
    a, b = traj.frame(3, ["density"]), other.frame(3, ["density"])
    assert not np.allclose(a.members["density"], b.members["density"])


def test_frames_are_independent_draws(traj):
    """Per-frame Spearman needs frames that genuinely differ, not a repeated field."""
    a = traj.frame(1, ["density"])["density"]
    b = traj.frame(2, ["density"])["density"]
    assert not np.allclose(a, b)


def test_members_within_a_frame_are_distinct(traj):
    members = traj.frame(1, ["density"]).members["density"]
    assert not np.allclose(members[0], members[1])


# --- the exchangeability property the analytic targets rest on -----------------------


def test_reference_is_not_the_member_mean(traj):
    """The truth is an independent draw, not the ensemble mean. Documented, and true."""
    frame = traj.frame(1, ["density"])
    assert not np.allclose(
        frame.fields["density"], frame.members["density"].mean(axis=0), atol=1e-8
    )


def test_rank_of_the_reference_is_uniform(traj):
    """Exchangeability, tested where it bites: the rank histogram must be flat.

    Pools every cell of every frame. Under exchangeability the reference is equally
    likely to fall in any of the N+1 gaps between sorted members, so a chi-square
    goodness-of-fit against the uniform must not reject. A generator that drew the
    reference with a different sigma -- the easiest mistake to make here -- produces a
    U-shaped or dome-shaped histogram and fails loudly.
    """
    counts = np.zeros(N_MEMBERS + 1, dtype=int)
    for t in range(len(traj)):
        frame = traj.frame(t, ["density"])
        ref = frame.fields["density"]
        members = frame.members["density"]
        ranks = (members < ref[None]).sum(axis=0)
        counts += np.bincount(ranks.ravel(), minlength=N_MEMBERS + 1)

    expected = counts.sum() / (N_MEMBERS + 1)
    _, p = stats.chisquare(counts, f_exp=np.full(N_MEMBERS + 1, expected))
    assert p > 0.01, f"rank histogram is not uniform (p={p:.4g}); counts={counts}"


def test_spread_matches_skill(traj):
    """The other face of exchangeability: RMS spread equals ensemble-mean RMSE.

    Computed here with the Fortin et al. (2014) estimator and the finite-ensemble
    factor sqrt((N+1)/N) that relates the two under exchangeability, so this is a check
    on the generator, not on any metric implementation.
    """
    variances, sq_errors = [], []
    for t in range(len(traj)):
        frame = traj.frame(t, ["density"])
        members = frame.members["density"]
        variances.append(members.var(axis=0, ddof=1))
        sq_errors.append((members.mean(axis=0) - frame.fields["density"]) ** 2)

    spread = np.sqrt(np.mean(variances))
    skill = np.sqrt(np.mean(sq_errors))
    ratio = spread / skill * np.sqrt((N_MEMBERS + 1) / N_MEMBERS)
    assert ratio == pytest.approx(1.0, abs=0.05), f"spread/skill is {ratio:.4g}, not ~1"


def test_sigma_controls_the_dispersion():
    """A larger sigma must widen the ensemble, so the knob is real and monotone."""
    spreads = []
    for sigma in (0.1, 0.4):
        traj = SyntheticEnsembleTrajectory(
            grid=GRID, n_members=8, n_frames=3, fields=("density",), sigma=sigma, seed=0
        )
        members = traj.frame(1, ["density"]).members["density"]
        spreads.append(np.sqrt(members.var(axis=0, ddof=1).mean()))
    assert spreads[1] > 2 * spreads[0]
