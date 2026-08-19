---
name: template_degradation
kind: degradation
---

**On length.** There are no word counts anywhere in this contract. Say what the section
needs to say and stop: a short section that is complete is better than a padded one, and
a reviewer reading the card is the judge, not a counter. If a section feels thin, the
question is what a reader still does not know after reading it, not how many words it has.

## Definition

TODO(fill) Exactly what is computed, as numbered display equations. State the
discretisation and the kernel or filter shape. Say what is not deducible from the
equation itself, and do not restate what is.

**Write the maths like this, and only like this** — inline `$ ... $`, display `$$ ... $$`
with the delimiters alone on their own lines, and `\tag{1}` for numbering, referred to in
prose as "Equation (1)". A card is read both on GitHub and on the documentation site, and
only this subset renders in both; `\begin{equation}`, `\label` and `\eqref` are shown by
GitHub as raw source with no error reported, so the checker refuses them.

### Boundary handling

TODO(fill) Required. This domain is doubly periodic, and whether your operator respects
that changes what it measures — a convolution that wraps and one that pads with zeros
disagree along every edge. Say which yours does. If the operator is pointwise and never
looks beyond a single cell, write `None.` and say so.

## Intuition

TODO(fill) For an early graduate student in any STEM field, with no mathematical notation
at all — the checker rejects dollar signs and LaTeX delimiters. Open with which way of
being wrong this degradation stands in for: a surrogate that over-smooths, one that shifts
a shock by a cell, one that gets the energy spectrum right and the phases wrong — say
which of those this imitates. Then describe in plain words what happens to a picture of the field at a weak setting and at a strong one,
and what a person would notice first. Include a small worked example, four by four is ideal,
showing the numbers before and after.

```
before           after
0 0 0 0          <put the real numbers here>
0 1 1 0
0 1 1 0
0 0 0 0
```

Finish with one sentence on what this degradation leaves untouched, because that is
usually what makes it a useful test.

## Severity scale

TODO(fill) What are the physical units of the severity number, and
what does each step of the ladder correspond to? If the severity is calibrated rather
than absolute — a fraction of the field's characteristic scale, or of the energy a filter
removes — say so, and say what that means for comparing it across fields, because the
number applied to density and the number applied to vorticity will differ.

## Limitations

TODO(fill) Where this degradation is not a fair stand-in for the
failure it imitates, where its severities stop being distinguishable, and any field whose
spectrum cannot resolve the whole ladder. If a severity level can collapse onto a milder
one or onto a no-op, say under what conditions.

## Exemplars

### The panel

<!-- GENERATED exemplars: written by `python -m fmeval.cards exemplars <name>`, do not edit -->

Not generated yet. Run `python -m fmeval.cards exemplars <name>`.

<!-- END GENERATED exemplars -->

TODO(fill) No mathematical notation. The figure does not explain
itself. Say what changes between the weak and the strong columns, which diagnostic row
makes it visible, and what a reader should check first. If the effect is invisible in the
field images and only shows up in one of the other rows, say that explicitly — that is
exactly the situation a reader will otherwise misread.

## References

\bibliography
