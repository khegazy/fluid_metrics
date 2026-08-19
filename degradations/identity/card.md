---
name: identity
kind: degradation
---

## Definition

The field is returned unchanged:

$$
g(x) = f(x) \tag{1}
$$

Equation (1) is applied as the level-zero entry of every ladder, so that the reference
value each metric reports is produced by the same code path as every degraded value,
rather than by a separate branch that could diverge from it.

### Boundary handling

None, and trivially so: nothing is read but the cell itself.

## Intuition

This is not a degradation and does not stand in for any model failure. It is the
control.

Its purpose is to make the reference an ordinary member of the ladder rather than a
special case. Every degraded field is produced by taking the reference and applying an
operator; the reference itself is produced by taking the reference and applying this one.
That means the reference value cannot drift away from the degraded values through some
difference in how it was computed, remapped or stored, because there is no difference.

It also gives every pairwise error metric a hard check with a known answer:

```
before                 after (identity)
0 0 0 0                0 0 0 0
0 1 1 0                0 1 1 0
0 1 1 0                0 1 1 0
0 0 0 0                0 0 0 0
```

Any pairwise metric comparing this output against its input must return exactly zero, and
a metric that returns a small non-zero number instead has a defect worth finding before it
is used on anything harder.

What it leaves untouched is everything.

## Severity scale

There is no severity. The ladder carries one level, numbered zero, and the
configuration flag ``include_reference`` controls whether it is present.

## Limitations

There is nothing here to be a limitation of. The operator is exact, and the only way
it can mislead is if it were somehow not applied to the reference by the same path as the
degradations -- which is precisely the failure its existence prevents.

## Exemplars

### The panel

{{ include _generated/exemplars.md }}

There is no panel for this operator, and the card's exemplars block says so with
``mode: none``. A figure showing a field beside three identical copies of itself would
occupy space in the gallery without saying anything.

What to check instead is numerical: in any run, every pairwise error metric should report
exactly zero at level zero of every axis. A small non-zero value there indicates the
reference is reaching the metric by a different route from the degraded fields.

## References

\bibliography
