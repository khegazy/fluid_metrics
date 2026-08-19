# Choosing a metric

This page is honest about its own limits: at present every implemented metric is a
**control** rather than a candidate, so it can tell you how the pointwise baselines differ
from one another and what they all miss, and not much else. It grows as candidates land.

The one page here that necessarily spans bundles, since comparison is the whole point.

## Start from the failure you care about

The cards are organised by metric; this table is organised by what goes wrong.

| What you need to detect | Measured behaviour |
|---|---|
| Amplitude errors — damping, added noise, lost small scales | Every pointwise control catches these, ordering every severity correctly in every frame on all three fields |
| Sub-cell displacement | MAE assigns 47 times the damage MSE does at an eighth of a cell. Of the controls, MAE is the one to reach for |
| Which of two models is better on one field | Any of the controls; they order the ladder near-identically (MAE against MSE, 0.987) so the choice barely matters |
| Comparing results across fields or datasets | NRMSE is the only dimensionless control. The others carry the field's units and cannot be compared across fields |
| A prediction with the right spectrum and wrong structure | Every pointwise control rejects the phase-randomised impostor firmly, at 0.66 to 1.41 damage |
| Where in the domain a model is wrong | MAE, MSE and RMSE each store a per-cell map; the metric value alone cannot tell you |

## What the controls do not do

All four are blind to position in the same way. A shock of exactly the right shape and
strength one cell over is penalised twice, once where it should be and once where it is,
and there is no setting of any of them that avoids this. That is not a defect to be tuned
away — it is a property of comparing cell by cell, and it is the reason position-tolerant
metrics are being developed.

They are also degenerate in a way worth stating: two very different fields can share a
value. The physics diagnostics are worse in this respect than the norms — enormously many
flows share a given enstrophy — which is why enstrophy and kinetic energy are described as
tripwires and should never be read alone.

## Choosing between the pointwise controls

They correlate above 0.95 with one another across the whole ladder, so **for ranking models
they are duplicates**. The differences that matter are elsewhere:

- **MSE** responds quadratically to displacement, so it reads as tolerant of small shifts
  and severe about moderate ones. Cheap, differentiable everywhere, and the value is in
  squared units.
- **RMSE** is MSE in the field's own units. It correlates with MSE at exactly 1 — a
  monotone square root cannot reorder anything — so reporting both adds nothing about which
  model is better.
- **MAE** responds linearly, which makes it far more sensitive to small displacement. Not
  differentiable at zero error, which matters for a training loss and not for a diagnostic.
- **NRMSE** is the only one whose value can be read across fields, because it is divided by
  the reference's own fluctuation.

## Using more than one

A panel of metrics that agree adds cost without adding information. The cross-metric
correlation on each card is there for this: if a candidate correlates above about 0.95 with
a control across the ladder, it is ordering the same things and the case for including both
has to be made on something other than ranking — a different magnitude response, or use as
a training loss.

## If you are an agent

Read [catalog.json](catalog.json) rather than this page. It carries the same facts in a
form that does not require parsing prose, including each metric's measured behaviour per
axis and field.
