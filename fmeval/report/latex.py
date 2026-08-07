"""LaTeX generation: escaping, booktabs tables, and document assembly.

The report is a LaTeX document that compiles unmodified on Overleaf. ``main.tex`` carries
the ``\\documentclass``, so uploading the folder as a zip is enough for Overleaf to detect
it, and every path in the document is relative.

**Escaping is the single most likely thing to break the build.** Metric names, degradation
labels, field names and flag strings all contain underscores, and an unescaped underscore
is a hard compile error rather than a cosmetic one. Every value that reaches the document
goes through :func:`escape`, and a test asserts no unescaped underscore survives into any
generated file.

Numbers are pre-formatted in Python rather than handed to ``siunitx`` column parsing. It
costs nothing and removes any dependence on the siunitx version Overleaf happens to ship.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

#: Characters LaTeX treats specially in text mode, and their replacements.
_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_ESCAPE_RE = re.compile("|".join(re.escape(k) for k in _ESCAPES))

#: Packages the report uses. All are in Overleaf's TeX Live and in NERSC's texlive/2024.
#: `listings` typesets the config appendix and needs no --shell-escape, unlike minted.
PACKAGES = (
    "geometry", "graphicx", "booktabs", "longtable", "caption",
    "xcolor", "amsmath", "listings", "hyperref",
)


def escape(text: object) -> str:
    """Escape a value for LaTeX text mode.

    Applied to every data-derived string that reaches the document. ``\\`` is handled by
    the same single pass as the rest, so a backslash cannot be double-escaped.
    """
    if text is None:
        return ""
    return _ESCAPE_RE.sub(lambda m: _ESCAPES[m.group()], str(text))


def code(text: object) -> str:
    """Escape a value and typeset it as an identifier."""
    return rf"\texttt{{{escape(text)}}}"


def number(value: object, digits: int = 3, *, na: str = "--") -> str:
    """Format a number for a table cell, pre-rendered so no LaTeX package parses it."""
    if value is None:
        return na
    try:
        v = float(value)
    except (TypeError, ValueError):
        return escape(value)
    if not np.isfinite(v):
        return na
    if v != 0 and (abs(v) < 10 ** -(digits + 1) or abs(v) >= 1e5):
        mantissa, exponent = f"{v:.{digits}e}".split("e")
        return rf"${mantissa}\times10^{{{int(exponent)}}}$"
    return f"{v:.{digits}f}"


def slug(name: str, **keys: object) -> str:
    """Filename stem: ``renderer__key-value``, restricted to ``[A-Za-z0-9_-]``.

    A single dot in the final filename matters: ``graphicx`` mis-parses paths with more.
    """
    parts = [name]
    for key in ("dataset", "metric", "field", "degradation", "t"):
        if key in keys and keys[key] not in (None, ""):
            parts.append(f"{key}-{_clean(keys[key])}")
    for key, value in keys.items():
        if key not in ("dataset", "metric", "field", "degradation", "t") and value not in (None, ""):
            parts.append(f"{key}-{_clean(value)}")
    return "__".join(parts)


def _clean(value: object) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9_-]+", "-", str(value))).strip("-")


# --- tables ---------------------------------------------------------------------------


def booktabs_table(
    df: pd.DataFrame,
    *,
    caption: str,
    label: str,
    formats: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    align: str | None = None,
    note: str = "",
    landscape: bool = False,
) -> str:
    """Render a DataFrame as a complete ``table`` float.

    A complete float rather than a bare tabular, so ``\\input{tables/x}`` works on its own
    and a colleague can lift the table straight into a paper.

    Args:
        df: Data to render. Every cell is escaped.
        caption: Caption text; escaped.
        label: Label suffix, used as ``tab:<label>``.
        formats: Column name -> printf-style format, or "code" to typeset as an identifier.
        headers: Column name -> display header. Defaults to the column name.
        align: Column alignment string. Defaults to left for text, right for numbers.
        note: Optional footnote below the table.
        landscape: Wrap in a smaller font for wide tables.
    """
    formats = formats or {}
    headers = headers or {}
    if df.empty:
        return (
            f"% generated {_stamp()}\n"
            "\\begin{table}[htbp]\n\\centering\n"
            f"\\caption{{{escape(caption)}}}\n\\label{{tab:{_clean(label)}}}\n"
            "\\emph{No data.}\n\\end{table}\n"
        )

    if align is None:
        align = "".join(
            "r" if pd.api.types.is_numeric_dtype(df[c]) else "l" for c in df.columns
        )

    head = " & ".join(rf"\textbf{{{escape(headers.get(c, c))}}}" for c in df.columns)
    body = []
    for _, row in df.iterrows():
        cells = []
        for column in df.columns:
            spec = formats.get(column)
            value = row[column]
            if spec == "code":
                cells.append(code(value))
            elif spec:
                cells.append(number(value, digits=int(spec)) if spec.isdigit()
                             else escape(spec % value))
            elif isinstance(value, (int, float, np.number)) and not isinstance(value, bool):
                cells.append(number(value))
            else:
                cells.append(escape(value))
        body.append(" & ".join(cells) + r" \\")

    size = "\\small\n" if landscape else ""
    footnote = f"\n\\par\\smallskip\n\\footnotesize {escape(note)}" if note else ""
    return (
        f"% generated {_stamp()}\n"
        "\\begin{table}[htbp]\n\\centering\n"
        f"{size}"
        f"\\caption{{{escape(caption)}}}\n"
        f"\\label{{tab:{_clean(label)}}}\n"
        f"\\begin{{tabular}}{{{align}}}\n"
        "\\toprule\n"
        f"{head} \\\\\n"
        "\\midrule\n"
        + "\n".join(body)
        + "\n\\bottomrule\n\\end{tabular}"
        + footnote
        + "\n\\end{table}\n"
    )


def figure(path: str, *, caption: str, label: str, width: str = r"\linewidth") -> str:
    """A ``figure`` float referencing ``plots/<stem>`` with the extension omitted.

    Omitting the extension lets LaTeX prefer the vector PDF and fall back to the PNG.
    """
    return (
        "\\begin{figure}[htbp]\n\\centering\n"
        f"\\includegraphics[width={width}]{{{path}}}\n"
        f"\\caption{{{escape(caption)}}}\n"
        f"\\label{{fig:{_clean(label)}}}\n"
        "\\end{figure}\n"
    )


def verbatim(text: str, *, caption: str = "") -> str:
    """A ``lstlisting`` block for config dumps and command lines.

    ``listings`` rather than ``verbatim`` so long lines wrap instead of overflowing the
    margin, and rather than ``minted`` so no ``--shell-escape`` is needed.
    """
    head = f"\\paragraph{{{escape(caption)}}}\n" if caption else ""
    return head + "\\begin{lstlisting}\n" + text.rstrip() + "\n\\end{lstlisting}\n"


# --- document assembly -------------------------------------------------------------------


def preamble(title: str, subtitle: str = "") -> str:
    """The shared preamble, kept in its own file so a section can be reused elsewhere."""
    uses = "\n".join(rf"\usepackage{{{p}}}" for p in PACKAGES)
    return rf"""% Generated by fluid_metrics. Compiles with pdflatex; renders on Overleaf.
\documentclass[11pt]{{article}}
\usepackage[margin=1in]{{geometry}}
{uses}
\usepackage[T1]{{fontenc}}

\lstset{{
  basicstyle=\ttfamily\footnotesize,
  breaklines=true,
  breakatwhitespace=false,
  columns=flexible,
  frame=single,
  showstringspaces=false,
}}
\captionsetup{{font=small}}
\setlength{{\parskip}}{{0.5em}}
\setlength{{\parindent}}{{0pt}}
\graphicspath{{{{plots/}}}}
\hypersetup{{colorlinks=true, linkcolor=blue!50!black, urlcolor=blue!50!black}}

\title{{{escape(title)}}}
\author{{{escape(subtitle)}}}
\date{{{_stamp()}}}
"""


def document(section_files: Sequence[str], *, title: str, subtitle: str = "") -> str:
    """``main.tex``: preamble, title, contents, and one ``\\input`` per section."""
    inputs = "\n".join(rf"\input{{sections/{name}}}" for name in section_files)
    return (
        "% Main document. Upload this folder to Overleaf as a zip; it is detected\n"
        "% automatically because it carries the \\documentclass.\n"
        "%\n"
        "% Local build:  module load texlive/2024 && latexmk -pdf main.tex\n"
        "\\input{preamble}\n\n"
        "\\begin{document}\n"
        "\\maketitle\n"
        "\\tableofcontents\n"
        "\\clearpage\n\n"
        f"{inputs}\n\n"
        "\\end{document}\n"
    )


def _stamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
