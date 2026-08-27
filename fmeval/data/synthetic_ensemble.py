"""A generated ensemble whose right answer is known in closed form.

Every other reader in this package opens a file. This one computes its frames, because
what it exists to provide is not data but a *calibrated null*: an ensemble for which the
correct value of every probabilistic metric can be written down and checked, so a metric
that disagrees is wrong rather than merely surprising. No ensemble of real flow
realizations exists yet (see ``issues/004-independent-realizations.md``); when one does,
these metrics will already have been validated against a case with no unknowns in it.

**The construction.** For each field, frame and cell,

.. math::

    \\text{truth} = b(x, t) + \\sigma \\varepsilon_0, \\qquad
    m_i = b(x, t) + \\sigma \\varepsilon_i, \\quad i = 1 \\dots N,

with every :math:`\\varepsilon` an independent standard normal and :math:`b` a
deterministic two-scale field that evolves with ``t``. The reference uses **the same**
:math:`\\sigma` as the members and is drawn independently of all of them, which makes the
reference and the members exchangeable: the truth is statistically indistinguishable from
an :math:`(N+1)`-th member. That single property is what pins the analytic targets --

* the rank of the reference among the members is uniform on :math:`\\{0 \\dots N\\}`, so a
  rank histogram is flat and its reliability index is zero up to sampling noise;
* the RMS ensemble spread equals the RMSE of the ensemble mean, up to the finite-ensemble
  factor :math:`\\sqrt{(N+1)/N}`, so the spread-to-skill ratio is one;
* CRPS matches the closed form for a normal predictive distribution.

The deterministic part is not decoration. A field of pure noise would make blur,
coarsening and low-pass degradations indistinguishable, exactly as ``tests/conftest.py``
explains for the synthetic fields there; this generator uses the same two-scale shape so
the miscalibration ladder acts on something with structure.

**This is not physical evidence.** It exercises a code path and validates estimators. Its
complexity rank is below every physical dataset for that reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from ..context import derive_rng
from .base import FIELDS, GridSpec, NanPolicy, Trajectory, register_reader


def base_field(
    shape: tuple[int, ...], n_channels: int, *, phase_t: float = 0.0
) -> np.ndarray:
    """The deterministic part: a periodic, two-scale field that drifts with ``phase_t``.

    Deliberately the same shape of function as ``tests.conftest.synthetic_field`` -- one
    large scale, one small scale, a per-channel phase offset -- so that a smoothing
    degradation bites the small scale first here exactly as it does there.

    Args:
        shape: Spatial extents, in ``(x, y[, z])`` order.
        n_channels: Number of channels; each gets its own phase offset.
        phase_t: Temporal phase, advancing the pattern from frame to frame.

    Returns:
        Array of shape ``(n_channels, *shape)``, float64, periodic on every axis.
    """
    coords = np.meshgrid(*[2 * np.pi * np.arange(n) / n for n in shape], indexing="ij")
    out = np.empty((n_channels, *shape), dtype=np.float64)
    for c in range(n_channels):
        phase = 0.7 * c + phase_t
        large = np.sin(coords[0] + phase)
        small = 0.35 * np.cos(4 * coords[0] + phase)
        for axis in coords[1:]:
            large = large * np.cos(axis + phase)
            small = small + 0.35 * np.sin(3 * axis + phase)
        out[c] = large + small
    return out


@register_reader("synthetic_ensemble")
class SyntheticEnsembleTrajectory(Trajectory):
    """An exchangeable Gaussian ensemble, generated on the fly from a seed."""

    is_ensemble = True

    def __init__(
        self,
        path: str | None = None,
        *,
        grid: Sequence[int] = (32, 32),
        n_members: int = 8,
        n_frames: int = 8,
        fields: Sequence[str] = ("density",),
        sigma: float = 0.15,
        omega: float = 0.35,
        seed: int = 0,
        nan_policy: NanPolicy = "error",
    ) -> None:
        """Configure the generator.

        Args:
            path: Ignored. Accepted so every reader can be constructed the same way from
                a dataset config; nothing is read from disk.
            grid: Spatial extents, in ``(x, y[, z])`` order.
            n_members: Ensemble size ``N``. At least two, since a spread needs two.
            n_frames: Number of frames to generate.
            fields: Canonical field names to expose.
            sigma: Dispersion of both the members and the reference. The knob that makes
                the ensemble wide or narrow; identical for both by construction, which is
                what exchangeability means here.
            omega: Temporal phase advance per frame of the deterministic part.
            seed: Master seed. Every draw derives from it deterministically.
            nan_policy: Passed through to the base validation.

        Raises:
            ValueError: On an unknown field, a degenerate ensemble size, or a
                non-positive sigma.
        """
        unknown = set(fields) - set(FIELDS)
        if unknown:
            raise ValueError(f"unknown canonical field(s): {sorted(unknown)}")
        if n_members < 2:
            raise ValueError(f"n_members must be >= 2 to have a spread, got {n_members}")
        if n_frames < 1:
            raise ValueError(f"n_frames must be >= 1, got {n_frames}")
        if sigma <= 0:
            raise ValueError(f"sigma must be > 0, got {sigma}")

        self.path = path
        self.nan_policy = nan_policy
        self._grid_shape = tuple(int(n) for n in grid)
        self._n_members = int(n_members)
        self._n_frames = int(n_frames)
        self._fields = tuple(fields)
        self._sigma = float(sigma)
        self._omega = float(omega)
        self._seed = int(seed)

    # --- the Trajectory contract ------------------------------------------------------

    @property
    def fields(self) -> tuple[str, ...]:
        return self._fields

    @property
    def times(self) -> np.ndarray:
        return np.arange(self._n_frames, dtype=float)

    @property
    def grid(self) -> GridSpec:
        n = len(self._grid_shape)
        return GridSpec(
            shape=self._grid_shape,
            spacing=(1.0,) * n,
            periodic=(True,) * n,
            dims=("x", "y", "z")[:n],
            origin=(0.0,) * n,
        )

    @property
    def meta(self) -> dict[str, Any]:
        return {
            "format": "synthetic_ensemble",
            "path": None,
            "n_members": self._n_members,
            "n_frames": self._n_frames,
            "grid": self._grid_shape,
            "sigma": self._sigma,
            "omega": self._omega,
            "seed": self._seed,
            "fields": list(self._fields),
            "notes": (
                "Generated, not measured. Reference and members are independent draws "
                "from one N(base, sigma^2) process, hence exchangeable. Not physical "
                "evidence."
            ),
        }

    @property
    def n_members(self) -> int:
        return self._n_members

    def read_frame(self, t: int, fields: Sequence[str]) -> dict[str, np.ndarray]:
        """Generate one frame: a reference realization and ``N`` members per field."""
        grid = self.grid
        out: dict[str, np.ndarray] = {}
        for name in fields:
            n_channels = FIELDS[name].n_channels(grid.n_spatial)
            base = base_field(
                self._grid_shape, n_channels, phase_t=self._omega * float(t)
            )

            # One generator per (member, frame, field), derived from content rather than
            # from call order, so a frame reads identically however the run reaches it.
            ref_rng = derive_rng(self._seed, "reference", t, name)
            out[name] = base + self._sigma * ref_rng.standard_normal(base.shape)

            members = np.empty((self._n_members, *base.shape), dtype=np.float64)
            for i in range(self._n_members):
                rng = derive_rng(self._seed, f"member{i}", t, name)
                members[i] = base + self._sigma * rng.standard_normal(base.shape)
            out[f"{name}__members"] = members
        return out
