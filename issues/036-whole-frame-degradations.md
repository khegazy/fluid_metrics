# `whole_frame=True` is documented in two places and implemented in none

**Category:** technical debt
**Priority:** medium
**Status:** fixed 2026-08-11 (`create_harness`)
**Test:** `tests/test_robustness.py::test_whole_frame_degradation_receives_the_field_dict`
(now passing)

## The problem in one sentence

`DegradationSpec.whole_frame` is declared, defaulted, documented in `degradations/registry.py`
and promised in AGENTS.md section 4, and `fmeval/ladder.py::apply_rung` never reads it.

## Evidence

AGENTS.md, "Adding a degradation":

> **Operators act on one field, `(C, *spatial) -> (C, *spatial)`.** … If you genuinely need
> cross-field access, declare `whole_frame=True`.

`degradations/registry.py`, module docstring and the `degradation` docstring, say the same:
"Receive the whole `dict[str, ndarray]` instead of one array."

`apply_rung` in full contains no occurrence of the string `whole_frame`. It always calls

```python
result = np.asarray(spec.fn(source, rung.severity, **kwargs), dtype=np.float64)
```

with `source = frame.fields[name]`, one field at a time. Registering an operator with
`whole_frame=True` and asserting on its argument type gives:

```
AssertionError: declared whole_frame=True but received ndarray
```

No shipped operator declares it, so nothing is broken today.

## Why it is worth more than a docstring deletion

The operators that most need cross-field access are the physically interesting ones, and three
are already written down as planned work:

- **issue 024, Leray projection** — solenoidal/dilatational splitting needs all velocity
  components together, and `degradations/spectral.py` already notes that its filters break the
  divergence constraint and that fixing it "is therefore left to issues/024";
- **issue 015, rotation** — must rotate the velocity *components*, not merely resample the grid;
  the geometric module's docstring says forgetting this "produces a plausible-looking field that
  is physically wrong";
- **issue 016, mass-weighted remap** — density-weighted operations need density beside velocity.

Each would be written against the documented contract, receive an array where it expected a
mapping, and fail with a numpy message pointing at the operator rather than at the declaration
that was ignored. In the rotation case in particular a silent wrong answer is plausible: an
operator that indexes `x[0]` and `x[1]` expecting two fields gets two *channels* instead, which
on a velocity field has exactly the right shape.

## What is needed

Either implement it in `apply_rung` — branch on `spec.whole_frame`, pass
`{name: frame.fields[name] for name in fields}`, and validate that the returned mapping has the
same keys and shapes — or remove the parameter from the registry and both docstrings and say in
AGENTS.md that cross-field operators are not supported yet.

Implementing is the better option given the three planned operators, but either is honest and the
present state is not. If it is implemented, the degradation contract test needs a case for it,
since `test_preserves_shape_and_dtype` and friends all call `spec.fn` with a bare array and would
have to dispatch on the declaration too.

## Acceptance criteria

An operator declaring `whole_frame=True` receives a `dict[str, ndarray]` from `apply_rung` and
its return value is validated key-by-key; or the parameter no longer exists anywhere.

## What was done

`apply_rung` reads `whole_frame` and dispatches to `_apply_whole_frame`, which calls the operator
once with the field mapping and a context describing the frame rather than any single field, then
validates what comes back: a mapping, containing every field it was given, each of unchanged shape.
The per-field bookkeeping — the resolved severity, the no-op check, the realised energy effect — is
computed afterwards exactly as for a per-field operator, so a whole-frame operator gets the same
degeneracy detection as everything else.

One combination is refused rather than guessed at: a whole-frame operator that also declares a
`calibration` gets one call for all fields while a calibrated severity resolves *per* field, so
there is no single severity to pass. That raises with an explanation instead of silently applying
one field's severity to another.

Still no shipped operator declares it. The point was to make the declaration true before the
operators that need it arrive — a Leray projection (issue 024), a rotation that must rotate
velocity components (issue 015), a density-weighted remap (issue 016).

## Related

`fmeval/ladder.py::apply_rung`; `degradations/registry.py`; AGENTS.md section 4;
issues 015, 016, 024.
