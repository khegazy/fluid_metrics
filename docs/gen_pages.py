"""Build the site's pages from the bundles, at docs build time.

Cards are read where they live rather than copied into ``docs/``. A colleague browsing the
repository and a reader on the site see the same bytes, and there is no second copy to
drift.

Three kinds of page are produced here:

* one page per bundle, its card wrapped in a header table drawn from the typed record and
  followed by the module's API;
* the indexes -- a filterable catalogue, the degradation gallery, the navigation tree;
* the machine surfaces, ``catalog.json`` and ``llms.txt``.

Links inside cards are written to work on GitHub, as ``../../degradations/<name>/card.md``.
They are rewritten here for the site's flatter layout, which is the one place the two
readers genuinely need different text.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import mkdocs_gen_files

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from fmeval.cards.catalog import build as build_catalog  # noqa: E402
from fmeval.cards.loader import iter_bundles, load_card  # noqa: E402

#: Cards link to each other by repository-relative path so GitHub resolves them. On the
#: site, pages are flat under metrics/ and degradations/, so those links are rewritten.
_CARD_LINK = re.compile(r"\]\(\.\./\.\./(metrics|degradations)/([a-z0-9_]+)/card\.md\)")
#: Figures live beside the card in _generated/; the site serves them from the page's dir.
_ASSET = re.compile(r"\]\(_generated/([^)]+)\)")


def _for_site(text: str, name: str) -> str:
    """Rewrite a card's repository-relative links and asset paths for the site.

    Assets are namespaced by bundle name. Every degradation calls its panel
    ``exemplars.png``, so copying them into one directory under their own names would
    leave whichever was written last and silently show the wrong figure on twenty pages.
    """
    # Pages are flat: metrics/<name>.md and degradations/<name>.md. From either, a
    # sibling section is one level up.
    text = _CARD_LINK.sub(lambda m: f"](../{m.group(1)}/{m.group(2)}.md)", text)
    return _ASSET.sub(lambda m: f"](_generated/{name}_{m.group(1)})", text)


def _front_matter_stripped(text: str) -> str:
    """A card without its YAML front matter, which the site header replaces."""
    if text.startswith("---"):
        return text.split("---", 2)[2].lstrip("\n")
    return text


def _header(entry: dict) -> str:
    """The typed record, as a table above the prose.

    Everything here is read from the card and the registry rather than restated by the
    author, so the summary a reader sees cannot disagree with what the code declares.
    """
    declared = entry["declared"]
    rows = [f"| | |", "|---|---|", f"| **status** | `{entry['status']}` |",
            f"| **category** | {entry['category']} |"]
    if entry["kind"] == "metric":
        rows += [
            f"| **arity** | {declared['arity']} |",
            f"| **fields** | {', '.join(declared['fields'])} |",
            f"| **units** | {declared['units']} |",
            f"| **direction** | {'higher is better' if declared['higher_is_better'] else 'lower is better'} |",
            f"| **differentiable** | {'yes' if declared['differentiable'] else 'no'} |",
            f"| **cost** | {declared['cost']} |",
        ]
        if entry["math"]:
            rows.append(f"| **complexity** | `{entry['math']['complexity']}` |")
    else:
        rows += [
            f"| **severity** | {declared['severity_name']}"
            + (f" [{declared['severity_units']}]" if declared["severity_units"] else "") + " |",
            f"| **relative to** | {declared['calibration'] or 'absolute'} |",
            f"| **ordered ladder** | {'yes' if declared['ordinal'] else 'no (canary)'} |",
            f"| **stochastic** | {'yes' if declared['stochastic'] else 'no'} |",
        ]
    evidence = entry["evidence"]
    measured = (f"`{evidence['run']}` on `{evidence['dataset']}`, {evidence.get('frames', 0)} frames"
                if evidence["measured"] else "not yet measured")
    rows.append(f"| **evidence** | {measured} |")
    rows.append(f"| **reviewed** | {'yes, ' + str(entry['reviewed_at']) if entry['reviewed'] else 'not yet'} |")
    return "\n".join(rows)


def _api(bundle) -> str:
    """The implementation's API, pulled from its docstrings by mkdocstrings."""
    module = f"{bundle.path.parent.name}.{bundle.name}.{bundle.implementation.stem}"
    return f"## Implementation\n\n::: {module}\n"


def main() -> None:
    catalog = build_catalog()
    by_name = {e["name"]: e for e in catalog["entries"]}
    nav_metrics, nav_degradations = [], []

    for bundle in iter_bundles():
        entry = by_name[bundle.name]
        card = _front_matter_stripped(bundle.card_md.read_text())
        page = f"{bundle.path.parent.name}/{bundle.name}.md"
        with mkdocs_gen_files.open(page, "w") as f:
            print(f"# {bundle.name}\n", file=f)
            print(f"{entry['summary']}\n", file=f)
            print(_header(entry) + "\n", file=f)
            print(_for_site(card, bundle.name), file=f)
            print("\n" + _api(bundle), file=f)
        mkdocs_gen_files.set_edit_path(page, f"{bundle.path.parent.name}/{bundle.name}/card.md")

        # Figures are served from beside the page.
        for asset in sorted((bundle.path / "_generated").glob("*.png")):
            target = f"{bundle.path.parent.name}/_generated/{bundle.name}_{asset.name}"
            with mkdocs_gen_files.open(target, "wb") as f:
                f.write(asset.read_bytes())

        (nav_metrics if bundle.kind == "metric" else nav_degradations).append(
            (bundle.name, entry["status"], f"{bundle.path.parent.name}/{bundle.name}.md")
        )

    _write_catalogue_page(catalog)
    _write_gallery(catalog)
    _write_protocol()
    _write_nav(nav_metrics, nav_degradations)
    _write_machine_surfaces(catalog)


def _write_catalogue_page(catalog: dict) -> None:
    """One table of every metric, filterable by the properties that matter."""
    with mkdocs_gen_files.open("catalogue.md", "w") as f:
        print("# Catalogue\n", file=f)
        print("Every metric and degradation in the repository. The same content is served "
              "as [catalog.json](catalog.json) for machine readers, which is what an agent "
              "should use rather than parsing this page.\n", file=f)
        print("## Metrics\n", file=f)
        print("| metric | status | category | units | differentiable | cost | evidence |", file=f)
        print("|---|---|---|---|---|---|---|", file=f)
        for e in catalog["entries"]:
            if e["kind"] != "metric":
                continue
            d = e["declared"]
            print(f"| [{e['name']}](metrics/{e['name']}.md) "
                  f"| <span class='status status-{e['status']}'>{e['status']}</span> "
                  f"| {e['category']} | {d['units']} "
                  f"| {'yes' if d['differentiable'] else 'no'} | {d['cost']} "
                  f"| {'measured' if e['evidence']['measured'] else '—'} |", file=f)
        print("\n## Degradations\n", file=f)
        print("| degradation | family | severity | relative to | ordered |", file=f)
        print("|---|---|---|---|---|", file=f)
        for e in catalog["entries"]:
            if e["kind"] != "degradation":
                continue
            d = e["declared"]
            units = f" [{d['severity_units']}]" if d["severity_units"] else ""
            print(f"| [{e['name']}](degradations/{e['name']}.md) | {d['family']} "
                  f"| {d['severity_name']}{units} | {d['calibration'] or 'absolute'} "
                  f"| {'yes' if d['ordinal'] else 'no (canary)'} |", file=f)


def _write_gallery(catalog: dict) -> None:
    """Every exemplar panel on one page, from the one canonical frame.

    The fastest route into the project for a new reader: scrolling it shows what each
    degradation does and how the severities compare, which prose cannot do at any length.
    """
    with mkdocs_gen_files.open("degradations/gallery.md", "w") as f:
        print("# Degradation gallery\n", file=f)
        print("Every degradation applied to the same snapshot, so the panels can be "
              "compared with one another. Each figure's columns are the original beside "
              "three severities, or beside several draws where the degradation has no "
              "ordered severity.\n", file=f)
        for e in catalog["entries"]:
            if e["kind"] != "degradation":
                continue
            panel = REPO / "degradations" / e["name"] / "_generated" / "exemplars.png"
            print(f"## [{e['name']}]({e['name']}.md)\n", file=f)
            print(f"{e['summary']}\n", file=f)
            if panel.is_file():
                print(f"![{e['name']}](_generated/{e['name']}_exemplars.png)\n", file=f)
            else:
                print("*No panel: this operator changes nothing.*\n", file=f)


def _write_protocol() -> None:
    """TEST_DESCRIPTION.md, served as the protocol reference rather than duplicated."""
    with mkdocs_gen_files.open("protocol.md", "w") as f:
        print((REPO / "TEST_DESCRIPTION.md").read_text(), file=f)


def _write_nav(metrics: list, degradations: list) -> None:
    """The navigation tree, grouped by status so controls and candidates are separable."""
    with mkdocs_gen_files.open("SUMMARY.md", "w") as f:
        print("- [Home](index.md)", file=f)
        print("- [Reading a card](reading-guide.md)", file=f)
        print("- [Choosing a metric](choosing-a-metric.md)", file=f)
        print("- [Working in the repository](working-with-the-repo.md)", file=f)
        print("- [Catalogue](catalogue.md)", file=f)
        print("- Metrics", file=f)
        for status in ("validated", "candidate", "control", "deprecated"):
            named = [m for m in metrics if m[1] == status]
            if named:
                print(f"    - {status}", file=f)
                for name, _, page in sorted(named):
                    print(f"        - [{name}]({page})", file=f)
        print("- Degradations", file=f)
        print("    - [Gallery](degradations/gallery.md)", file=f)
        for name, _, page in sorted(degradations):
            print(f"    - [{name}]({page})", file=f)
        print("- [Protocol](protocol.md)", file=f)
        print("- [Glossary](glossary.md)", file=f)


def _write_machine_surfaces(catalog: dict) -> None:
    """catalog.json and llms.txt: what an agent reads instead of the rendered pages."""
    with mkdocs_gen_files.open("catalog.json", "w") as f:
        print(json.dumps(catalog, indent=2, sort_keys=True), file=f)

    with mkdocs_gen_files.open("llms.txt", "w") as f:
        print("# pde_metrics\n", file=f)
        print("Metrics for evaluating machine-learning surrogates of PDEs. Each metric "
              "carries a card stating what it measures, how to read its output, where it "
              "misleads, and what it did on a recorded evaluation run.\n", file=f)
        print("For anything structural -- what exists, what it returns, how it behaved -- "
              "read /catalog.json rather than these pages.\n", file=f)
        print("## Metrics\n", file=f)
        for e in catalog["entries"]:
            if e["kind"] == "metric":
                print(f"- [{e['name']}](metrics/{e['name']}/): {e['summary']}", file=f)
        print("\n## Degradations\n", file=f)
        for e in catalog["entries"]:
            if e["kind"] == "degradation":
                print(f"- [{e['name']}](degradations/{e['name']}/): {e['summary']}", file=f)


main()
