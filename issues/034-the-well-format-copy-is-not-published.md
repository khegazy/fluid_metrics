# The Well-format copy is not published for HTTP access

**Priority:** low — one reader's remote path is covered only by a synthetic fixture.

## State as of 2026-08-28

Both kinet trajectories are now published, so the documented inner loop works without a
CFS mount:

```
HEAD .../D2Q9_shape-256-256_T-10000_H-dc804f.h5              200, 178271350284 bytes
HEAD .../D2Q9_shape-256-256_T-100_H-04a8a1.h5                200,   1794662470 bytes
HEAD .../D2Q9_shape-256-256_T-10000_H-dc804f_well-format.h5  404
```

`python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev degradation=quick` on a machine
with no `datasets` symlink completes in 19 s over 323 range requests and 262 MiB.

## What is still open

`well_re5e4` (14.6 GiB) is not published, so `WellTrajectory`'s remote path is exercised
only against the loopback server in `tests/test_remote_data.py` and never against a real
Well file served over HTTP. The two formats differ in exactly the way that matters here:
kinet stores its clock chunked one element per chunk, the Well layout stores it
contiguously, so they take opposite branches in `fmeval/data/_timeaxis.py`. The synthetic
fixture reproduces that difference deliberately, but a fixture agreeing with itself is
weaker evidence than the real file.

Publishing it needs no code change — the URL is derived from the path, so the existing
dataset config already points at the right place. The copy goes to
`/global/cfs/cdirs/m4790/www/Data/<same subpath>` with mode 644.

## `synthetic_ensemble` needs no publishing, and that is not an oversight

Checked 2026-08-28, because "publish the probabilistic dataset too" is a reasonable thing
to ask and the answer is not obvious from the dataset list. There is nothing to publish:
`fmeval/data/synthetic_ensemble.py` *computes* its frames rather than reading them, from a
fixed seed, so two instances return bitwise-identical fields and member stacks. Its config
says as much — `path: ${paths.data}` is declared only because every dataset config carries
one, and `evaluate.py` skips the existence check for the format.

It therefore already runs on any machine, with no CFS mount and no network. Materialising
it would mean a file to keep in step with the generator and a new registered reader format
for a stored ensemble, which none of the current readers handle, in exchange for bytes a
colleague already obtains identically by running it. The ensemble data that *is* worth
having is a set of real flow realizations —
[003](003-ensemble-data.md) and [004](004-independent-realizations.md).

## Related, and cheaper than any of this

The kinet writer records `discretization.temporal` as `{"grid": 10000, "resolution": 1.0,
"length": 10000.0}` — in *lattice-step* units, so it gives the number of frames but not the
physical timestep (2.2552744890219753e-4 here). Because of that,
`fmeval/data/_timeaxis.py` has to recover the step by reading two elements of the `time`
dataset and then verify the reconstruction against samples. Writing the physical `dt` (or
the total physical time) into that attribute at solve time would make a trajectory's clock
exact and free to read, and would remove the only place in this package that reconstructs
data rather than reading it.
