"""Reporting: LaTeX escaping, the renderer registry, and document assembly.

The escaping tests matter most. Metric and degradation names contain underscores, and an
unescaped underscore is a hard LaTeX error rather than a cosmetic one -- invisible until
compile time, and therefore invisible until someone uploads the folder to Overleaf.
"""

from __future__ import annotations

import re
import shutil

import numpy as np
import pandas as pd
import pytest

from fmeval.io import RunFolder, write_config, write_maps, write_results, write_run_meta
from fmeval.report import latex
from fmeval.report.driver import (
    build_context,
    render,
    write_document,
    write_manifest,
    write_summary_text,
)
from fmeval.report.registry import (
    PLOTS,
    SECTIONS,
    SECTIONS_BY_NUMBER,
    TABLES,
    iter_renderers,
)
from tests.test_analysis import make_frame

# --- escaping -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a_b", r"a\_b"),
        ("100%", r"100\%"),
        ("x&y", r"x\&y"),
        ("#1", r"\#1"),
        ("$x$", r"\$x\$"),
        ("{a}", r"\{a\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
        ("\\path", r"\textbackslash{}path"),
        ("", ""),
        (None, ""),
    ],
)
def test_escape(raw, expected):
    assert latex.escape(raw) == expected


def test_escape_does_not_double_escape_a_backslash():
    """A single pass, so the backslash introduced by an escape is not escaped again."""
    assert latex.escape("a\\b") == r"a\textbackslash{}b"


def test_code_escapes_then_wraps():
    assert latex.code("gaussian_blur") == r"\texttt{gaussian\_blur}"


def test_number_formatting():
    assert latex.number(0.5) == "0.500"
    assert latex.number(None) == "--"
    assert latex.number(float("nan")) == "--"
    assert latex.number(float("inf")) == "--"
    assert r"\times10^{" in latex.number(1.2e-9)


def test_slug_is_filesystem_and_latex_safe():
    stem = latex.slug("ladder_curves", metric="mse", field="vorticity")
    assert stem == "ladder_curves__metric-mse__field-vorticity"
    assert re.fullmatch(r"[A-Za-z0-9_-]+", stem)
    # graphicx mis-parses paths with more than one dot.
    assert "." not in latex.slug("x", field="a.b c/d")


def test_booktabs_table_escapes_every_cell():
    df = pd.DataFrame({"metric": ["a_b"], "note": ["100% & rising"]})
    tex = latex.booktabs_table(df, caption="c_1", label="t")
    assert r"a\_b" in tex and r"100\% \& rising" in tex and r"c\_1" in tex
    assert _unescaped_underscores(tex) == []


def test_booktabs_table_handles_an_empty_frame():
    tex = latex.booktabs_table(pd.DataFrame(), caption="none", label="e")
    assert "No data" in tex and "\\begin{table}" in tex


#: Commands whose argument is a filename or a key rather than typeset text. LaTeX does not
#: set these, so an underscore in them is both harmless and necessary -- the files really
#: are named e.g. `provenance_table.tex`.
_PATH_COMMANDS = ("input", "includegraphics", "label", "ref", "graphicspath", "lstset")


def _unescaped_underscores(text: str) -> list[str]:
    """Underscores that LaTeX would actually try to typeset.

    Excludes verbatim blocks and the arguments of path- and label-taking commands.
    """
    body = re.sub(r"\\begin\{lstlisting\}.*?\\end\{lstlisting\}", "", text, flags=re.S)
    for command in _PATH_COMMANDS:
        body = re.sub(rf"\\{command}(\[[^\]]*\])?\{{[^}}]*\}}", "", body)
    return [m.group() for m in re.finditer(r"(?<!\\)_", body)]


# --- registry -----------------------------------------------------------------------------


def test_every_renderer_declares_a_known_section():
    for spec in iter_renderers():
        assert spec.section in SECTIONS_BY_NUMBER, spec.name


def test_renderers_are_ordered_by_section():
    numbers = [s.section for s in iter_renderers()]
    assert numbers == sorted(numbers)


def test_section_numbers_are_unique_and_contiguous():
    numbers = [s.number for s in SECTIONS]
    assert numbers == sorted(set(numbers)) == list(range(1, len(SECTIONS) + 1))


def test_registries_are_not_empty():
    assert PLOTS and TABLES


def test_duplicate_registration_raises():
    from fmeval.report.registry import plot

    with pytest.raises(ValueError, match="duplicate"):

        @plot(section=3, name="ladder_curves")
        def _dupe(ctx, df, opts):
            return None


def test_unknown_section_raises():
    from fmeval.report.registry import plot

    with pytest.raises(ValueError, match="section"):

        @plot(section=99, name="_bad_section")
        def _bad(ctx, df, opts):
            return None


# --- end to end ------------------------------------------------------------------------------


@pytest.fixture
def run_folder(tmp_path):
    """A synthetic run folder, complete enough to render."""
    frames = []
    for metric in ("mse", "mae"):
        for field in ("vorticity", "density"):
            frames.append(make_frame(
                metric=metric, field=field, n_frames=8, noise=0.05, seed=1,
                axes={
                    "gaussian_blur": [1.0, 2.0, 3.0, 4.0],
                    "translate_x": [1.0, 3.0, 6.0, 9.0],
                    "gaussian_impostor": [8.0],
                    "uncorrelated": [10.0, 10.0, 10.0],
                },
            ))
    df = pd.concat(frames, ignore_index=True)

    folder = RunFolder(tmp_path / "mse_1").create()
    write_results(folder, df)
    digest = write_config(folder, {"metrics": ["mse"], "seed": 1, "note": "a_b"},
                          ["metrics=[mse]"])
    write_maps(folder, {"mse:vorticity__gaussian_blur_l2__t3": np.abs(
        np.random.default_rng(0).standard_normal((16, 8)))})
    write_run_meta(folder, run_id=1, config_hash=digest, metric="mse",
                   dataset="synthetic_d", n_frames=8, fields=["vorticity"],
                   analysis_grid=16, ladder_axes=["gaussian_blur"], n_rungs=12, seed=1,
                   command="python evaluate.py metrics=[mse]")
    return folder


def test_full_render(run_folder):
    ctx = build_context(run_folder, thresholds={"spearman": 0.9, "impostor_damage": 0.5},
                        bootstrap=0)
    rendered = render(run_folder, ctx, formats=("png",))
    write_document(run_folder, ctx, rendered)
    write_manifest(run_folder, rendered)
    write_summary_text(run_folder, ctx)

    assert any(r.status == "ok" for r in rendered)
    assert not [r for r in rendered if r.status == "error"], \
        [(r.name, r.reason) for r in rendered if r.status == "error"]
    assert (run_folder.root / "main.tex").exists()
    assert (run_folder.root / "preamble.tex").exists()
    assert (run_folder.root / "summary.txt").exists()
    assert list(run_folder.plots.glob("*.png"))
    assert list(run_folder.tables.glob("*.tex"))


def test_sections_are_written_in_ascending_order_with_none_empty(run_folder):
    ctx = build_context(run_folder, bootstrap=0)
    rendered = render(run_folder, ctx, formats=("png",))
    write_document(run_folder, ctx, rendered)

    names = sorted(p.name for p in run_folder.sections.glob("*.tex"))
    numbers = [int(n.split("_")[0]) for n in names]
    assert numbers == sorted(numbers)
    for path in run_folder.sections.glob("*.tex"):
        text = path.read_text()
        assert text.strip(), f"{path.name} is empty"
        assert "\\section{" in text


def test_no_unescaped_underscore_survives_into_any_generated_tex(run_folder):
    """The bug that would otherwise be found on Overleaf, not here."""
    ctx = build_context(run_folder, bootstrap=0)
    rendered = render(run_folder, ctx, formats=("png",))
    write_document(run_folder, ctx, rendered)

    for path in [*run_folder.sections.glob("*.tex"),
                 *run_folder.tables.glob("*.tex"),
                 run_folder.root / "main.tex"]:
        offenders = _unescaped_underscores(path.read_text())
        assert not offenders, f"{path.name} has {len(offenders)} unescaped underscore(s)"


def test_renderer_failures_are_recorded_but_not_fatal(run_folder, monkeypatch):
    """A bad figure must not destroy an expensive evaluation's output."""
    from fmeval.report import registry as rr

    def boom(ctx, df, opts):
        raise RuntimeError("deliberate")

    monkeypatch.setitem(rr.PLOTS, "ladder_curves",
                        rr.PLOTS["ladder_curves"].__class__(
                            **{**rr.PLOTS["ladder_curves"].__dict__, "fn": boom}))
    ctx = build_context(run_folder, bootstrap=0)
    rendered = render(run_folder, ctx, formats=("png",))
    failed = [r for r in rendered if r.name == "ladder_curves"]
    assert failed and failed[0].status == "error"
    assert any(r.status == "ok" for r in rendered), "other renderers must still run"


def test_single_metric_run_skips_cross_metric_renderers(run_folder):
    ctx = build_context(run_folder, bootstrap=0)
    ctx.df = ctx.df[ctx.df["metric"] == "mse"]
    ctx.card = ctx.card[ctx.card["metric"] == "mse"]
    rendered = render(run_folder, ctx, formats=("png",))
    skipped = {r.name: r.reason for r in rendered if r.status == "skipped"}
    assert "cost_frontier" in skipped
    assert "metrics" in skipped["cost_frontier"]


def test_config_appears_verbatim_in_the_report(run_folder):
    ctx = build_context(run_folder, bootstrap=0)
    rendered = render(run_folder, ctx, formats=("png",))
    write_document(run_folder, ctx, rendered)
    text = (run_folder.sections / "11_reproducibility.tex").read_text()
    assert "lstlisting" in text
    assert "metrics" in text, "the resolved config must be reproduced in the document"


# --- the compile check ------------------------------------------------------------------------


@pytest.mark.slow
def test_report_compiles_with_latex(run_folder):
    """Escaping bugs are invisible until compile time. Catch them here, not on Overleaf.

    Skipped when pdflatex is absent. On NERSC: ``module load texlive/2024``.
    """
    import subprocess

    if shutil.which("latexmk") is None:
        pytest.skip("latexmk not available")
    ctx = build_context(run_folder, bootstrap=0)
    rendered = render(run_folder, ctx, formats=("pdf", "png"))
    main = write_document(run_folder, ctx, rendered)
    result = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", main.name],
        cwd=main.parent, capture_output=True, text=True, timeout=600,
    )
    pdf = main.with_suffix(".pdf")
    assert result.returncode == 0, result.stdout[-4000:]
    assert pdf.exists() and pdf.stat().st_size > 1000


# --- the imshow lint --------------------------------------------------------------------------


def test_imshow_is_confined_to_the_style_helper():
    """Data is (X, Y); a raw imshow silently transposes every field picture.

    On square data the result looks entirely plausible, so this is the only thing that
    keeps the convention. ``monotonicity_heatmap`` is exempt: it draws a matrix of
    correlations, not a spatial field.
    """
    from pathlib import Path

    report_dir = Path(__file__).resolve().parent.parent / "fmeval" / "report"
    allowed = {"style.py"}
    for path in report_dir.glob("*.py"):
        if path.name in allowed:
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if ".imshow(" in line and "grid_df" not in line:
                raise AssertionError(
                    f"{path.name}:{number} calls imshow directly; spatial fields must go "
                    "through style.show_field, which applies the (X, Y) transpose"
                )
