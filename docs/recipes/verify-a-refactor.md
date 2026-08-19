# Verifying that a refactor changed no numbers

Use this whenever you change code without meaning to change results: moving files,
splitting modules, renaming, performance work. The standard is exact: **any numerical
difference is a bug you introduced, not an improvement.** This procedure has caught real
breakage — a module split once silently lost three degradation axes, 630 rows, while every
test still passed and the registry still listed all 21 operators. The row comparison below
is what found it.

The dev dataset is the right one here. It is banned from card evidence because its physics
is meaningless, but identity checking does not need physics — it needs the same numbers
twice, and the dev run takes seconds.

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

The expected output is `IDENTICAL` with zero missing and zero new rows. Stochastic axes are
included in this standard: the random draws are seeded from (run seed, label, frame,
field), so they reproduce bitwise.

## 4. If it is not identical

- **Rows are missing** → a degradation axis did not run. This is the module-split failure
  mode: a private helper the operator needed was lost, or an import broke. Check
  `python -c "from degradations import registry; registry.discover(); print(registry._IMPORT_ERRORS)"` —
  it must print an empty dict. A code defect in an operator stops the run outright; if
  your run completed with rows missing, find out why before anything else.
- **Values differ** → your change altered what something computes. Do not accept it, do
  not adjust tolerances, do not rerun hoping it goes away. Either find and fix the
  unintended change, or — if you believe the new values are *correct* and the old ones
  were wrong — stop and report exactly that, with the differing rows. That decision
  belongs to a human.
- **Only `wall_time_s` differs** → fine. It is excluded by comparing only `value`.

## 5. Afterwards

Run `pytest` as well — the identity check and the test suite catch different things. State
in your report that you ran this procedure and what it showed; "2268 rows, identical" is
one line and it is the line a reviewer most wants to see.
