"""The registry's two extensions for probabilistic metrics.

**A third arity.** ``ensemble`` metrics take ``fn(reference, members)`` where members is
``(N, C, *spatial)``. The positional count is the same as ``pairwise``, so the arity
itself -- not the signature -- is what tells the pipeline which of the two to build.

**A declared target.** Most metrics are best at zero and worse as the number grows. The
spread-to-skill ratio is best at *one*, and worse in both directions. Rather than
transform the metric into something monotone and report a number no one else in the
literature reports, the metric declares where its good value is and the analysis layer
orients itself accordingly.
"""

from __future__ import annotations

import numpy as np
import pytest

from metrics import registry


def test_ensemble_arity_registers():
    @registry.metric(name="_probe_ensemble_ok", arity="ensemble")
    def _fn(reference: np.ndarray, members: np.ndarray) -> float:
        return 0.0

    try:
        spec = registry.REGISTRY["_probe_ensemble_ok"]
        assert spec.arity == "ensemble"
    finally:
        registry.REGISTRY.pop("_probe_ensemble_ok", None)


def test_ensemble_arity_requires_two_positional_arguments():
    with pytest.raises(TypeError, match="positional"):

        @registry.metric(name="_probe_ensemble_bad", arity="ensemble")
        def _fn(only_one: np.ndarray) -> float:
            return 0.0

    registry.REGISTRY.pop("_probe_ensemble_bad", None)


def test_target_defaults_to_none():
    @registry.metric(name="_probe_no_target", arity="pairwise")
    def _fn(a: np.ndarray, b: np.ndarray) -> float:
        return 0.0

    try:
        assert registry.REGISTRY["_probe_no_target"].target is None
    finally:
        registry.REGISTRY.pop("_probe_no_target", None)


def test_target_is_recorded():
    @registry.metric(name="_probe_target", arity="ensemble", target=1.0)
    def _fn(reference: np.ndarray, members: np.ndarray) -> float:
        return 1.0

    try:
        assert registry.REGISTRY["_probe_target"].target == 1.0
    finally:
        registry.REGISTRY.pop("_probe_target", None)


def test_a_target_must_be_finite():
    """A NaN or infinite target would silently disable the orientation it exists for."""
    with pytest.raises(ValueError, match="target"):

        @registry.metric(name="_probe_bad_target", arity="ensemble", target=float("nan"))
        def _fn(reference: np.ndarray, members: np.ndarray) -> float:
            return 0.0

    registry.REGISTRY.pop("_probe_bad_target", None)


def test_a_target_metric_cannot_also_claim_higher_is_better():
    """The two are different orientation models; declaring both is a contradiction."""
    with pytest.raises(ValueError, match="target"):

        @registry.metric(
            name="_probe_target_conflict",
            arity="ensemble",
            target=1.0,
            higher_is_better=True,
        )
        def _fn(reference: np.ndarray, members: np.ndarray) -> float:
            return 0.0

    registry.REGISTRY.pop("_probe_target_conflict", None)
