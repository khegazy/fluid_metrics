# Choosing a metric

This page is honest about its own limits. At present every metric implemented here is a
**baseline control** — one of the familiar error norms that new candidate metrics will be
measured against — rather than a new candidate. So this page can tell you how those
familiar baselines differ from one another and what all of them miss, and not much more.
The page will grow as candidate metrics land.

This is also the one page on the site that necessarily spans several metrics, since
comparing them is the whole point of it.

## Start from the failure you care about

Every other page is organised by metric. This table is organised by what goes wrong in
the prediction. **Damage** in the entries below is the common 0-to-1 scale described in
[the reading guide](reading-guide.md): 0 is a perfect match, and 1 is what the metric
gives a field with no relationship to the truth.

| What you need to detect | What was measured |
|---|---|
| Errors of amplitude — damping, added noise, lost fine detail | Every baseline catches these, putting every strength of damage in the correct order in every snapshot, on all three physical fields |
| A feature displaced by less than one grid cell | MAE assigns 47 times the damage MSE does at an eighth of a cell. Of the baselines, MAE is the one to reach for |
| Which of two models is better on one field | Any of the baselines. They order the damage almost identically (MAE against MSE, 0.987) so the choice barely matters |
| Comparing results across different fields or datasets | NRMSE is the only baseline whose value carries no units. The others carry the field's own units and so cannot be compared from one field to another |
| A prediction with the right spectrum and the wrong structure | Every baseline rejects the fake prediction firmly, scoring it between 0.66 and 1.41 damage |
| Where in the domain a model is going wrong | MAE, MSE and RMSE each also store a map of the error cell by cell. The single metric value alone cannot tell you |

## What the baselines do not do

All four baselines are blind to position, in exactly the same way. A shock of precisely
the right shape and strength, one cell away from where it belongs, is penalised twice:
once in the cells the shock left and once in the cells the shock moved into. No setting of
any of these four metrics avoids that. It is not a defect to be tuned away — it is an
unavoidable consequence of comparing two fields one cell at a time, and it is the reason
metrics that tolerate small displacements are being developed.

The baselines are also ambiguous in a way worth stating: two completely different fields
can produce the same value. The physics-based diagnostics are worse in this respect than
the error norms — enormously many different flows share any given enstrophy — which is
why enstrophy and kinetic energy are described as rough alarms and should never be read
on their own.

## Choosing between the four baselines

All four correlate above 0.95 with one another across the whole set of degradations, so
**for the purpose of ranking models they are duplicates of each other**. The differences
that matter lie elsewhere:

- **MSE**, the mean squared error, responds to a displacement as the square of that
  displacement. MSE therefore reads as forgiving of small shifts and severe about
  moderate ones. Cheap to compute, differentiable everywhere, and its value is in the
  square of the field's units.
- **RMSE** is the square root of MSE, which puts the value back into the field's own
  units. RMSE correlates with MSE at exactly 1 — taking a square root cannot reorder
  anything — so reporting both tells you nothing extra about which model is better.
- **MAE**, the mean absolute error, responds to a displacement in direct proportion to
  that displacement, which makes MAE far more sensitive to small shifts. MAE is not
  differentiable where the error is exactly zero, which matters if you want to train
  against it and does not matter if you only want to measure with it.
- **NRMSE** is RMSE divided by how much the reference field itself varies. NRMSE is
  therefore the only one of the four whose value can be read across different fields.

## Using more than one metric at once

A panel of metrics that all agree with each other adds cost without adding information.
The cross-metric correlation reported on each card exists for exactly this check: if a
candidate metric correlates above about 0.95 with a baseline across the degradations, the
candidate is ordering the same things the baseline already ordered, and the case for
including both has to rest on something other than ranking — a different sensitivity to
small errors, say, or usefulness as a training loss.

## If you are a program rather than a person

Read [catalog.json](catalog.json) instead of this page. It carries the same facts in a
form that needs no prose parsing, including how each metric behaved on each degradation
and each physical field.
