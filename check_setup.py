"""Confirm the environment is usable, before running anything expensive.

    python check_setup.py

Reports what works and what does not, with the fix for each failure, and exits non-zero if
anything essential is missing. Written so a new user can tell an environment problem from a
code problem in one command, rather than reading a traceback from a failed evaluation.
"""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
OK, WARN, FAIL = "ok  ", "warn", "FAIL"


def main() -> int:
    results: list[tuple[str, str, str]] = []

    def record(status: str, item: str, detail: str = "") -> None:
        results.append((status, item, detail))

    # --- interpreter and dependencies -------------------------------------------------
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 12):
        record(OK, f"python {version}")
    else:
        record(FAIL, f"python {version}", "needs >= 3.12; recreate the environment")

    for module in ("numpy", "scipy", "h5py", "pandas", "matplotlib", "hydra", "omegaconf",
                   "yaml", "pytest"):
        try:
            mod = importlib.import_module(module)
            record(OK, module, getattr(mod, "__version__", ""))
        except ImportError:
            record(FAIL, module, "missing; install the dev extra "
                   "(`uv sync --extra dev`, or `pip install -e '.[dev]'`)")

    # --- the project's own packages ---------------------------------------------------
    try:
        from degradations import registry as deg
        from metrics import registry as met

        met.discover()
        deg.discover()
        record(OK, "metrics registry", f"{len(met.REGISTRY)} metrics")
        record(OK, "degradations registry", f"{len(deg.REGISTRY)} operators")
        for name, errors in (("metrics", met.discover()), ("degradations", deg.discover())):
            if errors:
                record(WARN, f"{name} import errors",
                       ", ".join(f"{m}: {e!r}" for m, e in errors.items()))
    except ImportError as exc:
        record(FAIL, "project packages",
               f"{exc}; install the project editable "
               "(`uv sync --extra dev`, or `pip install -e '.[dev]'`)")

    # --- the vendored spectral code, validated against an analytic result -------------
    try:
        import numpy as np

        from fmeval.data.base import GridSpec
        from fmeval.derived import vorticity_from_velocity

        n, dx = 32, 2 * np.pi / 32
        x = np.arange(n) * dx
        xx, yy = np.meshgrid(x, x, indexing="ij")
        u = np.stack([np.sin(xx) * np.cos(yy), -np.cos(xx) * np.sin(yy)])
        grid = GridSpec((n, n), (dx, dx), (True, True), ("x", "y"), (0.0, 0.0))
        error = float(np.abs(vorticity_from_velocity(u, grid)[0]
                             - 2 * np.sin(xx) * np.sin(yy)).max())
        if error < 1e-10:
            record(OK, "spectral vorticity", f"Taylor-Green error {error:.1e}")
        else:
            record(FAIL, "spectral vorticity", f"Taylor-Green error {error:.1e}, expected <1e-10")
    except Exception as exc:  # noqa: BLE001
        record(FAIL, "spectral vorticity", repr(exc))

    # --- the data root ----------------------------------------------------------------
    root = REPO / "datasets"
    if root.exists():
        target = root.resolve()
        record(OK, "dataset root", f"{root} -> {target}" if root.is_symlink() else str(root))
    else:
        record(WARN, "dataset root",
               "no `datasets` symlink (gitignored, so a fresh clone lacks it). "
               "Create it with `ln -s /global/cfs/cdirs/m4790/Data datasets`, or pass "
               "`paths.data=...`. Only needed to run evaluations, not tests")

    # --- LaTeX ------------------------------------------------------------------------
    if shutil.which("latexmk"):
        record(OK, "latexmk", "reports can be compiled locally")
    else:
        record(WARN, "latexmk",
               "not found; `--compile` will be skipped. On NERSC: `module load texlive/2024`. "
               "Reports still render as .tex and compile on Overleaf")

    # --- report -----------------------------------------------------------------------
    width = max(len(item) for _, item, _ in results)
    print()
    for status, item, detail in results:
        print(f"  [{status}] {item.ljust(width)}  {detail}")

    failures = [r for r in results if r[0] == FAIL]
    warnings = [r for r in results if r[0] == WARN]
    print()
    if failures:
        print(f"{len(failures)} problem(s) must be fixed before the suite will run.")
        return 1
    extra = f" {len(warnings)} optional item(s) missing." if warnings else ""
    print("Environment is usable." + extra)
    print("Next: `pytest` (~20 s), then "
          "`python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
