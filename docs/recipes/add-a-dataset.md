# Adding a dataset

A dataset enters this repository in two distinct capacities, and the second one is easy to
forget. First the dataset must be **readable**: a configuration file and, if the file
format is new, a reader. Then the dataset must become **citable evidence**: registered
with the card system, given a window of time over which the flow is properly developed,
evaluated, and calibrated. A dataset that is readable but not registered can be
experimented on freely, but no metric's page may cite it. That is the correct state for
scratch data and the wrong one for a physical regime the pages ought to cover.

## 1. Make it readable

Add `configs/dataset/<name>.yaml`, following an existing one: `format`, `path` (under
`${paths.data}`), `fields` from the canonical vocabulary, `time` selection, and the
`complexity` block naming its family and parameters.

If the file layout is new, add a reader in `fmeval/data/` implementing the `Trajectory`
contract in `fmeval/data/base.py`, and register it with `@register_reader`. Readers are a
deliberately closed set with explicit imports in `evaluate.py` — unlike metrics and
degradations, there is no discovery walk. Three rules are not negotiable: channel-first
arrays with trailing `(x, y, z)`; the fixed field vocabulary, tagged primitive or derived;
never slice the time axis. Test against the shared reader contract in
`tests/test_loader_contract.py` with a small synthetic file in `tests/fixtures_h5.py` that
reproduces the real format's quirks, and keep every fixture non-square.

If the data carries fields outside the canonical vocabulary — a magnetic field, say —
extend `FIELDS` in `fmeval/data/base.py` first, tagged primitive or derived. Derived
fields need a recompute rule in `fmeval/derived.py`, because they are recomputed on the
analysis grid, never block-averaged.

## 2. Check the calibration

The smoothing and spectral severities are resolved per field against a spectrum measured
from the data, so a new dataset changes what every calibrated severity means there. Run
the smoke evaluation and read the calibration table it writes:

```bash
python evaluate.py metrics=[mse] dataset=<name> degradation=quick
```

Look at `data/calibration.csv` in the results folder. The characteristic length scale of
each field should have resolved to a real number rather than NaN, the spread of those
scales should be small, and the configured list of strengths should produce genuinely
distinct experiments. A strength that collapses onto a milder one, or onto an operation
that does nothing at all, is flagged `severity_degenerate`. If a whole degradation
collapses on the new data, its list of strengths needs a range suited to that dataset —
and that is a finding worth recording rather than routing around.

## 3. Decide the developed-flow window

A metric's page may only cite physically meaningful data. Decide from the physics where
along the trajectory the flow has become properly developed — for the kinet run that was
`start=2000` — and how densely to sample that window (`reduction`). Record both the
decision and the reasoning as comments in the dataset's YAML file. This is a person's
decision to make; if you are an agent, propose a window with your reasoning and stop
there.

## 4. Register it as citable evidence

Edit `configs/cards/default.yaml`:

- add the dataset to `evidence_datasets` — until then, `fmeval.cards evidence` refuses
  runs on it by name;
- record its window under `evidence_window`;
- decide whether the **one fixed snapshot every example panel is drawn from** stays where
  it is. All the panels share a single snapshot so that the gallery can be compared
  side by side. Adding a second physical regime does not move that snapshot unless the
  panels should now illustrate the new regime, which is a person's decision.

## 5. Produce the evidence

On a machine with the data:

```bash
python evaluate.py 'metrics=[<all implemented>]' dataset=<name> \
    dataset.time.start=<start> dataset.time.reduction=<n>
python -m fmeval.cards evidence --all --results results/comparison_<stamp>
python -m fmeval.cards catalog
```

Each fingerprint file records which dataset it came from, so measurements from different
datasets accumulate rather than overwrite one another in principle. Note the current
limitation, though: a page displays **one** run's numbers, so regenerating against the new
dataset replaces the tables that were shown before. If you want two regimes shown side by
side, that is an extension to `evidence.py` to propose — never a reason to hand-edit
anything.

## 6. Finish

```bash
pytest                      # includes the reader contract and card checks
pytest -m data              # on a machine with the data mounted
```

Report the time window you chose and why, any strengths that collapsed on the new data,
and any physical field the fixed vocabulary did not already have.