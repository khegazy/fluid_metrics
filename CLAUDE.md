# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

This repository develops and tests metrics that quantify the quality of fluid simulations (especially ML surrogates of compressible, shocked, turbulent flow), with the eventual goal of using validated metrics as evaluation panels and training losses for a scientific foundation model. It is a collaborative research repo shared by several colleagues.

There is no application code yet — no build, lint, or test commands exist. When a Python package and test suite are added, update this file with the actual commands. The intended stack is Python with PyTorch/NumPy/SciPy, Hydra for configuration where sensible, and Weights & Biases for training logs.

## Source of truth: the metrics tracker

The "Fluid Metrics Exploration Tracker" (`Table_of_Ideas.tex`) is the working document for the whole project. It lives on Overleaf (edit link): https://www.overleaf.com/5216584535fbvsvrhpfmnd#1f594b

Claude Code cannot read Overleaf directly — when the tracker's content is needed, ask the user to attach or paste the current version rather than guessing at its contents. The tracker contains:

- A **master tracker table** of ~40 candidate metrics, each with a stable ID (e.g. OT-1, NM-2, TD-1). Use these IDs in code, commits, issues, and discussion. Keep the table's `Status` and `Owner` columns current as items move from `Not tested` → `In progress` → `Tested (result)`.
- Per-item sections with the definition, literature precedent, keywords, known pitfalls, and a promise rating (High/Medium/Low) with justification.
- A full bibliography. Every implemented metric should cite its source paper (and equation number where applicable) in a code comment.

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
