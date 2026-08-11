# `displacement_response` errors on a metric the documentation calls correct

**Category:** technical debt
**Priority:** low
**Status:** fixed 2026-08-11 (`create_harness`)
**Test:** `tests/test_robustness.py::test_the_displacement_figure_declines_rather_than_crashes_without_damage`
(now passing)

## The problem in one sentence

`displacement_response` sets a log-scaled x axis before checking that it has any finite data to
plot, so a metric with no dynamic range — which AGENTS.md explicitly says is correct rather than
a bug — produces a renderer error instead of a declared skip.

## Evidence

```bash
python evaluate.py metrics=[enstrophy] dataset=kinet_re5e4_dev \
    dataset.time.reduction=20 'degradation.only=[translate_x,translate_subpixel,uncorrelated]'
python make_report.py results/enstrophy_<stamp>
```

```
ERROR fmeval.report.driver: renderer displacement_response failed
  ...
ValueError: Data cannot be log-scaled because all values are <= 0
INFO make_report: enstrophy_<stamp>: error 1 · ok 9 · skipped 6
```

Still reproduces after the issue-030 work (`error 1 · ok 9 · skipped 6` on the current `main`).

The metric is degenerate — the anchor is a translation and enstrophy is translation-invariant, so
`span = 0` and the whole `damage` column is `NaN`. The renderer plots nothing, `ax.set_xscale("log")`
has already been called, and matplotlib finds no positive data when it comes to draw.

## Why this is a real complaint and not a cosmetic one

AGENTS.md section 3 is explicit:

> A single-field metric will be reported as `no dynamic range` with `rho = -1`, and **that is
> correct, not a bug you should try to fix**.

So this is a documented-correct configuration that produces an error line in the manifest. The
driver catches it and the run survives, which is the design working — but AGENTS.md section 6 is
equally explicit that this is the wrong mechanism:

> **Declare unavailability rather than crashing.** … For data-dependent cases call
> `ctx.require(cond, msg)`. Anything else that raises is caught, recorded in the manifest and
> non-fatal — a bad figure must never destroy an expensive evaluation.

`ctx.require` exists precisely for this and the renderer already uses it once, for
`"no translation axis in the ladder"`. The damage column being empty is the same kind of
condition and is not checked.

Two other renderers guard the same situation correctly, which is why the count reads
`skipped 6` — so this is one renderer out of step rather than a systemic gap.

## What is needed

In `displacement_response`, after collecting `points`, add

```python
ctx.require(np.isfinite(damage_values).any(), "no finite damage; the metric has no dynamic range")
```

before the axes are configured. Setting the scale only once there is something to draw would also
work and is arguably tidier.

While there: `_use_log` exists for exactly this decision on the y axis of `ladder_curves` and is
not used for this figure's x axis. Whether the displacement axis should be unconditionally log is
a separate question — with severities `[0.125 … 16]` it is a reasonable default — but it should
be applied after the data is known to be plottable.

## Acceptance criteria

`make_report.py` on a run folder whose only metric is degenerate reports `error 0`, with
`displacement_response` listed as skipped and a reason naming the missing damage.

## What was done

`displacement_response` declares unavailability with `ctx.require` *before* setting the log scale,
so a metric with no finite damage produces a declared skip with a reason rather than a matplotlib
error inside the renderer. Verified on the real `metrics=[enstrophy]` run folder from the evidence:
`ok 8 · skipped 8` with no errors, where it previously reported `error 1`.

## Related

`fmeval/report/plots.py::displacement_response`, `_use_log`; `fmeval/report/driver.py::render`;
AGENTS.md sections 3 and 6; issue 034 (the same "documented-correct metric breaks the report"
pattern, one layer up and fatal there).
