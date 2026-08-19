# pde_metrics

Metrics for evaluating ML surrogates of PDEs — compressible and incompressible flow, MHD,
probabilistic data and whatever comes next — with the eventual goal of using validated
metrics as evaluation panels and training losses for a scientific foundation model.
Compressible, shocked, turbulent flow is the first test case rather than the scope.

**The suite measures; it does not decide.** It produces a *report card* per metric: a
reproducible set of measurements against the criteria in
[TEST_DESCRIPTION.md](TEST_DESCRIPTION.md). Configurable thresholds only flag rows for
attention. Whether a metric joins the panel is the team's call.

## Quickstart

```bash
git clone git@github.com:khegazy/pde_metrics.git && cd pde_metrics
ln -s /global/cfs/cdirs/m4790/Data datasets   # gitignored; or set paths.data in the config
```

Then install into whatever environment you use. **Every command in this README is a plain
`python` or `pytest` call**, so activate your environment first and the rest follows; nothing
here assumes a particular tool.

```bash
# uv (recommended: uv.lock is committed, so everyone gets the same versions)
uv sync --extra dev && source .venv/bin/activate

# a plain venv
python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'

# conda
conda create -n pde_metrics python=3.12 && conda activate pde_metrics
pip install -e '.[dev]'
```

Requires Python 3.12 or newer. Then:

```bash
python check_setup.py     # confirms the environment; says what to fix
pytest                    # seconds; skips the CFS-reading and LaTeX tests
```

If anything goes wrong, run `check_setup.py` first — it separates an environment problem from a
code problem and prints the fix for each failure. The `datasets` symlink and `latexmk` show as
optional: tests do not need either.

Not activating is fine too: `uv run <command>` and `.venv/bin/python <script>` both work
without it, so prefix the commands below however you prefer.

### NERSC notes

- **Python 3.12 or newer.** `module load python/3.12-26.1.0` supplies one, and
  `uv python install 3.12` downloads one — the download is the more reproducible of the two.
- **Do not build the venv inside an activated conda env** — deactivate first, or a live
  `CONDA_PREFIX` confuses interpreter discovery.
- **Home has a quota and package caches grow.** Set `UV_CACHE_DIR` (or `PIP_CACHE_DIR`) to a
  project or scratch path if home is tight; the cache is disposable.
- **`torch` is an optional extra on purpose** (`pip install -e '.[torch]'`). Nothing in the
  current suite needs it, and the default PyPI wheel is not the build you want for
  Perlmutter GPUs.

## Running an evaluation

The entry point is `evaluate.py`. Everything it does is set by configuration, and **the metric
to test is the one thing you will override most often**, so start here:

```bash
# The standard test, with the metric chosen on the command line
python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev

# Several metrics in one run: each gets its own folder, plus a comparison folder
python evaluate.py 'metrics=[mae,mse,nrmse]' dataset=kinet_re5e4_dev
```

Quote the argument (`'metrics=[mae,mse]'`) whenever the list has commas, or the shell will
split it. A single-element list needs no quoting.

`python -m metrics` lists the names you can put there. An unknown name fails
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
python evaluate.py metrics=[mse] dataset=kinet_re5e4    # the 167 GiB trajectory
python evaluate.py metrics=[mse] degradation=quick      # 3 axes instead of 14
python evaluate.py metrics=[mse] report=none            # write data/ only
```

**Override a single value** with a dotted path. This reaches into whichever file was selected:

```bash
python evaluate.py metrics=[mse] dataset.time.reduction=100
python evaluate.py metrics=[mse] analysis_grid.resolution=128
python evaluate.py metrics=[mse] 'degradation.ladder.gaussian_blur.severities=[1,2,4]'
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
| `degradation.ladder.<entry>.severities=[1,2,4]` | Change one entry's severity levels |
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
python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev \
    degradation=quick dataset.time.max_frames=3

# A real run: three metrics on the developed flow, every 400th frame,
# vorticity only, on a 128^2 analysis grid.
python evaluate.py 'metrics=[mae,mse,nrmse]' dataset=kinet_re5e4 \
    dataset.time.start=2000 dataset.time.reduction=400 \
    'fields=[vorticity]' analysis_grid.resolution=128

# Then build the cross-metric report and compile it.
python make_report.py results/comparison_<time> --compile
```

**Use `kinet_re5e4_dev` only for smoke tests.** It is the first 100 solver steps, before the
flow develops, so a 16-cell displacement costs about 1e-4 of what an unrelated field costs
against 0.51 at t=5000. It will run, and its numbers mean nothing physically. Anything you
intend to report should use `dataset=kinet_re5e4` with `dataset.time.start=2000` or later.

### Several datasets at once

Hydra's multirun (`-m`) sweeps a group, running once per option:

```bash
python evaluate.py -m metrics=[mse] dataset=kinet_re5e4_dev,well_re5e4
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
| [CLAUDE.md](CLAUDE.md) | Scientific context: the problem framing and the evaluation protocol |
| [TEST_DESCRIPTION.md](TEST_DESCRIPTION.md) | Plain-language reference for every quantity the suite reports |
| [docs/working-with-the-repo.md](docs/working-with-the-repo.md) | What every file in a bundle is for, who edits it, and when |
| [docs/catalog.json](docs/catalog.json) | The machine-readable index of every metric and degradation. What an agent should read instead of parsing prose |
| [issues/](issues/) | Open items and future work, one file each |
| [.github/workflows/tests.yml](.github/workflows/tests.yml) | CI: runs the default test suite on every push to a pull request. It has no CFS and no TeX Live, so `pytest -m data` and `pytest -m slow` stay a local responsibility |

Every metric and degradation documents itself, in a **card** beside its implementation. A
card holds the definition, the plain-language explanation, how to read the output, where it
misleads, and the measurements from a recorded evaluation run — the last of those generated,
never typed. [metrics/mse/card.md](metrics/mse/card.md) is the worked example, and
[docs/](docs/) is published as a site.

## Adding things

A metric or a degradation is a **bundle**: one directory holding the implementation, its
tests, and the card documenting it. Scaffold it rather than creating files by hand, and the
card cannot be forgotten because it is already there:

```bash
python -m fmeval.cards new <name>                    # a metric bundle
python -m fmeval.cards new <name> --kind degradation
python -m fmeval.cards check <name>                  # says what is missing and how to fix it
```

Plots and tables for the LaTeX report are still one decorated function in `fmeval/report/`.
Datasets are a YAML file under `configs/dataset/`, and new file formats a reader in
`fmeval/data/`.

```bash
python -m metrics                 # what metrics exist
python -m degradations            # what degradations exist, with severity units
python -m fmeval.cards list       # bundles, with status and category
```

[AGENTS.md](AGENTS.md) has the full recipe, and
[docs/working-with-the-repo.md](docs/working-with-the-repo.md) explains what each file in a
bundle is for.
