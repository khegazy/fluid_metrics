"""The definition of what a ``card.yaml`` may contain, and the parser that enforces it.

This module is the single definition of the card schema. Nothing else in the repository
may hard-code a card field name; read the dataclasses here instead.

The guiding rule for what belongs in a card at all:

    Anything a machine can check, compare, or filter on lives in the typed card.
    Prose is reserved for what genuinely requires prose.

The second rule, which is what keeps the schema small: **a card never restates something
the code already declares.** Whether a metric is differentiable, symmetric, pairwise, or
expensive is declared on the ``@metric`` decorator and lives in its ``MetricSpec``; a
degradation's family, severity units and direction live in its ``DegradationSpec``. Those
are not repeated here, because two copies of a fact drift apart and the reader has no way
to tell which one is stale. The catalog merges the two sources at read time.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 1
"""Bump only for a change that invalidates existing cards; add a migration alongside.

See the module docstring of :mod:`fmeval.cards` for the versioning policy.
"""


# --------------------------------------------------------------------------------------
# Controlled vocabularies
# --------------------------------------------------------------------------------------

KINDS = ("metric", "degradation")

CATEGORIES = (
    "pointwise",
    "physical",
    "spectral",
    "statistical",
    "probabilistic",
    "transport",
    "functional",
    "geometric",
    "topological",
)
"""What kind of measurement a metric makes. Set by whoever adds the metric.

This is the primary way a reader browses: the navigation groups metrics by it, and it is
the first row of every metric's header table. Each name answers "what does this thing
look at?" rather than "how good is it" or "how far has the work got".

``pointwise``
    Compares the two fields cell by cell and never consults a neighbour. MAE, MSE, RMSE
    and NRMSE.
``physical``
    A conserved or derived physical quantity of the flow, characterising one field rather
    than comparing two. Enstrophy and kinetic energy.
``spectral``
    Compares scale by scale, in wavenumber. Reserved for metrics that actually resolve
    scales -- an energy-spectrum comparison, a band-limited error. Note that a quantity
    which merely *has* a spectral reading does not belong here: kinetic energy is the
    zeroth moment of E(k) and enstrophy the k^2-weighted moment, so that reading would
    put both in this bucket and separate neither, and both collapse the spectrum to a
    single number rather than resolving it.
``statistical``
    Compares distributions or moments of the field: increment PDFs, flatness, structure
    functions.
``probabilistic``
    Needs an ensemble. Spread, skill, CRPS. Mark N/A for a deterministic surrogate.
``transport``
    The cost of moving one field onto the other. Wasserstein and its relatives.
``functional``
    Norms that weight the scales differently from a plain average -- Sobolev, the
    negative-order norms.
``geometric``
    Where features are and what shape they have: shock-surface distances, feature
    displacement, curvature.
``topological``
    Which features exist and how they connect. Persistence diagrams.

The vocabulary is mathematical rather than tied to fluids, because this repository
evaluates metrics for PDEs in general -- compressible and incompressible flow, MHD,
ensemble data -- and a name drawn from one fluid phenomenon would not survive the second
application area. Degradation cards do not use this vocabulary: they reuse the ``family``
their registry entry already declares, and a test asserts the two agree.
"""

STATUSES = ("candidate", "validated", "deprecated")
"""How far the work on a bundle has got. **This is not a quality rating.**

``candidate``
    Implemented. Its evidence is either not yet generated or not yet reviewed by a human.
    This is the only status an agent may write.
``validated``
    The evaluation suite has been run on the canonical data *and* a human has read and
    signed the prose. It says the measurement was done and checked -- it does not say the
    results were good.
``deprecated``
    Superseded, kept so the record and any older results remain interpretable.

There was once a ``control`` status for the familiar baselines that candidates are read
against. It is gone, because it answered a different question from the other three and so
made the field mean two things at once: MSE was ``control`` and therefore could not also
say whether anyone had reviewed it. What kind of measurement a metric makes is now
``category``, which is orthogonal and is what the navigation groups by.

There is deliberately no ``rejected`` status, and nothing anywhere in this repository
reduces a metric to pass or fail. A metric that misses one thing usually catches another:
a spectral-energy metric is fooled by a phase-scrambled fake prediction and is still the
right tool for asking whether the energy cascade is reproduced. Collapsing that into a
verdict would discard exactly the information a reader needs. What a metric detects, what
it is blind to, and how it compares to the others is recorded in the measured evidence and
discussed in the card's ``## Results`` section.
"""

EXEMPLAR_MODES = ("severity", "draws", "none")
"""How a degradation's illustration panel is laid out.

``severity``
    Three severities -- weak, medium, strong -- beside the original. The usual case.
``draws``
    Several independent random draws beside the original. For degradations whose
    severity parameter carries no order: the phase-randomised impostor has no severity at
    all, and the unrelated-field anchor is indexed by draw number.
``none``
    No panel. Only the identity operator, which by definition changes nothing.
"""

DATA_REQUIREMENTS = ("ensemble", "vector_field", "time_series")
"""What a metric needs beyond a single pair of fields on the analysis grid.

Fields are not listed here: the ``@metric`` decorator's ``fields`` argument already says
which physical fields a metric accepts, and the card does not restate it.
"""

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# --------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------


class CardError(Exception):
    """A card is missing, malformed, or contradicts the code it documents.

    The message is the product here, not the exception type. An agent or a colleague who
    hits this should be able to fix the problem without reading any other document, so
    every instance states three things: where the problem is, what was expected in one
    sentence, and the exact command that repairs it.
    """

    def __init__(self, where: str, problem: str, fix: str) -> None:
        self.where = where
        self.problem = problem
        self.fix = fix
        super().__init__(f"{where}\n  {problem}\n  Fix: {fix}")


# --------------------------------------------------------------------------------------
# Card pieces
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Output:
    """What the single number a metric returns means, and what range it lives in.

    Metrics in this repository return one float per (field, frame, severity level); the
    structure over fields and frames comes from the evaluation loop, not from the metric.
    So there is one output per card, not a list.

    Direction (whether higher or lower is better) is *not* here: the ``@metric``
    decorator declares ``higher_is_better`` and the analysis layer already orients its
    statistics by it.
    """

    description: str
    lower: float | None = None
    upper: float | None = None


@dataclass(frozen=True)
class MathProperties:
    """Mathematical and computational properties the decorator does not already carry.

    ``differentiable`` and ``symmetric`` are absent on purpose: both are declared on the
    ``@metric`` decorator, and the contract tests check ``symmetric`` against the actual
    implementation. Repeating them here would create a second answer to the same question.
    """

    triangle_inequality: bool
    scale_dependent: bool
    """Whether the value changes when both fields are multiplied by the same constant."""
    resolution_dependent: bool
    """Whether the value changes with the analysis-grid resolution."""
    complexity: str
    """Big-O in the number of grid cells, e.g. ``"O(N)"`` or ``"O(N log N)"``."""


@dataclass(frozen=True)
class Exemplars:
    """Which severities to illustrate for a degradation, and how.

    Required on degradation cards: a degradation whose effect is never shown is not
    interpretable from prose alone, however careful the prose.
    """

    mode: str = "severity"
    levels: tuple[float, ...] = ()
    """Weak, medium and strong severities, which must be severities this degradation's
    ladder actually uses. Required when ``mode`` is ``severity``."""
    n_draws: int = 3
    """How many independent draws to show. Used when ``mode`` is ``draws``."""
    diagnostics: tuple[str, ...] = ()
    """Extra panel rows beyond the field itself, e.g. the difference from the original or
    the radially averaged spectrum. Chosen to expose the mechanism: a blur is legible in
    a radial spectrum, a translation is not, because a translation moves spectral phase
    rather than amplitude."""
    field_name: str = "vorticity"
    rationale: str = ""
    """Why these severities and these diagnostics. Becomes the figure caption."""


@dataclass(frozen=True)
class Review:
    """A human's signature on the prose half of the card.

    Existence checks cannot tell correct prose from fluent, plausible, wrong prose, and
    an agent produces the latter readily. Only a person reading it can. The hash records
    exactly which text was read, so later edits show up as unreviewed rather than
    inheriting the old signature.
    """

    prose_sha256: str
    reviewer: str
    date: _dt.date


@dataclass(frozen=True)
class Card:
    """The typed half of one bundle."""

    schema_version: int
    name: str
    kind: str
    category: str
    summary: str
    status: str
    owners: tuple[str, ...]
    output: Output
    math: MathProperties | None = None
    exemplars: Exemplars | None = None
    references: tuple[str, ...] = ()
    review: Review | None = None
    failure_mode: str = ""
    """Degradations only: in one sentence, what kind of model error this stands in for."""


# --------------------------------------------------------------------------------------
# Parsing and validation
# --------------------------------------------------------------------------------------


def _require(mapping: Any, key: str, where: str, fix: str) -> Any:
    if not isinstance(mapping, dict):
        raise CardError(where, f"expected a mapping, found {type(mapping).__name__}.", fix)
    if key not in mapping:
        raise CardError(where, f"required key {key!r} is missing.", fix)
    return mapping[key]


def _one_of(value: Any, allowed: tuple[str, ...], key: str, where: str, fix: str) -> str:
    if value not in allowed:
        raise CardError(
            where,
            f"{key} is {value!r}; allowed values are {', '.join(allowed)}.",
            fix,
        )
    return str(value)


def _str_tuple(value: Any, key: str, where: str, fix: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise CardError(where, f"{key} must be a list, found {type(value).__name__}.", fix)
    return tuple(str(v) for v in value)


def parse_card(data: Any, *, where: str) -> Card:
    """Validate a parsed ``card.yaml`` mapping and build a :class:`Card`.

    Args:
        data: The mapping produced by loading the YAML file.
        where: Human-readable location used in error messages, normally the file path.

    Returns:
        The validated card.

    Raises:
        CardError: On any violation. The message names the fix.
    """
    fix = "edit the file, then run  python -m fmeval.cards check <name>"

    version = _require(data, "schema_version", where, fix)
    if not isinstance(version, int):
        raise CardError(where, "schema_version must be an integer.", fix)
    if version > SCHEMA_VERSION:
        raise CardError(
            where,
            f"schema_version {version} is newer than this checkout understands "
            f"({SCHEMA_VERSION}).",
            "update your checkout; do not edit the version down, the card may use "
            "fields this code cannot interpret",
        )
    if version < SCHEMA_VERSION:
        data = migrate(dict(data), from_version=version, where=where)

    name = str(_require(data, "name", where, fix))
    if not _NAME_RE.match(name):
        raise CardError(
            where,
            f"name {name!r} must be lowercase letters, digits and underscores, starting "
            "with a letter, so it can be a directory name and a Python package name.",
            fix,
        )

    kind = _one_of(_require(data, "kind", where, fix), KINDS, "kind", where, fix)
    category = str(_require(data, "category", where, fix))
    if kind == "metric" and category not in CATEGORIES:
        raise CardError(
            where,
            f"category is {category!r}; allowed values are {', '.join(CATEGORIES)}.",
            "pick the closest category, or add a new one to CATEGORIES in "
            "fmeval/cards/schema.py with a sentence saying what belongs in it",
        )

    summary = str(_require(data, "summary", where, fix)).strip()
    if not 20 <= len(summary) <= 300:
        raise CardError(
            where,
            f"summary is {len(summary)} characters; it must be between 20 and 300, "
            "because it is the one line shown beside this bundle in every index.",
            fix,
        )

    status = _one_of(_require(data, "status", where, fix), STATUSES, "status", where, fix)
    owners = _str_tuple(_require(data, "owners", where, fix), "owners", where, fix)
    if not owners:
        raise CardError(where, "owners must name at least one person.", fix)

    card = Card(
        schema_version=SCHEMA_VERSION,
        name=name,
        kind=kind,
        category=category,
        summary=summary,
        status=status,
        owners=owners,
        output=_parse_output(_require(data, "output", where, fix), where, fix),
        math=_parse_math(data.get("math"), where, fix),
        exemplars=_parse_exemplars(data.get("exemplars"), where, fix),
        references=_str_tuple(data.get("references"), "references", where, fix),
        review=_parse_review(data.get("review"), where, fix),
        failure_mode=str(data.get("failure_mode") or "").strip(),
    )

    if card.kind == "degradation" and card.exemplars is None:
        raise CardError(
            where,
            "a degradation card needs an `exemplars` block: a degradation whose effect "
            "is never shown cannot be understood from prose alone.",
            "add an exemplars block, then run  python -m fmeval.cards exemplars " + name,
        )
    if card.kind == "metric" and card.math is None:
        raise CardError(where, "a metric card needs a `math` block.", fix)

    _check_unknown_keys(data, where)
    return card


_KNOWN_KEYS = frozenset(
    {
        "schema_version", "name", "kind", "category", "summary", "status", "owners",
        "output", "math", "exemplars", "references",
        "review", "failure_mode",
    }
)


def _check_unknown_keys(data: dict[str, Any], where: str) -> None:
    """Reject unrecognised top-level keys.

    A typo in a key name would otherwise be silently ignored, and the card would claim
    something no tool ever reads -- the exact failure this schema exists to prevent.
    """
    unknown = sorted(set(data) - _KNOWN_KEYS)
    if unknown:
        raise CardError(
            where,
            f"unrecognised key(s): {', '.join(unknown)}. A key nothing reads is a claim "
            "nothing checks.",
            "remove the key, correct the spelling, or add it to the schema in "
            "fmeval/cards/schema.py",
        )


def _parse_output(data: Any, where: str, fix: str) -> Output:
    description = str(_require(data, "description", where, fix)).strip()
    if len(description) < 10:
        raise CardError(where, "output.description is too short to be useful.", fix)
    bounds = data.get("bounds") or {}
    if not isinstance(bounds, dict):
        raise CardError(where, "output.bounds must be a mapping.", fix)
    lower, upper = bounds.get("lower"), bounds.get("upper")
    if lower is not None and upper is not None and float(lower) >= float(upper):
        raise CardError(
            where, f"output.bounds lower ({lower}) is not below upper ({upper}).", fix
        )
    return Output(
        description=description,
        lower=None if lower is None else float(lower),
        upper=None if upper is None else float(upper),
    )


def _parse_math(data: Any, where: str, fix: str) -> MathProperties | None:
    if data is None:
        return None
    return MathProperties(
        triangle_inequality=bool(_require(data, "triangle_inequality", where, fix)),
        scale_dependent=bool(_require(data, "scale_dependent", where, fix)),
        resolution_dependent=bool(_require(data, "resolution_dependent", where, fix)),
        complexity=str(_require(data, "complexity", where, fix)),
    )


def _parse_exemplars(data: Any, where: str, fix: str) -> Exemplars | None:
    if data is None:
        return None
    mode = _one_of(data.get("mode", "severity"), EXEMPLAR_MODES, "exemplars.mode", where, fix)
    levels = tuple(float(v) for v in (data.get("levels") or ()))
    if mode == "severity" and len(levels) != 3:
        raise CardError(
            where,
            f"exemplars.mode is 'severity' but {len(levels)} level(s) are listed. Give "
            "exactly three -- weak, medium and strong -- all of them severities this "
            "degradation's ladder actually uses.",
            fix,
        )
    # Deliberately not checked here: whether the levels are ordered weakest-first.
    # "Weakest" depends on the operator's declared severity_direction, which lives in the
    # registry -- band_attenuate is the one axis where a *smaller* number is a *stronger*
    # degradation, so a numeric sort would call its correct ordering wrong. The check is
    # made in fmeval.cards.loader, where the spec is in hand.
    rationale = str(data.get("rationale") or "").strip()
    if mode != "none" and len(rationale) < 20:
        raise CardError(
            where,
            "exemplars.rationale is missing or too short. It becomes the figure caption, "
            "so say why these severities and these diagnostics show the mechanism.",
            fix,
        )
    return Exemplars(
        mode=mode,
        levels=levels,
        n_draws=int(data.get("n_draws", 3)),
        diagnostics=_str_tuple(data.get("diagnostics"), "exemplars.diagnostics", where, fix),
        field_name=str(data.get("field_name", "vorticity")),
        rationale=rationale,
    )


def _parse_review(data: Any, where: str, fix: str) -> Review | None:
    if data is None:
        return None
    digest = str(_require(data, "prose_sha256", where, fix))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise CardError(
            where,
            "review.prose_sha256 is not a sha256 digest.",
            "run  python -m fmeval.cards sign <name> --by <who>  rather than writing it "
            "by hand",
        )
    date = _require(data, "reviewed_at", where, fix) if "reviewed_at" in data else _require(
        data, "date", where, fix
    )
    if isinstance(date, str):
        date = _dt.date.fromisoformat(date)
    if not isinstance(date, _dt.date):
        raise CardError(where, "review date must be an ISO date, e.g. 2026-08-18.", fix)
    return Review(
        prose_sha256=digest,
        reviewer=str(_require(data, "reviewer", where, fix)),
        date=date,
    )


def migrate(data: dict[str, Any], *, from_version: int, where: str) -> dict[str, Any]:
    """Bring a card written against an older schema up to :data:`SCHEMA_VERSION`.

    There are no migrations yet, because there has been no breaking change yet. When the
    first one lands, add a ``migrate_v1_to_v2`` function and dispatch to it here, so an
    old card keeps loading with a warning rather than failing.

    Args:
        data: The raw card mapping.
        from_version: The version recorded in the card.
        where: Location used in error messages.

    Returns:
        The migrated mapping.

    Raises:
        CardError: If no migration path exists.
    """
    raise CardError(
        where,
        f"card uses schema_version {from_version} and no migration to "
        f"{SCHEMA_VERSION} exists.",
        "add the migration to fmeval/cards/schema.py, or regenerate the card",
    )
