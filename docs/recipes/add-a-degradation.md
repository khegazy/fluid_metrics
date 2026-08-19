# Adding a way of damaging a field

A **degradation** takes a trusted field and makes it wrong in a controlled way, standing
in for a way a machine-learning surrogate fails in practice. Which failures the collection
covers determines what every metric's measurements *mean*, so adding one is as
consequential as adding a metric. The result of this recipe is one directory under
`degradations/` holding the operator, its written description, and its example panel — the
figure showing the degradation applied to one fixed snapshot at several strengths.

## 1. Create the directory

```bash
python -m fmeval.cards new <name> --kind degradation
```

## 2. Implement — `degradation.py`

One function decorated with `@degradation`, with the signature `fn(field, severity, *,
ctx, **options) -> ndarray`, returning an array of the same shape it was given.

- **Declare the strength setting honestly.** `severity_name` says what the number means,
  `severity_units` gives its units, and `severity_direction` says which way the number runs
  — declare `decreasing` when a *smaller* number is a *stronger* degradation, and a contract
  test will measure that claim against your code. Declare `calibration` when the number is
  not absolute but a fraction of something the field itself determines: `"scale"` for a
  fraction of the length over which the field varies, or `"energy_above"` / `"energy_below"`
  for a fraction of the field's energy above or below a cutoff. Getting the calibration side
  wrong silently reverses the order of your strengths while leaving every number looking
  plausible.
- Set `ordinal=False` if your strengths carry no order at all, which makes this a trap test
  rather than a graded sequence. Set `stochastic=True` if the operator draws random numbers
  — always from `ctx.rng`, never from a seed of your own.
- The domain wraps around in both directions, so wrap rather than pad at the edges.
- Helpers shared between operators go in `degradations/_shared/`, which the discovery walk
  skips.

## 3. Register the strengths it will be run at

Add an entry to `configs/degradation/default.yaml`, keyed by a **label** rather than by
the operator's name, which is what lets one operator appear several times with different
options. Choose strengths that are genuinely distinct experiments on *both* physical
fields. The calibration machinery flags any strength that resolves onto a milder strength,
or onto an operation that does nothing at all, and a flagged strength is excluded from the
statistics rather than quietly counted.

## 4. If this is a new family

Every metric's Results section has one subsection per family of degradation. A new family
must be added to `FAMILY_BLOCKS` in `fmeval/cards/evidence.py` and to `FAMILY_HEADINGS` in
`fmeval/cards/prose.py`, and every metric's `card.md` needs the new `###` subsection with
its generated block. Without those, your new degradation is measured and its numbers
appear in **no metric's page at all** — they land in the fingerprint file and nothing
renders them. This is the one sanctioned exception to "never edit another bundle": add the
empty subsection to each metric's page, and change nothing else in those pages.

## 5. The description

`card.yaml` works as it does for a metric, plus the **`exemplars`** block, which
configures the example panel: three strengths — weak, medium and strong, taken from the
entry you added in step 3 — and the rows that will expose the mechanism. Choose those rows
to suit the operator. A blur is obvious in `radial_spectrum`. A translation is not,
because a translation moves where the energy is and not how much of it there is, so use
`spectral_phase` or `difference` instead. Noise shows up in `pdf`, the distribution of
values. For an operator whose strengths carry no order, use `mode: draws`; only `identity`
uses `none`. Whatever you write in `rationale` becomes the figure's caption.

`card.md` differs from a metric's in two sections. `## Severity scale` replaces Reading
the output, and must say whether the strength number is absolute or resolved separately
for each field, and what each configured strength corresponds to. `## What the degradation
looks like` replaces Results; its hand-written part — what changes between the weak and
the strong columns, and which row of the panel makes that change visible — is what turns a
figure into an explanation.

The worked example in `## Intuition` must be produced by actually running the operator,
not written down from expectation. Several of the existing examples came out differently
from what their author expected, and those corrections are the most informative sentences
on their pages.

## 6. Generate the panel

```bash
python -m fmeval.cards exemplars <name>
```

The panel is drawn from the one fixed snapshot that every figure in the repository shares
(`configs/cards/default.yaml`). Never draw or edit these figures by hand. If a metric's
page links to your new degradation, regenerate that metric's measurements after generating
your panel.

## 7. Finish

```bash
python -m fmeval.cards check <name>
pytest
python -m fmeval.cards catalog
```

Report what you added, every `TODO(cite)` marker you left, and anything you could not
resolve.