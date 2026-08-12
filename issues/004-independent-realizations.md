# Only one seed per configuration

**Category:** data generation
**Priority:** medium
**Status:** open

## Context

The unrelated-field anchor and the statistical-twin comparison are built by translating
the reference by a large random offset. On a periodic domain that preserves every statistic
exactly, and it is verified to do so -- variance ratio 1.000000, flatness matching to three
decimals -- so it is a sound construction.

But an *independent realisation* at the same physical parameters would be the stronger test,
because it separates "wrong phase" from "wrong realisation", which translation cannot. Every
run in `kinet/doubly_periodic/old/` carries `R0-1`, so there is one seed per configuration.

There is also a known limitation of the translation construction: it only decorrelates a
broadband field. For a field dominated by a single large-scale mode the residual correlation
is cos(2 pi d / L), which no offset makes reliably small. Real turbulence is broadband so this
does not bite here, but the spread across draws is the diagnostic and should be watched.

## What is needed

Two or more runs at identical physical parameters with different initial-condition seeds.

## Acceptance criteria

A second realisation is available, and the anchor measured from it agrees with the
translation-based anchor to within the spread across draws.

## Related

`degradations/geometric.py::random_large_translation`; `uncorrelated_value` in TEST_DESCRIPTION.md.
