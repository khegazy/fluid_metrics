"""Checks on ``card.md``: the sections that must exist and what must be in them.

The prose half of a card is written for three readers at once, and the sections exist to
stop any one of them being forgotten:

* an **early graduate student in any STEM field**, who should finish ``## Intuition``
  knowing why the test matters and what its number means, without a background in fluids
  or ML -- and without being walked through it: state the idea directly, keep any example
  compact, and trust the reader with everything except the jargon;
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
    "Intuition": 70,
    "Reading the output": 80,
    "Assessment": 60,
    "Limitations": 80,
    "What to look for": 60,
    "Severity scale": 40,
}

NO_MATH_SECTIONS = frozenset({"Intuition", "What to look for"})
"""Sections a reader from outside the field must be able to follow, so notation is not
allowed in them. The audience is an early graduate student: avoid jargon, not rigor."""

SENTINELS = ("TODO(fill)", "TODO(cite)")
"""Markers a template leaves behind. Both must be gone before a card is complete.

``TODO(cite)`` is a failure on purpose: a citation that cannot be verified must be left
visibly missing rather than guessed at, and a guessed citation is worse than none.
"""

_MATH = re.compile(r"\$|\\\(|\\\[")

# --------------------------------------------------------------------------------------
# Math that renders everywhere
# --------------------------------------------------------------------------------------
#
# A card is read in two places, and the equations must render in both:
#
#   * GitHub's web UI, where a colleague browsing the repository sees the file directly;
#   * the documentation site, where MathJax typesets it.
#
# Their overlap is smaller than it looks, and the difference is silent -- an equation
# GitHub cannot parse is shown as its literal source, with no error anywhere. So the
# portable subset is enforced rather than trusted:
#
#   inline    $ ... $
#   display   $$ ... $$        with the delimiters alone on their own lines
#   numbering \tag{1}          referred to in prose as "Equation (1)"
#
# What is banned, and why:
#
#   \begin{equation} and the other numbered environments are not recognised by GitHub
#       unless wrapped in $$, and wrapping them then double-numbers on the site.
#   \label and \eqref are MathJax extensions that GitHub does not process at all, so a
#       cross-reference silently degrades into the raw command.
#   \( \) \[ \] are MathJax delimiters that GitHub does not recognise as math.
_BANNED_MATH: tuple[tuple[str, str], ...] = (
    (r"\\begin\{(equation|align|gather|eqnarray)\*?\}", "\\begin{equation} and the other "
     "numbered environments are not rendered by GitHub"),
    (r"\\label\{", "\\label is not processed outside a full LaTeX toolchain"),
    (r"\\eqref\{", "\\eqref is not processed outside a full LaTeX toolchain"),
    (r"\\\(|\\\)", "\\( and \\) are not recognised as math delimiters by GitHub"),
    (r"\\\[|\\\]", "\\[ and \\] are not recognised as math delimiters by GitHub"),
)

_DISPLAY_FENCE = re.compile(r"^\$\$\s*$", re.MULTILINE)
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_CODE_SPAN = re.compile(r"`[^`\n]+`")


def check_math(text: str) -> list[Problem]:
    """Check that every equation uses the subset that renders in both readers.

    Args:
        text: The contents of ``card.md``.

    Returns:
        One problem per unrenderable construct found. Empty means the math will render
        on GitHub and on the documentation site alike.
    """
    # Code is exempt in both forms. A card explaining why \begin{equation} is
    # refused has to be able to write \begin{equation}, and a worked example may
    # show LaTeX source on purpose.
    outside_code = _CODE_SPAN.sub("", _CODE_FENCE.sub("", text))
    problems: list[Problem] = []

    for pattern, why in _BANNED_MATH:
        match = re.search(pattern, outside_code)
        if match:
            problems.append(
                Problem(
                    "",
                    f"{match.group(0)!r} will not render: {why}. On GitHub the equation "
                    "appears as its own source, and nothing reports an error.",
                    "use $$ ... $$ on their own lines for display equations, $ ... $ "
                    "inline, and \\tag{1} for numbering; refer to it in prose as "
                    "'Equation (1)'",
                )
            )

    if len(_DISPLAY_FENCE.findall(outside_code)) % 2:
        problems.append(
            Problem(
                "",
                "an odd number of `$$` display-math fences: one block is unterminated, "
                "which swallows the rest of the section into an equation.",
                "check that every $$ that opens a display equation has one closing it",
            )
        )

    if outside_code.count("$") % 2:
        problems.append(
            Problem(
                "",
                "an odd number of `$` characters, so one inline equation is unterminated. "
                "A literal dollar sign has to be written as \\$.",
                "close the inline math, or escape the literal dollar sign",
            )
        )

    return problems


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

    problems.extend(check_math(text))

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
