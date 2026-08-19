# Refreshing the evidence

Every measured number on every page traces back to one pinned evaluation run. Replacing
that run — after adding a metric or a degradation, changing which strengths are applied,
or adding a dataset — is routine work, but the order of the steps matters and one step is
easy to miss.

## 1. Produce the run

On a machine with the data:

```bash
python evaluate.py 'metrics=[mae,mse,rmse,nrmse,enstrophy,kinetic_energy]' \
    dataset=kinet_re5e4 dataset.time.start=2000 dataset.time.reduction=50
```

Use the time window recorded in `configs/cards/default.yaml`, adding any newly implemented
metrics to the list. Note the name of the `results/comparison_<stamp>` folder the run
writes.

## 2. Regenerate in dependency order

```bash
python -m fmeval.cards exemplars --all                              # if operators or the
                                                                    # canonical frame changed
python -m fmeval.cards evidence --all --results results/comparison_<stamp>
python -m fmeval.cards catalog
```

Example panels come before measurements, because a metric's measurements may reference a
degradation's panel. The catalog comes last, because it reads the fingerprint files the
other two steps write. The committed catalog is compared against a freshly built one in
CI, so forgetting that last step fails the build rather than shipping a stale index.

## 3. The step that is easy to miss: the prose

Generated blocks update themselves. **Numbers that an author typed into sentences do
not.** The Results readings on each page cite specific values — ratios, correlations,
damage scores — from the previous run, and nothing mechanical reconciles them yet.
`issues/032` proposes that check; until it exists, reconciling them is a manual
obligation.

For every metric, compare each number in the hand-written Results text against the
regenerated tables beside it, and either correct the sentence or flag it. This has caused
real trouble before: the first pages carried damage scores of 0.80 and 0.51 for the fake
prediction, taken from a 15-snapshot run, while the reference run measured 0.90, 0.66 and
1.23. If you are an agent, list every number you changed in your report — that list is
exactly what a reviewer needs in order to re-check the work.

## 4. Signatures invalidate themselves — tell the humans

Editing prose changes the page's hash, so any signed page you corrected becomes unsigned.
That is correct behaviour: the signature attested to text that no longer exists.
Regenerating the blocks alone does **not** invalidate a signature, because generated
content is stripped out before hashing — which means a page whose tables changed but whose
prose still describes the old run keeps its signature while being wrong. That is the gap
`issues/032` describes. Until it closes, name in your report every signed page whose
tables materially changed, so that its owner can reread and re-sign.

## 5. Finish

```bash
python -m fmeval.cards check --all
pytest
```

Commit the reference to the new run folder, the regenerated `_generated/` content, the
catalog and the prose corrections together, so that the repository never holds a mixture
of numbers from two different runs.