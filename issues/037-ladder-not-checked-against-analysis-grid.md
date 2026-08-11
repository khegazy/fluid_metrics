# The ladder is never checked against the analysis grid, so a size knob aborts the run

**Category:** technical debt
**Priority:** medium
**Status:** fixed 2026-08-11 (`create_harness`)
**Test:** `tests/test_robustness.py::test_the_default_ladder_runs_at_every_analysis_resolution[8]`
(now passing)

## The problem in one sentence

`analysis_grid.resolution` is one of the two documented size knobs, and turning it down far
enough kills the run partway through the first frame with an error that names the operator but
not the knob.

## Evidence

```bash
python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev \
    dataset.time.reduction=50 analysis_grid.resolution=8
```

```
File "degradations/resolution.py", line 50, in coarsen
    return _upsample(block_average(x, factor), factor, x.shape[1:])
File "fmeval/remap.py", line 66, in block_average
    raise ValueError(f"factor {factor} does not divide grid {tuple(spatial)}")
ValueError: factor 16 does not divide grid (8, 8)
```

The shipped ladder coarsens by up to 16; the analysis grid is 8 cells across. Still reproduces
after the issue-030 calibration work, which does not touch `coarsen` — its severity is a
factor and stays absolute by design, correctly.

Two things make it worth fixing rather than documenting:

1. **The message points at the wrong thing.** Nothing in it mentions `analysis_grid.resolution`,
   which is the setting that caused it, and `coarsen: {severities: [2, 4, 8, 16]}` looks entirely
   reasonable in the config it came from.
2. **It fires inside the frame loop.** The ladder and the analysis grid are both fully known
   before the first frame is read, but the failure arrives after the first read. On the
   production trajectory at a low reduction that is a long wait for an error that was decidable
   at startup.

`analysis_grid.resolution=32` (with `coarsen` skipped) runs to completion, so the boundary is not
obvious from the outside either.

## What is *not* part of this issue

The related "a rung the grid cannot express becomes a silent no-op" problem **is already
handled** by the `severity_degenerate` machinery added for issue 030. Verified: on a 16-cell
axis, `translate_x` at severity 16 records `value = 0.0` and `energy_changed = 0.0`, is flagged,
is logged as *"level(s) [5] resolve to a severity at which the operator leaves the field
unchanged, and are excluded from the acceptance statistics"*, and is dropped by `summarise_axes`
so the axis reports `n_levels = 4`. That detector is measurement-based rather than
operator-declared, which is why it generalises to an uncalibrated operator like `translate`;
`tests/test_robustness.py::test_a_no_op_rung_is_flagged_and_excluded_on_an_absolute_severity_axis`
pins that generality so it is not lost in a future refactor.

So the remaining gap is only the hard crash, not the silent tie.

## What is needed

A pre-flight check between `build_ladder` and the frame loop: for each rung whose severity is an
absolute cell count or factor (`coarsen`, `subsample`, `translate`, `box_blur`, `median_blur`),
verify it is expressible on the analysis grid, and fail once at startup naming the rung, the
severity, the analysis resolution and the knob that set it.

Whether an out-of-range rung should be an error or a skipped-and-logged rung is a judgement call.
An error is probably right for `coarsen`, where the request is impossible; the no-op detector
above already handles the cases that merely degenerate.

## Acceptance criteria

`evaluate.py ... analysis_grid.resolution=8` either completes or fails before the first frame is
read, with a message naming `analysis_grid.resolution` and the offending ladder entry.

## What was done

`pipeline.run` now runs each rung once against an already-remapped probe frame before the frame
loop starts, and **drops the rungs that cannot run on the analysis grid**, with a warning naming
the operator, its severity, the grid, and the `analysis_grid.resolution` knob to change. The run
then proceeds on the rest: an unsupported rung is one missing experiment, not a reason to discard
the others. If nothing survives, that raises with the knob named.

A trial application rather than a per-operator declaration of what it supports, so it needs no
cooperation from operators and stays correct as they are added. It costs one extra application of
each rung per run, against a ladder cost measured in tens of seconds.

## Related

`fmeval/remap.py::block_average`; `degradations/resolution.py::coarsen`;
`fmeval/pipeline.py::run`; `evaluate.py`; issue 030 (the calibration work whose
`severity_degenerate` detector covers the other half of this).
