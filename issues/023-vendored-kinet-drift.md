# Vendored kinet code is pinned and may drift

**Category:** technical debt
**Priority:** low
**Status:** open

## Context

`fmeval/external/kinet_spectral.py` is a byte-for-byte copy of kinet's spectral
diagnostics, pinned at commit `454141e`, carrying its CC-BY-4.0 attribution. It is vendored
rather than imported because `import kinet` pulls in `mpi4py`, which cannot load libmpi on a
login node; the diagnostics themselves need only numpy.

Two consequences. The copy will drift if kinet's version changes, and nothing detects that.
And the attribution obligation is real -- kinet's `pyproject.toml` declares CC-BY-4.0.

Also worth recording: several other functions in the same kinet module are directly useful and
have not been vendored, so they should be taken from there rather than rewritten --
`divergence`, `strain_rate_tensor`, `palinstrophy_from_vorticity`, `shell_energy_spectrum`
and `shell_enstrophy_spectrum`, which cover PH-4, PH-5 and BD-1 almost directly.

Conversely there is **no** Helmholtz or Leray projection anywhere in kinet, so that one has to
be written from scratch -- see issue 024.

## What is needed

A check that compares the vendored copy against the source when both are available, or a
recorded decision to re-sync manually at stated intervals.

## Acceptance criteria

Either an automated drift check exists, or the pin and the re-sync procedure are recorded
where the next person will find them.

## Related

`fmeval/external/kinet_spectral.py`; issue 024.
