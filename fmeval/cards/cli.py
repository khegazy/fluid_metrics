"""``python -m fmeval.cards`` -- create, check and sign bundle cards.

Every subcommand is written on the assumption that whoever runs it, human or agent, has
read nothing else. Failures name the file, say in one sentence what was expected, and give
the command that repairs it. A message like ``AssertionError: False is not True`` sends the
reader guessing; a message that names the fix gets the problem solved without a second
document being consulted.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

from .loader import (
    Bundle,
    bundle_root,
    check_bundle_files,
    find_bundle,
    iter_bundles,
    load_card,
)
from .prose import check_prose
from .review import review_state
from .review import sign as build_signature
from .schema import CardError

TEMPLATE_DIR = "_template"


def _template(kind: str) -> Path:
    return bundle_root(kind) / TEMPLATE_DIR


def cmd_new(args: argparse.Namespace) -> int:
    """Scaffold a bundle from the template, with the name substituted throughout."""
    kind, name = args.kind, args.name
    if find_bundle(name) is not None:
        print(f"a bundle named {name!r} already exists", file=sys.stderr)
        return 1
    template = _template(kind)
    if not template.is_dir():
        print(f"no template at {template}", file=sys.stderr)
        return 1

    target = bundle_root(kind) / name
    shutil.copytree(template, target)
    placeholder = "template_metric" if kind == "metric" else "template_degradation"
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".md", ".yaml", ".bib"}:
            path.write_text(path.read_text().replace(placeholder, name))

    print(f"created {target.relative_to(bundle_root(kind).parent)}\n")
    print("Fill these in, in this order:")
    print(f"  1. {'metric.py' if kind == 'metric' else 'degradation.py'}"
          "  the implementation. This is the only file holding your science.")
    print("  2. test_metric.py   at least one test whose expected value you worked out")
    print("                      by hand. Keep the inputs small: this same example goes")
    print("                      into the card, so a 4x4 field is ideal.")
    print("  3. card.yaml        the typed record. Every field is documented in")
    print("                      fmeval/cards/schema.py.")
    print("  4. card.md          the prose. Leave '## Performance' and every include")
    print("                      line alone: those are generated, never written.")
    print("                      Write the '## Results' explanations once you have a run.")
    print(f"\nThen run:  python -m fmeval.cards check {name}")
    return 0


def _report(bundle: Bundle, *, strict: bool) -> int:
    """Print every problem with one bundle. Returns the number of errors."""
    errors = warnings = 0
    header_shown = False

    def show(where: str, problem: str, fix: str, *, warn: bool = False) -> None:
        nonlocal header_shown, errors, warnings
        if not header_shown:
            print(f"\n{bundle.path.name}/")
            header_shown = True
        label = "warning" if warn else "error"
        print(f"  [{label}] {where}\n    {problem}\n    Fix: {fix}")
        if warn:
            warnings += 1
        else:
            errors += 1

    for missing in check_bundle_files(bundle):
        show(bundle.path.name, missing, f"python -m fmeval.cards new {bundle.name}")

    try:
        card = load_card(bundle)
    except CardError as exc:
        show(exc.where, exc.problem, exc.fix)
        return errors

    if bundle.card_md.is_file():
        for problem in check_prose(
            bundle.card_md.read_text(), kind=bundle.kind, name=bundle.name
        ):
            warn = problem.severity == "warning" and card.status != "validated"
            where = f"card.md  {problem.section}".strip()
            show(where, problem.message, problem.fix, warn=warn)

        state = review_state(bundle, card.review.prose_sha256 if card.review else None)
        if state != "current":
            reason = (
                "no one has signed this prose yet. A card is signed once its claims "
                "are backed by a run."
                if state == "unsigned"
                else "the prose has changed since it was signed."
            )
            show(
                "card.yaml  review",
                reason
                + " Existence checks cannot tell correct prose from plausible-sounding "
                "wrong prose; only a person reading it can.",
                f"python -m fmeval.cards sign {bundle.name} --by <who>",
                warn=card.status != "validated",
            )

    return errors


def cmd_check(args: argparse.Namespace) -> int:
    """Validate one bundle or all of them."""
    bundles = iter_bundles() if args.all else [b for b in iter_bundles() if b.name == args.name]
    if not bundles:
        target = "no bundles" if args.all else f"no bundle named {args.name!r}"
        print(f"found {target} under metrics/ or degradations/", file=sys.stderr)
        return 1

    errors = sum(_report(b, strict=args.strict) for b in bundles)
    print(f"\nchecked {len(bundles)} bundle(s): {errors} error(s)")
    return 1 if errors else 0


def cmd_list(args: argparse.Namespace) -> int:
    """Print the bundles as a table, so the registry doubles as an index."""
    rows = []
    for bundle in iter_bundles(args.kind):
        try:
            card = load_card(bundle)
        except CardError:
            rows.append((bundle.name, bundle.kind, "?", "INVALID CARD", ""))
            continue
        if args.status and card.status != args.status:
            continue
        rows.append((card.name, card.kind, card.status, card.category, card.summary))
    if not rows:
        print("no bundles")
        return 0
    head = ("name", "kind", "status", "category", "summary")
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(head[:-1])]
    line = "  ".join(h.ljust(w) for h, w in zip(head[:-1], widths)) + "  summary"
    print(line)
    print("-" * min(len(line), 100))
    for row in rows:
        cells = "  ".join(c.ljust(w) for c, w in zip(row[:-1], widths))
        print(f"{cells}  {row[-1][:60]}")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    """Record that a human has read this bundle's prose.

    Refused while the bundle has no measurements. A signature says a person read the
    prose and stands behind it, and most of a card's claims are claims about how the
    metric behaved; there is nothing to stand behind until a run exists to back them.
    Signing first would put the ledger's strongest statement on the least supported text.
    """
    bundle = find_bundle(args.name)
    if bundle is None:
        print(f"no bundle named {args.name!r}", file=sys.stderr)
        return 1
    if not (bundle.path / "_generated" / "fingerprint.json").is_file():
        print(
            f"{args.name} has no measurements yet, so there is nothing for a signature "
            f"to stand behind.\n"
            f"A card is signed once its claims are backed by a run.\n"
            f"Fix: python -m fmeval.cards evidence {args.name} --results results/<run>",
            file=sys.stderr,
        )
        return 1
    data = yaml.safe_load(bundle.card_yaml.read_text()) or {}
    data["review"] = build_signature(bundle, args.by)
    bundle.card_yaml.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88)
    )
    print(f"signed {args.name} as read by {args.by}")
    return 0



def cmd_evidence(args: argparse.Namespace) -> int:
    """Fill in the measured half of one metric card, or of every one."""
    from .evidence import generate as generate_evidence
    from .evidence import load_run

    try:
        run = load_run(Path(args.results))
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    names = [b.name for b in iter_bundles("metric")] if args.name == "--all" else [args.name]
    for name in names:
        try:
            generate_evidence(name, run)
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"wrote evidence for {name} from {run.folder.name}")
    return 0


def cmd_exemplars(args: argparse.Namespace) -> int:
    """Render one degradation's exemplar panel, or every one."""
    from .exemplars import generate as generate_panel

    names = ([b.name for b in iter_bundles("degradation")]
             if args.name == "--all" else [args.name])
    for name in names:
        try:
            path = generate_panel(name)
        except (KeyError, FileNotFoundError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"{name}: {'no panel (mode: none)' if path is None else path}")
    return 0



def cmd_catalog(args: argparse.Namespace) -> int:
    """Write docs/catalog.json, the structured surface agents read instead of prose."""
    from .catalog import build, write

    path = write(Path(args.out))
    counts = build()["counts"]
    print(f"wrote {path}: {counts['metrics']} metrics, {counts['degradations']} "
          f"degradations, {counts['with_measurements']} with measurements, "
          f"{counts['reviewed']} reviewed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m fmeval.cards",
        description="Create, check and sign the cards that document each metric and "
        "degradation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="scaffold a bundle from the template")
    new.add_argument("name", help="the registered name, lowercase with underscores")
    new.add_argument("--kind", choices=("metric", "degradation"), default="metric")
    new.set_defaults(func=cmd_new)

    check = sub.add_parser("check", help="validate a bundle and say how to fix it")
    check.add_argument("name", nargs="?", help="bundle name; omit with --all")
    check.add_argument("--all", action="store_true", help="check every bundle")
    check.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as errors, as the validated status does",
    )
    check.set_defaults(func=cmd_check)

    listing = sub.add_parser("list", help="print the bundles as a table")
    listing.add_argument("--kind", choices=("metric", "degradation"), default=None)
    listing.add_argument("--status", default=None)
    listing.set_defaults(func=cmd_list)

    evidence = sub.add_parser(
        "evidence", help="fill in a metric card's measurements from an evaluation run")
    evidence.add_argument("name", help="the metric bundle, or --all for every one")
    evidence.add_argument("--results", required=True,
                          help="a results/<name>_<stamp> folder on the canonical dataset")
    evidence.set_defaults(func=cmd_evidence)

    exemplars = sub.add_parser(
        "exemplars", help="render a degradation's exemplar panel from the canonical frame")
    exemplars.add_argument("name", help="the degradation bundle, or --all for every one")
    exemplars.set_defaults(func=cmd_exemplars)

    catalog = sub.add_parser(
        "catalog", help="write the machine-readable index of every bundle")
    catalog.add_argument("--out", default="docs/catalog.json")
    catalog.set_defaults(func=cmd_catalog)

    signer = sub.add_parser("sign", help="record that a human has read the prose")
    signer.add_argument("name")
    signer.add_argument("--by", required=True, help="who read it")
    signer.set_defaults(func=cmd_sign)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check" and not args.all and not args.name:
        print("give a bundle name, or --all", file=sys.stderr)
        return 1
    return int(args.func(args))
