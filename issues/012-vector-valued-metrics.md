# Metrics returning spectra or PDFs

**Category:** deferred functionality
**Priority:** medium
**Status:** open

## Context

Some candidates naturally return a vector rather than a scalar: an energy spectrum, a
velocity-increment PDF, a persistence diagram summary. The registry already declares
`returns="vector"` and the pipeline expands such a metric into one row per component with a
`component` column, so the plumbing exists.

What is missing is the reporting: no renderer consumes vector output, and the analysis
treats every component as an independent scalar, which is wrong for a spectrum.

The pattern that probably wants following is to register the *scalarisation* as the metric
that enters the panel -- a Wasserstein distance between two spectra, say -- and treat the raw
spectrum as a diagnostic artefact rendered separately.

## What is needed

A vector store parallel to the tidy frame, and two renderers: a spectrum overlay and a
PDF overlay, each showing reference against variants. Both are also the natural home for the
flatness annotation that makes the Gaussian-field comparison self-evident.

## Acceptance criteria

A vector-returning metric runs end to end and its spectrum renders, with the scalar
reduction appearing in the summary alongside the other metrics.

## Related

`metrics/registry.py` (`returns`); `component` in `fmeval/pipeline.py`. BD-1, BD-4, OT-5, PS-4.
