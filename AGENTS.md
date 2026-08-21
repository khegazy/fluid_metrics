# Instructions for coding agents

**Read this before changing anything.** It is the canonical set of instructions for any agent
working in this repository, regardless of which assistant you are. `CLAUDE.md` carries the
scientific context; this file carries the mechanics.

The repository evaluates candidate metrics for judging fluid simulations. Its output is
evidence for a research decision, so a plausible-looking wrong number is worse than an
obvious failure. Most of the rules below exist because something specific went wrong.

> **The canonical instructions for extending the repository live in
> [`docs/recipes/`](docs/recipes/index.md)** — adding a metric, a degradation, a dataset,
> a diagnostic, and refreshing the recorded evidence. The sections below summarise; where
> this file and a recipe disagree, the recipe wins. The recipes are separate files, each
> pinned by its own test, so a careless edit to this file cannot destroy them.

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
pytest -q > /tmp/pt.txt 2>&1; RC=$?; tail -3 /tmp/pt.txt; [ $RC -eq 0 ] || exit 1
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

**Every command here is a plain `python` or `pytest` call.** Contributors use different
environment tools, so activate whichever one you have and run them as written; do not add a
`uv run` prefix back into documentation or code comments. `uv sync --extra dev` populates
`.venv` from the committed lockfile, and `pip install -e '.[dev]'` works the same way in a plain
venv or a conda env. Python 3.12 or newer. Neither the commands nor the imports need the repo
root as the working directory.

```bash
python check_setup.py               # confirm the environment; run this FIRST when anything
                                    # unexpected happens, before debugging code

pytest                              # ~20 s. Skips CFS-reading and LaTeX tests
pytest -m data                      # reads the real files on CFS
module load texlive/2024 && pytest -m slow   # compiles a report
pytest tests/test_analysis.py -k spearman    # one file, one pattern

python -m metrics                   # list registered metrics
python -m degradations              # list registered degradations, with units

python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev
python make_report.py results/mse_<time> --compile --zip
```

Use `dataset=kinet_re5e4_dev` for the inner loop: it is the 1.7 GB sibling and a full run takes
seconds. **It is not physically representative** — the first 100 solver steps, before the flow
develops — so never draw a physical conclusion from it. Use `dataset=kinet_re5e4` with
`dataset.time.start=2000` for anything you intend to report.

Two size knobs, both recorded with the results: `dataset.time.reduction` (evaluate every Nth
frame) and `analysis_grid.resolution` (the common analysis grid).

---

## 3. Adding a metric

A metric is a **bundle**: a directory under `metrics/` named exactly what users type in
`metrics=[...]`, holding the implementation, its tests, and the card that documents it.
Scaffold it, never create the files by hand:

```bash
python -m fmeval.cards new <name>            # metrics/<name>/, from the template
python -m fmeval.cards check <name>          # says exactly what is missing and how to fix it
```

`<name>` is lowercase with underscores and is a valid Python identifier, because discovery
imports the package. It is the metric's only identity: there are no separate IDs.

**The card is not optional.** `registry.get()` validates it, so a metric whose card is
missing or malformed fails when the harness asks for it, not later. Fill the bundle in this
order — the first two are yours, the rest an agent can complete from the contract:

1. **`metric.py`** — one `@metric`-decorated function returning one float per (field,
   frame, severity level). The decorator's fields are read by the harness and appear in the
   catalog; nothing in `card.yaml` repeats them.
2. **`test_metric.py`** — at least one test whose expected value you worked out by hand, on
   a small field. It is also the source of the worked example in the card, so the prose
   cannot drift from the code.
3. **`card.yaml`** — the typed record. Every field is documented in `fmeval/cards/schema.py`.
4. **`card.md`** — the prose, six sections in a fixed order. See §3.1.
5. **`python -m fmeval.cards evidence <name> --results results/<run>`** — writes the
   measured half from a recorded run. Never write those numbers yourself.

Reusing another bundle's function is expected rather than discouraged: `rmse` imports
`mse`, `nrmse` imports `rmse`. The decorator returns the function unwrapped and the import
system registers each bundle once, so the shared maths cannot drift apart.

### 3.1 What goes in `card.md`

Six sections, fixed order, all required: `## Definition`, `## Performance`, `## Intuition`,
`## Reading the output`, `## Limitations`, `## Results`, `## References`.

- **`## Definition`** — numbered equations, the discretisation, and a required
  `### Boundary handling` subsection. `None.` plus a clause is a fine answer for a
  pointwise metric. Write maths as `$ ... $` inline and `$$ ... $$` with `\tag{1}` for
  display, and nothing else: `\begin{equation}`, `\label` and `\eqref` typeset on the
  site and show as raw source on GitHub, so the checker refuses them.
- **`## Intuition`** — no notation at all, for an early graduate student in any field. What
  the metric measures, the mechanism, a worked example whose numbers come from
  `test_metric.py`, and one sentence naming what it ignores. Write about the metric, not
  about its standing in this project.
- **`## Reading the output`** — range, units, direction, what makes a value good, and which
  comparisons are valid.
- **`## Limitations`** — at least one concrete situation where it misleads.
- **`## Performance` and `## Results`** — generated. Leave the marked blocks alone; write
  only the explanation below each Results block, saying what that test found about this
  metric. Link each subsection to the degradations it reports rather than describing them.

There are no word counts. Say what the section needs to say and stop.

### 3.2 Rules that are not negotiable

- **Never invent a number or a citation.** If there is no run, the card says so. An
  unverifiable reference stays `TODO(cite)`, which fails validation on purpose.
- **Never state expected behaviour anywhere.** Every claim about how a metric behaves is
  either a measurement from a named run or a citation. Cards carry no predictions, and the
  schema refuses an `expectations` key.
- **Never write inside a `<!-- GENERATED ... -->` block**, and never edit `_generated/`.
- **Never set `status: validated`, and never sign a card.** Both are human acts; `sign`
  refuses anyway until measurements exist.
- **Never edit another bundle** while adding yours. If a change elsewhere seems necessary,
  stop and say why.

### 3.3 The decorator

Discovery walks the package, so there is no import list to edit and no registration call to
add.

```python
from metrics.registry import metric, pointwise_map


@metric(
    name="h_minus_one",          # the metric's identity: bundle directory, card key,
                                 # and what users type in metrics=[...]. Defaults to fn.__name__
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

A single-field metric will be reported as `no dynamic range`, and **that is correct, not a bug you
should try to fix**. The normalised damage scale is anchored between the reference and a
*translated* copy of it, which has identical statistics — so a single-field quantity takes the same
value at both anchors and the span is zero. On a smoothing axis you will also see `rho = -1`,
because smoothing reduces such quantities rather than increasing them. If you find yourself
"fixing" either, stop: you would be removing a true statement.

On an axis the quantity is *invariant* to — a translation, for a quantity that does not depend on
position — `rho` is reported as **NaN**, not as a number. It used to be a number: `np.roll` cannot
change enstrophy but it does change the summation order inside `np.mean`, so the severity levels differed in
the last bits, in an arbitrary order, and ranking that produced a confident-looking 0.707 printed
beside genuine correlations. Anything whose variation across an axis is below a relative
`analysis.DEGENERATE_SPAN` is now withheld rather than reported. The same applies to the damage
column when the anchor itself is round-off, and to the sensitivity and saturation levels when the
span is.

**Declare `higher_is_better` correctly, because it is now read.** Four statistics are one-sided —
monotonicity asks whether the value rises, the separability AUC is taken with
`alternative="greater"`, and the two threshold levels look for the first median to exceed a target.
The analysis multiplies the value by the declared direction before computing them, so `rho = +1`
means "responds correctly to damage" whichever convention you use. Declare it wrong and all four
invert; the symptom is a clean `-1` on every axis at once.

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

1. `python -m metrics` — confirm it appears with the metadata you expect.
2. `pytest` — the contract test is parametrized over the whole registry, so your metric
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

A degradation is a bundle too, under `degradations/`, scaffolded the same way:

```bash
python -m fmeval.cards new <name> --kind degradation
```

Which failure modes you probe determines what the acceptance measurements *mean*, so this
is as consequential as adding a metric.

Its card has the same shape with two differences. `card.yaml` needs an **`exemplars`**
block naming the three severities to illustrate and the diagnostic rows that expose the
mechanism — a blur is legible in `radial_spectrum`, a translation is not, because it moves
spectral phase rather than amplitude, so use `spectral_phase` or `difference` there; noise
shows up in `pdf`. For an operator with no ordered severity, use `mode: draws`. And
`card.md` replaces Reading the output with **`## Severity scale`**, which must say whether
the severity is absolute or calibrated per field, and Results with
**`## What the degradation looks like`** (formerly `## Exemplars`), whose generated block
holds the example panel and whose prose says what to look at in that panel.

Then generate the panel, from the one canonical frame every figure in the repository
shares:

```bash
python -m fmeval.cards exemplars <name>
```

Never draw those figures yourself and never edit them. If a metric card links to your
degradation, regenerate that metric's evidence after yours.

```python
from degradations.registry import degradation


@degradation(
    family="smoothing",              # one of degradations.registry.FAMILIES
    severity_name="sigma",           # what the number means; used as an axis label
    severity_units="cells",
    severity_direction="increasing", # "decreasing" if a SMALLER value is worse
    calibration="scale",             # None if the severity is in absolute units; see below
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
increasing-damage order before numbering the severity levels. Get this wrong and a low-pass cutoff list
written `[64, 32, 16, 8]` produces a perfectly inverted ladder and a rank correlation of −1,
with nothing else in the pipeline noticing. A test *verifies* your declaration by measuring
that damage really rises with level.

**`ordinal=False` for probes.** The Gaussian impostor and the unrelated-field anchor are not
severity levels on any monotone axis. Folding a probe into a family as "level 6" silently corrupts every
rank correlation it touches.

**Express relative severities against the fluctuation, never the raw value.** Density here is
`1.0 ± 1.8e-4`. A noise amplitude expressed as a fraction of the raw RMS would make the mildest
severity level total destruction and the ladder flat-topped for every metric.

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

**You do not have to declare how your operator rounds its severity.** A calibrated severity is a
real number while many operators act on a quantised one — a sharp filter selects whole sets of
modes, a windowed kernel takes an odd number of cells — so two different nominal severities can
resolve to the *same experiment*. The harness detects that by measurement rather than by
declaration: identical operations produce a bitwise identical field and therefore an exactly equal
`energy_changed`, so the repeat is flagged as `severity_degenerate` and excluded. A severity level that
resolves to doing nothing at all is caught the same way, by measuring that the output moved by more
than round-off relative to the field's own fluctuation.

What this means for you is only that **your operator must be deterministic in its severity** if it
is calibrated: given the same input and severity it must return the same array, or the detection
cannot tell a repeat from a fresh draw. Stochastic operators are exempt because they are never
calibrated.

**If you write a spectral operator, take `|k|` from `fmeval.wavenumbers`.** There were two
definitions of wavenumber magnitude and they disagreed about the diagonal modes: the filters
compared against a continuous `|k|` while the calibration binned into shells of `rint(|k|)`. On
density, whose energy is concentrated in the lowest modes, a low-pass asked to remove 30% removed
99.997% — and every intermediate number looked plausible. One definition, shared by both sides.

**Then:**

1. **Add your operator to `LADDERS` in `tests/test_degradation_contract.py`.** A test fails
   until you do, deliberately — otherwise your operator escapes every check below it.
2. `pytest` — you now get shape and dtype preservation, passthrough at zero severity,
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
   If it approaches the grid size, the harsher blur severity levels are smoothing over the whole domain and
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
   severity levels on density no matter what the config says.
4. **The degenerate-severity level warnings.** The run names every `(field, axis, level)` that resolved onto
   a milder severity level's severity or onto a no-op, and excludes them. A handful is normal and is a fact
   about the field. Whole axes collapsing to one severity level means the severity list does not suit this
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

Run with `pytest`. Markers: `data` reads real files on CFS, `slow` needs LaTeX; both are
excluded by default.

**CI runs the default suite on every push to a pull request** — `.github/workflows/tests.yml`,
which builds the environment from the committed lockfile, puts `.venv/bin` on PATH so its steps
are the same plain commands written above, and runs `check_setup.py`, both registry listings and
`pytest -ra`.

It cannot run the other two markers: a GitHub runner has no CFS and no TeX Live. So a green PR
says nothing about a `data`-marked test, and **verifying those stays a local responsibility** —
run `pytest -m data` yourself before asking for review on anything touching a reader, a remap or
an anchor. The LaTeX side is less exposed than it looks: the check that actually bites,
`test_no_unescaped_underscore_survives_into_any_generated_tex`, is an ordinary test and does run
in CI. Only the `latexmk` compile is left to `module load texlive/2024 && pytest -m slow`.

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
python make_report.py results/mse_<time>            # re-render from saved numbers
python make_report.py results/mse_<time> --compile  # also run latexmk
python make_report.py results/mse_<time> --zip      # Overleaf-ready archive
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
| **Pooling frames for rank correlation** | The flow evolves, so the worst severity level early is numerically smaller than the mildest severity level late. Every density axis was perfectly ordered *within* every frame while the pooled value read 0.10–0.91 | `analysis.py::_per_frame_rho` |
| **Averaging a derived field after a remap** | Block-averaged vorticity is not the curl of the velocity beside it: 5.6% / 18.3% / 25.9% at factors 2 / 4 / 8 | `fmeval/derived.py` |
| **Mixing stored and recomputed derived fields** | The solver's lattice stencil and a spectral derivative differ by 8.1% rms, so grid-independence would measure the discretisation, not the grid | `fmeval/derived.py::recompute_frame` |
| **Forgetting that spacing scales with the coarsening factor** | A spectral derivative at a coarse grid with fine spacing is inflated by exactly the factor | `GridSpec.coarsened` |
| **Deleting k=0 in a high-pass filter** | On density that removes a component four orders of magnitude larger than the cutoff controls; every severity level returned an identical damage of 2.7e7 | `degradations/spectral.py` |
| **Drawing impostor phases directly** | Violates Hermitian symmetry at the self-conjugate modes, so `irfftn` discards the imaginary part and corrupts the spectrum. Gives flatness 47.9 instead of 3 | `degradations/stochastic.py` |
| **Scavenging the unrelated-field anchor from a ladder severity_level** | A 16-cell translation reaches only ~0.6 of the true value, inflating every damage score by ~1.6x | `analysis.py::normalisation` |
| **Using a distant frame as a statistical twin** | The flow decays: 4000 steps away has 0.70 of the variance and a different flatness, and scores *closer* than a true twin | `degradations/geometric.py::random_large_translation` |
| **Splitting a module without its private helpers** | Helpers defined above the first decorator are easy to drop; three operators once raised `NameError` and the run completed with 630 rows missing. A code defect in an operator now stops the run, but the trap when extracting code remains | `fmeval/pipeline.py::_runnable_levels`, and the row comparison in `docs/recipes/verify-a-refactor.md` |
| **Writing maths or includes that render in only one reader** | `\begin{equation}` and include directives typeset on the site and appear as raw text on GitHub, with no error anywhere | the math checker in `fmeval/cards/prose.py`; generated blocks live in `card.md` between markers |
| **Typing measured numbers into prose** | A sentence citing values from an earlier run looks exactly as authoritative as the generated table beside it; impostor damages 0.80/0.51 sat in a card while the pinned run measured 0.90/0.66/1.23 | `issues/032`, and step 3 of `docs/recipes/refresh-the-evidence.md` |
| **Placing a `###` subsection mid-section** | Everything after it reads as belonging to it; a Boundary-handling subsection once swallowed the rest of the Definition | put required subsections at the end of their section |
| **Expecting byte-identical PNGs across matplotlib versions** | They differ; only the JSON fingerprints are byte-stable, and a determinism test on pixels will flake in CI | `docs/decisions.md`, "Figures are committed" |
| **Including the reference severity level in cross-metric correlation** | Every pairwise metric is 0 there, adding a shared point that pulls every correlation toward +1 | `analysis.py::cross_metric_correlation` |
| **A raw `imshow` on a spatial field** | Data is `(X, Y)`, so it transposes every picture — and looks fine on square data | `fmeval/report/style.py::show_field` |
| **Assuming `pressure == density / 3` bitwise** | The solver writes `density * float64(1/3)`; the two differ by one ulp | `fmeval/data/kinet_raw.py` |
| **Reading `time_scale` as a clock** | `time_scale[0]` is NaN and the values are ~0.5 constant. It is a solver stability quantity; use `time` | `fmeval/data/kinet_raw.py` |
| **Trusting the dev dataset physically** | It is the first 100 solver steps, before the flow develops. A 16-cell translation costs 1e-4 of what an unrelated field costs, against 0.51 at t=5000 | `configs/dataset/kinet_re5e4_dev.yaml` |
| **`git push` hanging** | X11 forwarding is attempted and stalls. Use `GIT_SSH_COMMAND="ssh -x" git push` | — |
| **`import kinet`** | Pulls in `mpi4py`, which cannot load libmpi on a login node. The spectral diagnostics are vendored instead | `fmeval/external/kinet_spectral.py` |
| **Two definitions of `\|k\|`** | The filters compared a continuous magnitude, the calibration binned into shells of `rint(\|k\|)`, so the diagonal modes fell on opposite sides of one cutoff. On density a low-pass asked to remove 30% removed 99.997% | `fmeval/wavenumbers.py` |
| **Ranking values that differ only in the last bits** | `np.roll` cannot change a translation-invariant quantity but does change the summation order in `np.mean`. The reported `rho` was 0.707 over a relative 1.6e-16 | `analysis.py::_is_round_off` |
| **A median as the scale in a degeneracy guard** | When most severity levels are round-off the median collapses with them, so the guard compares noise against noise and passes — defeated in exactly the case it exists for. Use the largest value | `analysis.py::normalisation` |
| **Assuming every metric rises with damage** | Three one-sided statistics scored a perfectly ordered similarity metric at `monotone_fraction = 0`, `AUC = 0`, `rho = -1`, flagging a correct metric on three criteria | `analysis.py::response_direction` |

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
| `CLAUDE.md` | Scientific context: the problem framing and the evaluation protocol |
| `TEST_DESCRIPTION.md` | Every quantity the suite reports, in plain language. **Update it when you add a reported quantity — a test enforces this** |
| `issues/README.md` | Open items with their evidence |
| `README.md` | Setup, and the NERSC specifics |
| `.github/workflows/tests.yml` | CI. Runs the default suite on every push to a PR; cannot run `-m data` or `-m slow` |
| `docs/catalog.json` | **Read this for anything structural** — what metrics exist, what they return, what properties they have, how they behaved. Do not parse prose for it |
| `docs/working-with-the-repo.md` | What every file in a bundle is for, and where you are expected to make changes |
| `fmeval/cards/schema.py` | Every `card.yaml` field, with the reasoning for it |
| `docs/recipes/` | **The canonical step-by-step instructions** for adding a metric, degradation, dataset or diagnostic, and for refreshing the evidence |

## Reading the repository

For anything structural, read `docs/catalog.json`. It merges what the code declares, what
each card states and what the recorded run measured, so it answers "which metrics are
differentiable, cheap, and measured?" without opening a card.

`python -m fmeval.cards list` and `python -m metrics` are the quick interactive
equivalents.

## Before you finish

```bash
python -m fmeval.cards check --all
pytest
python -m fmeval.cards catalog          # if you added or changed a bundle
mkdocs build --strict                   # if you touched docs/ or mkdocs.yml
```

Report what you added, any `TODO(cite)` you left and why, and anything the checker flagged
that you could not resolve.
