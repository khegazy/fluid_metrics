# Adding a metric

The result of this recipe is one directory under `metrics/` containing everything the
repository will ever hold about the metric: the implementation, tests that pin its worked
example, a machine-readable record, a written description aimed at three different kinds
of reader, and — once an evaluation run exists — the metric's measured behaviour. Follow
the steps in order; several of the later ones consume the output of earlier ones.

## 1. Scaffold

```bash
python -m fmeval.cards new <name>
python -m fmeval.cards check <name>     # run at any point; it names what is missing and the fix
```

`<name>` is lowercase with underscores, a valid Python identifier, and exactly what users
will type in `metrics=[<name>]`. That name is the metric's only identity — there are no
separate ID codes. `python -m fmeval.cards list` shows which names are taken. Never create
the files by hand.

## 2. Implement — `metric.py`

One function decorated with `@metric`, returning **one `float`** for each combination of
physical field, snapshot in time, and strength of damage. The evaluation loop handles the
looping over all three; your metric sees two arrays and returns a number.

- Set every decorator argument honestly: `arity` (how many fields the metric is handed),
  `fields`, `units`, `higher_is_better`, `differentiable`, `cost`, `symmetric` and
  `reduction`. The evaluation machinery reads these and the published catalog repeats them.
  Nothing in the written description restates them, so the decorator is the only place this
  information lives.
- Cite the source paper **and equation number** in the docstring for anything taken from
  the literature.
- Declare a keyword-only parameter named `ctx` if you need the grid, the reference field's
  fluctuation RMS, or a random number generator. Use the one `ctx` gives you; never create
  your own seed.
- Reuse code from another directory by importing it, the way `rmse` imports `mse`. The
  decorator returns the function unwrapped, so shared mathematics cannot drift apart into
  two disagreeing copies. Do not copy an equation from another directory.
- If your metric's total can be written as a sum over cells, add a companion function
  decorated with `@pointwise_map(of="<name>")` returning the contribution of each cell, and
  declare the `reduction` that turns that map back into the single number. The map is what
  lets a report show *where* in the domain a model went wrong.

## 3. Test — `test_metric.py`

At least one test whose expected value you computed **by hand**, on a field small enough
to check by eye — four cells by four cells is ideal. This test is the source of the worked
example in the written description, which is what stops the prose drifting away from the
code. Also test each behaviour the description will claim: a scaling law, an invariance,
an asymmetry. The properties every metric must have — returning zero on identical fields,
symmetry, and the per-cell map averaging back to the single value — are already tested
centrally, so do not repeat them here.

Run the smoke test before writing any prose:

```bash
python evaluate.py metrics=[<name>] dataset=kinet_re5e4_dev degradation=quick
```

## 4. The typed record — `card.yaml`

Every field is documented in `fmeval/cards/schema.py`; read that file rather than copying
another metric's record blindly. Choose `category` from the fixed list of allowed values.
Leave `status: candidate` and `review: null` — moving a metric past `candidate` is a
person's decision. The `math` block holds only what the decorator cannot declare:
`triangle_inequality`, `scale_dependent`, `resolution_dependent` and `complexity`.

## 5. The prose — `card.md`

Six things you write yourself, in a fixed order, with generated blocks between them. The
order runs from what the metric *is* to what the metric *did on our data*: Definition,
Performance (generated for you), Intuition, Reading the output, Limitations, Results and
References.

- **`## Definition`** — numbered display equations, the discretisation, and a required
  `### Boundary handling` subsection; `None.` plus one clause is the right answer for a
  metric that works one cell at a time. Say what the equation does not already say, and
  nothing that it does. Write
  maths as `$...$` inline and `$$...$$` with `\tag{1}` for display, and nothing else —
  `\begin{equation}`, `\label` and `\eqref` render on the site but show as raw source on
  GitHub, and the checker refuses them.
- **`## Intuition`** — no mathematical notation at all. Written for an early graduate
  student in any STEM field: direct, with no laboured analogies. Four things belong here:
  what the metric measures and which way of being wrong the metric reveals; how the metric
  works; the worked example with the numbers taken from `test_metric.py`; and one sentence
  naming what the metric ignores. Write about the metric itself, not about its standing in
  this project.
- **`## Reading the output`** — range and units, direction, what makes a value good and on
  what that depends, and which comparisons are valid and invalid.
- **`## Limitations`** — at least one concrete situation where the metric gives a
  misleading answer, described so that a reader will recognise that situation in their own
  results.
- **`## Results`** — one `###` subsection per kind of test. Each subsection opens with
  links to the degradations it reports, then its generated block of numbers, then your
  reading of those numbers — about this metric alone. What the evaluation run was is in the
  generated run summary; what a degradation does is on that degradation's own page, one
  link away. Leave the reading empty until measurements exist. There are no word counts
  anywhere: say what is needed and stop.

## 6. Measurements

```bash
python -m fmeval.cards evidence <name> --results results/<run>
```

Point that command at the reference evaluation run; `configs/cards/default.yaml` lists
which datasets qualify, and the command refuses smoke-test data. It fills in
`## Performance`, the run summary, the per-test tables and `_generated/fingerprint.json`.
Only after that should you write the Results readings. Any number you type into a sentence
must be one the fingerprint file supports, and pointing at the generated table beats
restating its values.

## 7. Finish

```bash
python -m fmeval.cards check <name>
pytest
python -m fmeval.cards catalog          # the committed catalog must match the bundles
```

Do not sign the description and do not touch `status`. Report what you added, every
`TODO(cite)` marker you left, and anything the checker flagged that you could not resolve.
