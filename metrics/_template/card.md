---
name: template_metric
kind: metric
---

## Claim

TODO(fill) In 40 to 150 words: which failure is this metric meant to catch? Name the
thing a model could get wrong that this number would reveal, and say why an existing
metric does not already reveal it. This is the argument for the metric existing, so write
it as an argument rather than a description.

## Intuition

TODO(fill) Written for a STEM undergraduate from any field — someone who may work in
chemistry or biology and has never opened a fluid simulation. **No mathematical notation
at all in this section** — the checker rejects dollar signs and LaTeX delimiters, so
describe the idea in words and keep the equations for the Definition section below.
Three things must be here:

First, a physical picture or analogy, stated without symbols, that gets the idea across.

Second, a worked example with real numbers. Two small fields, four by four is ideal, the
value this metric returns for them, and one sentence on why that number comes out. The
numbers must come from actually running the metric — put the same example in
`test_metric.py` so it cannot drift.

```
reference        candidate        result
0 0 0 0          0 0 0 0
0 1 1 0          0 0 1 1          <put the real number here>
0 1 1 0          0 0 1 1
0 0 0 0          0 0 0 0
```

Third, one sentence naming what this metric ignores. Every metric is blind to something,
and saying so here rather than only in Limitations is what makes this section honest.

## Reading the output

TODO(fill) At least 80 words, answering four questions in order. What is the range, and
what are the units? Is lower better, higher better, or is there a target value? What
counts as a good value, and what does that depend on? And which comparisons are
meaningful — across models, across resolutions, across datasets — and which of those are
invalid for this metric in particular?

## Prediction

TODO(fill) At least 60 words. The reasoning behind each entry in the `expectations` block
of `card.yaml`: why you expect this metric to behave that way along those axes. Write it
before you look at the evidence; a prediction made afterwards is not a prediction.

## Definition

TODO(fill) The exact definition, as numbered display equations. State the discretisation
and how boundaries are handled — those are part of the metric, not an implementation
detail. Cite sources as `[@bibkey]` and put the entry in this bundle's `refs.bib`,
including the equation number you took.

## Evidence

{{ include _generated/evidence.md }}

## Assessment

TODO(fill) At least 60 words. What the measurements actually show: where the predictions
held, where they did not, what this metric detects that the controls do not, and where it
simply tracks them. State plainly what it is blind to, including any canary it fails —
that is information a reader needs, not a mark against the metric. Finish with the
situations in which someone should reach for this metric. Do not write a verdict; nothing
in this repository passes or fails a metric.

## Limitations

TODO(fill) At least 80 words. At least one concrete situation where this metric gives a
misleading answer, described so precisely that a reader can recognise it in their own
results. Saturation, blind spots, and any case where the number disagrees with what a
person sees when they look at the two fields.

## References

\bibliography
