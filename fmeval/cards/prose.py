"""Checks on ``card.md``: the sections that must exist and what must be in them.

The prose half of a card is written for three readers at once, and the sections exist to
stop any one of them being forgotten:

* a **STEM undergraduate from any field**, who should finish ``## Intuition`` knowing why
  the test matters and what its number means, without a background in fluids or ML;
* a **domain expert**, who needs the definition, the discretisation and the failure modes;
* a **coding agent**, which needs the structure to be predictable enough that it never has
  to guess where something is.

Only the mechanical parts are checked here. Whether the prose is *good* is a human's
judgement, recorded through the review ledger in :mod:`fmeval.cards.review`.

On word counts
--------------
The minimum word counts are honest guesses, not calibrated numbers. They exist because an
unenforced request for documentation is ignored, but a word count does not measure
clarity, and an author told to write 120 words will pad to 120 words. So they are
*warnings* for a bundle still in progress and *failures* only for one claiming
``validated``. If a section says what it needs to say in 90 words, leave it at 90, let the
warning stand, and say so -- that is evidence the floor is wrong, and the floor should
move rather than the prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

METRIC_SECTIONS: tuple[str, ...] = (
    "Claim",
    "Intuition",
    "Reading the output",
    "Prediction",
    "Definition",
    "Evidence",
    "Assessment",
    "Limitations",
    "References",
)
"""Required H2 headings of a metric card, in the order they must appear.

``Assessment`` is deliberately not called "Verdict". A verdict invites a yes or a no, and
no metric here earns one: the useful thing to record is what this metric sees, what it
misses, and how it compares to the controls, so a reader can decide whether it fits the
question they are asking.
"""

DEGRADATION_SECTIONS: tuple[str, ...] = (
    "Claim",
    "Intuition",
    "Definition",
    "Severity scale",
    "Exemplars",
    "What to look for",
    "Limitations",
    "References",
)
"""Required H2 headings of a degradation card, in order.

``What to look for`` is the human companion to the generated figure. A panel of images
does not explain itself; this section says, in plain language, what changes between the
weak and strong columns and which diagnostic row reveals it.
"""

GENERATED_SECTIONS = frozenset({"Evidence", "Exemplars"})
"""Sections whose body is written by a generator and must not be typed by hand."""

WORD_FLOORS: dict[str, int] = {
    "Claim": 40,
    "Intuition": 120,
    "Reading the output": 80,
    "Prediction": 60,
    "Assessment": 60,
    "Limitations": 80,
    "What to look for": 60,
    "Severity scale": 40,
}

NO_MATH_SECTIONS = frozenset({"Intuition", "What to look for"})
"""Sections an undergraduate must be able to read, so notation is not allowed in them."""

SENTINELS = ("TODO(fill)", "TODO(cite)")
"""Markers a template leaves behind. Both must be gone before a card is complete.

``TODO(cite)`` is a failure on purpose: a citation that cannot be verified must be left
visibly missing rather than guessed at, and a guessed citation is worse than none.
"""

_MATH = re.compile(r"\$|\\\(|\\\[")
_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_INCLUDE = re.compile(r"^\{\{\s*include\s+\S+\s*\}\}$", re.MULTILINE)
_TABLE_OR_CODE = re.compile(r"^```|^\s*\|", re.MULTILINE)


@dataclass(frozen=True)
class Problem:
    """One thing wrong with a card's prose.

    Attributes:
        section: Which section it concerns, or ``""`` for a whole-file problem.
        message: What is wrong, in one sentence.
        fix: What to do about it.
        severity: ``"error"`` always fails; ``"warning"`` fails only for a card claiming
            ``validated``.
    """

    section: str
    message: str
    fix: str
    severity: str = "error"


def split_sections(text: str) -> dict[str, str]:
    """Split a card's prose into its H2 sections.

    Args:
        text: The contents of ``card.md``.

    Returns:
        Section title mapped to its body, in file order.
    """
    matches = list(_HEADING.finditer(text))
    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.end() : end].strip()
    return sections


def frontmatter(text: str) -> dict[str, str]:
    """Read the ``name:`` and ``kind:`` lines from a card's YAML front matter.

    Deliberately a two-key reader rather than a YAML parse: the front matter exists only
    to cross-check the file against its directory, and anything else that appeared there
    would be a second, unvalidated copy of the typed card.

    Args:
        text: The contents of ``card.md``.

    Returns:
        The keys found; empty if there is no front matter.
    """
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    found = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            found[key.strip()] = value.strip().strip("'\"")
    return found


def _words(body: str) -> int:
    """Count words, ignoring code blocks and tables so an example cannot pad the count."""
    prose = _TABLE_OR_CODE.sub("", body)
    prose = re.sub(r"```.*?```", "", prose, flags=re.DOTALL)
    return len(prose.split())


def check_prose(text: str, *, kind: str, name: str) -> list[Problem]:
    """Check one card's prose against the section contract.

    Args:
        text: The contents of ``card.md``.
        kind: ``"metric"`` or ``"degradation"``.
        name: The bundle name, used in the suggested fix commands.

    Returns:
        Every problem found, errors and warnings together. Empty means the prose passes
        every mechanical check -- which is not the same as being correct.
    """
    required = METRIC_SECTIONS if kind == "metric" else DEGRADATION_SECTIONS
    check = f"python -m fmeval.cards check {name}"
    problems: list[Problem] = []

    meta = frontmatter(text)
    if meta.get("name") != name:
        problems.append(
            Problem(
                "",
                f"front matter says name: {meta.get('name')!r}, but the bundle is {name!r}.",
                f"set `name: {name}` in the front matter",
            )
        )

    for sentinel in SENTINELS:
        if sentinel in text:
            problems.append(
                Problem(
                    "",
                    f"{sentinel} is still present, so this card is unfinished."
                    + (
                        " A citation you cannot verify must stay visibly missing rather "
                        "than be guessed at."
                        if sentinel == "TODO(cite)"
                        else ""
                    ),
                    "replace it with real content, or report it as unresolved",
                )
            )

    sections = split_sections(text)
    present = [s for s in sections if s in required]
    missing = [s for s in required if s not in sections]
    for section in missing:
        problems.append(
            Problem(section, f"section '## {section}' is missing.", check)
        )
    if present != [s for s in required if s in sections]:
        problems.append(
            Problem(
                "",
                "sections are out of order; the fixed order is: "
                + ", ".join(required)
                + ".",
                "reorder the headings",
            )
        )

    for section, body in sections.items():
        if section not in required:
            continue
        if section in GENERATED_SECTIONS:
            if not _INCLUDE.search(body) or len(body.splitlines()) > 3:
                problems.append(
                    Problem(
                        section,
                        f"'## {section}' is generated, but contains hand-written text. "
                        "Prose here would be a claim about measurements that nothing "
                        "checks.",
                        f"replace the body with the include line and run  "
                        f"python -m fmeval.cards "
                        f"{'evidence' if section == 'Evidence' else 'exemplars'} {name}",
                    )
                )
            continue
        if not body:
            problems.append(Problem(section, f"'## {section}' is empty.", check))
            continue
        if section in NO_MATH_SECTIONS and _MATH.search(body):
            problems.append(
                Problem(
                    section,
                    f"'## {section}' contains mathematical notation. This is the section "
                    "a reader from another field is guaranteed to read, so it has to work "
                    "without symbols.",
                    "move the equations to '## Definition' and describe the idea in words",
                )
            )
        floor = WORD_FLOORS.get(section)
        count = _words(body)
        if floor and count < floor:
            problems.append(
                Problem(
                    section,
                    f"'## {section}' is {count} words; the guideline is {floor}.",
                    "expand it, or -- if it already says what it needs to -- leave it and "
                    "report that the floor is wrong. Do not pad.",
                    severity="warning",
                )
            )
        if section == "Intuition" and not _TABLE_OR_CODE.search(body):
            problems.append(
                Problem(
                    section,
                    "'## Intuition' has no worked example. An abstract description is not "
                    "enough: show two small fields and the number the metric returns for "
                    "them.",
                    "add a small table or code block, using numbers your test_metric.py "
                    "actually produces",
                )
            )

    return problems
