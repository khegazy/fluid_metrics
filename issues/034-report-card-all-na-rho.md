# `report_card` raises when every ordinal axis has an undefined rank correlation

**Category:** technical debt
**Priority:** medium
**Status:** fixed 2026-08-11 (`create_harness`)
**Test:** `tests/test_robustness.py::test_report_card_survives_an_all_nan_rank_correlation`
(now passing)

## The problem in one sentence

`report_card` calls `groupby(...)["rho"].idxmin()` without guarding the all-NA case, so a metric
that is exactly constant on every ordinal axis takes down the whole report with a pandas error
that names nothing in this codebase.

## Evidence

```python
ValueError: Encountered all NA values
```

from

```python
worst = ordinal.loc[
    ordinal.groupby(keys, observed=True)["rho"].idxmin().dropna()
][[*keys, "degradation"]]
```

in `fmeval/analysis.py::report_card`. The `.dropna()` is applied to the *result* of `idxmin()`,
which is too late — `idxmin` raises before it returns.

Reproduced with a six-frame result frame in which a single-field invariant is exactly constant
across a translation-only ladder; the test in `tests/test_robustness.py` builds it in
milliseconds. `spearmanr` returns `NaN` for every frame of every ordinal axis, so `rho` is `NaN`
throughout and `idxmin` has nothing to minimise.

### Why this is worth fixing rather than documenting

The failure is **fatal, not cosmetic, and it is paid for twice**. `build_context` computes the
card before any renderer runs, so this is not one lost figure — it is the whole report. And it
happens after the evaluation, so on a long trajectory the I/O and the metric time are already
spent when it fires.

Three reachable configurations produce it:

- a single-field invariant (`enstrophy`, `kinetic_energy`) against a ladder of operators that all
  preserve it — translation preserves both exactly;
- any future degradation declaring a restricted `fields=(...)`, where `apply_rung` returns the
  source unchanged for the other fields, making every pairwise metric exactly 0 on that axis;
- `degradation.only=[...]` narrowing a run to axes a given metric happens to be blind to, which
  is a normal thing to do while iterating.

The near miss is instructive: `evaluate.py metrics=[enstrophy] ... 'degradation.only=[translate_x,uncorrelated]'`
does *not* crash today, because `np.roll` perturbs the pairwise-summation order and leaves a
round-off spread that `spearmanr` happily ranks. The report survives on an accident of floating
point — and reports `rho = 0.707` for its trouble, which is issue 033.

## What is needed

Guard the reduction. `idxmin(skipna=True)` still raises on an all-NA group in pandas 3, so the
group must be filtered — drop groups whose `rho` is entirely NA before taking the argmin, and
leave `worst_axis` empty for them. `rho_min` and `rho_median` already come through the `agg` path
as `NaN` without complaint, so the rest of the row is well defined.

## Acceptance criteria

A result frame in which every ordinal axis has `rho = NaN` produces a one-row card with
`rho_min = NaN` and an empty `worst_axis`, and `make_report.py` completes on it.

## What was done

Two `idxmin` calls in `report_card` were reached with an all-NA `rho`: the one building
`worst_axis` and a second inside the aggregate whose result was dropped a few lines later anyway.
The aggregate entry is gone and the `worst_axis` lookup now runs on the rows where `rho` is
defined, leaving `worst_axis` as NA when none is.

Two more all-NA reductions surfaced downstream once a run got that far, both on the same
configuration: `damage_max` over an all-NaN damage column, and the `reliability` section prose,
which took `idxmax`/`idxmin` over `rho` to name the best and worst axis. The prose now states that
the correlation is undefined on every axis and why that is correct for an invariant, rather than
raising. Verified end to end on a real `metrics=[enstrophy]` run with a translation-only ladder:
`ok 8 · skipped 8`, no errors, and the PDF compiles.

## Related

`fmeval/analysis.py::report_card`; `fmeval/report/driver.py::build_context`; issue 033;
issue 039, which is the same "a documented-correct metric breaks the report" pattern one layer up.
