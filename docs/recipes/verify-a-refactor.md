# Verifying that a refactor changed no numbers

Use this procedure whenever you change code without meaning to change any results: moving
files, splitting modules, renaming things, performance work. The standard is exact: **any
numerical difference is a bug you introduced, not an improvement.** This procedure has
caught real breakage. Splitting one module once silently lost three whole degradations —
630 rows of results — while every test still passed and the registry still listed all 21
operators. The row-by-row comparison below is what found that.

The development dataset is the right one to use here. That dataset is banned from a page's
evidence because its physics is meaningless, but checking that two runs are identical does
not need physics — it needs the same numbers twice, and a development run takes seconds.

## 1. Before you change anything: capture the baseline

```bash
python evaluate.py 'metrics=[mae,mse,rmse,nrmse,enstrophy,kinetic_energy]' \
    dataset=kinet_re5e4_dev degradation=default dataset.time.max_frames=3
cp "$(ls -td results/comparison_* | head -1)/data/results.csv" /tmp/before.csv
python -m metrics > /tmp/metrics_before.txt
python -m degradations > /tmp/degradations_before.txt
```

If you have already made your change, stop. Stash it, capture the baseline, unstash.

## 2. Make your change

## 3. Re-run and compare

```bash
python evaluate.py 'metrics=[mae,mse,rmse,nrmse,enstrophy,kinetic_energy]' \
    dataset=kinet_re5e4_dev degradation=default dataset.time.max_frames=3
python -m metrics > /tmp/metrics_after.txt
python -m degradations > /tmp/degradations_after.txt
diff /tmp/metrics_before.txt /tmp/metrics_after.txt
diff /tmp/degradations_before.txt /tmp/degradations_after.txt
```

Both diffs must be empty. Then compare every value, keyed so that row order cannot hide
anything:

```python
import pandas as pd

before = pd.read_csv("/tmp/before.csv")
import glob
after = pd.read_csv(sorted(glob.glob("results/comparison_*/data/results.csv"))[-1])

keys = ["metric", "field", "degradation", "level", "frame_index", "variant_label"]
b = before.set_index(keys)["value"].sort_index()
a = after.set_index(keys)["value"].sort_index()

missing = b.index.difference(a.index)
extra = a.index.difference(b.index)
print(f"rows: before={len(b)} after={len(a)}")
print(f"missing from after: {len(missing)}", list(missing[:3]))
print(f"new in after: {len(extra)}", list(extra[:3]))

shared = b.index.intersection(a.index)
diff = (b.loc[shared] != a.loc[shared])
print("IDENTICAL" if not diff.any() and not len(missing) and not len(extra)
      else f"DIFFERS on {int(diff.sum())} shared rows")
```

The expected output is `IDENTICAL`, with zero missing rows and zero new ones. Degradations
that draw random numbers are held to this same standard: every draw is seeded from the run
seed, the label, the snapshot and the field together, so the draws reproduce bit for bit.

## 4. If it is not identical

- **Rows are missing** → one degradation did not run at all. This is the failure mode a
  module split produces: a private helper the operator needed was lost, or an import broke.
  Check
  `python -c "from degradations import registry; registry.discover(); print(registry._IMPORT_ERRORS)"` —
  it must print an empty dict. A code defect in an operator stops the run outright; if
  your run completed with rows missing, find out why before anything else.
- **Values differ** → your change altered what something computes. Do not accept the new
  values, do not adjust tolerances, and do not rerun hoping the difference goes away.
  Either find and fix the unintended change, or — if you believe the new values are
  *correct* and the old ones were wrong — stop and report exactly that, listing the rows
  that differ. That decision belongs to a person.
- **Only `wall_time_s` differs** → fine. Timing is excluded from the check above, which
  compares only the `value` column.

## 5. Afterwards

Run `pytest` as well — this identity check and the test suite catch different things.
State in your report that you ran this procedure and what it showed. "2268 rows,
identical" is one line, and it is the line a reviewer most wants to see.