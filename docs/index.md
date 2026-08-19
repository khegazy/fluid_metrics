# pde_metrics

Metrics for judging how good a machine-learning simulation of a fluid is, and the
evidence for whether each metric actually works.

Three words are used constantly on this site, so they are worth fixing first. A
**simulation** solves the equations of fluid motion and is treated here as the truth. A
**surrogate** is a machine-learning model trained to predict what the simulation would
have produced, far faster and far less reliably. A **metric** is a single number scoring
how close the surrogate's prediction came to the truth.

The problem is that the obvious metrics are bad at this. Suppose a surrogate predicts a
shock — a sharp jump in pressure and density — one grid cell to the left of where the
shock really is. By any physical reading that surrogate has done well: the shock is
there, and it has the right shape and the right strength. But a metric that compares the
two fields one cell at a time counts two errors, one where the shock should be and is
not, and one where the shock is and should not be. Such a metric can rate that
prediction *worse* than a prediction containing no shock at all. This is called the
**double penalty**, and avoiding it is why choosing a metric is a research question
rather than a matter of taste.

This repository answers that question by measurement rather than by argument. A trusted
simulation is damaged in controlled, increasing steps, every metric is asked to score the
damaged versions, and everything measured is written down beside the metric it describes.

## What is here

Each metric, and each way of damaging a field, gets its own directory holding everything
the repository knows about it: the code, the tests, a machine-readable record, prose
written for three different kinds of reader, and the figures and numbers from a recorded
run. Nothing about a metric lives anywhere else. Such a directory is called a **bundle**,
and the page describing one is called its **card**.

**[Start with the gallery](degradations/gallery.md)** if you have never looked at a fluid
simulation before. The gallery shows every way of damaging a field, each applied to the
same snapshot, and a minute of scrolling conveys what the tests do better than prose of
any length.

**[Learn to read a metric page](reading-guide.md)** to see how one metric is documented,
then read [mse](metrics/mse.md) as the worked example.

**[Choose a metric](choosing-a-metric.md)** if you came here to pick one for your own
project.

**[Read catalog.json](catalog.json)** if you are a program rather than a person. That file
holds every structural fact — what exists, what each metric returns, what properties each
metric has, how each metric behaved — so no program has to parse prose to answer a
question about the code.

## What this repository does not do

This repository does not decide. No metric here is marked good or bad, and there is no
ranking. A metric that misses one kind of error usually catches another, so the useful
record is what each metric sees and what each metric is blind to, letting a reader match
a metric to the question they are asking.

Two consequences are worth stating plainly. Nothing on a metric's page is a prediction:
every claim about how a metric behaves is either a measurement from a named run or a
citation to published work. And where a page reports how far the work has got — whether
the metric has been measured, and whether a person has read and signed off on the
description — that says nothing about whether the results were good.
