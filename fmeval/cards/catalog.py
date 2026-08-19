"""The machine surface: every bundle's typed facts in one file.

`docs/catalog.json` is what an agent reads to answer a structural question -- what metrics
exist, what they return, what properties they have, how they behaved -- without parsing
prose. Prose is written for people and changes wording freely; a catalog entry is a
contract.

Nothing here is a new source of truth. Each entry merges three that already exist: the
registry spec, which the code declares; the card, which the author writes; and the
fingerprint, which the evidence generator measures. Where they disagree the merge does not
pick a winner -- disagreement means something is wrong and the card checks catch it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .loader import Bundle, iter_bundles, load_card

SCHEMA_VERSION = 1
"""Bump when an entry's shape changes in a way a consumer could not ignore."""


def _spec_fields(bundle: Bundle) -> dict[str, Any]:
    """What the code declares about this metric or degradation.

    Read from the registry rather than the card, so a catalog entry cannot claim a metric
    is differentiable when its decorator says otherwise.
    """
    if bundle.kind == "metric":
        from metrics import registry

        spec = registry.get(bundle.name)
        return {
            "arity": spec.arity,
            "fields": list(spec.fields),
            "returns": spec.returns,
            "units": spec.units,
            "cost": spec.cost,
            "differentiable": spec.differentiable,
            "symmetric": spec.symmetric,
            "higher_is_better": spec.higher_is_better,
            "reduction": spec.reduction,
            "has_pointwise_map": spec.has_pointwise,
        }

    from degradations import registry as deg

    spec = deg.get(bundle.name)
    return {
        "family": spec.family,
        "severity_name": spec.severity_name,
        "severity_units": spec.severity_units,
        "severity_direction": spec.severity_direction,
        "calibration": spec.calibration,
        "ordinal": spec.ordinal,
        "stochastic": spec.stochastic,
        "fields": list(spec.fields),
    }


def _measured(bundle: Bundle) -> dict[str, Any]:
    """What the recorded run measured, or an explicit statement that nothing has.

    A consumer must be able to tell "no measurements yet" from "measured and unremarkable"
    without inferring it from a missing key, so the shape is the same either way.
    """
    fingerprint = bundle.path / "_generated" / "fingerprint.json"
    if not fingerprint.is_file():
        return {"measured": False, "run": None, "dataset": None, "axes": [], "probes": []}

    data = json.loads(fingerprint.read_text())
    axes = [
        {
            "axis": row["degradation"],
            "field": row["field"],
            "family": row.get("degradation_family"),
            "is_probe": bool(row.get("is_probe")),
            "levels": row.get("n_levels"),
            "rank_correlation": row.get("rho"),
            "monotone_fraction": row.get("monotone_fraction"),
            "weakest_separation": row.get("separability_auc_min"),
            "first_detected_level": row.get("sensitivity_level"),
        }
        for row in data.get("axes", [])
    ]
    probes = [
        {
            "field": row["field"],
            "impostor_damage": row.get("gaussian_impostor_damage"),
            "impostor_nearest_level": row.get("gaussian_impostor_nearest_level"),
            "unrelated_field_value": row.get("uncorrelated_value"),
        }
        for row in data.get("probes", [])
    ]
    return {
        "measured": True,
        "run": data.get("run"),
        "dataset": data.get("dataset"),
        "frames": len(data.get("frames", [])),
        "axes": axes,
        "probes": probes,
    }


def entry(bundle: Bundle) -> dict[str, Any]:
    """One catalog entry: the code's declaration, the card, and the measurements."""
    card = load_card(bundle)
    review = card.review
    return {
        "name": card.name,
        "kind": card.kind,
        "category": card.category,
        "summary": card.summary,
        "status": card.status,
        "owners": list(card.owners),
        "path": f"{bundle.path.parent.name}/{bundle.path.name}",
        "card": f"{bundle.path.parent.name}/{bundle.path.name}/card.md",
        "declared": _spec_fields(bundle),
        "math": (
            {
                "triangle_inequality": card.math.triangle_inequality,
                "scale_dependent": card.math.scale_dependent,
                "resolution_dependent": card.math.resolution_dependent,
                "complexity": card.math.complexity,
            }
            if card.math is not None
            else None
        ),
        "output": {"description": card.output.description,
                   "lower_bound": card.output.lower,
                   "upper_bound": card.output.upper},
        "evidence": _measured(bundle),
        "reviewed": review is not None,
        "reviewed_by": review.reviewer if review else None,
        "reviewed_at": review.date.isoformat() if review else None,
    }


def build() -> dict[str, Any]:
    """The whole catalog, metrics and degradations together, sorted by name."""
    entries = sorted((entry(b) for b in iter_bundles()), key=lambda e: (e["kind"], e["name"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "counts": {
            "metrics": sum(1 for e in entries if e["kind"] == "metric"),
            "degradations": sum(1 for e in entries if e["kind"] == "degradation"),
            "with_measurements": sum(1 for e in entries if e["evidence"]["measured"]),
            "reviewed": sum(1 for e in entries if e["reviewed"]),
        },
        "entries": entries,
    }


def write(path: Path) -> Path:
    """Write the catalog, sorted and with a trailing newline so diffs stay readable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n")
    return path
