# Only one trajectory is published on the web

**Priority:** medium — the documented inner loop does not work without a CFS mount.

## Evidence

Measured 2026-08-27 against `https://portal.nersc.gov/project/m4790/Data`:

```
/Data/                                     -> kinet/ only
/Data/kinet/.../sys_Re-5e4_Ma-1en1/        -> D2Q9_shape-256-256_T-10000_H-dc804f.h5 only

HEAD .../D2Q9_shape-256-256_T-10000_H-dc804f.h5              200, 178271350284 bytes
HEAD .../D2Q9_shape-256-256_T-100_H-04a8a1.h5                404
HEAD .../D2Q9_shape-256-256_T-10000_H-dc804f_well-format.h5  404
```

The published file's `Content-Length` matches `os.path.getsize` of the CFS copy exactly, and
the two are bitwise identical through the reader — `pytest -m web` asserts that.

## Why it matters

The HTTP fallback added in `fmeval/data/locate.py` covers `kinet_re5e4` and nothing else. So
a colleague without CFS can run the production trajectory but **cannot run either of the
other two dataset configs**, and in particular cannot run the one the documentation tells
them to start with:

* `README.md` — "Use `kinet_re5e4_dev` only for smoke tests"
* `AGENTS.md` §2 and `evaluate.py`'s module docstring — `dataset=kinet_re5e4_dev`
* `docs/recipes/verify-a-refactor.md` — pins the phrase `dataset=kinet_re5e4_dev`

The production file works for a smoke test over HTTP (two frames cost about 3 MiB each and
a `degradation=quick` run takes a few seconds), so this is friction rather than a blocker.

## What would fix it

Copy `D2Q9_shape-256-256_T-100_H-04a8a1.h5` (1.7 GB) into the published tree. No code
change is needed — the URL is derived from the path, so the dataset config already points
at the right place. `well_re5e4` (14.6 GiB) would additionally give the `web` suite a
second layout to check, since the Well reader's remote path is currently only covered by
the loopback fixture.

## Related, and cheaper

The kinet writer records `discretization.temporal` as `{"grid": 10000, "resolution": 1.0,
"length": 10000.0}` — in *lattice-step* units, so it gives the number of frames but not the
physical timestep (2.2552744890219753e-4 here). Because of that, `fmeval/data/_timeaxis.py`
has to recover the step by reading two elements of the `time` dataset and then verify the
reconstruction against samples. Writing the physical `dt` (or the total physical time) into
that attribute at solve time would make a trajectory's clock exact and free to read, and
would remove the only place in this package that reconstructs data rather than reading it.
