# `metrics` is a very generic top-level import name

**Category:** technical debt
**Priority:** low
**Status:** open

## Context

Packaging resolved the original problem: with `pyproject.toml` and an editable install the
packages import from any directory, verified from `/tmp`.

What remains is that `metrics` is an extremely generic top-level import name. Any environment
that later grows another distribution providing a `metrics` package will collide, and the
failure mode -- one of them silently shadowing the other -- is confusing to diagnose.

The folder layout was requested and is good; this is only about the import name.

## What is needed

Either accept the risk, or rename the import package while keeping the requested folder
structure, for example by moving the packages under a `src/fluid_metrics/` layout with
`metrics` as a subpackage. The second is a mechanical change to import lines.

## Acceptance criteria

Either a note here recording the decision to accept it, or the rename completed with the
folder layout preserved.

## Related

`pyproject.toml`; `metrics/__init__.py`.
