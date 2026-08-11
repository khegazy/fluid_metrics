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
uv run python check_setup.py                   # confirms the environment; says what to fix
uv run pytest                                  # seconds; skips the CFS-reading and LaTeX tests
```

If anything goes wrong, run `check_setup.py` first — it separates an environment problem from a
code problem and prints the fix for each failure. The `datasets` symlink and `latexmk` show as
optional: tests do not need either.

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

The entry point is `evaluate.py`. Everything it does is set by configuration, and **the metric
to test is the one thing you will override most often**, so start here:

```bash
# The standard test, with the metric chosen on the command line
uv run python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev

# Several metrics in one run: each gets its own folder, plus a comparison folder
uv run python evaluate.py 'metrics=[mae,mse,nrmse]' dataset=kinet_re5e4_dev
```

Quote the argument (`'metrics=[mae,mse]'`) whenever the list has commas, or the shell will
split it. A single-element list needs no quoting.

`uv run python -m metrics` lists the names you can put there. An unknown name fails
immediately with the available list, rather than part-way through a run.

Results land in `results/<metric>_<time>/`, one folder per metric, each self-contained:
`main.tex` (compiles standalone and renders on Overleaf), `plots/`, `tables/`, and `data/`
holding every raw number behind the report plus the exact config that produced it.

### How the configuration is organised

Configuration is [Hydra](https://hydra.cc). `configs/config.yaml` is the top level; it selects
one option from each **config group**, and every value can be overridden from the command line.

```
configs/
├── config.yaml            top level: metrics, fields, seed, analysis grid, paths
├── dataset/               kinet_re5e4_dev · kinet_re5e4 · well_re5e4
├── degradation/           default · quick
├── report/                default · none
└── dataset_family/        reynolds_ladder_2d   (not yet consumed; see issues/011)
```

There are two different ways to change something, and the distinction matters:

**Choose a group option** with `group=option`. This swaps in a whole file:

```bash
uv run python evaluate.py metrics=[mse] dataset=kinet_re5e4    # the 167 GiB trajectory
uv run python evaluate.py metrics=[mse] degradation=quick      # 3 axes instead of 14
uv run python evaluate.py metrics=[mse] report=none            # write data/ only
```

**Override a single value** with a dotted path. This reaches into whichever file was selected:

```bash
uv run python evaluate.py metrics=[mse] dataset.time.reduction=100
uv run python evaluate.py metrics=[mse] analysis_grid.resolution=128
uv run python evaluate.py metrics=[mse] 'degradation.ladder.gaussian_blur.severities=[1,2,4]'
```

**`metrics` is deliberately not a config group.** It is a plain list, so choosing a metric is
`metrics=[mse]` rather than a file you have to create first. That is the whole point of the
registry: a new metric is one decorated function and it is immediately runnable by name.

### The overrides worth knowing

Every form below is covered by a test in `tests/test_configs.py`, so a command that appears
here works.

| Override | Effect |
|---|---|
| `metrics=[mse]` | Which metric(s) to test. **The usual override** |
| `dataset=kinet_re5e4` | Which dataset. `ls configs/dataset/` for the choices |
| `dataset.time.reduction=100` | Evaluate every 100th frame |
| `dataset.time.start=2000` | Skip the early, undeveloped part of the trajectory |
| `dataset.time.max_frames=5` | Hard cap, applied after the reduction. Good for a smoke test |
| `fields=[vorticity]` | Restrict to one field instead of all the dataset offers |
| `analysis_grid.resolution=128` | Coarsen both fields onto a common grid before measuring |
| `degradation=quick` | A 3-axis ladder, for iterating |
| `degradation.only=[translate_x]` | Run only these ladder entries |
| `degradation.skip=[median_blur]` | Drop these ladder entries |
| `degradation.ladder.<entry>.enabled=false` | Disable one entry |
| `degradation.ladder.<entry>.severities=[1,2,4]` | Change one entry's rungs |
| `report=none` | Skip figures and tables; render later with `make_report.py` |
| `report.style.theme=paper` | Vector PDF, Type-42 fonts, journal column widths |
| `seed=1` | Change the run seed |
| `paths.data=/path/to/data` | Point at your own data instead of the `datasets` symlink |

Two settings in `config.yaml` are load-bearing and commented there rather than left implicit:
`hydra.job.chdir` must stay `false`, and the Hydra output directories must stay plain relative
paths — interpolating `paths.results` into them breaks every multirun, because
`hydra.sweep.dir` is resolved before Hydra's own context exists.

### A worked example

```bash
# Smoke test: one metric, small ladder, three frames. A few seconds.
uv run python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev \
    degradation=quick dataset.time.max_frames=3

# A real run: three metrics on the developed flow, every 400th frame,
# vorticity only, on a 128^2 analysis grid.
uv run python evaluate.py 'metrics=[mae,mse,nrmse]' dataset=kinet_re5e4 \
    dataset.time.start=2000 dataset.time.reduction=400 \
    'fields=[vorticity]' analysis_grid.resolution=128

# Then build the cross-metric report and compile it.
uv run python make_report.py results/comparison_<time> --compile
```

**Use `kinet_re5e4_dev` only for smoke tests.** It is the first 100 solver steps, before the
flow develops, so a 16-cell displacement costs about 1e-4 of what an unrelated field costs
against 0.51 at t=5000. It will run, and its numbers mean nothing physically. Anything you
intend to report should use `dataset=kinet_re5e4` with `dataset.time.start=2000` or later.

### Several datasets at once

Hydra's multirun (`-m`) sweeps a group, running once per option:

```bash
uv run python evaluate.py -m metrics=[mse] dataset=kinet_re5e4_dev,well_re5e4
```

Each run writes its own folder. `fmeval.io.load_runs("mse_*")` concatenates them into one
frame when you want to compare across datasets.

### Sizing a run

Two independent knobs, both recorded with the results so a reduced run is never mistaken for a
full one: `dataset.time.reduction` (evaluate every Nth frame) and `analysis_grid.resolution`
(the common analysis grid). The full 10001-frame trajectory at `reduction=1` takes roughly half
an hour; the default of 50 is under a minute.

Hydra writes its own bookkeeping — the resolved config and the job log — to
`results/.hydra/`, out of the way of the run folders.

## Documentation

| File | What it is |
|---|---|
| [AGENTS.md](AGENTS.md) | **How to work in this repository** — adding metrics, degradations, data sources and figures; testing; the generated LaTeX; known traps. Read by coding agents, and worth reading yourself |
| [CLAUDE.md](CLAUDE.md) | Project conventions, the metric IDs, and the evaluation protocol |
| [TEST_DESCRIPTION.md](TEST_DESCRIPTION.md) | Plain-language reference for every quantity the suite reports |
| [issues/](issues/) | Open items and future work, one file each |

The project's **metrics tracker** is the source of truth for the candidate metrics and their
stable IDs (OT-1, NM-2, TD-1, …). Use those IDs in code, commits, and discussion; see
[CLAUDE.md](CLAUDE.md) for the identifier scheme and where the tracker lives.

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
