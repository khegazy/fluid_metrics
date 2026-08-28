"""Where a dataset actually lives: the local copy, or the published one.

The `datasets` symlink points at `/global/cfs/cdirs/m4790/Data` and exists only on NERSC,
so a colleague on another cluster has no local copy at all. The same tree is published at
`paths.data_url`, mirroring `paths.data` one directory for one, which is what lets a
dataset config keep a single `path: ${paths.data}/kinet/...` and no per-dataset URL.

Measured against the production trajectory on 2026-08-27: the portal's `Content-Length` is
178271350284, exactly `os.path.getsize` of the CFS copy.

This module is the *only* place that decision is made. It deliberately imports nothing to
do with HTTP, so `fmeval.cards.exemplars` -- which resolves dataset paths without Hydra and
has no business opening a socket -- can share it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from omegaconf import OmegaConf

#: The interpolation a dataset config writes. `evaluate.py` gets it already expanded by
#: Hydra; `exemplars.py` loads configs unresolved and still has it as a literal.
DATA_TOKEN = "${paths.data}"

REPO = Path(__file__).resolve().parent.parent.parent
CONFIG = REPO / "configs" / "config.yaml"


def is_url(value: str | Path) -> bool:
    """Whether a location is an HTTP(S) URL rather than a filesystem path."""
    return str(value).startswith(("http://", "https://"))


@dataclass(frozen=True)
class DataLocation:
    """Where a dataset was found, and what to hand the reader."""

    source: Literal["local", "url"]
    local: Path
    """The local path the config names, whether or not it exists."""
    url: str | None
    """The mirrored URL, when one could be derived."""
    target: Path | str
    """The local path or the URL -- what the reader is actually opened on."""


def _relative_to(local: Path, data_root: Path) -> Path | None:
    """The part of `local` below `data_root`, or None if it is not below it.

    Tried lexically first and then against resolved paths, because `paths.data` is normally
    a symlink: a config may name `<repo>/datasets/kinet/...` while an override names the
    CFS path the symlink points at, and those are the same file.
    """
    for candidate, root in ((local, data_root), (local.resolve(), data_root.resolve())):
        try:
            return candidate.relative_to(root)
        except ValueError:
            continue
    return None


def resolve_dataset_path(
    raw_path: str | Path,
    data_root: str | Path,
    *,
    data_url: str | None = None,
    allow_url: bool = True,
) -> DataLocation:
    """Resolve a dataset config's `path` to a local file or a published URL.

    The local copy always wins: falling back to the network when the data is sitting on
    the filesystem would turn a one-second read into a network-bound one and silently
    change what a run measured.

    Args:
        raw_path: The dataset config's `path`, resolved by Hydra or still carrying the
            literal `${paths.data}` token.
        data_root: `paths.data`.
        data_url: `paths.data_url`, or None to refuse the network.
        allow_url: Whether the fallback may be taken at all.

    Returns:
        Where to read from.

    Raises:
        FileNotFoundError: If there is no local file and no URL can be derived. The
            message says which of the several reasons applies, because this is the error
            a new user hits first.
    """
    data_root = Path(str(data_root))
    local = Path(str(raw_path).replace(DATA_TOKEN, str(data_root)))

    relative = _relative_to(local, data_root)
    url: str | None = None
    if data_url and relative is not None:
        # Built from the relative path, never a second string substitution: `paths.data`
        # is a documented override, so the token is not always what stands in front of it.
        # Each segment is quoted -- a filename with a space or a `#` truncates a raw URL.
        url = data_url.rstrip("/") + "/" + "/".join(quote(p) for p in relative.parts)

    if local.exists():
        return DataLocation("local", local, url, local)

    if allow_url and url is not None:
        return DataLocation("url", local, url, url)

    raise FileNotFoundError(_why_unreachable(local, data_root, data_url, relative, allow_url))


def _why_unreachable(
    local: Path,
    data_root: Path,
    data_url: str | None,
    relative: Path | None,
    allow_url: bool,
) -> str:
    """Explain a missing dataset in terms of the cause, not the failed open."""
    lines = [f"no readable copy of {local.name}:", f"  local: {local} (does not exist)"]
    if not allow_url:
        lines += ["  remote: not attempted (the caller asked for a local copy only)"]
    elif not data_url:
        lines += [
            "  remote: not attempted (`paths.data_url` is null)",
            "",
            "Set `paths.data_url` to read the published copy over HTTP.",
        ]
    elif relative is None:
        lines += [
            f"  remote: no mirror (the path is not under `paths.data`, {data_root})",
            "",
            "The published tree mirrors `paths.data` one directory for one, so a path",
            "outside it has no URL to derive. Point `paths.data` at the root that",
            "contains this file, or name a file below it.",
        ]
    if not data_root.exists():
        lines += [
            "",
            f"The dataset root does not exist either: {data_root}",
            "",
            "That path comes from `paths.data` in configs/config.yaml, which defaults to a",
            "`datasets` symlink in the repository root. The symlink is gitignored because",
            "it is machine-specific, so a fresh clone does not have it. On NERSC:",
            "",
            "    ln -s /global/cfs/cdirs/m4790/Data datasets",
            "",
            "Elsewhere, leave it absent and let `paths.data_url` serve the data.",
        ]
    return "\n".join(lines)


def default_data_url() -> str | None:
    """`paths.data_url` from configs/config.yaml, read without Hydra.

    Safe because that key is a plain literal: `paths.data` interpolates
    `${hydra:runtime.cwd}` and would raise here, but it is never touched.
    """
    cfg = OmegaConf.load(CONFIG)
    return cfg.get("paths", {}).get("data_url")


def trajectory_provenance(trajectory: Any) -> dict[str, Any]:
    """What to record in `run_meta.json` about which copy of the data was read.

    Must be called before `close()`: the request counters live on the HTTP file object,
    which `close()` releases.
    """
    record: dict[str, Any] = {
        "source": getattr(trajectory, "location_source", "local"),
        "path": str(getattr(trajectory, "source", "")),
    }
    remote = getattr(trajectory, "_remote", None)
    if remote is not None:
        record.update(remote.provenance())
    return record
