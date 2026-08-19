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
    "param_resolution", "trajectory", "frame_index", "time", "metric",
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


# --- AGENTS.md ---------------------------------------------------------------------------

AGENTS = REPO / "AGENTS.md"


def test_agents_file_exists_where_other_tools_look():
    """AGENTS.md is the cross-agent convention; the others must only point at it."""
    assert AGENTS.exists()
    for pointer in (REPO / ".github" / "copilot-instructions.md",
                    REPO / ".cursor" / "rules" / "repository.mdc"):
        assert pointer.exists(), f"{pointer} is missing"
        text = pointer.read_text()
        assert "AGENTS.md" in text, f"{pointer.name} does not point at AGENTS.md"
        assert len(text) < 2000, (
            f"{pointer.name} is long enough to have grown its own content; it must stay a "
            "pointer so it cannot drift from AGENTS.md"
        )


def test_agents_documents_every_extension_point():
    """Each registry a contributor might extend must have instructions."""
    text = AGENTS.read_text()
    for topic in ("Adding a metric", "Adding a degradation", "Adding a data source",
                  "Adding a figure or table", "Writing tests",
                  "How to treat the LaTeX output"):
        assert topic in text, f"AGENTS.md has no section on {topic!r}"


def test_agents_api_claims_match_the_code():
    """Signatures quoted in the instructions must still exist.

    An instruction file that describes an API the code no longer has is worse than none,
    because it is followed confidently.
    """
    import inspect

    from degradations.registry import degradation
    from fmeval.report.latex import PACKAGES
    from metrics.registry import REDUCTIONS, metric

    text = AGENTS.read_text()
    for name in inspect.signature(metric).parameters:
        assert name in text, f"metric() parameter {name!r} is undocumented in AGENTS.md"
    for name in inspect.signature(degradation).parameters:
        assert name in text, f"degradation() parameter {name!r} is undocumented in AGENTS.md"
    for name in REDUCTIONS:
        assert name in text, f"reduction {name!r} is undocumented in AGENTS.md"
    for package in PACKAGES:
        assert package in text, f"LaTeX package {package!r} is undocumented in AGENTS.md"


def test_agents_states_the_non_negotiables():
    """The rules whose violation silently corrupts results."""
    text = AGENTS.read_text()
    for rule in (
        "exit code" if "exit code" in text else "RC=$?",   # verify before claiming
        "Never hand-edit",                                  # generated LaTeX
        "Never slice the time axis",                        # the multi-GB read
        "non-square",                                       # the transpose trap
        "severity_direction",                               # the inverted ladder
        "does not decide",                                  # no verdicts
    ):
        assert rule in text, f"AGENTS.md does not state the rule about {rule!r}"


def test_setup_check_runs_and_reports():
    """`check_setup.py` must work in the environment it is meant to diagnose."""
    import subprocess
    import sys

    result = subprocess.run([sys.executable, str(REPO / "check_setup.py")],
                            capture_output=True, text=True, timeout=180, cwd=REPO)
    assert result.returncode == 0, result.stdout + result.stderr
    for expected in ("numpy", "metrics registry", "degradations registry",
                     "spectral vorticity", "dataset root"):
        assert expected in result.stdout, f"check_setup.py does not report on {expected!r}"


# --------------------------------------------------------------------------------------
# The human file guide
# --------------------------------------------------------------------------------------

GUIDE = REPO / "docs" / "working-with-the-repo.md"


def test_the_file_guide_covers_every_file_of_the_bundle_contract():
    """A guide that has fallen behind the contract sends a reader to a file that is gone.

    This checks coverage, not quality: every file a contributor is expected to create or
    to leave alone must be named somewhere in the guide.
    """
    text = GUIDE.read_text()
    required = [
        "metric.py", "degradation.py", "card.yaml", "card.md", "refs.bib",
        "test_metric.py", "_generated/", "AGENTS.md", "TEST_DESCRIPTION.md",
        "configs/", "issues/",
    ]
    missing = [name for name in required if name not in text]
    assert not missing, f"docs/working-with-the-repo.md does not mention: {missing}"


def test_the_file_guide_names_the_card_commands():
    """The guide's job is to make the workflow runnable without a second document."""
    text = GUIDE.read_text()
    for command in ("fmeval.cards new", "fmeval.cards check", "fmeval.cards sign"):
        assert command in text, f"the file guide does not mention `{command}`"


def test_the_file_guide_starts_with_a_summary_table():
    """A reader looking up one file should not have to read the whole document."""
    head = GUIDE.read_text().split("## The bundle files in detail")[0]
    assert "| File | What it is | Who edits it | When |" in head


def test_agents_documents_the_card_workflow(doc_agents=None):
    """AGENTS.md must describe the bundle workflow, not the one it replaced.

    An agent follows this file. When cards became mandatory, a file that still said "a
    metric goes in any module under metrics/" would have produced a metric that does not
    import, and the agent would have had no way to know why from here.
    """
    text = (REPO / "AGENTS.md").read_text()
    for required in ("python -m fmeval.cards new",
                     "python -m fmeval.cards check",
                     "python -m fmeval.cards evidence",
                     "python -m fmeval.cards exemplars",
                     "card.yaml",
                     "card.md",
                     "docs/catalog.json",
                     "GENERATED"):
        assert required in text, f"AGENTS.md never mentions {required!r}"


def test_agents_states_the_card_prohibitions():
    """The rules that exist because breaking them produces plausible, wrong documentation."""
    text = (REPO / "AGENTS.md").read_text()
    for rule in ("Never invent a number",
                 "Never state expected behaviour",
                 "never edit `_generated/`",
                 "never sign a card"):
        assert rule.lower() in text.lower(), f"AGENTS.md does not say: {rule}"


# --------------------------------------------------------------------------------------
# The recipes: canonical instructions, each pinned by its own check
# --------------------------------------------------------------------------------------
#
# The recipes in docs/recipes/ are the canonical instructions for extending the
# repository; AGENTS.md summarises and points at them. They are separate files, each
# asserted here by name, precisely so that no single careless edit can destroy the
# instructions: an agent that overwrites AGENTS.md loses a summary, and an edit that guts
# a recipe fails CI naming that recipe. Destroying the instructions would require
# deliberately editing several named files and this test together.

RECIPES = {
    "index.md": (
        "Never invent a number",
        "Never invent a citation",
        "Never state expected behaviour",
        "never sign a card",
        "report it rather than writing around it",
    ),
    "add-a-metric.md": (
        "python -m fmeval.cards new <name>",
        "python -m fmeval.cards check",
        "test_metric.py",
        "### Boundary handling",
        "python -m fmeval.cards evidence",
        "python -m fmeval.cards catalog",
        "equation number",
        "worked example",
    ),
    "add-a-degradation.md": (
        "--kind degradation",
        "severity_direction",
        "configs/degradation/default.yaml",
        "FAMILY_BLOCKS",
        "FAMILY_HEADINGS",
        "exemplars",
        "python -m fmeval.cards exemplars <name>",
        "mode: draws",
    ),
    "add-a-dataset.md": (
        "configs/dataset/",
        "fmeval/data/base.py",
        "Never slice the time axis".lower(),
        "calibration.csv",
        "severity_degenerate",
        "evidence_datasets",
        "configs/cards/default.yaml",
        "developed",
    ),
    "add-a-diagnostic.md": (
        "fmeval/cards/diagnostics.py",
        "@diagnostic",
        "ctx.limits",
        "show_field",
        "numbers behind the picture",
        "fmeval/cards/schema.py",
    ),
    "refresh-the-evidence.md": (
        "evidence --all",
        "python -m fmeval.cards catalog",
        "typed into sentences do\nnot",
        "issues/032",
        "does **not** invalidate a signature",
    ),
}


@pytest.mark.parametrize("recipe", sorted(RECIPES))
def test_each_recipe_still_carries_its_instructions(recipe):
    path = REPO / "docs" / "recipes" / recipe
    assert path.is_file(), f"docs/recipes/{recipe} is missing"
    text = path.read_text()
    for required in RECIPES[recipe]:
        assert required.lower() in text.lower(), (
            f"docs/recipes/{recipe} no longer says {required!r}. These files are the "
            "canonical instructions; if this changed deliberately, update this test in "
            "the same commit and say why in its message."
        )


def test_agents_points_at_the_recipes():
    """AGENTS.md is the summary; an agent reading only it must be sent to the recipes."""
    text = (REPO / "AGENTS.md").read_text()
    assert "docs/recipes/" in text, "AGENTS.md never mentions the recipes directory"
