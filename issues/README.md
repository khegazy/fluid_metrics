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
| [030](030-axis-severity-calibration.md) | Severity ranges should follow each field's spectrum — **fixed**; severities on the smoothing and spectral axes are now relative and resolved per field against a measured spectrum | fixed |
| [031](031-saturation-never-reached.md) | No ladder rung reaches the unrelated-field level | medium |
| [032](032-translation-invariant-anchor.md) | The `D = 1` anchor is empty for a translation-invariant metric — **fixed**; the degeneracy guard now scales against the largest response, so damage is withheld rather than reported from round-off | fixed |
| [033](033-rank-correlation-over-round-off.md) | A rank correlation computed from float64 round-off is reported as a measurement — **fixed**; `rho` and the threshold levels are withheld below a relative 1e-9 | fixed |
| [035](035-higher-is-better-is-never-read.md) | `higher_is_better` is declared on every metric and consumed by no analysis — **fixed**; the four one-sided statistics are oriented by the metric's own direction | fixed |

## Technical debt

| ID | Title | Priority |
|---|---|---|
| [020](020-import-name-collision.md) | `metrics` is a very generic top-level import name | low |
| [022](022-sim-config-parsing.md) | Solver configs carry executable YAML tags | low |
| [023](023-vendored-kinet-drift.md) | Vendored kinet code is pinned and may drift | low |
| [034](034-report-card-all-na-rho.md) | `report_card` raises when every ordinal axis has an undefined `rho` — **fixed**, along with two more all-NA reductions downstream of it | fixed |
| [036](036-whole-frame-degradations.md) | `whole_frame=True` is documented in two places and implemented in none — **fixed**; `apply_rung` dispatches on it and validates what comes back | fixed |
| [037](037-ladder-not-checked-against-analysis-grid.md) | The ladder is never checked against the analysis grid, so a size knob aborts the run — **fixed**; a pre-flight drops rungs that cannot run there, naming the knob | fixed |
| [038](038-error-map-frame-position-bounds.md) | An out-of-range `error_map.frames` position fails as a raw numpy `IndexError` — **fixed** | fixed |
| [039](039-displacement-figure-crashes-on-a-degenerate-metric.md) | `displacement_response` errors on a metric the documentation calls correct — **fixed**; it declares the skip with `ctx.require` | fixed |

Issues 032–039 were found by running the harness against inputs the existing tests do not
reach: a metric invariant to the operator the `D = 1` anchor is built from, a metric that improves
as damage rises, an analysis grid the configured ladder does not fit on. Each carries a test in
`tests/test_robustness.py` and all of them now pass; the `xfail(strict=True)` markers that recorded
them have been removed as each was fixed, which is what strict mode is for. **Follow the same
pattern for a new defect**: reproduce it, write the test, mark it `xfail(strict=True)` naming the
issue file, and let strict mode send whoever fixes it back here. Do not delete a marker without
fixing the issue it names.

## Resolved

| ID | Title | Outcome |
|---|---|---|
| [021](021-tracker-ids-for-baselines.md) | Identifier for the L^p baselines | `NM-0` accepted 2026-08-07. One follow-up: add it to the master table in the metrics tracker |
