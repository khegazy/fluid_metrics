# A rank correlation computed from float64 round-off is reported as a measurement

**Category:** method
**Priority:** medium
**Status:** fixed 2026-08-11 (`create_harness`)
**Test:** `tests/test_robustness.py::test_rank_correlation_is_withheld_when_the_variation_is_round_off`
(now passing)

## The problem in one sentence

`summarise_axes` computes and reports `rho` for any axis with two or more levels, with no check
that the values it is ranking differ by more than floating-point noise.

## Evidence

Reproduced with the real command:

```bash
python evaluate.py metrics=[enstrophy] dataset=kinet_re5e4_dev \
    dataset.time.reduction=20 'degradation.only=[translate_x,uncorrelated]'
```

Enstrophy is `0.5 <|ω|²>` and `translate` is `np.roll`, so the rung values are mathematically
identical. They are not *bitwise* identical, because rolling the array changes the summation
order inside `np.mean`, which uses pairwise summation. Measured per-frame relative spread across
the five rungs:

| frame | 1 | 21 | 41 | 61 | 81 |
|---|---|---|---|---|---|
| `(max − min)/│mean│` | 0.0 | 1.62e-16 | 1.62e-16 | 0.0 | 1.62e-16 |

The run folder's `report_card.csv` then reads:

```
metric,field,n_axes,rho_min,worst_axis,...,flags
enstrophy,vorticity,1,0.7071067811865475,translate_x,...,spearman=0.71 < 0.9; ...
```

`rho = 0.707` on the axis named as the metric's *worst*. It is entirely round-off. The same
number is printed in the `monotonicity_heatmap` cell, formatted to two decimals and coloured on
the same `RdBu_r` scale as the genuine correlations beside it, with nothing to distinguish it.

## Why the existing guards do not cover it

Two things already exist and neither reaches `rho`:

- `normalisation`'s `degenerate` flag did fire on this run, so the *damage* column is `NaN` and
  the card carries `no dynamic range`. That flag is about the clean-to-anchor span; it does not
  gate `rho`, which is what the heatmap and the `spearman` threshold both read.
- Issue 030's `severity_degenerate` catches a rung the operator left *unchanged*. Here the
  operator did change the array — it rolled it — so no rung is a no-op. The whole ladder is
  meaningful; it is the *metric* that cannot see it.

The two mechanisms are per-rung and per-span respectively. What is missing is a per-axis check on
the metric's response.

## What is needed

Withhold `rho` (report `NaN`) when the values being ranked span less than a few ulp of their own
magnitude. `scipy.stats.spearmanr` already returns `NaN` for an exactly constant input and
`ConstantInputWarning` is raised — the case here is the *nearly* constant one, which is
indistinguishable in meaning and distinguishable in arithmetic.

A threshold of order `1e-12 × median(|value|)` on the per-frame range would separate this from
any real response by many orders of magnitude; the smallest genuine per-frame spread measured
anywhere in the current suite is the sub-pixel translation ladder at ~1e-3 relative.

Note this is *not* the same as declaring enstrophy broken. AGENTS.md is explicit that a
single-field metric legitimately has no dynamic range against this ladder and that the resulting
report is correct rather than a bug. The defect is that a number which means "no response" is
rendered as a number that means "a moderate monotone response".

## Acceptance criteria

An axis whose per-frame values differ only at the ulp level reports `rho = NaN`, and the
monotonicity heatmap leaves that cell blank rather than printing a value. A genuinely weak but
real response — the 0.125-cell sub-pixel rung, say — is unaffected.

## What was done

`summarise_axes` now withholds `rho` when the values being ranked differ by less than
`DEGENERATE_SPAN = 1e-9` of their own largest magnitude, per frame and pooled, via
`analysis._is_round_off`. The enstrophy-against-translation run that used to report
`rho_min = 0.707` on `translate_x` now reports NaN and the report card flags `no dynamic range`.

The same guard was applied to `_threshold_level`, which had the same defect in a third statistic:
any target built from a round-off span is cleared by round-off, so both the sensitivity and
saturation levels read `1.0` — "fires at rung 1" — for a quantity translation cannot change at all.
They are now NaN.

`separability_auc_min` is deliberately **not** withheld. Its answer over round-off is ~0.5, which
is the correct statement that adjacent rungs cannot be separated, so it is more informative than
NaN.

## Related

`fmeval/analysis.py::summarise_axes`, `_per_frame_rho`; issue 032 (the same round-off reaching
the damage column through a different route); `fmeval/report/plots.py::monotonicity_heatmap`.
