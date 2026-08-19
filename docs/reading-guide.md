# Reading a card

Every metric is documented the same way, in six sections in a fixed order. The order runs
from what the metric *is* to what it *did here*, and the break between those two matters:
the first four sections hold for any dataset, so if you are adopting a metric for your own
work you can stop at Limitations. The last two are findings about one recorded run.

## Definition

The equation, its discretisation, and how boundaries are handled. That last one is a
required subsection and "None." is a common and perfectly good answer — a metric that
never looks beyond a single cell has no boundary to treat. It is stated rather than left
out because periodic wrap, reflection and zero padding give different numbers from the
same formula, and silence looks identical to "none" while being much less informative.

## Intuition

The same content in words, with no notation at all, written for an early graduate student
in any field. It opens with what the metric measures and which way of being wrong it
reveals, explains the mechanism, and includes a small worked example — usually a four-by-
four grid — whose numbers come from the metric's own test file, so the prose cannot drift
from the code. It closes by naming what the metric ignores, because every metric is blind
to something.

## Reading the output

What to do with a number you are holding: its range and units, whether lower or higher is
better, what makes a value good and on what that depends, and which comparisons are valid.
That last part is the one most often needed. Comparing a pointwise metric across two grid
resolutions, for instance, is invalid without remapping, because the value is a mean over
cells and refining the grid reweights the small scales.

## Limitations

At least one concrete situation where the metric gives a misleading answer, described so
you can recognise it in your own results.

## Performance and Results

The measured half, and none of it is typed by hand. **Performance** is a single table near
the top of the card: how the metric behaved on every family of test, per physical field, so
cards can be compared at a glance. **Results** breaks that down one test at a time, each
subsection linking to the degradation it reports, showing that degradation's numbers, and
then saying in a few sentences what they mean for this metric.

Three quantities recur, and they are worth knowing before you read a table:

**Damage** rescales a metric's raw value so that 0 is the reference and 1 is what a field
with the right statistics and no relation to the truth scores. It is what makes a density
result and a vorticity result comparable. A damage above 1 means the metric considers
something *worse* than unrelated.

**Rank correlation** is the per-frame Spearman correlation between the metric and the
severity. It is computed within a frame and never pooled across the trajectory, because
these flows decay: pooling would measure the decay rather than the metric.

**Separation** is the smallest overlap between neighbouring severities. A metric can be
perfectly ordered on average and still be unable to tell one severity from the next.

## What you will not find

No score, no ranking, and no pass or fail. If you want to know whether a metric is right
for you, the question the cards are built to answer is what it detects and what it misses.

## About the figures

Colour limits are shared across each row of a panel and printed at its edge. This matters
more than it sounds: autoscaling each panel separately would make a strong degradation
look identical to the original, and it would do so silently.
