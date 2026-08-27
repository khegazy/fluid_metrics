"""Shared validation for ensemble-arity metrics.

Kept in a leading-underscore module so :func:`metrics.registry.discover` skips it: it is a
helper, not a bundle. The check it performs is the one that separates a wrong answer from
an exception. A member stack handed over as ``(C, N, *spatial)`` instead of
``(N, C, *spatial)`` has the same size and dtype as the right thing, so every metric here
would reduce over the channel axis, average the wrong quantity, and return a number that
looks entirely plausible.
"""

from __future__ import annotations

import numpy as np


def as_ensemble(
    reference: np.ndarray, members: np.ndarray, *, min_members: int = 1, what: str = "metric"
) -> tuple[np.ndarray, np.ndarray]:
    """Validate and normalise a ``(reference, members)`` pair.

    Args:
        reference: Reference realization, ``(C, *spatial)``.
        members: Ensemble members, ``(N, C, *spatial)`` with the member axis leading.
        min_members: Smallest ensemble this metric is defined for. Two for anything that
            needs a sample variance.
        what: Metric name, for the error message.

    Returns:
        The pair as contiguous float64 arrays.

    Raises:
        ValueError: If the member axis is missing, misplaced, or too short.
    """
    reference = np.ascontiguousarray(reference, dtype=np.float64)
    members = np.ascontiguousarray(members, dtype=np.float64)

    if members.ndim != reference.ndim + 1 or members.shape[1:] != reference.shape:
        raise ValueError(
            f"{what}: members has shape {members.shape}, expected "
            f"(N, *{reference.shape}) with the member axis leading"
        )
    if members.shape[0] < min_members:
        got = members.shape[0]
        need = "at least two members" if min_members >= 2 else "at least one member"
        raise ValueError(f"{what}: needs {need} to be defined, got {got}")
    return reference, members
