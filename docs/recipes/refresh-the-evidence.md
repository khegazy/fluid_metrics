# Refreshing the evidence

Every measured number in every card traces to one pinned evaluation run. Replacing that
run — after adding a metric or degradation, changing the ladder, or adding a dataset — is
routine, but the order matters and one step is easy to miss.

## 1. Produce the run

On a machine with the data:

```bash
python evaluate.py 'metrics=[mae,mse,rmse,nrmse,enstrophy,kinetic_energy]' \
    dataset=kinet_re5e4 dataset.time.start=2000 dataset.time.reduction=50
```

Use the window from `configs/cards/default.yaml`, adding any newly implemented metrics to
the list. Note the `results/comparison_<stamp>` folder it writes.

## 2. Regenerate in dependency order

```bash
python -m fmeval.cards exemplars --all                              # if operators or the
                                                                    # canonical frame changed
python -m fmeval.cards evidence --all --results results/comparison_<stamp>
python -m fmeval.cards catalog
```

Exemplars before evidence, because metric evidence may reference degradation panels;
catalog last, because it reads the fingerprints. The committed catalog is diffed in CI, so
forgetting the last step fails the build rather than shipping a stale index.

## 3. The step that is easy to miss: the prose

Generated blocks update themselves. **Numbers that an author typed into sentences do
not.** The Results readings in each card cite specific values — ratios, correlations,
damages — from the previous run, and nothing mechanical reconciles them yet
(`issues/032` proposes the check; until it exists this is a manual obligation).

For every metric card, compare each number in the hand-written Results text against the
regenerated tables beside it, and correct the sentence or flag it. This has bitten before:
the first cards carried impostor damages of 0.80/0.51 from a 15-frame run, and the
canonical run measured 0.90/0.66/1.23. If you are an agent, list every prose number you
changed in your report — that list is exactly what a reviewer needs to re-verify.

## 4. Signatures invalidate themselves — tell the humans

Editing prose changes the card's hash, so any signed card you corrected becomes unsigned,
which is correct: the signature attested to text that no longer exists. Regenerating
blocks alone does **not** invalidate a signature (generated content is stripped before
hashing) — so a card whose tables changed but whose prose still describes the old run
keeps its signature while being wrong. That is the gap in `issues/032`; until it closes,
name every signed card whose tables materially changed in your report, so its owner can
reread and re-sign.

## 5. Finish

```bash
python -m fmeval.cards check --all
pytest
```

Commit the run folder reference, the regenerated `_generated/` content, the catalog, and
the prose corrections together, so the repository never holds a mixture of two runs.
