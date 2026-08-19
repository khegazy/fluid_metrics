# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

This repository develops and tests metrics that quantify the quality of fluid simulations (especially ML surrogates of compressible, shocked, turbulent flow), with the eventual goal of using validated metrics as evaluation panels and training losses for a scientific foundation model. It is a collaborative research repo shared by several colleagues.

## Read AGENTS.md first

[`AGENTS.md`](AGENTS.md) is the canonical instruction file for every agent working here,
whichever assistant it is. It covers how to add a metric, a degradation, a data source or a
report renderer; the testing conventions; how to treat the generated LaTeX; and a table of
traps that have already caught someone. This file carries the scientific context that
`AGENTS.md` deliberately does not duplicate.

## Commands

Commands are plain `python` and `pytest` calls, run in whatever environment the contributor
has activated — colleagues use uv, plain venvs and conda, so **do not reintroduce a `uv run`
prefix** anywhere. `uv sync --extra dev` populates `.venv` from the committed lockfile;
`pip install -e '.[dev]'` does the same elsewhere. Nothing needs the repo root as the working
directory.

```bash
python check_setup.py                        # confirm the environment before anything expensive
pytest                                       # ~20 s; skips the CFS-reading and LaTeX tests
pytest -m data                               # reads the real files on CFS
module load texlive/2024 && pytest -m slow   # compiles a report with latexmk
pytest tests/test_analysis.py -q -k spearman # one file, one pattern

python -m metrics                            # what metrics exist
python -m degradations                       # what degradations exist, with severity units

python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev
python make_report.py results/mse_<time> --compile --zip
```

`evaluate.py` writes one `results/<metric>_<time>/` folder per metric plus a
`comparison_<time>/` when several metrics run. Each is self-contained — raw numbers, resolved
config, provenance, and a `main.tex` that compiles standalone and renders on Overleaf.

Two size knobs, both recorded with the results: `dataset.time.reduction` (evaluate every Nth
frame) and `analysis_grid.resolution` (the IN-2 analysis grid). The full trajectory at
reduction 1 is roughly half an hour; the default of 50 is under a minute.

Stack: NumPy/SciPy/h5py/pandas/matplotlib with Hydra for configuration. PyTorch is an optional
extra and nothing currently needs it. Weights & Biases is not wired in yet.

## Documentation

| File | What it is |
|---|---|
| `TEST_DESCRIPTION.md` | Plain-language reference for every quantity the suite reports. A copy is placed in each run folder. A test fails if a reported column, degradation or figure is undocumented |
| `issues/` | Open items, one file per item with its evidence. `issues/README.md` is the index |
| `README.md` | Setup and the NERSC specifics |

## Source of truth: the cards in this repository

Each implemented metric and degradation documents itself in a **card** beside its
implementation, and `docs/catalog.json` is the machine-readable index of all of them. That
is the source of truth for anything implemented: what it computes, what properties it has,
and what it did on a recorded run. Read the catalog rather than parsing prose, and see
`AGENTS.md` §3 for how to add one.

The external **metrics tracker** remains the planning document for metrics that do not
exist yet — candidate ideas, literature precedent, promise ratings, the bibliography. It is
maintained outside this repository; ask the user where it currently lives and to paste the
relevant part rather than guessing, and do not assume a copy exists here. `Table_of_Ideas.tex`
in the repository root is a historical snapshot of it and is not maintained.

The two-letter ID prefixes (OT-, NM-, TD-, …) are **retired**. They were invented before the
cards existed, they meant nothing to a reader who had not been told the scheme, and a bundle's
directory name — which is what users type in `metrics=[...]` — is now its only identity. A
card's `category` field carries what the prefix used to gesture at, from a controlled
vocabulary in `fmeval/cards/schema.py`. Cards may differ from the tracker; where they do, the
measured card wins.

Every implemented metric should still cite its source paper, with the equation number, in
its `## Definition` section and in `refs.bib`.

## Core problem framing

- **The central pathology is the "double penalty" / shock-shift problem**: pointwise norms like L² doubly penalize a sharp feature (shock, shocklet, eddy) that is correct in shape and amplitude but slightly displaced. The same pathology is called "double penalty" in weather verification and "cycle skipping" in seismic inversion — both fields have mature solutions this project imports rather than reinvents. Every metric here exists to capture a failure mode L² misses.
- **Organizing principle (NM-3, mollification split)**: decompose a field into a smooth part and a sharp/singular remainder, and apply the right metric to each — ordinary norms on the smooth part, position-tolerant metrics (Wasserstein, shock-set distances) on the sharp part. Coherent vortex extraction (BD-3) and the Helmholtz solenoidal/dilatational split (PH-6) are principled instances of the same idea. Most metrics in the tracker slot into one side of this split.
- **The north-star test case is shocklet-populated compressible turbulence** — many small shocks embedded in turbulence, not one isolated front. Metrics that only work for isolated trackable fronts are rated accordingly.
- **Diagnostics and training losses are separate artifacts with separate requirements.** A diagnostic may be non-differentiable, expensive, and discontinuous; a training loss may not. Do not conflate the two when implementing.

## Evaluation protocol (how a metric earns its place)

Every candidate metric is validated on the degradation-ladder protocol (IN-3):

1. **Reference**: DNS at Re ≈ 500, isotropic and doubly periodic shear. A Boltzmann solver is planned as the baseline predictor.
2. **Ladder**: the solver degraded in controlled steps (grid coarsening, plus an orthogonal axis such as noise or artificial viscosity).
3. **Acceptance**: a metric joins the panel only if it is monotone in degradation with high Spearman rank correlation. Non-monotone metrics are dangerous for model selection.
4. **Canary (IN-4)**: a Gaussian random field matched to the reference energy spectrum is included as an impostor predictor. Any metric that scores it well is phase-blind and must not be used alone.
5. Also record: sensitivity (where the metric first departs from clean vs. where a human sees degradation), wall-clock cost per evaluation, and cross-metric correlation to prune redundant panel members.

First-wave priorities (in order of value per effort): IN-4, NM-2 (Ḣ⁻¹ norm), TD-1 (persistence diagrams), OT-5 + PS-4 (increment-PDF W₁ and flatness), SH-1 + SH-2 (shock detector + surface distances), PH-2 + PH-3 (weak PDE residual + solver-consistency residual). PS-2 and PS-3 apply only when ensembles are available; mark them N/A for deterministic surrogates.

## Implementation conventions

- **Fix detector thresholds once in the evaluator and never tune them per model** — otherwise the metric becomes gameable. This applies to shock sensors (SH-1), vortex criteria (PD-4), and any thresholded quantity.
- **Known-correct estimators matter**: e.g. ensemble spread must be computed as the square root of the average ensemble variance, not the average of spreads (Fortin et al. 2014, see PS-3 in the tracker). When the tracker records a computational gotcha, follow it.
- **Cross-mesh comparison (IN-2)**: remap fields conservatively onto a common analysis grid, compare cell averages rather than point samples, and record the remapping operator as part of the metric definition.
- Cite the source paper and equation/table number in a comment for any equation taken from the literature; the tracker's bibliography has the references.
- Label new code as prototype or production quality; metric-evaluation code that feeds acceptance decisions should be production quality.
- **`NM-0` is the accepted identifier for the pointwise baseline controls** (MAE, MSE, RMSE, NRMSE). It denotes the family the candidates must beat rather than a candidate itself. It is not yet in the master table; adding it there is the one open follow-up on `issues/021`.

## What exists, and what building it corrected

Three plugin registries, all discovered by name from config, all extended by one decorated
function: **metrics** (`metrics/`), **degradations** (`degradations/`, 20 operators in 7
families), and **report renderers** (`fmeval/report/`). Readers live in `fmeval/data/` and are
a closed set with explicit imports, deliberately unlike the other two.

Five findings from running this on the real data. Each is documented where the code lives, and
each would have quietly corrupted results:

1. **Rank correlation must be computed per frame, not pooled.** The density perturbation grows
   six orders of magnitude along the trajectory, so pooling frames measures the flow's
   evolution rather than the metric's response. Measured: every density axis perfectly ordered
   within every frame while the pooled value read 0.10 to 0.91.
2. **Derived fields must be recomputed after a remap, never averaged.** Block-averaging
   vorticity gives a field that is not the curl of the velocity beside it; the difference is
   5.6% / 18.3% / 25.9% at coarsening factors 2 / 4 / 8. Related: never mix the solver's
   stored vorticity with a recomputed one — they differ by 8.1% rms because the solver used a
   lattice stencil.
3. **High-pass filters must preserve the spatial mean.** Deleting k=0 on density removes a
   component four orders of magnitude larger than the cutoff controls; every severity level gave an
   identical damage of 2.7e7 and the axis carried no ordering at all.
4. **The unrelated-field anchor must be measured, not scavenged.** A 16-cell translation
   reaches only ~0.6 of the true value, which inflated every damage score by ~1.6x. A distant
   frame is also wrong: the flow decays, so it has 0.70 of the variance and a different
   flatness.
5. **Severity ranges must follow each field's spectrum.** Fixed cutoffs applied to every field
   alike produce flags that point at the axis rather than the metric: the same blur list reached
   1.2% of the unrelated-field level on density while working well on vorticity, and the same
   filter cutoffs saturated by the second severity level on density. Fixed: severities on the
   smoothing and spectral axes are now *relative* — a fraction of the field's characteristic
   scale, or of the energy a filter removes — and resolved per field against a spectrum measured
   from the data. Every calibrated axis is now monotone on both fields from one config that names
   no field. Three further defects surfaced only when this was measured: a low-pass severity
   mapped to the wrong side of its cutoff inverted that axis while leaving every number
   plausible; rounding a calibrated width to an even window displaced the field by half a cell
   and broke monotonicity; and a severity level can resolve onto a milder severity level's severity or onto a no-op,
   which the rank correlation would otherwise score as agreement. Severity levels that are not distinct
   experiments are now detected and excluded (`severity_degenerate`).

   Two limits calibration does not remove, both properties of these fields rather than of the
   config: 69% of density's fluctuation energy sits in the four diagonal modes at |k| = √2 and
   only 3e-5 of it in the axis modes at |k| = 1, so the available cutoffs there are few and far
   apart and a *sharp* filter cannot resolve four severity levels at all. The high-pass axis is squeezed
   between a no-op below those diagonal modes and near-total damage above them, so it alone does
   not reach the factor-five damage range the other axes do.

   A related correction, found while reporting the realised energy removal: the calibration and
   the filters had **two different definitions of |k|** — the filters compared a continuous
   magnitude, the calibration binned into shells of `rint(|k|)` — which put the diagonal modes on
   opposite sides of the same cutoff. On density that made a low-pass asked to remove 30% remove
   99.997%, with every intermediate number looking plausible. There is now one definition, in
   `fmeval/wavenumbers.py`, and the requested and realised fractions agree to within a few
   percent wherever the spectrum can resolve the request.

Also worth carrying forward: the IN-4 Gaussian field does **not** catch the L^p family — it
catches metrics built only on the amplitude spectrum, and MSE rejects it firmly at 0.51–0.80.
And a high cross-metric rank correlation does not mean two metrics agree in magnitude: MAE and
MSE correlate at 0.995 across the ladder yet differ by 55x in displacement damage at an eighth
of a cell, because one is linear and the other quadratic in the displacement.
