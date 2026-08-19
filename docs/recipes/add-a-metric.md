# Adding a metric

The result of this recipe is one directory under `metrics/` that contains everything the
repository will ever hold about the metric: the implementation, tests that pin its worked
example, a typed record, prose for three audiences, and — once a run exists — its measured
behaviour. Follow the steps in order; several later ones consume earlier ones.

## 1. Scaffold

```bash
python -m fmeval.cards new <name>
python -m fmeval.cards check <name>     # run at any point; it names what is missing and the fix
```

`<name>` is lowercase with underscores, a valid Python identifier, and exactly what users
will type in `metrics=[<name>]`. It is the metric's only identity — there are no separate
IDs. `python -m fmeval.cards list` shows what is taken. Never create the files by hand.

## 2. Implement — `metric.py`

One `@metric`-decorated function returning **one `float` per (field, frame, severity
level)**. The pipeline loops over frames, fields and severities; the metric sees two arrays
and returns a number.

- Set every decorator field honestly: `arity`, `fields`, `units`, `higher_is_better`,
  `differentiable`, `cost`, `symmetric`, `reduction`. These are read by the harness and
  published in the catalog; nothing in the card repeats them, so they are the only place
  this information lives.
- Cite the source paper **and equation number** in the docstring for anything taken from
  the literature.
- Declare a keyword-only `ctx` if you need the grid, the reference fluctuation RMS, or a
  seeded RNG — never seed your own.
- Reuse across bundles by importing: `rmse` imports `mse`. The decorator returns the
  function unwrapped, so shared maths cannot drift apart. Do not copy an equation from
  another bundle.
- If the metric is pointwise-decomposable, add a `@pointwise_map(of="<name>")` companion
  returning the per-cell density, and declare the `reduction` that carries the map back to
  the scalar.

## 3. Test — `test_metric.py`

At least one test whose expected value you computed **by hand**, on a field small enough to
verify visually — four by four is ideal. This test is the source of the worked example in
the card, which is what stops the prose drifting from the code. Also test each behaviour
the card will claim: a scaling law, an invariance, an asymmetry. The registry-wide contract
(zero on identical fields, symmetry, map-reduces-to-scalar) is already tested centrally; do
not repeat it.

Run the smoke test before writing any prose:

```bash
python evaluate.py metrics=[<name>] dataset=kinet_re5e4_dev degradation=quick
```

## 4. The typed record — `card.yaml`

Every field is documented in `fmeval/cards/schema.py`; read it rather than copying another
card blindly. Choose `category` from the controlled vocabulary. Leave `status: candidate`
and `review: null`. The `math` block holds only what the decorator does not:
`triangle_inequality`, `scale_dependent`, `resolution_dependent`, `complexity`.

## 5. The prose — `card.md`

Six hand-written concerns in a fixed order, with generated blocks between them. The order
runs from what the metric *is* to what it *did here*: Definition, Performance (generated),
Intuition, Reading the output, Limitations, Results, References.

- **`## Definition`** — numbered display equations, the discretisation, and a required
  `### Boundary handling` subsection; `None.` plus one clause is the right answer for a
  pointwise metric. Say what the equation does not already say and nothing it does. Write
  maths as `$...$` inline and `$$...$$` with `\tag{1}` for display, and nothing else —
  `\begin{equation}`, `\label` and `\eqref` render on the site but show as raw source on
  GitHub, and the checker refuses them.
- **`## Intuition`** — no mathematical notation at all. For an early graduate student in
  any STEM field: direct, no belaboured analogies. Four things: what it measures and which
  way of being wrong it reveals; the mechanism; the worked example with the numbers from
  `test_metric.py`; one sentence naming what it ignores. Write about the metric, not its
  standing in this project.
- **`## Reading the output`** — range and units, direction, what makes a value good and on
  what that depends, and which comparisons are valid and invalid.
- **`## Limitations`** — at least one concrete situation where it misleads, described so a
  reader recognises it in their own results.
- **`## Results`** — one `###` subsection per kind of test. Each opens with links to the
  degradation bundles it reports, then its generated block, then your reading of those
  numbers — about this metric only. What the run was is in the generated run summary; what
  a degradation does is in its bundle, one link away. Leave the reading empty until
  measurements exist. There are no word counts anywhere: say what is needed and stop.

## 6. Measurements

```bash
python -m fmeval.cards evidence <name> --results results/<run>
```

Point it at the canonical run (see `configs/cards/default.yaml` for which datasets
qualify — it refuses smoke-test data). This fills `## Performance`, the run summary, the
per-test tables and `_generated/fingerprint.json`. Only after this, write the Results
readings. Any number you type into prose must be one the fingerprint supports; prefer
citing the generated table over restating values.

## 7. Finish

```bash
python -m fmeval.cards check <name>
pytest
python -m fmeval.cards catalog          # the committed catalog must match the bundles
```

Do not sign the card and do not touch `status`. Report what you added, every `TODO(cite)`,
and anything the checker flagged that you could not resolve.
