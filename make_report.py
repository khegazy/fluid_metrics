"""Build a LaTeX report from a run folder, without recomputing any metric.

    uv run python make_report.py results/mse_1786224531
    uv run python make_report.py results/mse_1786224531 --style paper --compile
    uv run python make_report.py results/mse_1786224531 --zip
    uv run python make_report.py results/mse_1786224531 --only ladder_curves

Re-rendering from saved numbers is what you do repeatedly while writing a paper, and it is
also what keeps the generator honest: ``evaluate.py`` calls the same entry point, so there
is one code path that produces a report and it is exercised every time.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from fmeval.io import RunFolder
from fmeval.report.driver import (
    build_context,
    render,
    status_line,
    write_document,
    write_manifest,
    write_summary_text,
)

log = logging.getLogger("make_report")

DEFAULT_THRESHOLDS = {
    "spearman": 0.90,
    "separability_auc": 0.80,
    "impostor_damage": 0.50,
    "redundancy": 0.95,
}


def build(
    folder_path: Path | str,
    *,
    theme: str = "notebook",
    only: tuple[str, ...] = (),
    skip: tuple[str, ...] = (),
    formats: tuple[str, ...] = ("pdf", "png"),
    thresholds: dict[str, float] | None = None,
    bootstrap: int = 200,
) -> Path:
    """Render one run folder. Returns the path to ``main.tex``."""
    folder = RunFolder(Path(folder_path))
    if not folder.data.is_dir():
        raise FileNotFoundError(f"{folder.root} has no data/ directory")

    ctx = build_context(folder, theme=theme,
                        thresholds=thresholds or DEFAULT_THRESHOLDS,
                        bootstrap=bootstrap)
    rendered = render(folder, ctx, only=only, skip=skip, formats=formats)
    main = write_document(folder, ctx, rendered)
    write_manifest(folder, rendered)
    write_summary_text(folder, ctx)
    log.info("%s: %s", folder.root.name, status_line(rendered))
    return main


def compile_pdf(main: Path) -> bool:
    """Run latexmk if it is available. Returns whether a PDF was produced."""
    if shutil.which("latexmk") is None:
        log.warning("latexmk not found; skipping compilation "
                    "(on NERSC: module load texlive/2024)")
        return False
    result = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", main.name],
        cwd=main.parent, capture_output=True, text=True, timeout=600,
    )
    pdf = main.with_suffix(".pdf")
    if result.returncode != 0 or not pdf.exists():
        log.error("latexmk failed:\n%s", result.stdout[-3000:])
        return False
    log.info("compiled %s", pdf)
    return True


def make_zip(folder: Path) -> Path:
    """Archive the folder for upload to Overleaf, which detects main.tex automatically."""
    archive = folder.parent / f"{folder.name}.zip"
    if archive.exists():
        archive.unlink()
    shutil.make_archive(str(archive.with_suffix("")), "zip",
                        root_dir=folder.parent, base_dir=folder.name)
    log.info("wrote %s", archive)
    return archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path, help="a results/<metric>_<time>/ directory")
    parser.add_argument("--style", choices=("notebook", "paper"), default="notebook",
                        help="paper uses vector PDF, Type 42 fonts and journal widths")
    parser.add_argument("--only", nargs="*", default=[],
                        help="render only these renderers, by name")
    parser.add_argument("--skip", nargs="*", default=[])
    parser.add_argument("--formats", nargs="*", default=["pdf", "png"])
    parser.add_argument("--bootstrap", type=int, default=200,
                        help="bootstrap resamples for the correlation interval")
    parser.add_argument("--compile", action="store_true", help="also run latexmk")
    parser.add_argument("--zip", action="store_true",
                        help="write an Overleaf-ready archive beside the folder")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s",
                        stream=sys.stdout, force=True)

    main_tex = build(
        args.folder,
        theme=args.style,
        only=tuple(args.only),
        skip=tuple(args.skip),
        formats=tuple(args.formats),
        bootstrap=args.bootstrap,
    )
    print(f"wrote {main_tex}")

    if args.compile and not compile_pdf(main_tex):
        return 1
    if args.zip:
        make_zip(Path(args.folder))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
