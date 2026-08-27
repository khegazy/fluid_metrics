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
from fmeval.cards.loader import iter_bundles  # noqa: E402
from fmeval.cards.schema import CATEGORIES  # noqa: E402

#: Cards link to each other by repository-relative path so GitHub resolves them. On the
#: site, pages are flat under metrics/ and degradations/, so those links are rewritten.
_CARD_LINK = re.compile(r"\]\(\.\./\.\./(metrics|degradations)/([a-z0-9_]+)/card\.md\)")
#: Figures live beside the card in _generated/; the site serves them from the page's dir.
_ASSET = re.compile(r"\]\(_generated/([^)]+)\)")
#: A card link written from the repository root, as the protocol reference and the top-level
#: markdown files use. Same rewrite as _CARD_LINK, one directory level shallower.
_ROOT_CARD_LINK = re.compile(r"\]\((metrics|degradations)/([a-z0-9_]+)/card\.md\)")

#: What a degradation's severity number is measured against, said in words. The card
#: stores a short code; a first-time reader needs the sentence, not the code.
#: A metric's type -- what kind of measurement it makes -- said in words. The card stores
#: a short code and `catalog.json` carries it; a reader needs the sentence. Keys are
#: `fmeval.cards.schema.CATEGORIES`, and a test holds the two in step.
_METRIC_CATEGORY = {
    "pointwise": "compares the fields cell by cell",
    "physical": "a physical quantity of the flow",
    "spectral": "compares the fields scale by scale",
    "statistical": "compares distributions or moments of the field",
    "probabilistic": "compares whole ensembles",
    "transport": "the cost of moving one field onto the other",
    "functional": "a norm that weights the scales differently",
    "geometric": "where features are, and what shape they have",
    "topological": "which features exist, and how they connect",
}

#: A degradation reuses the `family` its registry entry declares rather than the metric
#: vocabulary above. The two overlap in spelling and not in meaning -- `pointwise` is
#: cell-by-cell *comparison* for a metric and cell-by-cell *distortion* for a degradation,
#: and `spectral` and `geometric` diverge the same way -- so they are separate maps and the
#: kind of the bundle chooses between them. One shared map silently mislabelled whichever
#: sense was written second.
_DEGRADATION_FAMILY = {
    "smoothing": "smoothing away fine detail",
    "spectral": "filtering out chosen scales",
    "geometric": "moving features to the wrong place",
    "resolution": "losing grid resolution",
    "stochastic": "adding noise",
    "pointwise": "distorting each cell's value",
    "ensemble": "making the ensemble the wrong width",
}

_CALIBRATION = {
    None: "a fixed number, the same on every field",
    "scale": "a fraction of the field's own characteristic length",
    "energy_above": "a fraction of the field's energy above the cutoff",
    "energy_below": "a fraction of the field's energy below the cutoff",
}


def _for_site(text: str, name: str) -> str:
    """Rewrite a card's repository-relative links and asset paths for the site.

    Assets are namespaced by bundle name. Every degradation calls its example panel
    ``exemplars.png``, so copying the panels into one directory under their own names
    would leave whichever panel was written last and silently show the wrong figure on
    twenty pages.
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
    kind_row = ("what kind of metric" if entry["kind"] == "metric"
                else "what kind of damage")
    rows = ["| | |", "|---|---|",
            f"| **{kind_row}** | {_category(entry)} |",
            f"| **how far the work has got** | `{entry['status']}` |"]
    if entry["kind"] == "metric":
        inputs = {"pairwise": "two fields: a prediction and the reference to compare it against",
                  "single": "one field on its own, which it characterises rather than compares",
                  }.get(declared["arity"], str(declared["arity"]))
        fields = declared["fields"]
        accepts = "any physical field" if list(fields) == ["*"] else ", ".join(fields)
        rows += [
            f"| **what it is given** | {inputs} |",
            f"| **physical fields it accepts** | {accepts} |",
            f"| **units of the value** | {declared['units']} |",
            f"| **which direction is better** | "
            f"{'higher is better' if declared['higher_is_better'] else 'lower is better'} |",
            f"| **usable as a training loss (differentiable)** | "
            f"{'yes' if declared['differentiable'] else 'no'} |",
            f"| **cost to evaluate** | {declared['cost']} |",
        ]
        if entry["math"]:
            rows.append(f"| **cost as the grid grows** | `{entry['math']['complexity']}` |")
    else:
        rows += [
            f"| **what its strength setting means** | {declared['severity_name']}"
            + (f", in {declared['severity_units']}" if declared["severity_units"] else "")
            + " |",
            f"| **that strength is measured against** | "
            f"{_CALIBRATION.get(declared['calibration'], declared['calibration'])} |",
            f"| **strengths run mildest to worst** | "
            f"{'yes' if declared['ordinal'] else 'no: this is a trap test, not a ladder'} |",
            f"| **uses randomness** | {'yes' if declared['stochastic'] else 'no'} |",
        ]
    evidence = entry["evidence"]
    measured = (f"`{evidence['run']}` on `{evidence['dataset']}`, "
                f"{evidence.get('frames', 0)} frames"
                if evidence["measured"] else "not yet measured")
    rows.append(f"| **measured on** | {measured} |")
    rows.append(f"| **read and signed by a person** | "
                f"{'yes, ' + str(entry['reviewed_at']) if entry['reviewed'] else 'not yet'} |")
    return "\n".join(rows)


#: Shown once at the top of every bundle page. A reader arriving from a search engine
#: lands on one of these pages and nowhere else, so the words the page cannot avoid using
#: are defined here rather than only on the home page.
_ORIENTATION = {
    "metric": "!!! info \"New here?\"\n"
              "    A **metric** scores how close a predicted fluid field is to the truth.\n"
              "    A **degradation** damages a trusted field by a known amount, so that\n"
              "    metrics can be tested against errors whose size and kind are already\n"
              "    known. **Damage** puts every metric on one 0-to-1 scale, where 0 is the\n"
              "    undamaged field and 1 is a field with no relationship to the truth.\n"
              "    Every other term is in the [glossary](../glossary.md), and\n"
              "    [how to read this page](../reading-guide.md) explains the layout below.",
    "degradation": "!!! info \"New here?\"\n"
                   "    A **degradation** damages a trusted fluid simulation by a known\n"
                   "    amount, standing in for a way a machine-learning model gets things\n"
                   "    wrong. Applying one at several increasing strengths gives errors of\n"
                   "    known size, which is how the **metrics** on this site are tested.\n"
                   "    Every other term is in the [glossary](../glossary.md), and the\n"
                   "    [gallery](gallery.md) shows every degradation side by side.",
}


def _category(entry: dict) -> str:
    """The bundle's type said in words, with the stored code beside it.

    Both are shown: the words are for a reader, and the code is what a contributor types
    into ``card.yaml`` and what ``catalog.json`` carries. Which vocabulary applies depends
    on the kind of bundle -- see the note on ``_DEGRADATION_FAMILY``.
    """
    code = entry["category"]
    words = _METRIC_CATEGORY if entry["kind"] == "metric" else _DEGRADATION_FAMILY
    said = words.get(code)
    return f"{said} (`{code}`)" if said else str(code)


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
            print(_ORIENTATION[bundle.kind] + "\n", file=f)
            print(_header(entry) + "\n", file=f)
            print(_for_site(card, bundle.name), file=f)
            print("\n" + _api(bundle), file=f)
        mkdocs_gen_files.set_edit_path(page, f"{bundle.path.parent.name}/{bundle.name}/card.md")

        # Figures are served from beside the page.
        for asset in sorted((bundle.path / "_generated").glob("*.png")):
            target = f"{bundle.path.parent.name}/_generated/{bundle.name}_{asset.name}"
            with mkdocs_gen_files.open(target, "wb") as f:
                f.write(asset.read_bytes())

        # Metrics are grouped in the navigation by type, degradations by nothing.
        (nav_metrics if bundle.kind == "metric" else nav_degradations).append(
            (bundle.name, entry["category"], f"{bundle.path.parent.name}/{bundle.name}.md")
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
        print("Every metric and every degradation in the repository. A **metric** scores "
              "how close a prediction is to the truth; a **degradation** damages a "
              "trusted field in a controlled way, so that the metrics can be tested "
              "against damage of a known size. The same content is available as "
              "[catalog.json](catalog.json).\n", file=f)
        print("## Metrics\n", file=f)
        print("| metric | how far the work has got | what kind of metric | units of the value | "
              "usable as a training loss | cost to evaluate | measured yet |", file=f)
        print("|---|---|---|---|---|---|---|", file=f)
        for e in catalog["entries"]:
            if e["kind"] != "metric":
                continue
            d = e["declared"]
            print(f"| [{e['name']}](metrics/{e['name']}.md) "
                  f"| <span class='status status-{e['status']}'>{e['status']}</span> "
                  f"| {_category(e)} | {d['units']} "
                  f"| {'yes' if d['differentiable'] else 'no'} | {d['cost']} "
                  f"| {'measured' if e['evidence']['measured'] else '—'} |", file=f)
        print("\n## Degradations\n", file=f)
        print("| degradation | what kind of damage | what its strength setting means | "
              "that strength is measured against | strengths run mildest to worst |",
              file=f)
        print("|---|---|---|---|---|", file=f)
        for e in catalog["entries"]:
            if e["kind"] != "degradation":
                continue
            d = e["declared"]
            units = f", in {d['severity_units']}" if d["severity_units"] else ""
            against = _CALIBRATION.get(d["calibration"], d["calibration"])
            print(f"| [{e['name']}](degradations/{e['name']}.md) | {_category(e)} "
                  f"| {d['severity_name']}{units} | {against} "
                  f"| {'yes' if d['ordinal'] else 'no: a trap test'} |", file=f)


def _write_gallery(catalog: dict) -> None:
    """Every example panel on one page, all drawn from the same snapshot.

    The fastest route into the project for a new reader: scrolling the gallery shows what
    each degradation does and how its strengths compare, which prose cannot do at any
    length.
    """
    with mkdocs_gen_files.open("degradations/gallery.md", "w") as f:
        print("# Gallery: what every degradation does to a field\n", file=f)
        print("A **degradation** damages a trusted simulation in a controlled way, so "
              "that a metric can be tested against damage of a known size and kind. "
              "Every degradation below is applied to the same snapshot of the same "
              "simulation, so the panels can be compared with one another.\n", file=f)
        print("In each figure the leftmost column is the original, undamaged field. The "
              "columns to its right are the same field after the degradation has been "
              "applied, getting stronger from left to right — or, for the few "
              "degradations that have no notion of strength, several independent random "
              "draws. The rows are different ways of looking at the same field.\n",
              file=f)
        for e in catalog["entries"]:
            if e["kind"] != "degradation":
                continue
            panel = REPO / "degradations" / e["name"] / "_generated" / "exemplars.png"
            print(f"## [{e['name']}]({e['name']}.md)\n", file=f)
            print(f"{e['summary']}\n", file=f)
            if panel.is_file():
                print(f"![{e['name']}](_generated/{e['name']}_exemplars.png)\n", file=f)
            else:
                print("*No panel: this operator leaves the field exactly as it found "
                      "it, so there would be nothing to show.*\n", file=f)


def _write_protocol() -> None:
    """TEST_DESCRIPTION.md, served as the protocol reference rather than duplicated.

    Its links to cards are written to resolve in the repository, where a card is
    `metrics/<name>/card.md`. On the site the pages are flat, so they are rewritten here --
    the same one-place fix the bundle pages need.
    """
    text = (REPO / "TEST_DESCRIPTION.md").read_text()
    text = _ROOT_CARD_LINK.sub(lambda m: f"]({m.group(1)}/{m.group(2)}.md)", text)
    with mkdocs_gen_files.open("protocol.md", "w") as f:
        print(text, file=f)


def _write_nav(metrics: list, degradations: list) -> None:
    """The navigation tree, with the metrics grouped by what kind of measurement they make.

    Grouping used to be by ``status``, which answered "how far has the work got" -- a
    question about this repository's progress rather than about metrics, and one that gave
    a reader scanning the sidebar no way to find the metric they wanted. Type answers
    "what does this thing look at", which is the question someone browsing actually has.
    The group label is the type said in words for the same reason.

    Groups follow the order of ``CATEGORIES`` rather than the alphabet, so the ordering is
    declared in one place and adding a type does not silently reshuffle the sidebar. A type
    with no metrics in it is skipped.

    The recipes and the deliberate-absences page are absent on purpose. They instruct
    somebody extending this repository, which is a different job from understanding a
    metric, and ``exclude_docs`` in ``mkdocs.yml`` keeps them out of the build entirely.
    """
    with mkdocs_gen_files.open("SUMMARY.md", "w") as f:
        print("- [Home](index.md)", file=f)
        print("- [How to read a metric page](reading-guide.md)", file=f)
        print("- [Choosing a metric](choosing-a-metric.md)", file=f)
        print("- [Working in the repository](working-with-the-repo.md)", file=f)
        print("- [Catalogue](catalogue.md)", file=f)
        print("- Metrics", file=f)
        for category in CATEGORIES:
            named = [m for m in metrics if m[1] == category]
            if named:
                said = _METRIC_CATEGORY.get(category, category)
                print(f"    - {category} — {said}", file=f)
                for name, _, page in sorted(named):
                    print(f"        - [{name}]({page})", file=f)
        # Anything whose type is not in CATEGORIES would vanish from the sidebar without
        # failing anything, so it is listed rather than dropped. The schema rejects such a
        # value, so reaching this is a sign the two have come apart.
        for name, category, page in sorted(m for m in metrics if m[1] not in CATEGORIES):
            print(f"    - [{name}]({page})", file=f)
        print("- Degradations", file=f)
        print("    - [Gallery: what each one does](degradations/gallery.md)", file=f)
        for name, _, page in sorted(degradations):
            print(f"    - [{name}]({page})", file=f)
        print("- [What the suite measures](protocol.md)", file=f)
        print("- [Glossary](glossary.md)", file=f)


def _write_machine_surfaces(catalog: dict) -> None:
    """catalog.json and llms.txt: what an agent reads instead of the rendered pages."""
    with mkdocs_gen_files.open("catalog.json", "w") as f:
        print(json.dumps(catalog, indent=2, sort_keys=True), file=f)

    with mkdocs_gen_files.open("llms.txt", "w") as f:
        print("# pde_metrics\n", file=f)
        print("Metrics for evaluating machine-learning surrogates of PDEs. Each metric "
              "carries a card stating what the metric measures, how to read its output, "
              "where the metric misleads, and what the metric did on a recorded "
              "evaluation run.\n", file=f)
        print("For anything structural -- what exists, what a metric returns, how a "
              "metric behaved -- read /catalog.json rather than these pages.\n", file=f)
        print("## Metrics\n", file=f)
        for e in catalog["entries"]:
            if e["kind"] == "metric":
                print(f"- [{e['name']}](metrics/{e['name']}/): {e['summary']}", file=f)
        print("\n## Degradations\n", file=f)
        for e in catalog["entries"]:
            if e["kind"] == "degradation":
                print(f"- [{e['name']}](degradations/{e['name']}/): {e['summary']}", file=f)


main()
