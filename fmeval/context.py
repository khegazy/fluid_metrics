"""Context objects passed to metrics and degradations that ask for one.

A function opts in simply by declaring a keyword-only ``ctx`` parameter; the registries
detect that at registration time. The point is that the common case -- ``mae(a, b)`` --
needs no boilerplate, while an operator that needs grid spacing or an RNG can have it
without every operator paying for it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from .data.base import GridSpec


@dataclass(frozen=True)
class FieldContext:
    """Everything an operator might need about the field it is acting on."""

    field: str
    grid: GridSpec
    frame_index: int
    time: float
    #: Fluctuation RMS of the *reference* field: the field minus its spatial mean. Noise
    #: amplitudes are specified relative to this rather than to the raw RMS, because
    #: density is 1.0 +/- 1.8e-4 and a fraction of the raw RMS would be pure destruction.
    fluctuation_rms: float
    rng: np.random.Generator

    @property
    def spatial_axes(self) -> tuple[int, ...]:
        """Negative axis indices of the spatial dimensions, in (x, y, z) order."""
        return tuple(range(-self.grid.n_spatial, 0))

    def axis(self, dim: str) -> int:
        """Negative axis index of a named dimension. Never hardcode -1 or -2."""
        return self.grid.axis(dim)


# Alias: metrics and degradations receive the same object, but the two registries talk
# about it in their own vocabulary.
MetricContext = FieldContext


def fluctuation_rms(x: np.ndarray) -> float:
    """RMS of ``x`` about its spatial mean, per channel then pooled.

    The scale that noise and gain severities are expressed in. Zero for a uniform field,
    which callers must handle.
    """
    spatial = tuple(range(1, x.ndim))
    fluct = x - x.mean(axis=spatial, keepdims=True)
    return float(np.sqrt((fluct**2).mean()))


def derive_rng(seed: int, label: str, frame_index: int, field: str) -> np.random.Generator:
    """A generator determined entirely by its inputs, never by call order.

    Uses :mod:`hashlib`, not the builtin ``hash()``, which is salted per process and would
    make results irreproducible across runs.

    Deriving from content rather than advancing one shared generator makes results
    invariant to the time reduction factor, to ladder ordering, to metric selection, and
    to any future parallelisation over frames. That last one is the reason it is worth the
    extra lines: when an expensive metric forces a process pool, the numbers must not move.
    """

    def _h(text: str) -> int:
        return int.from_bytes(
            hashlib.blake2b(text.encode(), digest_size=8).digest(), "little"
        )

    return np.random.default_rng([seed, _h(label), int(frame_index), _h(field)])
