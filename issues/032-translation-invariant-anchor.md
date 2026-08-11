# The D = 1 anchor is empty for a translation-invariant metric, and nothing notices

**Category:** method
**Priority:** high
**Status:** fixed 2026-08-11 (`create_harness`)
**Test:** `tests/test_robustness.py::test_damage_is_not_reported_against_an_anchor_the_metric_cannot_see`
and `::test_degeneracy_guard_fires_when_most_rungs_are_round_off` (both now passing)

## The problem in one sentence

The `uncorrelated` anchor that defines `D = 1` is built by *translating* the reference, so it is
identically zero for any metric invariant to translation — which is most of the position-tolerant
family this project exists to develop — and the resulting damage column is a ratio of two
round-off numbers reported as a measurement.

## Evidence

Measured through the real pipeline on the production trajectory (`kinet_re5e4`, t = 5000–6000,
reduction 250, vorticity), with a radially averaged energy-spectrum metric of the BD-1 shape
added temporarily. Raw values, median over frames:

| rung | `mse` | `h_minus_one` (NM-2) | `spectrum_l1` (BD-1) |
|---|---|---|---|
| reference | 0 | 0 | 0 |
| gaussian_blur σ=1 | 1.12e-7 | 3.85e-4 | 9.79e-2 |
| gaussian_blur σ=4 | 1.32e-6 | 2.49e-3 | 3.52e-1 |
| translate_x = 4 | 3.33e-6 | 6.75e-3 | **1.30e-16** |
| gaussian_impostor | 1.21e-5 | 7.82e-2 | **1.77e-16** |
| **uncorrelated (the D = 1 anchor)** | 1.43e-5 | 9.73e-2 | **1.51e-16** |

The spectrum metric behaves exactly as documented: it sees the blur and is blind to translation
and to the impostor, because both preserve `|F(f)|`. That is correct behaviour and it is what
IN-4 is designed to expose.

What the harness then reports is not correct:

```
metric        gaussian_impostor_damage   uncorrelated_damage   anchor_source
spectrum_l1              1.167                   1.0            uncorrelated
```

`normalisation` produced `value_uncorrelated = 1.51e-16`, `span = 1.51e-16`, and
`degenerate = False`. Damage 1.17 reads as "the impostor is worse than two unrelated fields".
The truth is that the metric cannot separate any of them and every number in that row is a ratio
of float64 round-off.

Read by the rule AGENTS.md gives for the canary column — "a metric that scores it near the
reference is phase-blind" — a colleague concludes the spectral metric *passes* IN-4. That is the
exact inversion the canary exists to prevent, and it lands on the one metric class the canary was
written for.

### Why the existing guard did not fire

`normalisation` already has a degeneracy guard:

```python
scale = float(np.nanmedian(np.abs(g["value"]))) or 1.0
degenerate = not np.isfinite(span) or abs(span) < 1e-12 * scale
```

The scale is the **median** of `|value|` over every row of the group. For this metric eight of
the eleven rung-types are round-off (three translations, the impostor, four anchor draws, the
reference), so the median is itself ≈ 1.3e-16 and the test becomes
`1.5e-16 < 1e-12 × 1.3e-16 = 1.3e-28`, which is false. The guard compares round-off against
round-off, and is defeated in precisely the case it exists for.

Using `max(|value|)` instead of the median fires correctly here: `1e-12 × 0.352 = 3.5e-13`, and
`1.5e-16` is comfortably below it. That is a one-line change and it is worth making on its own,
but it does not address the first defect below.

## Two distinct defects

1. **The anchor construction is not valid for every metric.** `random_large_translation`
   preserves every statistic *and* every quantity computed from `|F(f)|` alone. Its docstring
   already carries one caveat (a single-mode field), but not this one, which is far more likely
   to bite: OT-5 increment PDFs, PS-4 flatness, BD-1 spectra, BD-2 two-point correlations and any
   translation-invariant TDA summary all have an identically empty anchor. Nothing in the
   pipeline checks that the anchor operator actually moves the metric it is anchoring.

2. **The degeneracy guard's scale is the wrong reference** (above).

## What is needed

- Compare the anchor against the metric's own genuine dynamic range, not against a median that
  the degenerate rungs themselves drag down. `max(|value|)` over the group is the obvious
  candidate.
- When the anchor is indistinguishable from clean, `damage` must be `NaN` and `anchor_source`
  must say so rather than reading `uncorrelated` as if it had been measured. The
  `no dynamic range` flag already exists; it simply is not reached here.
- Longer term, the anchor needs a construction that is not a symmetry of the field for
  translation-invariant metrics. An independent realisation of the same physics is the right
  object and the data does not currently provide one — see issue 004, which this raises the
  priority of.

## Acceptance criteria

A metric that is invariant to the anchor operator is reported with `degenerate = True`, a `NaN`
damage column and a `no dynamic range` flag, on a run that also contains a metric with a healthy
anchor. The `spectrum_l1` probe in `tests/test_robustness.py` reproduces the situation in
milliseconds without touching CFS.

## What was done

`normalisation` now takes its degeneracy scale from the **largest** value in the group rather than
the median. The median is defeated in exactly the case the guard exists for: a metric invariant to
the operator the anchor is built from returns round-off on the anchor, on the impostor and on every
translation rung, so more than half the rows are round-off and the median collapses with them. The
threshold is `DEGENERATE_SPAN = 1e-9` relative, documented in `fmeval/analysis.py` — well above
accumulated round-off on a 256^2 reduction and well below the 1e-4 of range that the mildest rung
doing real work moves the value by.

Damage was already NaN'd for a degenerate span by `add_damage`, so fixing the guard fixed the
reported probe damage with it: the spectral metric that used to report `gaussian_impostor_damage =
1.167` against a 1.5e-16 anchor now reports NaN, and the report card carries the existing
`no dynamic range` flag instead. Both `xfail` markers are removed and the tests pass.

**What this does not do.** It reports the absence of an anchor rather than supplying one. A
translation-invariant metric still has no measured `D = 1` scale, so its damage column is empty and
its IN-4 verdict has to be read from the raw values. Building an anchor such a metric *can* see —
an independent realisation at the same parameters, or a phase-randomised field with the same
spectrum for the metrics that are not spectral — needs data this repository does not have, and is
issue 004.

## Related

`fmeval/analysis.py::normalisation`, `_uncorrelated_anchor`;
`degradations/geometric.py::random_large_translation`; issue 004 (independent realisations);
issue 033 (the same round-off reaching `rho`);
`tests/test_capabilities.py::test_the_impostor_is_scored_perfectly_by_a_spectrum_only_metric`,
which confirms the canary construction itself is sound — the fault is in the normalisation it is
read through.
