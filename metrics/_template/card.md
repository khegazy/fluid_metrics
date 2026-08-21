---
name: template_metric
kind: metric
---

**On length.** There are no word counts anywhere in this contract. Say what the section
needs to say and stop: a short section that is complete is better than a padded one, and
a reviewer reading the card is the judge, not a counter. If a section feels thin, the
question is what a reader still does not know after reading it, not how many words it has.

## Definition

TODO(fill) The exact definition, as numbered display equations. State the
discretisation — it is part of the metric, not an implementation detail. Say what is not
deducible from the equation itself, and do not restate what is: that a sum runs over the
indices it is written with is not worth a sentence. Cite sources as `[@bibkey]` and put
the entry in this bundle's `refs.bib`, including the equation number you took.

**Write the maths like this, and only like this.** A card is read both on GitHub and on
the documentation site, and only this subset renders in both. Anything else is shown by
GitHub as its own raw source, with no error reported anywhere, so the checker refuses it:

```
inline      $ ... $
display     $$ ... $$        delimiters alone on their own lines
numbering   \tag{1}          referred to in prose as "Equation (1)"
```

Do not use `\begin{equation}`, `\label` or `\eqref`: those need a full LaTeX toolchain
and degrade silently. An example of the expected form:

$$
\mathrm{METRIC}(f, g) = \frac{1}{N} \sum_{i=1}^{N} \bigl( f_i - g_i \bigr)^2 \tag{1}
$$

and then refer to it as Equation (1) in the prose.

### Boundary handling

TODO(fill) Required, and "None." is a valid answer. If the calculation never looks beyond
a single cell, write `None.` and one clause saying so. If it does consult a neighbourhood
— a stencil, a convolution, a transform — say exactly what happens at the edge of the
domain: periodic wrap, reflection, zero padding, or edge cells dropped. Two
implementations of the same formula that differ only here produce different numbers, and
a reader has no way to tell which you used unless you write it down.

## Performance

<!-- GENERATED performance: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED performance -->

## Intuition

TODO(fill) Written for an early graduate student in any STEM field — someone comfortable
with means, variances and fields, but who may never have opened a fluid simulation and
should not have to know this project's vocabulary. **No mathematical notation at all in
this section** — the checker rejects dollar signs and LaTeX delimiters, so describe the
idea in words; the equations belong in the Definition section above.

Be direct and be brief. State what the metric computes and what that implies; do not
build up to it through an extended analogy, and do not explain what the reader already
knows. Four things must be here:

First, what this metric measures and which way of being wrong it reveals — stated as a
property of the metric, in a sentence or two. Write about the metric, not about its place
in this repository: whether it is a baseline or a candidate is recorded in `card.yaml`,
and how it compares to other metrics belongs in Results, where measurements back the
claim.

Second, the idea itself, in words, including the mechanism behind its characteristic
behaviour.

Third, a compact worked example with real numbers — two small fields, four by four is
ideal, the value this metric returns, and one sentence on why. The numbers must come from
actually running the metric — put the same example in `test_metric.py` so it cannot
drift.

```
reference        candidate        result
0 0 0 0          0 0 0 0
0 1 1 0          0 0 1 1          <put the real number here>
0 1 1 0          0 0 1 1
0 0 0 0          0 0 0 0
```

Fourth, one sentence naming what this metric ignores. Every metric is blind to something,
and saying so here rather than only in Limitations is what makes this section honest.

## Reading the output

TODO(fill) Answer four questions, in order. What is the range, and
what are the units? Is lower better, higher better, or is there a target value? What
counts as a good value, and what does that depend on? And which comparisons are
meaningful — across models, across resolutions, across datasets — and which of those are
invalid for this metric in particular?

## Limitations

TODO(fill) At least one concrete situation where this metric gives a
misleading answer, described so precisely that a reader can recognise it in their own
results. Saturation, blind spots, and any case where the number disagrees with what a
person sees when they look at the two fields.

## Results

<!-- GENERATED run: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED run -->

One subsection per kind of test: the degradations it reports, then their generated
numbers, then what those numbers show about this metric. Keep the evidence beside the
claim it supports.

Say only what this metric did. What the run was — dataset, Reynolds number, resolution,
frames — is in the run summary above, once. What a degradation does, and what its
severity numbers mean, is in its own bundle, which the links reach. Repeating either here
means writing it once per metric and keeping thirty copies true.

Run `python -m fmeval.cards evidence <name> --results results/<run>` to produce the
includes. Never write the numbers yourself, and never edit anything under `_generated/`.
Delete any subsection whose degradations this metric was not run against, and add `###
Trap tests` and `### Compared with the other metrics` only if you have measurements for
them.

### Smoothing

[gaussian_blur](../../degradations/gaussian_blur/card.md) ·
[box_blur](../../degradations/box_blur/card.md)

<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED results_smoothing -->

TODO(fill) What the smoothing degradations found. Say what the numbers show, not what you
expected them to show, and say it about this metric: what the run was is in the run
summary above, and what the degradation does is in its own bundle.

### Spectral filtering

[lowpass_ideal](../../degradations/lowpass_ideal/card.md) ·
[highpass_ideal](../../degradations/highpass_ideal/card.md)

<!-- GENERATED results_spectral: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED results_spectral -->

TODO(fill) What the spectral degradations found.

### Displacement

[translate_x](../../degradations/translate/card.md) ·
[translate_subpixel](../../degradations/translate_subpixel/card.md)

<!-- GENERATED results_geometric: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED results_geometric -->

TODO(fill) What the displacement degradations found. This is where a
cell-by-cell metric is usually at its worst, so say how yours compares.

### Resolution loss

[coarsen](../../degradations/coarsen/card.md)

<!-- GENERATED results_resolution: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED results_resolution -->

TODO(fill) What coarsening found.

### Noise

[additive_noise](../../degradations/additive_noise/card.md)

<!-- GENERATED results_stochastic: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED results_stochastic -->

TODO(fill) What the noise degradation found.

### Trap tests

[gaussian_impostor](../../degradations/gaussian_impostor/card.md) ·
[uncorrelated](../../degradations/random_large_translation/card.md)

<!-- GENERATED results_canaries: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED results_canaries -->

TODO(fill) The phase-scrambled fake prediction and the unrelated-field anchor. State
plainly what your metric does with them, including any trap test it falls for — that is
information a reader needs, not a mark against the metric.

### Compared with the other metrics

<!-- GENERATED results_summary: written by `python -m fmeval.cards evidence <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards evidence <name>`.

<!-- END GENERATED results_summary -->

TODO(fill) What holds across every degradation: how this metric correlates
with the controls, where it merely tracks them, and the situations in which someone
should reach for it. Do not write a verdict; nothing in this repository passes or fails a
metric.

## References

\bibliography
