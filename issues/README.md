# Open items

One file per item, so future work is written down where a colleague will find it rather than
living in a plan document or in someone's memory. Each file states the evidence, not just the
intent: six months from now "we need a lower-Reynolds reference" is useless without the
measurement that showed why.

Write an issue while the evidence is in front of you. One written from memory later is worth
much less.

## Data generation required

These block criteria that are designed and implemented but cannot be exercised.

| ID | Title | Priority |
|---|---|---|
| [001](001-low-reynolds-reference.md) | The protocol specifies Re ~ 500; no such dataset exists | medium |
| [002](002-shocklet-dataset.md) | No shocklet-populated compressible turbulence | accepted, scheduled |
| [003](003-ensemble-data.md) | CRPS and spread-to-skill need ensembles — estimators built and validated on a synthetic ensemble; physical data is [004](004-independent-realizations.md) | resolved for the estimators |
| [004](004-independent-realizations.md) | Only one seed per configuration | medium |
| [005](005-3d-and-cost-extrapolation.md) | All data is two-dimensional | low |
| [034](034-the-well-format-copy-is-not-published.md) | The Well-format copy is not published, so that reader's HTTP path is only covered by a fixture | low |

## Deferred functionality

Designed, hooks in place, not built.

| ID | Title | Priority |
|---|---|---|
| [010](010-forecast-pair-reader.md) | Read the real prediction/target pairs | **high** |
| [011](011-cross-dataset-comparison.md) | Compare metrics across a Reynolds ladder | medium |
| [012](012-vector-valued-metrics.md) | Metrics returning spectra or PDFs | medium |
| [013](013-remaining-intuition-figures.md) | Outlier, invariance, triangle-inequality figures | low |
| [014](014-gradient-signal-criterion.md) | Gradient quality where L2 goes flat | medium |
| [015](015-rotation-degradation.md) | Rotation, which must rotate vector components | low |
| [016](016-mass-weighted-remap.md) | Momentum-conserving remap option | low |
| [024](024-leray-projection.md) | Solenoidal projection for the spectral operators | low |

## Method and calibration

| ID | Title | Priority |
|---|---|---|
| [031](031-saturation-never-reached.md) | No ladder severity level reaches the unrelated-field level | medium |

## Technical debt

| ID | Title | Priority |
|---|---|---|
| [020](020-import-name-collision.md) | `metrics` is a very generic top-level import name | low |
| [032](032-prose-numbers-can-go-stale.md) | Numbers written into card prose can go stale unnoticed | medium |
| [033](033-link-rewriting-is-only-checked-for-deadness.md) | Site link rewriting is checked for dead links, not correct destinations | medium |
| [022](022-sim-config-parsing.md) | Solver configs carry executable YAML tags | low |
| [023](023-vendored-kinet-drift.md) | Vendored kinet code is pinned and may drift | low |

**When a defect is fixed, delete its file.** This folder holds what is *open*; the write-up,
its measurements and the fix all stay together in the commit that closed it, which is where they
are useful. `git log --diff-filter=D --stat -- issues/` lists what has been closed and points at
those commits.

**The pattern for a new defect**: reproduce it, write the test, mark it `xfail(strict=True)`
naming the issue file, and write the issue with the measurement in front of you. Strict mode is
what makes the loop close — fixing the defect makes the test pass, strict mode turns an
unexpected pass into a failure, and whoever fixed it is sent back to remove the marker and the
issue. Do not delete a marker without fixing the issue it names.

## Resolved

| ID | Title | Outcome |
|---|---|---|
| [021](021-tracker-ids-for-baselines.md) | Identifier for the L^p baselines | `NM-0` accepted 2026-08-07. One follow-up: add it to the master table in the metrics tracker |
