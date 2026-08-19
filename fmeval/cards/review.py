"""The review ledger: a record of which prose a human has actually read.

Every mechanical check in this repository can confirm that a section exists, that it is
long enough, and that it contains no mathematical notation. None of them can tell correct
prose from prose that is fluent, plausible and wrong -- which is exactly what a language
model produces when it is asked to describe a metric it has not measured. Only a person
reading the text can catch that.

So the prose carries a signature. ``card.yaml`` records the SHA-256 of the ``card.md``
that a named person read, on a named date. Editing the prose changes the hash, and the
card is unreviewed again until someone signs it. That is a warning for a bundle still
being worked on, and a hard failure for one marked ``validated`` -- because ``validated``
is precisely the claim that a human checked it.

The hash is taken over the prose alone -- generated blocks are stripped first, so
regenerating evidence never invalidates a signature while editing prose always does --
after normalising line endings and trailing
whitespace. The generated sections of ``card.md`` contain only an include directive, not
the generated text itself, so regenerating evidence never invalidates a review.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re

from .loader import Bundle

_TRAILING_WS = re.compile(r"[ \t]+$", re.MULTILINE)


def normalise(text: str) -> str:
    """Put prose into the canonical form the hash is taken over.

    Line endings and trailing spaces differ between editors and platforms and say nothing
    about the content, so they are removed before hashing. Otherwise a colleague on a
    different machine would appear to have changed prose they only opened.

    Args:
        text: The raw file contents.

    Returns:
        The normalised text.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_WS.sub("", text)
    from .prose import strip_generated

    text = strip_generated(text)
    return text.rstrip("\n") + "\n"


def prose_digest(bundle: Bundle) -> str:
    """SHA-256 of a bundle's normalised ``card.md``.

    Args:
        bundle: The bundle whose prose to hash.

    Returns:
        The digest as 64 lowercase hex characters.

    Raises:
        FileNotFoundError: If the bundle has no ``card.md``.
    """
    text = normalise(bundle.card_md.read_text())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def review_state(bundle: Bundle, recorded: str | None) -> str:
    """Compare the prose on disk with the signature in the card.

    Args:
        bundle: The bundle to check.
        recorded: The digest recorded in ``card.yaml``, or ``None`` if unsigned.

    Returns:
        ``"unsigned"`` when no one has signed, ``"stale"`` when the prose changed since
        the signature, ``"current"`` when they agree.
    """
    if recorded is None:
        return "unsigned"
    return "current" if recorded == prose_digest(bundle) else "stale"


def sign(bundle: Bundle, reviewer: str, *, today: _dt.date | None = None) -> dict[str, str]:
    """Build the review block recording that ``reviewer`` has read this bundle's prose.

    Writing the block is the caller's job; this function only computes it, so the same
    code can be used to preview a signature without modifying the card.

    Args:
        bundle: The bundle being signed.
        reviewer: Who read it. A name or handle, recorded verbatim.
        today: The date to record. Defaults to the current date.

    Returns:
        A mapping ready to be written under ``review:`` in ``card.yaml``.
    """
    return {
        "prose_sha256": prose_digest(bundle),
        "reviewer": reviewer,
        "date": (today or _dt.date.today()).isoformat(),
    }
