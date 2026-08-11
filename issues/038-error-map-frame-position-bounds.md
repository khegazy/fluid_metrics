# An out-of-range `error_map.frames` position fails as a raw numpy IndexError

**Category:** technical debt
**Priority:** low
**Status:** fixed 2026-08-11 (`create_harness`)
**Test:** `tests/test_robustness.py::test_a_map_frame_position_outside_the_selection_is_reported_clearly`
(now passing)

## The problem in one sentence

`report.error_map.frames` holds positions *within the selected frames*, so what is valid depends
on `dataset.time.reduction` and the trajectory length, and exceeding it raises a numpy error that
names neither setting.

## Evidence

`fmeval/pipeline.py::run`:

```python
keep_frames = {indices[i] for i in maps.frames} if maps.enabled and maps.frames else set()
```

With a four-frame selection and `frames: [0, 7]`:

```
IndexError: index 7 is out of bounds for axis 0 with size 4
```

Raised before any frame is read, which is the one good thing about it. The message names
"axis 0" and a size that appears in no config file; the two settings that produced it —
`report.error_map.frames` and `dataset.time.reduction` — are not mentioned.

The shipped default is `frames: [-1]`, which is always valid, so this is only reachable once
someone edits it. But the coupling is genuinely non-obvious: raising `dataset.time.reduction` to
iterate faster shrinks the selection, and a `frames` list written against the previous reduction
silently becomes invalid. That is a normal thing to do while iterating on a report.

## What is needed

Bounds-check `maps.frames` against `len(indices)` and raise a `ValueError` naming
`report.error_map.frames`, the offending position, the number of selected frames, and the
reduction that produced it. Negative positions must keep working — `-1` is the documented and
default idiom for "the last selected frame".

One line, and it turns a numpy traceback into a sentence.

## Acceptance criteria

`MapRequest(enabled=True, frames=[0, 7])` against a four-frame selection raises a `ValueError`
whose message contains `error_map.frames`; `frames=[-1]` and `frames=[0, -1]` continue to work.

## What was done

`pipeline._map_frames` bounds-checks each position and raises a `ValueError` naming
`report.error_map.frames`, the size of the selection, the settings that determine it
(`dataset.time.reduction`, `start`/`stop`, `max_frames`) and the valid range. Negative positions
still count from the end, since `-1` is the shipped default.

## Related

`fmeval/pipeline.py::run`, `MapRequest`; `configs/report/default.yaml`.
