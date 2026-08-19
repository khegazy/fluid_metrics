# pde_metrics

Metrics for evaluating machine-learning surrogates of PDEs, and the evidence for whether
each one works.

A surrogate that predicts a shock one cell to the left of the true one has, by any physical
reading, done well. A pointwise norm scores it as two errors — one where the shock should
be and is not, one where it is and should not be — and can rate it worse than a prediction
with no shock at all. That is the double penalty, and it is why choosing a metric is a
research question rather than a matter of taste.

This repository answers that question by measurement. Every metric is run against a ladder
of controlled degradations on real turbulence data, and everything measured is written
down beside the metric it describes.

## What is here

Each metric and each degradation is a **bundle**: a directory holding the implementation,
its tests, a typed record, prose written for three different readers, and the figures and
numbers from a recorded evaluation run. Nothing about a metric lives anywhere else.

**[Start with the gallery](degradations/gallery.md)** if you have never opened a fluid
simulation. It shows every degradation applied to the same snapshot, and a minute of
scrolling conveys what the tests do better than prose of any length.

**[Read a card](reading-guide.md)** to understand how one metric is documented, then read
[mse](metrics/mse.md) as the worked example.

**[Choose a metric](choosing-a-metric.md)** if you came here to pick one for your own
project.

**[Read catalog.json](catalog.json)** if you are an agent. It holds every structural fact —
what exists, what it returns, what properties it has, how it behaved — so you never have to
parse prose to answer a question about the code.

## What this repository does not do

It does not decide. No metric here is marked good or bad, and there is no ranking. A metric
that misses one thing usually catches another, and the useful record is what each one sees
and what it is blind to, so a reader can match a metric to the question they are asking.

Two consequences worth stating plainly. Nothing in a card is a prediction: every claim
about how a metric behaves is either a measurement from a named run or a citation to
published work. And a card's `status` describes whether the work has been done and
reviewed, never whether the results were good.
