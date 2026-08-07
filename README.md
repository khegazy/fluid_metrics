# fluid_metrics

Metrics that quantify the quality of fluid simulations — especially ML surrogates of
compressible, shocked, turbulent flow — with the eventual goal of using validated metrics as
evaluation panels and training losses for a scientific foundation model.

**The suite measures; it does not decide.** It produces a *report card* per metric: a
reproducible set of measurements against the criteria in
[TEST_DESCRIPTION.md](TEST_DESCRIPTION.md). Configurable thresholds only flag rows for
attention. Whether a metric joins the panel is the team's call.

## Quickstart

```bash
# One-time, if uv is not already available (installs to ~/.local/bin — add it to PATH)
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone <repo> && cd fluid_metrics
ln -s /global/cfs/cdirs/m4790/Data datasets   # gitignored; or set paths.data in the config

uv sync --extra dev                            # populates .venv from uv.lock, installs editable
uv run pytest                                  # seconds; skips the CFS-reading and LaTeX tests
```

Every command also works without `uv` on `PATH`, since `uv sync` creates a normal venv:

```bash
.venv/bin/python -m pytest
```

`uv.lock` is committed, so `uv sync` gives everyone the same versions rather than resolving
differently per machine.

### NERSC notes

- **`uv` needs a Python 3.12.** `uv python install 3.12` downloads one, or
  `module load python/3.12-26.1.0` supplies one. The download is more reproducible.
- **Do not run `uv sync` inside an activated conda env** — deactivate first, or a live
  `CONDA_PREFIX` confuses interpreter discovery.
- **Home has a quota and the uv cache grows.** Set `UV_CACHE_DIR` to a project or scratch
  path if home is tight; the cache is disposable.
- **`torch` is an optional extra on purpose** (`uv sync --extra torch`). Nothing in the
  current suite needs it, and the default PyPI wheel is not the build you want for
  Perlmutter GPUs.

## Running an evaluation

```bash
uv run python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev
```

Results land in `results/<metric>_<time>/`, one folder per metric, each self-contained:
`main.tex` (compiles standalone and renders on Overleaf), `plots/`, `tables/`, and `data/`
holding every raw number behind the report plus the exact config that produced it.

Large datasets are sized with two independent knobs — `dataset.time.reduction` (evaluate
every Nth frame) and `analysis_grid.resolution` (the IN-2 analysis grid). Both are recorded
with the results, so a reduced run is never mistaken for a full one.

## Documentation

| File | What it is |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Project conventions, the metric-tracker IDs, and the evaluation protocol |
| [TEST_DESCRIPTION.md](TEST_DESCRIPTION.md) | Plain-language reference for every quantity the suite reports |
| [issues/](issues/) | Open items and future work, one file each |

The **Fluid Metrics Exploration Tracker** (`Table_of_Ideas.tex`) on Overleaf is the source of
truth for the candidate metrics and their stable IDs (OT-1, NM-2, TD-1, …). Use those IDs in
code, commits, and discussion.

## Adding things

Three plugin registries, all discovered by name from the config — a contribution is one
decorated function in one file, with no import list to update:

| To add a… | Put it in | Decorate with |
|---|---|---|
| metric | `metrics/` (any module or subpackage) | `@metric(...)` |
| degradation | `degradations/` | `@degradation(...)` |
| plot or table | `fmeval/report/` | `@plot(...)` / `@table(...)` |

Datasets are added as a YAML file under `configs/dataset/`, and new file formats as a reader
in `fmeval/data/`.

```bash
uv run python -m metrics.registry        # what metrics exist
uv run python -m degradations.registry   # what degradations exist, with severity units
```
