# Numbers written into card prose can go stale without anything noticing

**Category:** technical debt
**Priority:** medium
**Status:** open

## Context

A card holds two kinds of number, and only one of them is protected.

**Generated numbers** live in the marked blocks that `python -m fmeval.cards evidence`
writes. They come from one named run, the marker records which command produced them, and
regenerating rewrites them. They cannot silently describe a different experiment from the
one the card claims.

**Hand-carried numbers** are the ones an author types into a sentence, having taken them
from a run by hand. In `metrics/mse/card.md` the generated table reports a weakest
separation of 0.838 on `translate_subpixel`; the paragraph below it says the damage ratios
per doubling are 3.98, 3.94 and 3.75 and that MAE assigns 47 times the damage at an eighth
of a cell. Those three ratios and that factor are hand-carried. Nothing checks them.

This is not hypothetical. Before the canonical run existed, the same paragraphs cited
0.80 and 0.51 for impostor damage, 55x for the MAE/MSE ratio, and 0.995 for the MAE-MSE
correlation. Those came from a 15-frame run at a different time window, recorded in
`issues/021`. They sat in the card looking exactly as authoritative as the generated
tables and describing a different experiment. They were caught only because generating the
evidence happened to put the correct values directly beside them, and the corrected values
are 0.90/0.66/1.23, 47x and 0.987.

The failure mode is not an author being careless. It is that a sentence and a table look
equally trustworthy to a reader, while only one of them is maintained.

## Why the prose numbers are worth keeping

A table can report 0.987. Only a sentence can say that two metrics ordering damage alike
while weighting it 47 times differently makes them duplicates for ranking models and not
for training losses. The interpretation needs the number inside it, so the answer is not
to ban numbers from prose.

## What exists already, and what it does not cover

- The review ledger hashes the prose, so editing it invalidates a signature and forces a
  human to look again. It deliberately does **not** invalidate on regenerating evidence --
  which is exactly the case where the prose can drift from the tables beside it.
- `_generated/fingerprint.json` records which run every table came from, so a discrepancy
  is discoverable by hand. Nothing discovers it automatically.

## Proposed solution: check prose numbers against fingerprint.json

`fingerprint.json` already holds every per-axis and per-probe statistic for the run a card
cites, so it is the natural thing to check against.

A test would extract the numbers appearing in the hand-written parts of `card.md` -- the
text outside the generated blocks, which `fmeval.cards.prose.strip_generated` already
isolates -- and require each to match some value in that bundle's `fingerprint.json`
within a tolerance that accounts for the rounding an author does when writing prose.

Two complications to design around:

1. **Derived quantities.** "47 times the damage" is a ratio of two fingerprint values and
   appears in neither. So is "3.98, 3.94 and 3.75", which are ratios between consecutive
   severities. A check that demanded a literal match would fail on the most useful
   sentences in the card. The likely answer is an explicit declaration -- a `derived`
   block in `card.yaml` naming each such quantity and how it is computed, so the check
   recomputes it from the fingerprint rather than trusting the sentence.
2. **Numbers that are not measurements.** Equation numbers, grid sizes, severity counts
   and years in citations are all numerals in prose that have nothing to do with the run.
   The check needs to distinguish those, most simply by only examining sentences in the
   `## Results` subsections and `## Performance`, where every number should be a
   measurement.

A cheaper first step, if the full check proves awkward: record in the fingerprint the run
identifier the prose was last checked against, and warn when a card's generated blocks
cite a newer run than its prose was reconciled with. That does not verify any individual
number, but it does tell a reader and a reviewer that the two halves of the card are no
longer known to agree.

## Acceptance criteria

- A card whose prose cites a number that the fingerprint contradicts fails a test, with a
  message naming the sentence and the value the run actually gives.
- A derived quantity such as a ratio between two severities can be stated in prose without
  the check rejecting it, and is recomputed from the fingerprint rather than trusted.
- Re-running `python -m fmeval.cards evidence` against a different run surfaces every
  prose number that no longer matches, rather than leaving them to be found by eye.

## Related

- `fmeval/cards/evidence.py` writes the fingerprint and the generated blocks.
- `fmeval/cards/prose.py` `strip_generated` already separates prose from generated content
  for the review hash, and is the same separation this check needs.
- `issues/021` records the earlier run these stale numbers came from.
