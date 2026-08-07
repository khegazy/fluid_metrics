"""Registry of metric functions.

A metric is an ordinary function decorated with :func:`metric`. The decorator records
metadata and returns the function *unwrapped*, so metrics stay directly importable and
testable without the harness and carry no per-call indirection.

Two arities are supported:

* ``arity="pairwise"`` -- ``fn(reference, candidate)``, both ``(C, *spatial)``
* ``arity="single"``   -- ``fn(x)``, ``(C, *spatial)``

If a function additionally declares a keyword-only parameter named ``ctx``, the pipeline
passes a :class:`~fmeval.context.MetricContext` carrying grid spacing, periodicity, the
field name and the physical time. Detection happens once, here, via :mod:`inspect`, so the
common case needs no boilerplate.

Some metrics are *pointwise-decomposable*: their scalar value is a reduction of a per-cell
density. Declare the companion map with :func:`pointwise_map` and the reduction with the
``reduction=`` argument; the contract test then verifies ``R(map(a, b)) == metric(a, b)``.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field as dc_field
from typing import Any, Literal

import numpy as np

Arity = Literal["pairwise", "single"]
Cost = Literal["cheap", "moderate", "expensive"]
Returns = Literal["scalar", "vector"]

#: How a pointwise map reduces to the metric's scalar value. ``C`` is the channel count of
#: the *input* field, because maps are summed over channels before reduction.
REDUCTIONS: dict[str, Callable[[np.ndarray, int], float]] = {
    "mean": lambda m, c: float(m.mean() / c),
    "sum": lambda m, c: float(m.sum()),
    "sqrt_mean": lambda m, c: float(np.sqrt(m.mean() / c)),
}


@dataclass(frozen=True)
class MetricSpec:
    """Everything the harness knows about one metric."""

    name: str
    fn: Callable[..., Any]
    tracker_id: str | None
    arity: Arity
    fields: tuple[str, ...]
    returns: Returns
    differentiable: bool
    cost: Cost
    higher_is_better: bool
    symmetric: bool
    units: str
    doc: str
    module: str
    takes_ctx: bool
    reduction: str
    pointwise: Callable[..., np.ndarray] | None = None
    defaults: dict[str, Any] = dc_field(default_factory=dict)

    @property
    def has_pointwise(self) -> bool:
        return self.pointwise is not None

    def reduce(self, map_: np.ndarray, n_channels: int) -> float:
        """Apply this metric's declared reduction to a pointwise map."""
        return REDUCTIONS[self.reduction](map_, n_channels)


REGISTRY: dict[str, MetricSpec] = {}
_IMPORT_ERRORS: dict[str, Exception] = {}
_DISCOVERED = False


def metric(
    *,
    name: str | None = None,
    tracker_id: str | None = None,
    arity: Arity = "pairwise",
    fields: Sequence[str] = ("*",),
    returns: Returns = "scalar",
    differentiable: bool = True,
    cost: Cost = "cheap",
    higher_is_better: bool = False,
    symmetric: bool = True,
    units: str = "field",
    reduction: str = "mean",
    defaults: dict[str, Any] | None = None,
) -> Callable[[Callable], Callable]:
    """Register a metric function under ``name`` (defaults to the function name).

    Args:
        name: Registry key. Defaults to ``fn.__name__``.
        tracker_id: Stable ID from ``Table_of_Ideas.tex`` (e.g. ``"NM-2"``).
        arity: ``"pairwise"`` for ``fn(reference, candidate)``, ``"single"`` for ``fn(x)``.
        fields: Canonical field names this metric accepts; ``("*",)`` means any.
        returns: ``"scalar"`` for a float, ``"vector"`` for a 1-D array.
        differentiable: Whether it could serve as a training loss. Declared, not inferred.
        cost: Advisory tier; the pipeline warns on expensive metrics over many frames.
        higher_is_better: Whether larger values mean a better match.
        symmetric: Pairwise only. Enables the symmetry contract test.
        units: Free text, e.g. ``"field"``, ``"field^2"``, ``"dimensionless"``.
        reduction: How a pointwise map reduces to the scalar. Key of :data:`REDUCTIONS`.
        defaults: Default keyword arguments, overridable from config.

    Returns:
        The undecorated function, so it stays a plain callable.

    Raises:
        ValueError: On a duplicate name or an unknown reduction.
        TypeError: If the positional-argument count does not match ``arity``.
    """

    def _decorate(fn: Callable) -> Callable:
        key = name or fn.__name__
        if key in REGISTRY:
            raise ValueError(
                f"duplicate metric {key!r}: {REGISTRY[key].module} vs {fn.__module__}"
            )
        if reduction not in REDUCTIONS:
            raise ValueError(
                f"{key}: unknown reduction {reduction!r}; expected one of {sorted(REDUCTIONS)}"
            )

        params = inspect.signature(fn).parameters
        takes_ctx = "ctx" in params
        n_pos = sum(
            p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
            for p in params.values()
        )
        expected = 2 if arity == "pairwise" else 1
        if n_pos != expected:
            raise TypeError(
                f"{key}: arity={arity!r} needs {expected} positional argument(s), "
                f"found {n_pos}"
            )

        REGISTRY[key] = MetricSpec(
            name=key,
            fn=fn,
            tracker_id=tracker_id,
            arity=arity,
            fields=tuple(fields),
            returns=returns,
            differentiable=differentiable,
            cost=cost,
            higher_is_better=higher_is_better,
            symmetric=symmetric,
            units=units,
            doc=(fn.__doc__ or "").strip(),
            module=fn.__module__,
            takes_ctx=takes_ctx,
            reduction=reduction,
            defaults=dict(defaults or {}),
        )
        return fn

    return _decorate


def pointwise_map(*, of: str) -> Callable[[Callable], Callable]:
    """Attach a per-cell density function to an already-registered metric.

    The map takes the same arguments as its metric and returns an array with the channel
    axis reduced away -- shape ``(*spatial)``. Reducing it with the metric's declared
    ``reduction`` must reproduce the metric's scalar; the contract test enforces that.

    Args:
        of: Name of the metric this map belongs to. Must already be registered, so the
            map is defined *after* its metric in the same module.
    """

    def _decorate(fn: Callable) -> Callable:
        if of not in REGISTRY:
            raise ValueError(
                f"pointwise_map(of={of!r}): metric is not registered; define the map "
                "after the metric it belongs to"
            )
        spec = REGISTRY[of]
        if spec.has_pointwise:
            raise ValueError(f"metric {of!r} already has a pointwise map")
        REGISTRY[of] = dataclasses.replace(spec, pointwise=fn)
        return fn

    return _decorate


def discover(force: bool = False) -> dict[str, Exception]:
    """Import every module under ``metrics/`` so the decorators fire.

    Import failures are collected rather than raised: one colleague's broken
    work-in-progress file must not abort everyone's run. The collected errors surface in
    the :func:`get` error message when a lookup actually misses.

    Args:
        force: Re-run discovery even if it has already been done.

    Returns:
        Mapping of module name to the exception it raised, empty if all imported.
    """
    global _DISCOVERED
    if _DISCOVERED and not force:
        return _IMPORT_ERRORS

    import metrics as _pkg

    for mod in pkgutil.walk_packages(_pkg.__path__, prefix=f"{_pkg.__name__}."):
        leaf = mod.name.rsplit(".", 1)[-1]
        if leaf.startswith("_") or leaf == "registry":
            continue
        try:
            importlib.import_module(mod.name)
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            _IMPORT_ERRORS[mod.name] = exc
    _DISCOVERED = True
    return _IMPORT_ERRORS


def get(name: str) -> MetricSpec:
    """Look up a metric by name, running discovery first if needed.

    Raises:
        KeyError: If no such metric exists. The message lists what is available and, if
            any metric modules failed to import, what went wrong with them.
    """
    if name not in REGISTRY:
        errors = discover()
        if name not in REGISTRY:
            hint = ""
            if errors:
                broken = ", ".join(f"{m}: {e!r}" for m, e in errors.items())
                hint = f"\n(modules that failed to import: {broken})"
            raise KeyError(
                f"unknown metric {name!r}; available: {sorted(REGISTRY)}{hint}"
            )
    return REGISTRY[name]


def available() -> list[str]:
    """Names of every registered metric, after discovery."""
    discover()
    return sorted(REGISTRY)


def _main() -> None:
    """Print the registry as a table. Entry point for ``python -m metrics``."""
    discover()
    if not REGISTRY:
        print("no metrics registered")
        return
    rows = [
        (
            s.name,
            s.tracker_id or "-",
            s.arity,
            ",".join(s.fields),
            s.units,
            s.cost,
            "yes" if s.has_pointwise else "-",
            "yes" if s.differentiable else "-",
        )
        for s in sorted(REGISTRY.values(), key=lambda s: (s.tracker_id or "", s.name))
    ]
    head = ("metric", "id", "arity", "fields", "units", "cost", "pointwise", "diff'able")
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(head)]
    line = "  ".join(h.ljust(w) for h, w in zip(head, widths))
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))
    for mod, exc in _IMPORT_ERRORS.items():
        print(f"\n!! {mod} failed to import: {exc!r}")
