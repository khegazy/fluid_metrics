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

Environment is `uv` with a committed lockfile. `.venv/bin/python` works everywhere `uv run`
does, and neither needs the repo root as the working directory.

```bash
uv sync --extra dev                 # populate .venv from uv.lock
uv run python check_setup.py        # confirm the environment before anything expensive
uv run pytest                       # ~20 s; skips the CFS-reading and LaTeX tests
uv run pytest -m data               # reads the real files on CFS
module load texlive/2024 && uv run pytest -m slow   # compiles a report with latexmk
uv run pytest tests/test_analysis.py -q -k spearman # one file, one pattern

uv run python -m metrics            # what metrics exist
uv run python -m degradations       # what degradations exist, with severity units

uv run python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev
uv run python make_report.py results/mse_<time> --compile --zip
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

## Source of truth: the metrics tracker

The project's metrics tracker is the working document for the whole effort. It is maintained
outside this repository — ask the user where it currently lives and to paste or attach the
relevant part rather than guessing at its contents, and do not assume a copy exists in the
repo. It holds:

- A **master table** of ~40 candidate metrics, each with a stable ID (e.g. OT-1, NM-2, TD-1).
  Use these IDs in code, commits, issues, and discussion, and report results back so the
  `Status` column reflects what has been measured.
- Per-item sections with the definition, literature precedent, keywords, known pitfalls, and a
  promise rating (High/Medium/Low) with justification.
- A full bibliography. Every implemented metric should cite its source paper (and equation
  number where applicable) in a code comment.

ID prefixes: OT (optimal transport), SH (shock geometry), NM (function-space norms), CG (curvature/differential geometry), PH (physics invariants), PD (pattern/feature detection), TD (topological data analysis), BD (basis decompositions), PS (probabilistic/distributional), IN (infrastructure and protocol).

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
   component four orders of magnitude larger than the cutoff controls; every rung gave an
   identical damage of 2.7e7 and the axis carried no ordering at all.
4. **The unrelated-field anchor must be measured, not scavenged.** A 16-cell translation
   reaches only ~0.6 of the true value, which inflated every damage score by ~1.6x. A distant
   frame is also wrong: the flow decays, so it has 0.70 of the variance and a different
   flatness.
5. **Severity ranges must follow each field's spectrum.** Fixed cutoffs applied to every field
   alike produce flags that point at the axis rather than the metric: the same blur list reached
   1.2% of the unrelated-field level on density while working well on vorticity, and the same
   filter cutoffs saturated by the second rung on density. Fixed (issue 030): severities on the
   smoothing and spectral axes are now *relative* — a fraction of the field's characteristic
   scale, or of the energy a filter removes — and resolved per field against a spectrum measured
   from the data. Every calibrated axis is now monotone on both fields from one config that names
   no field. Three further defects surfaced only when this was measured: a low-pass severity
   mapped to the wrong side of its cutoff inverted that axis while leaving every number
   plausible; rounding a calibrated width to an even window displaced the field by half a cell
   and broke monotonicity; and a rung can resolve onto a milder rung's severity or onto a no-op,
   which the rank correlation would otherwise score as agreement. Rungs that are not distinct
   experiments are now detected and excluded (`severity_degenerate`).

   Two limits calibration does not remove, both properties of these fields rather than of the
   config: density keeps 69% of its fluctuation energy in the single shell k=1, so a *sharp*
   filter cannot resolve four rungs there at all, and the high-pass axis is squeezed between a
   no-op below that shell and near-total damage above it, so it alone does not reach the
   factor-five damage range the other axes do.

Also worth carrying forward: the IN-4 Gaussian field does **not** catch the L^p family — it
catches metrics built only on the amplitude spectrum, and MSE rejects it firmly at 0.51–0.80.
And a high cross-metric rank correlation does not mean two metrics agree in magnitude: MAE and
MSE correlate at 0.995 across the ladder yet differ by 55x in displacement damage at an eighth
of a cell, because one is linear and the other quadratic in the displacement.
