# Compare metrics across a Reynolds ladder

**Category:** deferred functionality
**Priority:** medium
**Status:** open

## Context

The eventual question is whether a metric's behaviour holds as physical complexity rises.
A metric that is monotone at Re = 5e4 and scrambles at Re = 1e5 is not trustworthy for a
foundation model.

The ladder exists: `datasets/kinet/doubly_periodic/old/` holds five runs at Re = 5e4, 6.25e4,
7.5e4, 8.75e4 and 1e5, all at Ma = 0.1 with identical initial conditions
(`I-8e1_eps-5en2_R0-1`), so Reynolds number is the only varying parameter.

The groundwork is in place: every result row carries `dataset_family`, `complexity_rank` and
the physical parameters; `configs/dataset_family/reynolds_ladder_2d.yaml` declares the ordered
set; `fmeval/io.py:load_runs()` concatenates several run folders; and report section 12 is
reserved and activates itself when two or more datasets of one family appear.

Native resolutions differ across the five runs (mostly 512^2), which is why the analysis grid
must be pinned for any comparison. That is the reason the IN-2 remap was built first.

## What is needed

Dataset configs for the four remaining members, and a renderer for section 12 plotting
rho, the Gaussian-field damage and the sensitivity rung against `complexity_rank`.

## Acceptance criteria

A multirun over the family produces one comparison folder whose section 12 renders, and
absolute values are not compared across rungs -- only normalised damage and rank statistics.

## Related

`configs/dataset_family/reynolds_ladder_2d.yaml`; section 12 in `fmeval/report/registry.py`.
