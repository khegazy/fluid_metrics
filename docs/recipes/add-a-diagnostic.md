# Adding a diagnostic

A diagnostic is one row of an exemplar panel: a way of looking at a field that makes a
degradation's mechanism visible. The existing rows are the field itself, the difference,
the radial spectrum, the spectral phase, the value distribution, a lineout, and the
autocorrelation. Add one when a degradation's effect is invisible in all of those — that
situation is the only reason to.

## 1. One function in `fmeval/cards/diagnostics.py`

```python
@diagnostic(name="structure_function", label="structure function")
def draw_structure_function(ax, data, ctx: RowContext) -> dict[str, float]:
    """One sentence on what this row reveals, and for which degradations."""
    ...
    return {"scaling_exponent": ...}
```

Registered by the same decorator pattern as everything else; no import list to update.
Three obligations, none optional:

- **Use the row's shared limits.** `ctx.limits` is computed once per row and passed to
  every column. Autoscaling your own panel is the one mistake that makes a strong
  degradation look identical to the original, silently.
- **Draw any field through `fmeval.report.style.show_field`** — it is the only place
  `imshow` may be called, and a lint test enforces that.
- **Return the numbers behind the picture.** An agent reading the site cannot open a PNG;
  what you return lands in `exemplars.json` beside it. A figure with no numeric
  counterpart is a bug.

If the row draws a signed quantity, declare `signed=True` so it gets a diverging map
centred on zero. If it needs special limits (log scales, fixed ranges), extend
`_row_limits` in `fmeval/cards/figures.py` with a case for your name.

## 2. Add it to the card vocabulary

Add the name to the exemplars diagnostics vocabulary in `fmeval/cards/schema.py`, so cards
can declare it and a typo in a card fails validation instead of silently drawing nothing.

## 3. Use and verify it

Declare it in some degradation's `exemplars.diagnostics`, regenerate that panel, and look
at it:

```bash
python -m fmeval.cards exemplars <degradation>
```

The test is whether the mechanism is visible in your row when it is invisible in the field
row. If it is not, the diagnostic does not earn its place. Add a unit test in
`tests/test_cards.py` asserting the returned statistics on a field you construct — the
statistics are the contract, the pixels are not.

## 4. Finish

```bash
pytest
```

Report which degradation's panel now shows something it could not before; that sentence is
the justification for the diagnostic existing.
