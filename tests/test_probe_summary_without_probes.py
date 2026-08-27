"""A run whose ladder contains no probe must not report a probe.

The trap tests -- the phase-scrambled impostor and the unrelated-field anchor -- are
ordinary ladder entries, and a custom ladder is free to omit them. The miscalibration
ladder does: an impostor built by scrambling the phases of one field says nothing about
whether an *ensemble* is honestly dispersed, so it is not on that axis.

When it is omitted, `probe_summary` used to return a bare row carrying the group keys and
no probe columns, and the card generator turned each such row into a
"trap test: fake prediction, right spectrum" line reading `damage —`. A reader has no way
to tell that from a trap test that ran and could not be scored, which is a different and
much more interesting claim. Absent must look absent.
"""

from __future__ import annotations

import pandas as pd

from fmeval.analysis import normalisation, probe_summary
from fmeval.pipeline import RESULT_DTYPES


def _rows(degradations: dict[str, list[float]], *, metric: str = "m") -> pd.DataFrame:
    """A minimal tidy frame over the real schema, one value per level per frame."""
    defaults: dict[str, object] = {
        "dataset": "d", "dataset_family": "", "complexity_rank": 0,
        "param_reynolds": float("nan"), "param_mach": float("nan"),
        "param_resolution": 64, "trajectory": "t", "time": 0.0, "field": "density",
        "analysis_grid": 64, "remap_op": "block_mean", "metric": metric,
        "arity": "pairwise", "higher_is_better": False, "degradation_op": "op",
        "degradation_family": "smoothing", "severity": 0.0, "severity_nominal": 0.0,
        "calibration": "", "severity_degenerate": False, "energy_removed": 0.0,
        "energy_changed": 0.0, "severity_name": "s", "variant_label": "v",
        "component": "", "seed": 0, "wall_time_s": 0.0, "n_members": None,
        "target_value": float("nan"),
    }
    out = []
    for label, values in degradations.items():
        for level, value in enumerate(values):
            for frame_index in range(3):
                row = dict(defaults)
                row.update(degradation=label, level=level, frame_index=frame_index,
                           value=value, degradation_op=label)
                out.append({k: row[k] for k in RESULT_DTYPES})
    return pd.DataFrame(out)


def test_no_probe_row_when_the_ladder_has_no_probe():
    df = _rows({"identity": [0.0], "gaussian_blur": [0.0, 0.1, 0.2]})
    summary = probe_summary(df, normalisation(df))
    assert summary.empty, (
        "a ladder with no probe produced a probe row; the card generator renders one "
        f"trap-test line per row here. Got:\n{summary}"
    )


def test_the_empty_result_still_carries_the_key_columns():
    """Empty must still be filterable.

    Every consumer selects on metric or field before reading this frame. A frame with no
    rows *and* no columns raises a KeyError on that filter, which is how the first attempt
    at the fix above turned a cosmetic defect into a crash in `cards evidence`.
    """
    df = _rows({"identity": [0.0], "gaussian_blur": [0.0, 0.1, 0.2]})
    summary = probe_summary(df, normalisation(df))
    assert {"dataset", "metric", "field"} <= set(summary.columns)
    assert summary[summary["metric"] == "m"].empty  # the filter itself must not raise


def test_a_probe_row_still_appears_when_the_probe_ran():
    df = _rows({
        "identity": [0.0],
        "gaussian_blur": [0.0, 0.1, 0.2],
        "gaussian_impostor": [0.5],
        "uncorrelated": [1.0],
    })
    summary = probe_summary(df, normalisation(df))
    assert len(summary) == 1
    assert "gaussian_impostor_damage" in summary.columns
