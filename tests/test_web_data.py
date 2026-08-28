"""Evaluating a metric against the copy of the data published on the web.

Marked `web`, so `pytest` skips it: it reaches portal.nersc.gov. The offline half of the
same machinery -- ranges, retries, the refusal to drain a 200 -- is covered by
tests/test_remote_data.py against a local server and runs on every push.

Both kinet trajectories are published (the Well-format copy is not; see issues/034). The
end-to-end evaluation reads a handful of frames from the middle of the production run;
`kinet_re5e4_dev` is checked separately, because it is the dataset the documentation tells a
newcomer to start with and the one they cannot open at all without this fallback.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from omegaconf import OmegaConf

from evaluate import dataset_info, open_trajectory, select_fields
from fmeval.data.base import TimeSelection
from fmeval.data.kinet_raw import KinetRawTrajectory
from fmeval.data.locate import default_data_url, resolve_dataset_path
from fmeval.ladder import build_ladder
from fmeval.pipeline import run
from metrics import registry as metric_registry
from tests.test_configs import build

pytestmark = pytest.mark.web

DATASET = "kinet_re5e4"
FRAMES = (1, 5000, 10000)

#: Two 256^2 frames cost ~2.5-3.2 MiB each. The budget is loose enough not to be brittle
#: and tight enough that reinstating the full `time[:]` read -- 2.5 GiB -- blows past it.
BYTE_BUDGET = 64 * 1024 * 1024


@pytest.fixture
def web_cfg(tmp_path):
    """The published copy, with the local one deliberately out of reach.

    `paths.data` pointing at an empty directory *is* the test. On NERSC the CFS copy is
    mounted, so without this the run reads it, passes, and proves nothing about the
    feature under test.
    """
    return build(
        f"dataset={DATASET}",
        "metrics=[mse]",
        "degradation=quick",
        f"paths.data={tmp_path}",
        "dataset.time.start=5000",
        "dataset.time.reduction=1",
        "dataset.time.max_frames=2",
    )


def test_the_fallback_fires_when_there_is_no_local_copy(web_cfg):
    location = resolve_dataset_path(
        web_cfg.dataset.path, web_cfg.paths.data, data_url=web_cfg.paths.data_url
    )
    assert location.source == "url"
    assert location.url.startswith("https://portal.nersc.gov/")
    assert location.url.endswith("D2Q9_shape-256-256_T-10000_H-dc804f.h5")


def test_mse_evaluates_against_the_published_trajectory(web_cfg):
    """The end-to-end claim: a metric runs on a machine with no CFS mount."""
    specs = [metric_registry.get("mse")]
    trajectory = open_trajectory(web_cfg)
    try:
        assert trajectory.is_remote, "read the local copy; the fallback did not fire"

        fields = select_fields(web_cfg, trajectory, specs)
        selection = TimeSelection(**dict(web_cfg.dataset.time))
        severity_levels = build_ladder(
            OmegaConf.to_container(web_cfg.degradation.ladder, resolve=True),
            include_reference=True,
        )
        result = run(
            trajectory,
            specs,
            severity_levels,
            fields=fields,
            selection=selection,
            dataset=dataset_info(web_cfg),
            seed=int(web_cfg.seed),
        )
        stats = trajectory._remote.stats
    finally:
        trajectory.close()

    assert not result.rows.empty
    values = result.rows["value"].to_numpy()
    assert np.isfinite(values).all(), "a non-finite mse came back from the remote read"

    # d(x, x) == 0. The reference level applies `identity`, comparing the field with
    # itself, so anything else means two reads of the same frame returned different bytes.
    reference = result.rows[result.rows["level"] == 0]["value"].to_numpy()
    assert reference.size, "the ladder produced no reference level"
    assert np.all(reference == 0.0), f"mse against an undegraded field was {reference}"

    assert stats.bytes_fetched < BYTE_BUDGET, (
        f"fetched {stats.bytes_fetched / 2**20:.1f} MiB for {result.n_frames} frames. "
        "A 256^2 frame costs 2.5-3.2 MiB; a full read of the chunked `time` dataset "
        "costs 2.5 GiB, which is the regression this budget exists to catch."
    )


def test_the_dev_trajectory_is_published_too(tmp_path):
    """The documented inner loop must work on a machine with no CFS mount.

    `README.md`, `AGENTS.md` section 2, `evaluate.py`'s docstring and a pinned phrase in
    docs/recipes/verify-a-refactor.md all start a newcomer on `kinet_re5e4_dev`. Until it
    was published that command failed for anyone without CFS, which is the whole audience
    this fallback exists for.
    """
    cfg = build("dataset=kinet_re5e4_dev", f"paths.data={tmp_path}")
    trajectory = open_trajectory(cfg)
    try:
        assert trajectory.is_remote
        assert trajectory.source.endswith("D2Q9_shape-256-256_T-100_H-04a8a1.h5")
        assert len(trajectory) == 101
        frame = trajectory.frame(1, ["density", "velocity", "vorticity"])
        assert np.isfinite(frame["density"]).all()
        assert frame.grid.shape == (256, 256)
    finally:
        trajectory.close()


def test_opening_the_published_trajectory_is_cheap(web_cfg):
    """Measured 2026-08-27: 3 requests and 0.05 s, including the clock.

    The clock is the part that can silently regress: `time` is chunked one element per
    chunk, so reading it whole is 9938 requests and 297 s.
    """
    trajectory = open_trajectory(web_cfg)
    try:
        stats = trajectory._remote.stats
        assert len(trajectory) == 10001
        assert stats.requests < 50, f"opening took {stats.requests} requests"
    finally:
        trajectory.close()


def test_the_remote_and_local_copies_are_the_same_bytes():
    """The ground-truth check AGENTS.md asks for: validate against reality, not a fixture.

    `assert_array_equal`, not `assert_allclose`: this is the same file decoded by the same
    reader, so anything short of bitwise equality is a transport bug. (Contrast
    `test_raw_and_well_readers_agree_on_the_same_simulation`, which legitimately allows a
    tolerance because the Well copy is float32.)
    """
    cfg = build(f"dataset={DATASET}")
    local = resolve_dataset_path(
        cfg.dataset.path, cfg.paths.data, data_url=None, allow_url=False
    ).local
    if not local.exists():
        pytest.skip(f"the local copy is not mounted here: {local}")

    url = f"{default_data_url()}/{local.relative_to(cfg.paths.data)}"
    reader_kwargs = {"periodic": [True, True]}

    with KinetRawTrajectory(local, **reader_kwargs) as here, \
            KinetRawTrajectory(url, **reader_kwargs) as there:
        assert there.is_remote and not here.is_remote
        assert there._remote.size == os.path.getsize(local), (
            "the published file is a different size from the local one"
        )
        assert there.grid == here.grid
        assert there.fields == here.fields
        assert len(there) == len(here)

        # All 10001 entries, which also checks the affine reconstruction of the clock
        # against every stored value rather than the ten the reader sampled.
        np.testing.assert_array_equal(there.times, here.times)

        for t in FRAMES:
            expected = here.frame(t, here.fields)
            got = there.frame(t, there.fields)
            assert got.time == expected.time
            for name, array in expected.fields.items():
                np.testing.assert_array_equal(got.fields[name], array, err_msg=f"{name} at t={t}")
