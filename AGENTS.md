# Instructions for coding agents

**Read this before changing anything.** It is the canonical set of instructions for any agent
working in this repository, regardless of which assistant you are. `CLAUDE.md` carries the
scientific context; this file carries the mechanics.

The repository evaluates candidate metrics for judging fluid simulations. Its output is
evidence for a research decision, so a plausible-looking wrong number is worse than an
obvious failure. Most of the rules below exist because something specific went wrong.

## Contents

1. [Ground rules](#1-ground-rules)
2. [Environment and commands](#2-environment-and-commands)
3. [Adding a metric](#3-adding-a-metric)
4. [Adding a degradation](#4-adding-a-degradation)
5. [Adding a data source](#5-adding-a-data-source)
6. [Adding a figure or table](#6-adding-a-figure-or-table)
7. [Writing tests](#7-writing-tests)
8. [How to treat the LaTeX output](#8-how-to-treat-the-latex-output)
9. [Traps that have already caught someone](#9-traps-that-have-already-caught-someone)
10. [Committing](#10-committing)

---

## 1. Ground rules

**Verify before you claim.** Never report that something works without having run it and read
the output. In particular, never write `pytest | tail` and chain on `&&` — a pipeline's exit
status is the *last* command's, so failures pass silently. Use:

```bash
uv run pytest -q > /tmp/pt.txt 2>&1; RC=$?; tail -3 /tmp/pt.txt; [ $RC -eq 0 ] || exit 1
```

**Measure; do not assume.** If you state a number in a docstring, a commit message, or a
report, you must have computed it. If you cannot compute it, say so and label it a conjecture.
Several docstrings here carry measured values precisely so the next person does not have to
re-derive them; keep that habit.

**When a measurement contradicts you, the measurement wins.** If you assert something and then
find it is wrong, correct it in the code and say so plainly. There are corrections recorded in
`CLAUDE.md` and in several docstrings that exist because a prediction failed. That is normal and
useful; hiding it is not.

**The suite measures, it does not decide.** No verdict columns, no accept/reject labels. There
are configured thresholds, and they only populate an advisory `flags` column. **Never tune a
threshold so that a metric passes.** If a threshold looks wrong, argue for changing it in an
issue and say what evidence would settle it.

**Never tune a detector threshold per metric or per model.** Anything thresholded is fixed once
in the evaluator. A per-model threshold makes the metric gameable, which is the failure the
whole exercise is meant to detect.

**Record the reason, not just the change.** When you fix something subtle, put the evidence in
the docstring where the code lives. "Preserves the mean" is much less useful than "preserves
the mean, because deleting k=0 on density removed a component four orders of magnitude larger
than the cutoff controls and flattened the whole axis".

**Write an issue while the evidence is in front of you.** `issues/` holds one file per open
item with its measurements. An issue written later from memory is worth much less.

---

## 2. Environment and commands

`uv` with a committed lockfile. `.venv/bin/python` works anywhere `uv run` does.

```bash
uv sync --extra dev                 # populate .venv from uv.lock
uv run python check_setup.py        # confirm the environment; run this FIRST when anything
                                    # unexpected happens, before debugging code

uv run pytest                       # ~20 s. Skips CFS-reading and LaTeX tests
uv run pytest -m data               # reads the real files on CFS
module load texlive/2024 && uv run pytest -m slow   # compiles a report
uv run pytest tests/test_analysis.py -k spearman    # one file, one pattern

uv run python -m metrics            # list registered metrics
uv run python -m degradations       # list registered degradations, with units

uv run python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev
uv run python make_report.py results/mse_<time> --compile --zip
```

Use `dataset=kinet_re5e4_dev` for the inner loop: it is the 1.7 GB sibling and a full run takes
seconds. **It is not physically representative** — the first 100 solver steps, before the flow
develops — so never draw a physical conclusion from it. Use `dataset=kinet_re5e4` with
`dataset.time.start=2000` for anything you intend to report.

Two size knobs, both recorded with the results: `dataset.time.reduction` (evaluate every Nth
frame) and `analysis_grid.resolution` (the common analysis grid).

---

## 3. Adding a metric

A metric goes in any module or subpackage under `metrics/`. Discovery walks the package, so
there is no import list to edit and no registration call to add.

```python
from metrics.registry import metric, pointwise_map


@metric(
    name="h_minus_one",          # defaults to the function name
    tracker_id="NM-2",           # the stable ID from the metrics tracker; see CLAUDE.md
    arity="pairwise",            # "pairwise" -> fn(reference, candidate); "single" -> fn(x)
    fields=("vorticity",),       # canonical fields it accepts; ("*",) for any
    returns="scalar",            # "scalar" -> float; "vector" -> 1-D array
    differentiable=True,         # declared, never inferred. Could this be a training loss?
    cost="cheap",                # cheap | moderate | expensive (advisory; warns on long runs)
    higher_is_better=False,
    symmetric=True,              # enables an automatic symmetry check
    units="field",               # free text: "field", "field^2", "dimensionless"
    reduction="mean",            # how a pointwise map reduces; see below
)
def h_minus_one(reference, candidate, *, ctx):
    """One-line summary; it becomes the caption fallback and the registry listing.

    Peyre (2018), ESAIM:COCV 24(4), 1489, Eq. (1.2) -- cite the paper and equation for
    anything taken from the literature.
    """
    ...
```

**Arity.** `pairwise` takes `(reference, candidate)`; `single` takes `(x)` and characterises one
field. Both receive `(C, *spatial)` float64 arrays. The decorator checks the positional
argument count against the declared arity and raises at import time if they disagree.

A single-field metric will be reported as `no dynamic range` with `rho = -1`, and **that is
correct, not a bug you should try to fix**. The normalised damage scale is anchored between the
reference and a *translated* copy of it, which has identical statistics — so a single-field
quantity takes the same value at both anchors and the span is zero. `rho = -1` follows because
smoothing reduces such quantities rather than increasing them. If you find yourself
"fixing" this, stop: you would be removing a true statement.

**`ctx` is opt-in.** Declare a keyword-only parameter named `ctx` and you receive a
`FieldContext` with the grid (spacing, periodicity, dimension names), the frame index, the
physical time, the reference fluctuation RMS, and a seeded generator. Omit it and you get
nothing extra — which is why `mae(reference, candidate)` needs no boilerplate. Never hardcode
an axis index: use `ctx.axis("x")`, because which axis is x depends on the dimension count.

**Pointwise maps.** If the metric is a reduction of a per-cell density, declare the companion.
It is what makes the `field_gallery` figure possible, and for a displaced feature it shows the
double penalty as two lobes rather than as an argument.

```python
@pointwise_map(of="h_minus_one")      # must come AFTER the metric it belongs to
def h_minus_one_map(reference, candidate, *, ctx):
    """Per-cell density, summed over channels. Reduces to the metric by mean/C."""
    ...
```

**Get the reduction right — this is the easy mistake.** The declared `reduction` is verified by
a test, and two cases catch people:

- Maps are summed over channels, so a `mean` reduction is `map.mean() / C`, not `map.mean()`.
- `rmse` uses `sqrt_mean`: its map is the *squared* error and does **not** average to the
  metric value.

Available reductions are in `metrics/registry.py::REDUCTIONS`; add one there if you need it.

**Heavy imports go inside the function body.** Every metric module is imported on every run, so
a module-level `import torch` is a startup cost paid by everyone, including runs that never
touch your metric.

**Then, before you are done:**

1. `uv run python -m metrics` — confirm it appears with the metadata you expect.
2. `uv run pytest` — the contract test is parametrized over the whole registry, so your metric
   is now automatically checked for `d(x,x) == 0`, declared symmetry, return type, shape
   rejection, float32/float64 agreement, monotonicity on a synthetic blur ladder, and the
   map-reduces-to-metric identity. You do not write any of that.
3. **Add an entry to `TEST_DESCRIPTION.md`** if your metric introduces a new reported quantity.
   A test fails otherwise.
4. Report the result back to the metrics tracker, so its `Status` column reflects what has
   actually been measured. Ask the maintainer where the tracker currently lives; do not assume
   a file in this repository.

---

## 4. Adding a degradation

Degradations live under `degradations/` and are discovered the same way. Which failure modes
you probe determines what the acceptance measurements *mean*, so this is as consequential as
adding a metric.

```python
from degradations.registry import degradation


@degradation(
    family="smoothing",              # one of degradations.registry.FAMILIES
    severity_name="sigma",           # what the number means; used as an axis label
    severity_units="cells",
    severity_direction="increasing", # "decreasing" if a SMALLER value is worse
    calibration="scale",             # None if the severity is in absolute units; see below
    quantise=None,                   # how you round the severity internally, if you do
    ordinal=True,                    # False for a probe that is not on a monotone axis
    stochastic=False,                # True to redraw the RNG per frame
    fields=("*",),
    defaults={"order": 4},           # per-entry options, overridable in config
)
def my_blur(x, severity, *, ctx):
    """One line; shown by `python -m degradations`."""
    return ...
```

**Operators act on one field, `(C, *spatial) -> (C, *spatial)`.** The driver applies yours to
each requested field with a generator derived from `(seed, label, frame_index, field)`, so
deterministic operators stay consistent across fields and stochastic ones draw independently.
If you genuinely need cross-field access, declare `whole_frame=True`.

**`severity_direction` is not cosmetic.** The ladder builder sorts severities into
increasing-damage order before numbering the rungs. Get this wrong and a low-pass cutoff list
written `[64, 32, 16, 8]` produces a perfectly inverted ladder and a rank correlation of −1,
with nothing else in the pipeline noticing. A test *verifies* your declaration by measuring
that damage really rises with level.

**`ordinal=False` for probes.** The Gaussian impostor and the unrelated-field anchor are not
rungs on any monotone axis. Folding a probe into a family as "level 6" silently corrupts every
rank correlation it touches.

**Express relative severities against the fluctuation, never the raw value.** Density here is
`1.0 ± 1.8e-4`. A noise amplitude expressed as a fraction of the raw RMS would make the mildest
rung total destruction and the ladder flat-topped for every metric.

**`calibration` is how you avoid a severity that means different things on different fields.**
A wavenumber or a smoothing width in cells lands in a completely different place depending on
where a field keeps its energy, and here those places differ by a factor of five: the density
fluctuation varies on ~160 cells against ~34 for vorticity. Declare what your severity scales
with and the ladder resolves it per field against a measured spectrum:

| `calibration` | the config severity is | resolved to |
|---|---|---|
| `None` | already field-independent (a factor, a displacement) or already relative to something measured (noise vs the fluctuation RMS) | used as written |
| `"scale"` | a fraction of the characteristic scale | a length in cells |
| `"energy_above"` | the fraction of energy to remove from *above* the cutoff — a low-pass | a cutoff wavenumber |
| `"energy_below"` | the fraction to remove from *below* it — a high-pass | a cutoff wavenumber |

Choosing the wrong side of `energy_above` / `energy_below` silently inverts the axis: "remove
5%" then resolves to the wavenumber *holding* 5% of the energy and removes the other 95%. Your
function receives the resolved absolute value, and both it and the nominal one are recorded on
every row.

**`quantise` is how the harness knows two rungs are the same experiment.** If your operator
rounds its severity internally — a sharp filter zeroes whole wavenumber shells, a windowed kernel
takes an odd number of cells — pass that rounding function. Two nominal severities that quantise
alike are one experiment, and the harness flags the repeat as `severity_degenerate` and excludes
it. Without the declaration a repeated rung is scored as a genuine fourth point: the rank
correlation reads a tie as agreement and the separability compares a distribution against itself.
Operators that use the severity as given (a Gaussian sigma, a Fourier phase shift) leave it
`None`. A rung that resolves to doing nothing at all is caught separately, by measuring that the
output moved by more than round-off.

**Then:**

1. **Add your operator to `LADDERS` in `tests/test_degradation_contract.py`.** A test fails
   until you do, deliberately — otherwise your operator escapes every check below it.
2. `uv run pytest` — you now get shape and dtype preservation, passthrough at zero severity,
   direction verification, and seed reproducibility for free.
3. Add a row to the degradation table in `TEST_DESCRIPTION.md`. A test enforces this.
4. Add it to `configs/degradation/default.yaml` if it should run by default, with `enabled:
   false` if it is situational.

---

## 5. Adding a data source

Readers are a deliberately *closed* set with explicit imports, unlike metrics and degradations.
They are harness infrastructure rather than an open contributor surface, so the discovery
mechanism that suits an open set would only add indirection.

Subclass `Trajectory` in a new module under `fmeval/data/`. Only `read_frame` is abstract; the
shape, dtype and finiteness validation lives in the concrete `frame()` and every reader
inherits it.

```python
from .base import GridSpec, Trajectory, register_reader


@register_reader("my_format")
class MyTrajectory(Trajectory):
    @property
    def fields(self) -> tuple[str, ...]: ...     # canonical names actually present
    @property
    def times(self): ...                         # (T,) physical time, float64
    @property
    def grid(self) -> GridSpec: ...
    @property
    def meta(self) -> dict: ...                  # path, format, source attributes

    def read_frame(self, t: int, fields):
        """Return {name: (C, *spatial)}. `t` is an int index, never a slice."""
```

Then add the module to the import line in `evaluate.py::open_trajectory`, and write a dataset
config under `configs/dataset/`.

### Three rules that are not negotiable

**1. Canonical layout is channel-first with spatial axes trailing in `(x, y, z)` order.** The
solver writes `(C, X, Y, Z)` and drops dimensions right to left, so 2D is `(C, X, Y)`. Do not
convert to the image convention: that would mean a transpose on every read and a permanent
mismatch with the solver's own output. Write everything against "the trailing `n_spatial` axes,
in order", which is also what makes 3D a non-event.

**2. Never slice the time axis.** These files are chunked one frame per chunk, so
`density[0, 0, :, i, j]` touches all 10001 chunks — 5 GB of I/O for 80 KB of data.
`frame()` rejects non-integer indices, and a test monkeypatches `h5py` to record every key and
assert the time position is always an `int`. That test is the only thing standing between a
one-character edit and a hundredfold slowdown, and no correctness test would catch it.

**3. Tag fields primitive or derived.** Density and velocity are stored and are remapped
directly. Vorticity and pressure are computed from them and must be **recomputed** after any
remap, never averaged — block-averaging vorticity gives a field that is not the curl of the
velocity beside it, by 5.6% / 18.3% / 25.9% at coarsening factors 2 / 4 / 8.

### Every new dataset needs its severity calibration checked

**The ladder's severities are not absolute numbers, and they are re-measured for every dataset.**
The smoothing widths and filter cutoffs in `configs/degradation/default.yaml` are fractions — of
the field's characteristic scale, or of the energy a filter removes — and the pipeline resolves
them per field against a spectrum it measures from the data itself. Nothing needs to be entered by
hand and no config edit is required to run a new dataset. What *does* need doing is checking that
the calibration it measured is usable, because a severity list that resolves well on one flow can
resolve onto a wall on another.

The run logs one line per field and writes `data/calibration.csv`. Read four things from it:

1. **`characteristic_scale`**, in cells. This is the unit every smoothing width is a fraction of.
   If it approaches the grid size, the harsher blur rungs are smoothing over the whole domain and
   are no longer probing anything local.
2. **`scale_spread`**, the fractional variation across the sampled frames. Above `DRIFT_WARN`
   (0.25) the run warns, and it means what it says: **a single calibration is not trustworthy for
   that trajectory.** The flow's spectrum is moving enough over the frames being evaluated that
   one fixed ladder is a compromise between different flows. Vorticity on the production
   trajectory sits at 21–33% depending on the span, so this warning fires in normal use — narrow
   the time window, or treat that field's calibrated axes as approximate and say so.
3. **`k_energy_50 / 90 / 99`**, the wavenumbers holding those fractions of the fluctuation energy.
   These tell you immediately how much room a filter ladder has. Density on this data reads
   1 / 2 / 5: with only about three usable shells, a *sharp* filter cannot produce four distinct
   rungs on density no matter what the config says.
4. **The degenerate-rung warnings.** The run names every `(field, axis, level)` that resolved onto
   a milder rung's severity or onto a no-op, and excludes them. A handful is normal and is a fact
   about the field. Whole axes collapsing to one rung means the severity list does not suit this
   data, and the fix is a wider or better-placed list of *fractions* — never a per-field number,
   which would make the metric gameable.

A field with no fluctuation energy at all cannot be calibrated. The run logs a skip for it and any
calibrated axis then fails loudly on that field rather than applying an energy fraction as though
it were a wavenumber.

Two consequences worth knowing before they surprise you. Because the calibration is measured from
the frames actually evaluated, **changing `dataset.time.reduction` moves the resolved severities
slightly** — about 5e-6 relative, measured — so runs at different reductions are not bitwise
comparable, which was already the rule for other reasons. And because the calibration is part of
what a number means, `data/calibration.csv` belongs with any result you hand to someone: a
calibrated severity without it is uninterpretable.

### Test fixtures must be non-square

Every real dataset is square (256², 512²). A reader that transposes x and y therefore passes
every test on real-shaped data and produces silently wrong pictures forever. Synthetic fixtures
are **16×8**, and they write `u = 1, v = 2` at t=0 so a channel swap fails just as loudly.
Reproduce the format's quirks deliberately: a fixture that stops reproducing a quirk is itself
a signal that the real format has changed.

### Validate against ground truth where you can

`tests/test_loader_contract.py` has a `data`-marked test that reads the *same* simulation
through both the raw and the Well readers and asserts identical grids, times and values. That
is what validates the abstraction against reality rather than against a fixture someone wrote.
If your new format has an existing counterpart, add the equivalent check.

---

## 6. Adding a figure or table

Renderers live in `fmeval/report/plots.py` and `tables.py`. One decorated function plus a
section number; the writer groups by section and emits the narrative in order, so there is no
dispatch list to edit.

```python
from .registry import plot
from .context import FigureItem, PlotResult


@plot(
    section=3,                    # which chapter; see registry.SECTIONS
    order=20,                     # position within the chapter
    scope="per_metric_field",     # global | per_field | per_metric | per_metric_field
    title="Response to each degradation",
    requires_columns=("degradation", "level", "value"),
    requires_degradations=("gaussian_impostor",),
    min_metrics=2, min_axes=1, min_frames=4, min_datasets=1,
    requires_maps=False,
    defaults={"logy": "auto"},
)
def my_figure(ctx, df, opts) -> PlotResult:
    """One line; becomes the caption fallback."""
    ctx.require(some_condition, "why this cannot run")   # data-dependent skip
    fig, grid = ctx.style.figure(1, 1)
    ...
    return PlotResult([FigureItem(fig, {"field": field}, caption="...", data=tidy)])
```

**Two rules keep this maintainable.**

*All non-trivial computation lives in `fmeval/analysis.py`.* Renderers arrange precomputed
numbers. That is what makes a figure and its table consistent by construction, and it means the
statistics are testable without touching matplotlib.

*Renderers never write files and never mutate global state.* The driver owns paths, formats and
rcParams. So every renderer is callable from a notebook, and a run cannot depend on the order
its renderers happened to execute in.

**Declare unavailability rather than crashing.** The `requires_*` and `min_*` fields are checked
*before* your function is entered, which covers most cases at no cost. For data-dependent cases
call `ctx.require(cond, msg)`. Anything else that raises is caught, recorded in the manifest and
non-fatal — a bad figure must never destroy an expensive evaluation.

**Spatial fields go through `style.show_field()`.** It is the only place `imshow` may be called,
and a lint test enforces that. Data is `(X, Y)`, so a raw `imshow` transposes every picture in
the report — and on square data the result looks entirely plausible.

**Share colour limits across a figure.** Autoscaling each panel makes a heavily smoothed field
look identical to the reference, which is the opposite of what a gallery is for.

**Attach the numbers.** `FigureItem.data` is written beside the figure as a CSV. The rule is
that no number appears in the report without a machine-readable source in the same folder.

---

## 7. Writing tests

Run with `uv run pytest`. Markers: `data` reads real files on CFS, `slow` needs LaTeX; both are
excluded by default.

**Prefer a contract test parametrized over a registry** to a test of one implementation. The
metric, degradation and loader contracts are each parametrized over their whole registry, so
every future contribution inherits them. That is the single highest-leverage pattern here.

**Test the property, not the current value.** `assert rho == 1.0` on a synthetic monotone ladder
is a property. `assert value == 0.0037` pins an implementation detail and will be deleted by
whoever next changes anything.

**Make failure messages diagnostic.** Say what was measured and what it implies:

```python
assert damage == sorted(damage), (
    f"{spec.name}: damage {damage} is not increasing across sorted severities "
    f"{severities}; severity_direction={spec.severity_direction!r} may be wrong"
)
```

**Statistical assertions need statistical tolerances.** Flatness is a fourth moment and noisy on
one realisation — measured spread on a 64² grid is 2.9 ± 0.2 across seeds. Average over seeds
and assert on the mean, with a loose per-seed bound that still separates a correct 3 from a
broken 48.

**Keep the default suite fast and offline.** Synthetic fixtures, milliseconds, no CFS. Reserve
the real files for `data`-marked tests.

---

## 8. How to treat the LaTeX output

**Everything under `results/` is generated. Never hand-edit it.** If a report is wrong, fix the
renderer or the analysis and re-run `make_report.py`. A hand-patched report is indistinguishable
from a correct one and will be trusted.

```bash
uv run python make_report.py results/mse_<time>            # re-render from saved numbers
uv run python make_report.py results/mse_<time> --compile  # also run latexmk
uv run python make_report.py results/mse_<time> --zip      # Overleaf-ready archive
```

Re-rendering never recomputes a metric, so iterating on presentation is instant. `evaluate.py`
calls the same entry point, so there is exactly one code path that produces a report.

**Escape every data-derived string.** Metric and degradation names contain underscores, and an
unescaped underscore is a *hard compile error*, not a cosmetic one — invisible until compile
time, and therefore invisible until someone uploads the folder to Overleaf. Use
`fmeval.report.latex.escape()` for text and `code()` for identifiers. A test asserts no
unescaped underscore survives into any generated file, and a `slow`-marked test compiles the
document.

**Pre-format numbers in Python.** `latex.number()` emits fixed strings rather than relying on a
package to parse them, which removes any dependence on the `siunitx` version Overleaf happens
to ship.

**Standard packages only.** `geometry, graphicx, booktabs, longtable, caption, xcolor, amsmath,
listings, hyperref`. No `minted`, nothing needing `--shell-escape`, no local `.sty`. The
document must compile on Overleaf with no setup.

**Keep run folders self-contained.** A folder holds the raw numbers, the resolved config, full
provenance, a copy of `TEST_DESCRIPTION.md`, and a `main.tex` that compiles standalone. Never
add a path that points outside the folder — it is meant to survive being zipped and handed to
someone.

**Generated prose must quote measured values.** Section text is written by
`fmeval/report/driver.py::_section_prose`, which reads numbers out of the analysis frames.
**Never hardcode a number into report prose.** If you want the report to say something, compute
it and interpolate it.

**Filenames** come from `latex.slug()`: `[A-Za-z0-9_-]` with a single dot, because `graphicx`
mis-parses paths with more. Figures are referenced without an extension so LaTeX prefers the
PDF and falls back to the PNG.

### Hand-written LaTeX, if any appears

The rule above applies to *generated* output under `results/`. A `.tex` file elsewhere in the
repository is a working document and may be edited directly — but check two things first.

Confirm it is not a duplicate of a document maintained elsewhere, typically on Overleaf. If it
is, **the two diverge the moment either is edited**, so say so explicitly when you change one,
and prefer handing back a patch to apply at the canonical copy.

Confirm it still compiles: `module load texlive/2024 && latexmk -pdf <file>.tex`. Note that a
document with a bibliography needs three passes for references to resolve; a single pass reports
undefined citations that are not real problems.

---

## 9. Traps that have already caught someone

Each of these was found by measurement, and each would have quietly corrupted results. They are
listed so nobody has to rediscover them.

| Trap | What happens | Where the fix lives |
|---|---|---|
| **Pooling frames for rank correlation** | The flow evolves, so the worst rung early is numerically smaller than the mildest rung late. Every density axis was perfectly ordered *within* every frame while the pooled value read 0.10–0.91 | `analysis.py::_per_frame_rho` |
| **Averaging a derived field after a remap** | Block-averaged vorticity is not the curl of the velocity beside it: 5.6% / 18.3% / 25.9% at factors 2 / 4 / 8 | `fmeval/derived.py` |
| **Mixing stored and recomputed derived fields** | The solver's lattice stencil and a spectral derivative differ by 8.1% rms, so grid-independence would measure the discretisation, not the grid | `fmeval/derived.py::recompute_frame` |
| **Forgetting that spacing scales with the coarsening factor** | A spectral derivative at a coarse grid with fine spacing is inflated by exactly the factor | `GridSpec.coarsened` |
| **Deleting k=0 in a high-pass filter** | On density that removes a component four orders of magnitude larger than the cutoff controls; every rung returned an identical damage of 2.7e7 | `degradations/spectral.py` |
| **Drawing impostor phases directly** | Violates Hermitian symmetry at the self-conjugate modes, so `irfftn` discards the imaginary part and corrupts the spectrum. Gives flatness 47.9 instead of 3 | `degradations/stochastic.py` |
| **Scavenging the unrelated-field anchor from a ladder rung** | A 16-cell translation reaches only ~0.6 of the true value, inflating every damage score by ~1.6x | `analysis.py::normalisation` |
| **Using a distant frame as a statistical twin** | The flow decays: 4000 steps away has 0.70 of the variance and a different flatness, and scores *closer* than a true twin | `degradations/geometric.py::random_large_translation` |
| **Including the reference rung in cross-metric correlation** | Every pairwise metric is 0 there, adding a shared point that pulls every correlation toward +1 | `analysis.py::cross_metric_correlation` |
| **A raw `imshow` on a spatial field** | Data is `(X, Y)`, so it transposes every picture — and looks fine on square data | `fmeval/report/style.py::show_field` |
| **Assuming `pressure == density / 3` bitwise** | The solver writes `density * float64(1/3)`; the two differ by one ulp | `fmeval/data/kinet_raw.py` |
| **Reading `time_scale` as a clock** | `time_scale[0]` is NaN and the values are ~0.5 constant. It is a solver stability quantity; use `time` | `fmeval/data/kinet_raw.py` |
| **Trusting the dev dataset physically** | It is the first 100 solver steps, before the flow develops. A 16-cell translation costs 1e-4 of what an unrelated field costs, against 0.51 at t=5000 | `configs/dataset/kinet_re5e4_dev.yaml` |
| **`git push` hanging** | X11 forwarding is attempted and stalls. Use `GIT_SSH_COMMAND="ssh -x" git push` | — |
| **`import kinet`** | Pulls in `mpi4py`, which cannot load libmpi on a login node. The spectral diagnostics are vendored instead | `fmeval/external/kinet_spectral.py` |

Two interpretive traps, which are not bugs but produce wrong conclusions:

**The Gaussian-impostor check does not catch the L^p family.** MSE scores it 0.51–0.80 because
pointwise metrics are phase-*sensitive*; randomising phases is the most damaging thing you can
do to them. The check is aimed at quantities that are functions of `|F(f)|` alone — an energy
spectrum, a two-point correlation — which score it *perfectly*. A report where everything
passes is not reassuring; it means nothing in the panel can be caught by it yet.

**High rank correlation does not mean two metrics agree.** MAE and MSE correlate at 0.995 across
the ladder yet differ by 55× in displacement damage at an eighth of a cell, because one is
linear and the other quadratic in the displacement. For ranking they are duplicates; as losses
they are not.

---

## 10. Committing

Branch from `main`. Do not commit to `main` directly, and do not commit or push unless asked.

**Never commit without a verified green suite.** See the exit-code idiom in
[Ground rules](#1-ground-rules).

**Never commit `results/`.** It is gitignored, along with `.venv/`, `__pycache__/`, LaTeX build
artifacts, and the `datasets` symlink — that last one is machine-specific and the dataset root
belongs in `configs/config.yaml` as `paths.data`.

**Write commit messages that explain the reasoning.** State what changed, why, and what evidence
supports it. If a measurement drove the change, quote it. If the change corrects something you
previously asserted, say so — several commits here do, and that record is useful.

```bash
GIT_SSH_COMMAND="ssh -x -o BatchMode=yes" git push origin <branch>
```

---

## Where else to look

| File | What it is |
|---|---|
| `CLAUDE.md` | Scientific context: the problem framing, the tracker IDs, the evaluation protocol |
| `TEST_DESCRIPTION.md` | Every quantity the suite reports, in plain language. **Update it when you add a reported quantity — a test enforces this** |
| `issues/README.md` | Open items with their evidence |
| `README.md` | Setup, and the NERSC specifics |
