# CRPS and spread-to-skill need ensembles

**Category:** data generation
**Priority:** low
**Status:** resolved for the estimators; open for physical ensemble data (see 004)

## Context

Two probabilistic criteria were designed but not applicable. The continuous ranked
probability score reduces to mean absolute error for a deterministic prediction, so it
conveys nothing beyond MAE unless an ensemble or a generative model is available; the
spread-to-skill ratio needs an ensemble by definition. Every dataset here was a single
deterministic realisation.

## What was done

The harness now carries ensembles end to end, and four metrics are implemented, validated
and documented: `crps` (fair estimator), `spread_skill`, `rank_histogram` and
`ensemble_mean_rmse`. `Frame` gained an optional `members` slot, `Trajectory` an
`is_ensemble` flag, the metric registry an `ensemble` arity, and the degradation registry
an `ensemble` flag with two dispersion operators (`spread_inflate`, `spread_deflate`)
plus a broadcast lane that applies every existing per-field operator to each member.

The spread estimator is the one this issue asked for: the square root of the mean ensemble
variance, with the finite-ensemble factor sqrt((M+1)/M) so a calibrated ensemble reads one
at any size. A regression test constructs a case where the naive mean-of-spreads differs by
sqrt(2) and fails if the implementation is swapped for it; that was verified by making the
swap and watching the test go red.

`configs/dataset/synthetic_ensemble.yaml` provides the ensemble. It is **generated, not
simulated**: the reference is drawn from the same process as the members with the same
sigma, making them exchangeable, so every metric has an analytic target — flat rank
histogram, spread-to-skill of one, CRPS matching the Gaussian closed form. That is what
validates the estimators. It is not physical evidence and its complexity rank is -1.

## Acceptance criteria

Met. `python evaluate.py 'metrics=[mae,crps,spread_skill,rank_histogram,ensemble_mean_rmse]'
dataset=synthetic_ensemble degradation=ensemble_miscalibration` runs end to end, and on
that run, per-frame means:

| axis | mae | ensemble_mean_rmse | crps | spread_skill | rank_histogram |
|---|---|---|---|---|---|
| clean | 0.124 | 0.155 | 0.085 | 0.995 | 0.049 |
| spread_deflate, harshest | 0.124 | 0.155 | 0.109 | 0.199 | 1.239 |
| spread_inflate, harshest | 0.124 | 0.155 | 0.141 | 3.978 | 1.009 |
| bias, harshest | 0.379 | 0.409 | 0.300 | 0.378 | 1.513 |

CRPS and spread-to-skill differ from MAE, as required. The two dispersion axes are the
sharper result: both deterministic metrics are constant on them to three decimals while
every probabilistic metric responds, which is the separation the panel exists to provide.

## The cards carry this run as evidence

`configs/cards/default.yaml` now admits `synthetic_ensemble` alongside `kinet_re5e4`, and
all four cards cite it. The two entries are there for different reasons and the cards say
which is which: a run on the synthetic ensemble establishes that an estimator computes what
it claims to, checkable against arithmetic, and nothing more. The dataset carries no `_dev`
suffix precisely because that suffix marks a reduced version of a real dataset, and a card
citing one fails its tests; this is the full and only form of a calibrated null.

Two defects in the card machinery surfaced only once these cards had evidence to generate,
both of which would have affected any custom ladder:

1. `probe_summary` returned a bare row for a run whose ladder contains no probe, and the
   generator rendered it as a "trap test: fake prediction, right spectrum" line scored with
   an em dash — indistinguishable from a trap test that ran and could not be scored. The
   miscalibration ladder has no impostor, since scrambling one field's phases says nothing
   about whether an ensemble is honestly dispersed.
2. `FAMILY_BLOCKS` in `evidence.py` and `FAMILY_HEADINGS` in `prose.py` were two
   hand-maintained lists of the same families. The `ensemble` family was added to one and
   not the other, so the cards named the subsection, passed the prose check, and kept their
   "Not generated yet" placeholder while `cards evidence` reported success. The blocks are
   now derived from the headings, and a test pins them together.

## What remains

**Physical ensemble data**, which is issue [004](004-independent-realizations.md) and not
this one. Nothing measured here says how these metrics behave on turbulence: the synthetic
fields have no shocks, no intermittency and no coherent structure, and the degradation
families a physical run would exercise — smoothing, spectral filtering, displacement,
resolution loss — are absent from these cards for that reason. When an ensemble of real
runs at fixed parameters with perturbed initial conditions exists, the four cards should be
regenerated against it and the `synthetic_ensemble` entry in the evidence allowlist
reconsidered.

## Related

- [004](004-independent-realizations.md) — the physical ensemble these metrics need next.
- `metrics/{crps,spread_skill,rank_histogram,ensemble_mean_rmse}/card.md`
- `TEST_DESCRIPTION.md`, "Metrics with a target value", for how a metric calibrated at one
  rather than zero is ranked without misreporting it.
