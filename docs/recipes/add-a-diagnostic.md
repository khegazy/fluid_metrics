# Adding a new row to the example figures

Every degradation's page carries an **example panel**: one figure whose columns are the
same snapshot, undamaged and then damaged at increasing strengths, and whose rows are
different ways of looking at that same field. A **diagnostic** is one of those rows — a
way of looking at a field that makes some degradation's mechanism visible.

The rows that already exist are the field itself, the difference from the original, the
radial spectrum, the spectral phase, the distribution of values, a single line cut across
the domain, and the autocorrelation. Add a new row only when a degradation's effect is
invisible in every one of those. That situation is the only reason to add one.

## 1. One function in `fmeval/cards/diagnostics.py`

```python
@diagnostic(name="structure_function", label="structure function")
def draw_structure_function(ax, data, ctx: RowContext) -> dict[str, float]:
    """One sentence on what this row reveals, and for which degradations."""
    ...
    return {"scaling_exponent": ...}
```

Rows are registered by the same decorator pattern as everything else in this repository,
so there is no import list to update. Three obligations, none of them optional:

- **Use the row's shared colour limits.** `ctx.limits` is computed once for the whole row
  and passed to every column in it. Autoscaling your own panel is the one mistake that
  makes a heavily damaged field look identical to the original, and it does so silently.
- **Draw any field through `fmeval.report.style.show_field`**, which is the only place in
  the codebase where `imshow` may be called. A lint test enforces that.
- **Return the numbers behind the picture.** A program reading this site cannot open a PNG,
  so whatever you return is written into `exemplars.json` beside the figure. A row with no
  numeric counterpart is a bug.

If your row draws a quantity that can be positive or negative, declare `signed=True` so
that it gets a colour map centred on zero. If it needs special limits — a log scale, a
fixed range — extend `_row_limits` in `fmeval/cards/figures.py` with a case for your row's
name.

## 2. Add the name to the vocabulary

Add your row's name to the list of allowed diagnostics in `fmeval/cards/schema.py`, so
that a degradation can declare it and a typo in a degradation's configuration fails
validation instead of silently drawing nothing.

## 3. Use the row, and check that it earns its place

Declare your row in some degradation's `exemplars.diagnostics`, regenerate that panel, and
look at the result:

```bash
python -m fmeval.cards exemplars <degradation>
```

The test is whether the mechanism is visible in your row when it is invisible in the row
showing the field itself. If it is not, the row does not earn its place. Add a unit test
in `tests/test_cards.py` asserting the statistics your function returns for a field you
construct by hand — those statistics are the contract, and the pixels are not.

## 4. Finish

```bash
pytest
```

Report which degradation's panel now shows something it could not show before. That
sentence is the justification for the new row existing.