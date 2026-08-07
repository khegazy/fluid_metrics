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
| [002](002-shocklet-dataset.md) | No shocklet-populated compressible turbulence | **high** |
| [003](003-ensemble-data.md) | CRPS and spread-to-skill need ensembles | low |
| [004](004-independent-realizations.md) | Only one seed per configuration | medium |
| [005](005-3d-and-cost-extrapolation.md) | All data is two-dimensional | low |

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
| [030](030-axis-severity-calibration.md) | Severity ranges should follow each field's spectrum | **high** |
| [031](031-saturation-never-reached.md) | No ladder rung reaches the unrelated-field level | medium |

## Technical debt

| ID | Title | Priority |
|---|---|---|
| [020](020-import-name-collision.md) | `metrics` is a very generic top-level import name | low |
| [021](021-tracker-ids-for-baselines.md) | `NM-0` for the L^p baselines is invented | **decide early** |
| [022](022-sim-config-parsing.md) | Solver configs carry executable YAML tags | low |
| [023](023-vendored-kinet-drift.md) | Vendored kinet code is pinned and may drift | low |
