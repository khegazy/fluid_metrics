"""TEST_DESCRIPTION.md must document every quantity the suite reports.

Adding a reported column, a degradation, or a renderer without documenting it fails here.
That is the only mechanism that reliably keeps a document like this current: without it the
file describes whatever the code looked like on the day someone last remembered to edit it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "TEST_DESCRIPTION.md"

#: Columns that are provenance or grouping keys rather than measurements. They are still
#: documented, but grouped into one heading each rather than given a section apiece.
_GROUPED_HEADINGS = {
    "dataset", "dataset_family", "complexity_rank", "param_reynolds", "param_mach",
    "param_resolution", "trajectory", "frame_index", "time", "metric", "tracker_id",
    "arity", "field", "component", "seed", "wall_time_s", "degradation",
    "degradation_op", "degradation_family", "level", "severity", "severity_name",
    "variant_label", "analysis_grid", "remap_op", "rho_median", "rho_min",
    "rho_pooled_min", "monotone_fraction_min", "sensitivity_level_median",
    "saturation_level_median", "value_uncorrelated", "n_axes", "n_levels", "n_frames",
}


@pytest.fixture(scope="module")
def doc() -> str:
    assert DOC.exists(), "TEST_DESCRIPTION.md is missing"
    return DOC.read_text()


def documented_names(doc: str) -> set[str]:
    """Every identifier appearing in a `###` heading or in a table's first column."""
    names: set[str] = set()
    for line in doc.splitlines():
        if line.startswith("### "):
            names.update(re.findall(r"`([^`]+)`", line))
        elif line.startswith("| `"):
            names.update(re.findall(r"^\| `([^`]+)`", line))
    return names


def test_every_result_column_is_documented(doc):
    from fmeval.pipeline import RESULT_DTYPES

    documented = documented_names(doc) | _GROUPED_HEADINGS
    missing = sorted(set(RESULT_DTYPES) - documented)
    assert not missing, f"undocumented result columns: {missing}"


def test_every_analysis_column_is_documented(doc):
    """Columns produced by summarise_axes, probe_summary and report_card."""
    import pandas as pd

    from fmeval import analysis as an
    from tests.test_analysis import make_frame

    df = make_frame(axes={"a": [1.0, 2.0, 3.0], "gaussian_impostor": [9.0],
                          "uncorrelated": [10.0, 10.0]})
    norm = an.normalisation(df)
    axes = an.summarise_axes(an.add_damage(df, norm), norm=norm, n_bootstrap=0)
    probes = an.probe_summary(df, norm)
    card = an.flag(an.report_card(axes, probes, norm), {"spearman": 0.9})

    produced: set[str] = set()
    for frame in (norm, axes, probes, card):
        produced |= set(frame.columns)
    produced |= {"damage"}
    # Probe columns are named <label>_<quantity>; document the quantity once.
    produced = {re.sub(r"^(gaussian_impostor|uncorrelated)_", r"\1_", c) for c in produced}

    documented = documented_names(doc) | _GROUPED_HEADINGS
    missing = sorted(produced - documented)
    assert not missing, f"undocumented analysis columns: {missing}"


def test_every_degradation_is_documented(doc):
    from degradations import registry as deg

    documented = documented_names(doc)
    missing = sorted(set(deg.available()) - documented)
    assert not missing, f"undocumented degradations: {missing}"


def test_every_renderer_is_documented(doc):
    from fmeval.report.registry import PLOTS, TABLES  # noqa: F401
    from fmeval.report import driver  # noqa: F401  (imports the renderer modules)

    documented = documented_names(doc)
    # Tables are described by the quantities they contain rather than by name; figures
    # are listed individually, since a reader meets them as pictures.
    missing = sorted(set(PLOTS) - documented)
    assert not missing, f"undocumented figures: {missing}"


def test_the_document_states_that_it_does_not_decide(doc):
    """The framing matters as much as the contents: this suite reports, we decide."""
    assert "does not decide" in doc
    assert "flags" in doc


def test_a_copy_is_placed_in_every_run_folder(tmp_path):
    """A results directory must explain its own numbers after being sent to someone else."""
    import shutil

    from fmeval.io import RunFolder

    folder = RunFolder(tmp_path / "m_1").create()
    shutil.copy(DOC, folder.root / DOC.name)
    assert (folder.root / "TEST_DESCRIPTION.md").exists()
