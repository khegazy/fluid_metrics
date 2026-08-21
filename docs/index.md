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

Each metric, and each way of damaging a field, gets its own page: what it computes, what
the number means, where it misleads, and the figures and measurements from a recorded run
on real turbulence data.

**[Start with the gallery](degradations/gallery.md)** if you have never looked at a fluid
simulation before. The gallery shows every way of damaging a field, each applied to the
same snapshot, and a minute of scrolling conveys what the tests do better than prose of
any length.

**[Learn to read a metric page](reading-guide.md)** to see how one metric is documented,
then read [mse](metrics/mse.md) as the worked example.

**[Choose a metric](choosing-a-metric.md)** if you came here to pick one for your own
project.
