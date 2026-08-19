# Adding a degradation

A degradation stands in for a way a surrogate fails. Which failures the ladder probes
determines what every metric's measurements *mean*, so this is as consequential as adding a
metric. The result is one directory under `degradations/` holding the operator, its card,
and its exemplar panel.

## 1. Scaffold

```bash
python -m fmeval.cards new <name> --kind degradation
```

## 2. Implement — `degradation.py`

One `@degradation`-decorated function `fn(field, severity, *, ctx, **options) -> ndarray`,
same shape out as in.

- **Declare the severity honestly**: `severity_name`, `severity_units`,
  `severity_direction` (declare `decreasing` if a smaller number is a stronger
  degradation — a contract test measures this claim), and `calibration` if the severity is
  a fraction of the field's scale (`"scale"`) or of its spectral energy (`"energy_above"` /
  `"energy_below"`). A wrong calibration side silently inverts the axis.
- Set `ordinal=False` if the levels carry no order (a canary), and `stochastic=True` if it
  draws randomness — always from `ctx.rng`, never your own seed.
- Respect the doubly periodic domain: wrap, don't pad.
- Shared helpers go in `degradations/_shared/`, which discovery skips.

## 3. Register it on the ladder

Add an entry to `configs/degradation/default.yaml`, keyed by a **label** (the same operator
can appear under several labels with different options). Choose severities that are
distinct experiments on *both* fields — the calibration machinery flags levels that
collapse onto each other or onto a no-op, and flagged levels are excluded, not free.

## 4. If this is a new family

The Results section of every metric card has one subsection per family. A new family must
be added to `FAMILY_BLOCKS` in `fmeval/cards/evidence.py` and `FAMILY_HEADINGS` in
`fmeval/cards/prose.py`, and each metric card needs the new `###` subsection with its
generated block. Without this, the new axis is measured and its numbers appear in **no
metric card** — they land in the fingerprint and nothing renders them. This is the one
sanctioned exception to "never edit another bundle": adding the empty subsection to each
metric card, and nothing else in it.

## 5. The card

`card.yaml` as for a metric, plus the **`exemplars`** block: three severities — weak,
medium, strong, taken from your ladder entry — and the diagnostics that expose the
mechanism. A blur is legible in `radial_spectrum`; a translation is not, because it moves
spectral phase, not amplitude — use `spectral_phase` or `difference`; noise shows in `pdf`.
For an operator with no ordered severity use `mode: draws`; only identity uses `none`. The
`rationale` becomes the figure caption.

`card.md` differs from a metric's: `## Severity scale` replaces Reading the output and must
say whether the severity is absolute or calibrated per field and what each level of the
ladder corresponds to; `## Exemplars` replaces Results, and its hand-written part —
what changes between the weak and strong columns, and which diagnostic row makes it
visible — is what turns the figure into an explanation. The worked example in
`## Intuition` must be computed by running the operator, not written from expectation:
several existing examples came out differently than their author expected, and those
corrections are the most informative sentences in their cards.

## 6. Generate the panel

```bash
python -m fmeval.cards exemplars <name>
```

Drawn from the one canonical frame every figure shares (`configs/cards/default.yaml`).
Never draw or edit these figures by hand. If a metric card links to your axis, regenerate
that metric's evidence after yours.

## 7. Finish

```bash
python -m fmeval.cards check <name>
pytest
python -m fmeval.cards catalog
```

Report additions, `TODO(cite)` markers, and anything unresolved.
