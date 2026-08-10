# `NM-0` is the reserved identifier for the pointwise baselines

**Category:** technical debt
**Priority:** —
**Status:** RESOLVED (2026-08-07) — accepted

## Decision

`NM-0` is accepted as the identifier for the pointwise baseline controls: MAE, MSE, RMSE and
NRMSE. It is now a real slot rather than a placeholder, and result CSVs carrying it are
correct.

## Context

MAE, MSE, RMSE and NRMSE are tagged `tracker_id = "NM-0"`. The identifier did not originate in the
metrics tracker — it was introduced here as a reserved slot for pointwise baseline controls, on the grounds that these are not candidate metrics but the control the candidates
must beat. The identifier lands in every result row and every provenance snapshot, so it
needed blessing before it spread through the CSVs.

`PH-4` on enstrophy and kinetic energy was taken from the document and was never in question.

## Remaining action

Add `NM-0` to the master table in the metrics tracker so the document and the code agree, with
a note that it denotes the pointwise baseline family rather than a candidate metric. Until that
happens, someone reading the tracker alone will not find the identifier that appears in every
result file.

## Related

`metrics/standard_ml.py`; the master table in the metrics tracker.

---

## Ready-to-paste LaTeX for the metrics tracker

Claude Code has no Overleaf access, so this is written out for copying by hand. Three
insertions.

### 1. Master table row

In the `longtable` in Section~\ref{sec:master}, immediately after the line

```latex
\multicolumn{7}{@{}l}{\emph{Norms and function-space metrics}}\\
```

and before the `NM-1` row, insert:

```latex
NM-0 & Pointwise $L^p$ baselines (MAE, MSE, RMSE, NRMSE) & --- & Low & n/a$^\ddagger$ & Implemented; measured & \\
```

### 2. Footnote under the master table

Beside the existing `$^{*}$` and `$^\dagger$` notes:

```latex
\noindent
$^\ddagger$ NM-0 is not a candidate and carries no promise rating. It is the pointwise
control that every other entry is read against, implemented so that each candidate has a
baseline to be compared with.
```

### 3. Subsection, at the head of the "Norms and function-space metrics" section

```latex
\subsection{NM-0. Pointwise $L^p$ baselines --- control}

\paragraph{What it is.} Mean absolute error, mean squared error, root mean squared error,
and RMSE normalised by the RMS of the reference \emph{fluctuation}. These are not
candidates; they are the control against which the rest of this document is read. A panel
in which $L^2$ scores well everywhere is a broken panel.

\paragraph{Why NRMSE is included.} On the weakly compressible data the density field is
$1.0 \pm 1.8\times10^{-4}$. Normalising by the raw RMS would hide four orders of magnitude
of relative error and make density and velocity results incomparable on a single axis, so
the spatial mean is removed before normalising.

\paragraph{Response to displacement follows the order of the norm.} For a displacement
$\delta$ small compared with the scale of variation, $f(x+\delta) - f(x) \simeq \delta\,
\partial_x f$, so the two families inherit different powers:
\begin{equation}
\mathrm{MSE} \simeq \delta^{2}\bigl\langle (\partial_x f)^2 \bigr\rangle,
\qquad
\mathrm{MAE} \simeq \delta\,\bigl\langle |\partial_x f| \bigr\rangle .
\label{eq:lp-displacement}
\end{equation}
Measured on $256^2$ vorticity at $\mathrm{Re}=5\times10^4$ over 21 frames of developed
flow, the ratios per doubling of distance in the sub-cell range are $3.99$, $3.95$, $3.82$
for MSE (quadratic predicts $4$) and $2.00$, $1.98$, $1.93$ for MAE (linear predicts $2$),
confirming Equation~\eqref{eq:lp-displacement} to better than 5\%. Damage below is
normalised so that $1$ is the value two statistically identical but positionally unrelated
fields receive.

\begin{center}
\begin{tabular}{@{}lrrrrrrrr@{}}
\toprule
displacement [cells] & 0.125 & 0.25 & 0.5 & 1 & 2 & 4 & 8 & 16 \\
\midrule
MSE   & 0.0004 & 0.0017 & 0.0069 & 0.0262 & 0.0887 & 0.1785 & 0.2789 & 0.4481 \\
MAE   & 0.0221 & 0.0441 & 0.0875 & 0.1692 & 0.3005 & 0.4343 & 0.5835 & 0.6757 \\
NRMSE & 0.0216 & 0.0432 & 0.0858 & 0.1674 & 0.3053 & 0.4392 & 0.5590 & 0.7047 \\
\bottomrule
\end{tabular}
\end{center}

\noindent
The practical consequence is that MAE assigns 55 times the damage MSE does at an eighth of
a cell, and 6.5 times at one full cell. \emph{If a pointwise metric is wanted that notices
sub-cell displacement, MAE is strictly preferable to MSE}, and the quadratic suppression is
why MSE reads as tolerant of small shifts while being severe at moderate ones. The double
penalty does not have a single onset; its onset depends on the order of the norm.

\paragraph{The Gaussian-impostor canary (IN-4) does not catch this family.} Measured, MSE
assigns the spectrum-matched field $0.80$ on vorticity and $0.51$ on velocity: it rejects it
firmly, because a phase-randomised field is pointwise uncorrelated with the reference. $L^p$
metrics are phase-\emph{sensitive}. IN-4 is aimed at quantities that are functions of
$|\hat f|$ alone, such as BD-1 and BD-2, which score the impostor perfectly. A report in
which every implemented metric passes IN-4 should therefore not be read as reassuring until
a spectrum-only metric is in the panel.

\paragraph{Redundancy, and a caution.} Across the full degradation ladder the three
baselines correlate at $\rho = 0.995$ (MAE/MSE), $0.970$ (MSE/NRMSE) and $0.968$
(MAE/NRMSE), all above the 0.95 pruning threshold, so they order the degradations almost
identically. They nonetheless differ by $55\times$ in displacement damage at an eighth of a
cell. High rank correlation means two metrics \emph{order} damage the same way; it does not
mean they \emph{weight} it the same. For model selection by ranking these are duplicates;
as training losses they are not.

\rating{No rating. NM-0 is the control, not a candidate.}
```
