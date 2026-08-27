"""Registry of degradation operators.

Same shape and same discovery mechanism as the metric registry, so adding a degradation is
one decorated function in one file::

    @degradation(family="smoothing", severity_name="sigma", severity_units="cells")
    def gaussian_blur(x, severity, *, ctx):
        '''Isotropic Gaussian kernel smoothing, periodic wrap.'''
        return gaussian_filter(x, sigma=severity, mode="wrap", axes=ctx.spatial_axes)

**Operators act on one field at a time**, ``(C, *spatial) -> (C, *spatial)``. That keeps
almost every operator a two-line pure array function. The ladder builder applies the
operator to each requested field with an RNG derived from
``(seed, label, frame_index, field)``, so deterministic operators stay automatically
consistent across fields while stochastic ones get independent draws. An operator that
genuinely needs cross-field access declares ``whole_frame=True``.

Two pieces of metadata exist to stop silent corruption of every Spearman downstream:

``severity_direction``
    Whether damage rises or falls with the severity value. The builder sorts each severity
    list into increasing-damage order, so a low-pass cutoff list written ``[64, 32, 16, 8]``
    gets the right ordinal levels instead of a perfectly inverted ladder.

``ordinal``
    Whether the operator lies on a monotone axis at all. The IN-4 impostor does not; it is
    a pass/fail canary, and folding it in as "level 6" of some family would corrupt every
    rank correlation it touched.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Literal

Direction = Literal["increasing", "decreasing"]

#: What an operator's severity is expressed relative to. ``None`` means absolute units.
#:
#: ``"energy_above"`` / ``"energy_below"`` -- the severity is the fraction of the field's
#: fluctuation energy the operator destroys, resolved to a cutoff wavenumber against the
#: measured spectrum. The two differ by which side of the cutoff is removed: a low-pass removes
#: what lies *above* it, a high-pass what lies *below*. Declaring the wrong one silently
#: inverts the axis, which is why it is the operator's business to say and not the ladder's to
#: guess: with the sides swapped, "remove 5% of the energy" resolves to the wavenumber holding
#: 5% of it and removes 95% instead.
#: ``"scale"`` -- the severity is a fraction of the field's characteristic scale, resolved to a
#: length in cells.
#:
#: Absolute units are right where the number is already field-independent (a coarsening factor,
#: a displacement in cells) or already relative to something measured (noise as a fraction of
#: the fluctuation RMS). They are wrong for a wavenumber or a smoothing width, because those
#: land in completely different places depending on where the field keeps its energy.
Calibration = Literal["energy_above", "energy_below", "scale"]

#: Coarse grouping, used for plot colour and for the "worst axis" summary. NOT the unit of
#: rank correlation -- that is the ladder entry, since `gaussian_blur` and `median_blur`
#: are separate ordinal axes even though both are `smoothing`.
FAMILIES = (
    "identity",
    "smoothing",
    "spectral",
    "geometric",
    "resolution",
    "stochastic",
    "pointwise",
    "ensemble",
)


@dataclass(frozen=True)
class DegradationSpec:
    """Everything the harness knows about one degradation operator."""

    name: str
    fn: Callable[..., Any]
    family: str
    severity_name: str
    severity_units: str
    severity_direction: Direction
    calibration: Calibration | None
    ordinal: bool
    stochastic: bool
    fields: tuple[str, ...]
    whole_frame: bool
    doc: str
    module: str
    takes_ctx: bool
    defaults: dict[str, Any] = dc_field(default_factory=dict)
    ensemble: bool = False
    """Whether the operator acts on the whole ``(N, C, *spatial)`` member stack.

    An ordinary operator is applied to each member independently, which is the right
    thing for anything that models a per-member fault -- bias, noise, smoothing. An
    operator that changes the ensemble's *dispersion* cannot work that way, because
    scaling one member about its own value is meaningless; it needs to see the members
    together, and declares this.
    """

    def sort_severities(self, severities: Sequence[float]) -> list[float]:
        """Order a severity list by increasing damage.

        A ``decreasing`` operator (low-pass cutoff, say) is sorted descending, so index 0
        is always the mildest severity level whatever order the config author wrote.
        """
        return sorted(severities, reverse=self.severity_direction == "decreasing")


REGISTRY: dict[str, DegradationSpec] = {}
CARD_VALIDATOR: Callable[[Any], None] | None = None
"""Optional check run when a degradation is requested by name.

:mod:`fmeval.cards` installs a validator here that reads the degradation's card and refuses
to hand back a spec whose documentation is missing or contradicts the code. It is a hook
rather than a direct import for two reasons: this module would otherwise depend on the
whole harness (and its pandas and matplotlib dependencies) when it needs only numpy, and
validating at *lookup* rather than at *import* means a half-written card in one bundle
cannot break an unrelated run. See ``fmeval/cards/loader.py``.
"""

_IMPORT_ERRORS: dict[str, Exception] = {}
_DISCOVERED = False


def degradation(
    *,
    name: str | None = None,
    family: str = "stochastic",
    severity_name: str = "severity",
    severity_units: str = "",
    severity_direction: Direction = "increasing",
    calibration: Calibration | None = None,
    ordinal: bool = True,
    stochastic: bool = False,
    fields: Sequence[str] = ("*",),
    whole_frame: bool = False,
    ensemble: bool = False,
    defaults: dict[str, Any] | None = None,
) -> Callable[[Callable], Callable]:
    """Register a degradation operator.

    Args:
        name: Registry key. Defaults to the function name.
        family: One of :data:`FAMILIES`. Grouping only, never the correlation unit.
        severity_name: What the severity number means, e.g. ``"sigma"``, ``"cutoff"``.
            Used as the axis label wherever the ladder is plotted.
        severity_units: e.g. ``"cells"``, ``"wavenumber"``, ``"fraction of rms"``.
        severity_direction: ``"increasing"`` if larger severity means more damage,
            ``"decreasing"`` if smaller does.
        calibration: What the severity is relative to, or None for absolute units. See
            :data:`Calibration`. A calibrated severity is resolved per field against a
            measured spectrum, so the same config number means the same thing on a smooth
            field and a broadband one.
        ordinal: Whether this operator participates in monotonicity and Spearman. False
            for the IN-4 canary.
        stochastic: Whether to redraw the RNG per frame. A frozen noise field would be a
            systematic bias rather than noise.
        fields: Canonical field names it can act on; ``("*",)`` means any.
        whole_frame: Receive the whole ``dict[str, ndarray]`` instead of one array. For
            the rare operator needing cross-field access.
        ensemble: Receive one field's ``(N, C, *spatial)`` member stack instead of a
            single array. For an operator that changes the ensemble's dispersion, which
            cannot be expressed member by member. Mutually exclusive with
            ``whole_frame``. Operators that do not declare it are applied to each member
            independently when the frame carries an ensemble.
        defaults: Default keyword options, overridable per ladder entry in config.

    Returns:
        The undecorated function.
    """

    def _decorate(fn: Callable) -> Callable:
        key = name or fn.__name__
        if key in REGISTRY:
            raise ValueError(
                f"duplicate degradation {key!r}: {REGISTRY[key].module} vs {fn.__module__}"
            )
        if family not in FAMILIES:
            raise ValueError(
                f"{key}: unknown family {family!r}; expected one of {FAMILIES}"
            )
        if ensemble and whole_frame:
            raise ValueError(
                f"{key}: declares both ensemble and whole_frame; one receives the member "
                "stack of a single field, the other the field mapping of a whole frame"
            )

        params = inspect.signature(fn).parameters
        n_pos = sum(
            p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
            for p in params.values()
        )
        if n_pos != 2:
            raise TypeError(
                f"{key}: a degradation takes 2 positional arguments (field, severity), "
                f"found {n_pos}"
            )

        REGISTRY[key] = DegradationSpec(
            name=key,
            fn=fn,
            family=family,
            severity_name=severity_name,
            severity_units=severity_units,
            severity_direction=severity_direction,
            calibration=calibration,
            ordinal=ordinal,
            stochastic=stochastic,
            fields=tuple(fields),
            whole_frame=whole_frame,
            doc=(fn.__doc__ or "").strip(),
            module=fn.__module__,
            takes_ctx="ctx" in params,
            defaults=dict(defaults or {}),
            ensemble=ensemble,
        )
        return fn

    return _decorate


def discover(force: bool = False) -> dict[str, Exception]:
    """Import every module under ``degradations/`` so the decorators fire.

    Import errors are collected rather than raised, for the same reason as in the metric
    registry: a broken work-in-progress file must not abort everyone's run.
    """
    global _DISCOVERED
    if _DISCOVERED and not force:
        return _IMPORT_ERRORS

    import degradations as _pkg

    for mod in pkgutil.walk_packages(_pkg.__path__, prefix=f"{_pkg.__name__}."):
        # Every component after the package name is checked, not just the last one:
        # a bundle directory named `_template` must not be entered even though the
        # module inside it is called `metric`. Leading underscores mark templates and
        # shared helpers; `test_` marks the tests that live inside each bundle, which
        # would otherwise drag pytest into every evaluation run.
        parts = mod.name.split(".")[1:]
        if any(p.startswith(("_", "test_")) for p in parts) or parts[-1] == "registry":
            continue
        try:
            importlib.import_module(mod.name)
        except Exception as exc:  # noqa: BLE001 - deliberate, see docstring
            _IMPORT_ERRORS[mod.name] = exc
    _DISCOVERED = True
    return _IMPORT_ERRORS


def get(name: str) -> DegradationSpec:
    """Look up a degradation by name, running discovery first if needed."""
    if name not in REGISTRY:
        errors = discover()
        if name not in REGISTRY:
            hint = ""
            if errors:
                broken = ", ".join(f"{m}: {e!r}" for m, e in errors.items())
                hint = f"\n(modules that failed to import: {broken})"
            raise KeyError(
                f"unknown degradation {name!r}; available: {sorted(REGISTRY)}{hint}"
            )
    spec = REGISTRY[name]
    if CARD_VALIDATOR is not None:
        CARD_VALIDATOR(spec)
    return spec


def available() -> list[str]:
    """Names of every registered degradation, after discovery."""
    discover()
    return sorted(REGISTRY)


def _main() -> None:
    """Print the registry as a table. Entry point for ``python -m degradations``."""
    discover()
    if not REGISTRY:
        print("no degradations registered")
        return
    rows = [
        (
            s.name,
            s.family,
            f"{s.severity_name} [{s.severity_units}]" if s.severity_units
            else s.severity_name,
            s.calibration or "absolute",
            s.severity_direction,
            "yes" if s.ordinal else "NO (canary)",
            "yes" if s.stochastic else "-",
            ",".join(s.fields),
        )
        for s in sorted(REGISTRY.values(), key=lambda s: (s.family, s.name))
    ]
    head = ("degradation", "family", "severity", "relative to", "direction", "ordinal",
            "stoch", "fields")
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(head)]
    line = "  ".join(h.ljust(w) for h, w in zip(head, widths))
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))
    for mod, exc in _IMPORT_ERRORS.items():
        print(f"\n!! {mod} failed to import: {exc!r}")
