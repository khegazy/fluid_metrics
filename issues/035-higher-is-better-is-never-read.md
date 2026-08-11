# `higher_is_better` is declared on every metric and consumed by no analysis

**Category:** method
**Priority:** high
**Status:** fixed 2026-08-11 (`create_harness`)
**Test:** `tests/test_robustness.py::test_a_similarity_metric_is_scored_in_its_own_direction`
(now passing)

## The problem in one sentence

Three of the ordering statistics in `fmeval/analysis.py` hardcode "damage makes the value rise",
so a metric where larger is better arrives in the report card flagged on three criteria at once
while being perfectly well behaved.

## Evidence

`grep -rn higher_is_better` over the repository finds it declared in `MetricSpec`, set on all six
registered metrics, and read in exactly two places — both of them in
`tests/test_metric_contract.py`. Nothing in `fmeval/analysis.py` imports it.

The three statistics that assume a direction:

| statistic | the assumption |
|---|---|
| `_monotone_fraction` | `np.all(np.diff(values) > 0)` |
| `_min_adjacent_auc` | `mannwhitneyu(xb, xa, alternative="greater")` |
| `_threshold_level` | first level with `median >= clean + fraction * span` |

Measured on an eight-frame synthetic axis falling perfectly from 1.0 to 0.2 — the shape of any
correlation, SSIM or skill-score metric, and of PS-2/PS-3 when ensembles arrive:

| statistic | reported | correct reading |
|---|---|---|
| `rho` | −1.0 | perfectly ordered |
| `monotone_fraction` | 0.0 | 1.0 — monotone on every frame |
| `separability_auc_min` | 0.0 | 1.0 — adjacent rungs perfectly separable |
| `saturation_level` | 1.0 | meaningless; the comparison runs the wrong way |

With the shipped thresholds (`spearman: 0.90`, `separability_auc: 0.80`) that row is flagged on
both, and the third number is silently wrong rather than flagged. A colleague reading the card
sees a metric failing every criterion.

## Why it matters now rather than later

No registered metric is `higher_is_better=True` today, so nothing is currently mis-reported. But
the first-wave list in CLAUDE.md is full of candidates that will be, or that at least are not
monotone-increasing in damage: PS-2/PS-3 (skill scores), any correlation- or coherence-based
BD-2 quantity, and any normalised similarity built on top of OT-1. The declaration exists, the
contract test already checks that the metric's *own* direction is consistent
(`test_monotone_on_synthetic_blur_ladder` expects `rho = -1` when `higher_is_better`), and then
the analysis layer ignores it. That is the worst arrangement: the metadata is present and looks
authoritative.

`rho = -1` itself is arguably fine to leave as-is — it is a true statement about the correlation,
and AGENTS.md already explains the `rho = -1` convention for single-field metrics. The three
statistics above are not: they report a *false* statement about monotonicity and separability.

## What is needed

Pass the metric's declared direction into `summarise_axes` and use it to orient the three
statistics. The sign is available from `metrics.registry.get(metric).higher_is_better`; the frame
already carries the metric name on every row, so no new column is required.

The threshold comparison in `flag` then needs to read `abs(rho_min)` or an oriented `rho`,
otherwise a correctly ordered `higher_is_better` metric is still flagged on the `spearman`
criterion. Deciding which of those two is right is a judgement call worth making explicitly
rather than by default — `abs` would also mask a genuinely anti-correlated `higher_is_better=False`
metric, which is a real failure and should stay visible.

## Acceptance criteria

A `higher_is_better=True` metric on a perfectly ordered descending ladder reports
`monotone_fraction = 1.0`, `separability_auc_min ≈ 1.0`, a sensible `sensitivity_level`, and no
flags. A `higher_is_better=False` metric is unaffected.

## What was done

`analysis.response_direction` resolves a `+1 / -1` sign per (dataset, metric, field), and
`summarise_axes` multiplies the value by it before computing the four one-sided statistics, so
"rises with damage" holds by construction and none of them needs a direction argument. **`rho = +1`
now means "responds correctly to damage" whichever convention the metric uses.** Reported values
stay in the metric's own units; the sign is recorded as `higher_is_better` on the axis table.

The direction comes from the metric's declaration, which is now carried on every result row as a
`higher_is_better` column — so re-rendering an old folder uses the same direction the run did,
rather than depending on what happens to be in the registry at render time. When a run does not
record it, the direction is instead *measured*: the `uncorrelated` anchor is as bad as a field can
look by construction, so an anchor below the clean value means larger is better. Measuring is the
fallback rather than the primary source precisely because that anchor is empty for a
translation-invariant metric, which is issue 032.

The synthetic falling axis from the evidence above now reports `monotone_fraction = 1.0` and
`separability_auc_min = 1.0` where it read 0.0 for both.

## Related

`fmeval/analysis.py::_monotone_fraction`, `_min_adjacent_auc`, `_threshold_level`, `flag`;
`metrics/registry.py::MetricSpec.higher_is_better`; CLAUDE.md, "First-wave priorities".
