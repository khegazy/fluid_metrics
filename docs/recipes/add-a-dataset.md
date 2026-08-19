# Adding a dataset

A dataset enters this repository in two distinct capacities, and the second is the one
easy to forget. First it must be **readable**: a config and, if the format is new, a
reader. Then it must become **citable evidence**: registered with the card system, given a
developed-flow window, evaluated, and calibrated. A dataset that is readable but not
registered can be experimented on but no card may cite it, which is the correct state for
scratch data and the wrong one for a regime the cards should cover.

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

Look at `data/calibration.csv` in the run folder: the characteristic scales should be
resolved (not NaN), the scale spread should be small, and the configured severity lists
should produce distinct levels — collapsed or no-op levels are flagged
`severity_degenerate`. If a whole axis degenerates on the new data, its severity list
needs a dataset-appropriate range, and that is a finding worth recording, not routing
around.

## 3. Decide the developed-flow window

Cards may only cite physically meaningful data. Decide from the physics where the
trajectory is developed — for the kinet run that was `start=2000` — and how densely to
sample it (`reduction`). Record the decision and the reasoning in the dataset YAML as
comments. This is a human decision; if you are an agent, propose a window with your
reasoning and stop.

## 4. Register it as citable evidence

Edit `configs/cards/default.yaml`:

- add the dataset to `evidence_datasets` — until then, `fmeval.cards evidence` refuses
  runs on it by name;
- record its window under `evidence_window`;
- decide whether the **canonical exemplar frame** stays where it is. All exemplar panels
  share one frame so the gallery is comparable; a second regime does not change that frame
  unless the panels should now illustrate the new regime, which is a human decision.

## 5. Produce the evidence

On a machine with the data:

```bash
python evaluate.py 'metrics=[<all implemented>]' dataset=<name> \
    dataset.time.start=<start> dataset.time.reduction=<n>
python -m fmeval.cards evidence --all --results results/comparison_<stamp>
python -m fmeval.cards catalog
```

Fingerprints record their dataset, so per-dataset evidence accumulates rather than
overwrites conceptually — but note the current limitation: a card renders **one** run's
numbers, so regenerating against the new dataset replaces the displayed tables. If the
intent is side-by-side regimes, that is an extension to `evidence.py` to propose, not a
reason to hand-edit anything.

## 6. Finish

```bash
pytest                      # includes the reader contract and card checks
pytest -m data              # on a machine with the data mounted
```

Report: the window chosen and why, any degenerate severity levels on the new data, and any
field the canonical vocabulary lacked.
