"""Generate a degradation's exemplar panel from the one canonical frame.

Reads the frame named in ``configs/cards/default.yaml``, applies the operator at the three
severities the card declares, and renders the panel plus the numbers behind it. Every
panel in the repository comes from that one frame: two degradations illustrated on
different snapshots cannot be compared, which would defeat the gallery that puts all of
them on one page.

This reads the dataset directly and never a run folder. An exemplar shows what a
degradation does to a field, which is a property of the operator rather than of any
metric, so it needs no evaluation to have been performed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from omegaconf import OmegaConf

from degradations import registry as deg_registry
from fmeval.calibration import calibrate
from fmeval.context import FieldContext, derive_rng
from fmeval.ladder import resolve_severity, SeverityLevel

REPO = Path(__file__).resolve().parent.parent.parent
CARDS_CONFIG = REPO / "configs" / "cards" / "default.yaml"


@dataclass(frozen=True)
class CanonicalFrame:
    """The one snapshot every exemplar panel in the repository is drawn from."""

    index: int
    dataset: str
    fields: dict[str, np.ndarray]
    grid: Any
    time: float


def load_cards_config() -> Any:
    """Load the card-generation settings.

    Plain OmegaConf rather than Hydra: generating documentation is not an experiment and
    should not create a run folder or a ``.hydra`` directory.
    """
    return OmegaConf.load(CARDS_CONFIG)


def load_canonical_frame(cfg: Any | None = None) -> CanonicalFrame:
    """Read the canonical exemplar frame from the dataset it names.

    Args:
        cfg: Card settings; loaded from ``configs/cards/default.yaml`` if omitted.

    Returns:
        The frame, with every field the config asks to illustrate.

    Raises:
        FileNotFoundError: If the dataset is not reachable, which on a machine without the
            CFS mount is the expected outcome and the reason exemplars are generated where
            the data lives rather than in CI.
    """
    cfg = cfg or load_cards_config()
    # Read without resolving: the dataset configs interpolate ${paths.data}, which only
    # Hydra supplies. Documentation generation is not a Hydra run, so the one key that
    # matters is substituted directly below.
    dataset_cfg = OmegaConf.load(
        REPO / "configs" / "dataset" / f"{cfg.exemplar_frame.dataset}.yaml"
    )
    raw_path = OmegaConf.to_container(dataset_cfg, resolve=False)["path"]

    from fmeval.data import kinet_raw, well  # noqa: F401  (register the formats)
    from fmeval.data.base import READERS

    path = Path(str(raw_path).replace("${paths.data}", str(REPO / "datasets")))
    if not path.exists():
        raise FileNotFoundError(
            f"the canonical exemplar frame needs {path}, which is not readable here.\n"
            "Exemplar panels are generated where the data lives (NERSC) and committed, "
            "rather than in CI."
        )
    reader_kwargs = OmegaConf.to_container(dataset_cfg.get("reader", {}), resolve=True)
    trajectory = READERS[str(dataset_cfg.format)](path, **reader_kwargs)

    wanted = [f for f in cfg.exemplar_frame.fields if f in trajectory.fields]
    frame = trajectory.frame(int(cfg.exemplar_frame.index), wanted)
    return CanonicalFrame(index=int(cfg.exemplar_frame.index),
                          dataset=str(cfg.exemplar_frame.dataset),
                          fields=dict(frame.fields), grid=frame.grid, time=float(frame.time))


def build_columns(name: str, card: Any, frame: CanonicalFrame, *, seed: int) -> tuple[list, dict]:
    """Apply the operator at each declared severity and label the columns.

    Severities are resolved through the same path the ladder uses, so a calibrated axis
    shows the number that was actually applied to this field rather than the fraction that
    was configured. Titles carry that resolved value and its units, because "medium" does
    not describe a picture.

    Returns:
        The columns, and a record of what was applied for the fingerprint.
    """
    from .figures import Column

    spec = deg_registry.get(name)
    field_name = card.exemplars.field_name
    data = frame.fields[field_name]

    calibration = calibrate({field_name: [data]}, frame.grid, [field_name])
    columns = [Column(title="original", data=data)]
    applied: dict[str, Any] = {"severities": [], "resolved": [], "mode": card.exemplars.mode}

    if card.exemplars.mode == "draws":
        for draw in range(card.exemplars.n_draws):
            ctx = _context(field_name, frame, data, seed=seed, label=f"{name}_draw{draw}")
            columns.append(Column(title=f"draw {draw + 1}", data=spec.fn(data, float(draw), ctx=ctx)))
            applied["severities"].append(draw)
        return columns, applied

    for severity in card.exemplars.levels:
        level = SeverityLevel(
            label=name, op=name, family=spec.family, level=1, severity=float(severity),
            calibration=spec.calibration, severity_name=spec.severity_name,
            severity_units=spec.severity_units, ordinal=spec.ordinal,
            stochastic=spec.stochastic, options={},
        )
        resolved = resolve_severity(level, field_name, calibration)
        ctx = _context(field_name, frame, data, seed=seed, label=f"{name}_{severity}")
        columns.append(Column(title=_title(spec, resolved), data=spec.fn(data, resolved, ctx=ctx)))
        applied["severities"].append(float(severity))
        applied["resolved"].append(float(resolved))
    return columns, applied


def _title(spec: Any, resolved: float) -> str:
    """Panel title: the severity that was applied, with its units."""
    units = f" {spec.severity_units}" if spec.severity_units else ""
    return f"{spec.severity_name} = {resolved:.3g}{units}"


def _context(field_name: str, frame: CanonicalFrame, data: np.ndarray, *,
             seed: int, label: str) -> FieldContext:
    """A field context matching the one the pipeline builds, so panels match runs."""
    fluctuation = data - data.mean(axis=tuple(range(1, data.ndim)), keepdims=True)
    return FieldContext(
        field=field_name, grid=frame.grid, frame_index=frame.index, time=frame.time,
        fluctuation_rms=float(np.sqrt((fluctuation**2).mean())),
        rng=derive_rng(seed, label, frame.index, field_name),
    )


def generate(name: str, *, seed: int = 20260807) -> Path | None:
    """Render one degradation's exemplar panel and write its caption and numbers.

    Args:
        name: The degradation bundle to illustrate.
        seed: Run seed, so a stochastic operator's draws reproduce.

    Returns:
        The path to the written panel, or ``None`` if the card declares ``mode: none``.
    """
    from .figures import exemplar_panel
    from .loader import find_bundle, load_card

    bundle = find_bundle(name)
    if bundle is None:
        raise KeyError(f"no degradation bundle named {name!r}")
    card = load_card(bundle)
    if card.exemplars is None or card.exemplars.mode == "none":
        return None

    cfg = load_cards_config()
    frame = load_canonical_frame(cfg)
    columns, applied = build_columns(name, card, frame, seed=seed)

    out = bundle.path / "_generated"
    panel = exemplar_panel(
        columns, list(card.exemplars.diagnostics), path=out / "exemplars.png",
        title=f"{name} on {card.exemplars.field_name}, frame {frame.index}",
        grid=frame.grid, dpi=int(cfg.figures.dpi), theme=str(cfg.figures.theme),
    )

    fingerprint = {
        "degradation": name,
        "field": card.exemplars.field_name,
        "dataset": frame.dataset,
        "frame_index": frame.index,
        "time": frame.time,
        "seed": seed,
        "applied": applied,
        "panels": panel.statistics,
    }
    (out / "exemplars.json").write_text(json.dumps(fingerprint, indent=2, sort_keys=True) + "\n")
    (out / "exemplars.md").write_text(_caption(name, card, frame, applied, panel.statistics))
    return panel.path


def _caption(name: str, card: Any, frame: CanonicalFrame, applied: dict,
             statistics: dict) -> str:
    """The caption, stating what actually happened rather than what was expected.

    The card's rationale says why these severities were chosen; the measured numbers say
    what they did. Both belong under the figure, and only one of them can be written in
    advance.
    """
    lines = [
        "<!-- GENERATED by fmeval.cards.exemplars -- do not edit -->",
        "",
        f"![exemplar panel for {name}](exemplars.png)",
        "",
        f"**{name}** on {card.exemplars.field_name}, frame {frame.index} of "
        f"`{frame.dataset}`. {card.exemplars.rationale}",
        "",
    ]
    if applied["mode"] == "severity" and applied.get("resolved"):
        lines += ["| configured | applied | difference RMS | power retained |",
                  "|---|---|---|---|"]
        for configured, resolved in zip(applied["severities"], applied["resolved"]):
            title = None
            for key in statistics.get("field", {}):
                if key != "original":
                    title = key
            diff = statistics.get("difference", {})
            spectrum = statistics.get("radial_spectrum", {})
            keys = [k for k in diff if k != "original"]
            idx = applied["resolved"].index(resolved)
            k = keys[idx] if idx < len(keys) else None
            rms = f"{diff[k]['rms']:.4g}" if k and k in diff else "--"
            retained = f"{spectrum[k]['power_retained']:.4g}" if k and k in spectrum else "--"
            lines.append(f"| {configured:g} | {resolved:.4g} | {rms} | {retained} |")
        lines.append("")
    return "\n".join(lines) + "\n"
