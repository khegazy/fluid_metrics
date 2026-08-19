"""The card contract: what every bundle must carry, and what a bad card must say.

Two kinds of test live here. The first checks the schema and the prose rules against
hand-built examples, so a change to the rules shows up as a specific failure rather than
as twenty bundles going red at once. The second is parametrized over every bundle on
disk, so a real bundle that drifts out of contract names itself.

The parametrized tests pass vacuously while no bundles exist yet. That is intended: the
card system lands before the bundles move, so the move can be verified one bundle at a
time.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import pathlib
import re

import pytest
import yaml

from fmeval.cards import loader, prose, review

REPO = pathlib.Path(__file__).resolve().parent.parent
from fmeval.cards.schema import SCHEMA_VERSION, CardError, parse_card

# --------------------------------------------------------------------------------------
# A minimal valid card, used as the base for the negative tests
# --------------------------------------------------------------------------------------

VALID_METRIC_CARD = {
    "schema_version": SCHEMA_VERSION,
    "name": "example",
    "kind": "metric",
    "category": "pointwise_norms",
    "summary": "An example card used by the tests, long enough to satisfy the floor.",
    "status": "candidate",
    "owners": ["khegazy"],
    "output": {
        "description": "Mean over cells of the squared difference.",
        "bounds": {"lower": 0.0, "upper": None},
    },
    "math": {
        "triangle_inequality": False,
        "scale_dependent": True,
        "resolution_dependent": True,
        "complexity": "O(N)",
    },
}


def card(**overrides):
    """A valid card mapping with the given keys replaced."""
    data = {k: (v.copy() if isinstance(v, dict) else v) for k, v in VALID_METRIC_CARD.items()}
    data.update(overrides)
    return data


def parse(data):
    return parse_card(data, where="test card")


# --------------------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------------------


def test_a_minimal_card_parses():
    parsed = parse(card())
    assert parsed.name == "example"
    assert parsed.status == "candidate"


@pytest.mark.parametrize("missing", ["name", "kind", "category", "summary", "status", "owners"])
def test_every_required_key_is_required(missing):
    data = card()
    del data[missing]
    with pytest.raises(CardError, match=missing):
        parse(data)


def test_an_unknown_key_is_rejected():
    """A key nothing reads is a claim nothing checks, which is the failure mode the card
    system exists to prevent. A typo must not pass silently."""
    with pytest.raises(CardError, match="unrecognised key"):
        parse(card(triangle_inequality=True))


def test_status_vocabulary_is_closed_and_has_no_rejected_value():
    """`rejected` is absent on purpose: nothing here reduces a metric to pass or fail."""
    from fmeval.cards.schema import STATUSES

    assert "rejected" not in STATUSES
    assert set(STATUSES) == {"candidate", "validated", "control", "deprecated"}
    with pytest.raises(CardError, match="status"):
        parse(card(status="rejected"))


def test_a_metric_needs_a_category_from_the_vocabulary():
    with pytest.raises(CardError, match="category"):
        parse(card(category="fluids"))


def test_a_metric_card_needs_its_math_block():
    data = card()
    del data["math"]
    with pytest.raises(CardError, match="math"):
        parse(data)


def test_bounds_must_be_ordered():
    with pytest.raises(CardError, match="not below"):
        parse(card(output={"description": "Something measurable.",
                           "bounds": {"lower": 1.0, "upper": 0.0}}))


def test_a_newer_schema_version_is_refused_rather_than_guessed_at():
    """A card from the future may use fields this code cannot interpret. Refusing is the
    only safe answer; the error tells the reader to update rather than to edit the card."""
    with pytest.raises(CardError, match="newer than this checkout"):
        parse(card(schema_version=SCHEMA_VERSION + 1))


def test_a_card_cannot_carry_a_prediction():
    """Nothing in a card may state how a metric is expected to behave.

    A statement about behaviour is either measured -- and then it belongs in the
    generated evidence -- or it comes from published work, and then it belongs in
    `## Definition` or `## Assessment` with a citation. An unsourced prediction is an
    opinion, and an opinion in structured YAML reads like a finding.
    """
    with pytest.raises(CardError, match="unrecognised key"):
        parse(card(expectations=[{"axis": "translate_x", "response": "increasing"}]))


def test_a_degradation_card_must_illustrate_itself():
    """A degradation whose effect is never shown cannot be understood from prose alone."""
    data = card(kind="degradation", category="smoothing")
    del data["math"]
    with pytest.raises(CardError, match="exemplars"):
        parse(data)


def test_severity_exemplars_need_exactly_three_ordered_levels():
    base = card(kind="degradation", category="smoothing")
    del base["math"]
    rationale = "Weak is at the grid limit, strong removes the inertial range."
    with pytest.raises(CardError, match="three"):
        parse({**base, "exemplars": {"mode": "severity", "levels": [1.0, 4.0],
                                     "rationale": rationale}})
    # Ordering is checked against the operator's declared severity_direction, in
    # fmeval.cards.loader, rather than here: for band_attenuate a smaller number is a
    # stronger degradation, so a numeric sort would call its correct ordering wrong.
    descending = parse({**base, "exemplars": {"mode": "severity", "levels": [16.0, 4.0, 1.0],
                                              "rationale": rationale}})
    assert descending.exemplars.levels == (16.0, 4.0, 1.0)


def test_exemplar_order_is_checked_against_the_declared_direction():
    """A decreasing-severity operator lists its exemplars largest first, and that is right.

    band_attenuate states a *retained* fraction, so 0.8 is milder than 0.0. The check
    lives where the registry spec is in hand, because "weakest" is not a numeric fact.
    """
    from degradations import registry as deg
    from fmeval.cards import loader

    deg.discover()
    bundle = loader.find_bundle("band_attenuate")
    card = loader.load_card(bundle)
    assert card.exemplars.levels == (0.8, 0.5, 0.0)
    loader._check_exemplar_order(card, deg.get("band_attenuate"), bundle)  # must not raise

    inverted = deg.get("gaussian_blur")
    with pytest.raises(CardError, match="weakest to strongest"):
        loader._check_exemplar_order(card, inverted, bundle)


def test_a_degradation_without_an_ordered_severity_uses_draws_instead():
    """The phase-randomised impostor has no severity, and the unrelated-field anchor is
    indexed by draw number. Neither can be shown as weak/medium/strong."""
    base = card(kind="degradation", category="stochastic")
    del base["math"]
    parsed = parse({**base, "exemplars": {
        "mode": "draws", "n_draws": 3,
        "rationale": "Severity is meaningless here; independent draws show the spread.",
    }})
    assert parsed.exemplars is not None
    assert parsed.exemplars.mode == "draws"
    assert parsed.exemplars.levels == ()


def test_a_review_signature_must_look_like_a_digest():
    with pytest.raises(CardError, match="sha256"):
        parse(card(review={"prose_sha256": "not-a-hash", "reviewer": "x",
                           "date": "2026-08-18"}))


def test_a_review_round_trips():
    parsed = parse(card(review={"prose_sha256": "a" * 64, "reviewer": "khegazy",
                                "date": "2026-08-18"}))
    assert parsed.review is not None
    assert parsed.review.date == dt.date(2026, 8, 18)


# --------------------------------------------------------------------------------------
# Prose
# --------------------------------------------------------------------------------------


def build_prose(name="example", **bodies):
    """Assemble a metric card.md with every required section present."""
    defaults = {section: f"Body for {section}. " * 40 for section in prose.METRIC_SECTIONS}
    defaults["Intuition"] = (
        "A physical picture without symbols. " * 30
        + "\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
        + "It ignores where a feature sits."
    )
    defaults["Definition"] = (
        "Body for Definition. " * 20
        + "\n\n### Boundary handling\n\nNone. The operation is local to each cell."
    )
    defaults["Performance"] = "<!-- GENERATED performance: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED performance -->"
    defaults["Results"] = (
        "### Smoothing\n\n"
        "[gaussian_blur](../../degradations/gaussian_blur/card.md)\n\n"
        "<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED results_smoothing -->\n\n"
        + "What the smoothing axes found, stated in enough words to clear the floor. " * 4
    )
    defaults["References"] = "\\bibliography"
    defaults.update(bodies)
    text = f"---\nname: {name}\nkind: metric\n---\n\n"
    for section in prose.METRIC_SECTIONS:
        text += f"## {section}\n\n{defaults[section]}\n\n"
    return text


def problems_for(text, **kwargs):
    kwargs.setdefault("kind", "metric")
    kwargs.setdefault("name", "example")
    return prose.check_prose(text, **kwargs)


def test_a_complete_card_has_no_prose_problems():
    assert problems_for(build_prose()) == []


def test_a_missing_section_is_named():
    text = build_prose().replace("## Limitations", "## Limits")
    messages = [p.message for p in problems_for(text)]
    assert any("Limitations" in m for m in messages)


def test_sections_must_be_in_the_fixed_order():
    text = build_prose()
    first, second, third = prose.METRIC_SECTIONS[:3]
    a, b, c = (text.index(f"## {s}") for s in (first, second, third))
    swapped = text[:a] + text[b:c] + text[a:b] + text[c:]
    assert any("out of order" in p.message for p in problems_for(swapped))


def test_the_declared_order_is_the_one_the_cards_use():
    """The order is a decision, so it is written down once and asserted here.

    Definition first: the equation is the thing being documented, and every later section
    is commentary on it. The account of the metric itself finishes with Limitations, and
    only then does the card turn to what this repository measured -- so a reader adopting
    the metric elsewhere can stop after Limitations and have everything that holds
    independently of our runs.
    """
    assert prose.METRIC_SECTIONS == (
        "Definition",
        "Performance",
        "Intuition",
        "Reading the output",
        "Limitations",
        "Results",
        "References",
    )
    assert prose.DEGRADATION_SECTIONS == (
        "Definition",
        "Intuition",
        "Severity scale",
        "Limitations",
        "Exemplars",
        "References",
    )


def test_the_outside_reader_section_may_not_contain_notation():
    """Intuition is the one section a reader from another field is guaranteed to read."""
    text = build_prose(Intuition="The error is $\\sum (a-b)^2$ over cells. " * 30
                       + "\n\n```\n1 2\n```\n")
    assert any("mathematical notation" in p.message for p in problems_for(text))


def test_the_outside_reader_section_must_show_a_worked_example():
    text = build_prose(Intuition="Words about the idea, but no numbers anywhere. " * 30)
    assert any("worked example" in p.message for p in problems_for(text))


def test_the_definition_must_state_its_boundary_handling():
    """The detail most likely to differ silently between two implementations.

    Periodic wrap, reflection, zero padding and dropping the edge give different numbers
    from the same formula, and a reader comparing across projects cannot tell which was
    used. Silence and "none" look identical; only one of them is a claim.
    """
    text = build_prose(Definition="An equation and some words about it. " * 10)
    assert any("Boundary handling" in p.message for p in problems_for(text))


def test_none_is_an_acceptable_boundary_answer():
    text = build_prose(
        Definition=(
            "An equation and some words about it. " * 10
            + "\n\n### Boundary handling\n\nNone. The operation is local to each cell."
        )
    )
    assert not any("Boundary handling" in p.message for p in problems_for(text))


def test_the_performance_summary_may_not_be_hand_written():
    """A number typed into the summary is a claim about a measurement nothing checks.

    The section sits near the top so it can be read at a glance and compared across
    metrics, which is exactly why it must come from the generator rather than from
    whoever last edited the card.
    """
    text = build_prose(Performance="Excellent on smoothing, weak on displacement.")
    assert any("hand-written" in p.message for p in problems_for(text))


def test_the_performance_summary_accepts_its_include():
    text = build_prose(Performance="<!-- GENERATED performance: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED performance -->")
    assert not any(p.section == "Performance" for p in problems_for(text))


def test_results_must_be_broken_into_subsections():
    """One kind of test per subsection, so evidence sits beside the claim it supports."""
    text = build_prose(Results="Everything went well across the whole ladder. " * 10)
    assert any("no '###' subsections" in p.message for p in problems_for(text))


def test_a_result_subsection_needs_its_generated_numbers():
    text = build_prose(
        Results="### Smoothing\n\nMSE rose steeply with kernel width. " * 6
    )
    assert any("generated block" in p.message for p in problems_for(text))


def test_measurements_come_before_the_explanation():
    """The number is the evidence; the prose reads it. Reversed, the prose leads."""
    text = build_prose(
        Results=(
            "### Smoothing\n\nMSE rose steeply with kernel width, as the numbers below "
            "show and as anyone would say. \n\n<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED results_smoothing -->\n"
        )
    )
    assert any("before its generated numbers" in p.message for p in problems_for(text))


def test_an_unexplained_result_subsection_warns_but_does_not_fail():
    """A subsection whose evidence has not been generated has nothing to explain yet."""
    text = build_prose(
        Results=(
            "### Smoothing\n\n"
            "[gaussian_blur](../../degradations/gaussian_blur/card.md)\n\n"
            "<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED results_smoothing -->\n"
        )
    )
    problems = problems_for(text)
    unexplained = [p for p in problems if "nothing said about them" in p.message]
    assert unexplained and all(p.severity == "warning" for p in unexplained)


def test_the_contract_sets_no_word_counts():
    """Length is described in the templates and judged by a reader, never counted.

    A count measures length rather than clarity, and an author told to reach a number
    reaches that number -- so the check would manufacture the padding it was meant to
    prevent.
    """
    assert not hasattr(prose, "WORD_FLOORS")
    assert not hasattr(prose, "RESULT_PROSE_FLOOR")
    assert not hasattr(prose, "RESULT_PROSE_CEILING")
    long_enough = build_prose(Limitations="It saturates on shifted shocks.")
    assert not any(
        "words" in p.message and p.section == "Limitations" for p in problems_for(long_enough)
    )


def test_the_run_summary_may_precede_the_subsections():
    """One include before the first subsection is the run summary, stated once.

    Which dataset, resolution and frames produced the numbers is the same for every
    subsection of every card, so it is said here rather than thirty times.
    """
    text = build_prose(
        Results=(
            "<!-- GENERATED run: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED run -->\n\n### Smoothing\n\n"
            "[gaussian_blur](../../degradations/gaussian_blur/card.md)\n\n"
            "<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED results_smoothing -->\n\n"
            + "What the smoothing axes found, at length. " * 5
        )
    )
    assert not any("before its first subsection" in p.message for p in problems_for(text))


def test_a_second_preamble_include_is_refused():
    text = build_prose(
        Results=(
            "<!-- GENERATED run: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED run -->\n\n"
            "<!-- GENERATED results_summary: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED results_summary -->\n\n### Smoothing\n\n"
            "[gaussian_blur](../../degradations/gaussian_blur/card.md)\n\n"
            "<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED results_smoothing -->\n\n"
            + "What the smoothing axes found, at length. " * 5
        )
    )
    assert any("before its first subsection" in p.message for p in problems_for(text))


def test_a_result_subsection_must_link_to_its_degradations():
    """The card sends the reader out for what the test is, rather than restating it."""
    text = build_prose(
        Results=(
            "### Smoothing\n\n<!-- GENERATED results_smoothing: written by `python -m fmeval.cards evidence example`, do not edit -->\n\nplaceholder\n\n<!-- END GENERATED results_smoothing -->\n\n"
            + "What the smoothing axes found, at length. " * 5
        )
    )
    assert any("does not link to the degradations" in p.message for p in problems_for(text))


def test_the_portable_subset_is_accepted():
    text = (
        "Inline $f_{c,i}$ and a display equation:\n\n"
        "$$\n\\mathrm{MSE} = \\frac{1}{N} \\sum_i d_i^2 \\tag{1}\n$$\n\n"
        "as Equation (1) shows.\n"
    )
    assert prose.check_math(text) == []


def test_an_unterminated_display_block_is_caught():
    """One missing fence swallows the rest of the section into an equation."""
    problems = prose.check_math("$$\nx = 1\n\n## Next section\n")
    assert any("unterminated" in p.message for p in problems)


def test_an_unterminated_inline_equation_is_caught():
    problems = prose.check_math("The value $x is large.\n")
    assert any("odd number of `$`" in p.message for p in problems)


def test_math_inside_a_code_block_is_left_alone():
    """A card may legitimately show LaTeX source as an example of what not to write."""
    text = "```\n\\begin{equation}\nx = 1\n\\end{equation}\n```\n"
    assert prose.check_math(text) == []


def test_front_matter_must_agree_with_the_bundle_name():
    assert any("front matter" in p.message for p in problems_for(build_prose(name="other")))


# --------------------------------------------------------------------------------------
# Review ledger
# --------------------------------------------------------------------------------------


def test_signing_is_insensitive_to_line_endings_and_trailing_space(tmp_path):
    """A colleague opening the file on another platform must not appear to have edited it."""
    bundle = loader.Bundle(name="example", kind="metric", path=tmp_path)
    (tmp_path / "card.md").write_text("## Intuition\n\nSomething.\n")
    first = review.prose_digest(bundle)
    (tmp_path / "card.md").write_text("## Intuition\r\n\r\nSomething.   \r\n")
    assert review.prose_digest(bundle) == first


def test_editing_prose_makes_a_signature_stale(tmp_path):
    bundle = loader.Bundle(name="example", kind="metric", path=tmp_path)
    (tmp_path / "card.md").write_text("## Intuition\n\nOriginal.\n")
    signature = review.sign(bundle, "khegazy")
    assert review.review_state(bundle, signature["prose_sha256"]) == "current"
    (tmp_path / "card.md").write_text("## Intuition\n\nRewritten by something.\n")
    assert review.review_state(bundle, signature["prose_sha256"]) == "stale"


def test_an_unsigned_card_reports_unsigned(tmp_path):
    bundle = loader.Bundle(name="example", kind="metric", path=tmp_path)
    (tmp_path / "card.md").write_text("## Intuition\n\nSomething.\n")
    assert review.review_state(bundle, None) == "unsigned"


# --------------------------------------------------------------------------------------
# Loader
# --------------------------------------------------------------------------------------


def test_a_card_whose_name_disagrees_with_its_directory_is_refused(tmp_path):
    """The name is the metric's identity; two answers to 'what is this called' is a bug."""
    (tmp_path / "card.yaml").write_text(yaml.safe_dump(card(name="something_else")))
    bundle = loader.Bundle(name="example", kind="metric", path=tmp_path)
    with pytest.raises(CardError, match="directory"):
        loader.load_card(bundle)


def test_a_missing_card_names_the_command_that_creates_one(tmp_path):
    bundle = loader.Bundle(name="example", kind="metric", path=tmp_path)
    with pytest.raises(CardError) as caught:
        loader.load_card(bundle)
    assert "python -m fmeval.cards new example" in str(caught.value)


def test_every_card_error_states_where_what_and_the_fix():
    """The error message is the product. An agent given a good one fixes the problem; an
    agent given `False is not True` guesses."""
    with pytest.raises(CardError) as caught:
        parse(card(status="excellent"))
    message = str(caught.value)
    assert "test card" in message and "status" in message and "Fix:" in message


# --------------------------------------------------------------------------------------
# Every bundle on disk
# --------------------------------------------------------------------------------------

BUNDLES = loader.iter_bundles()
IDS = [f"{b.kind}:{b.name}" for b in BUNDLES]


@pytest.mark.parametrize("bundle", BUNDLES, ids=IDS)
def test_bundle_has_every_required_file(bundle):
    assert check_files(bundle) == [], f"{bundle.name}: " + "; ".join(check_files(bundle))


def check_files(bundle):
    return loader.check_bundle_files(bundle)


@pytest.mark.parametrize("bundle", BUNDLES, ids=IDS)
def test_bundle_card_is_valid(bundle):
    loader.load_card(bundle)


@pytest.mark.parametrize("bundle", BUNDLES, ids=IDS)
def test_bundle_prose_has_no_errors(bundle):
    """Warnings are allowed while a bundle is in progress; errors are not."""
    card_ = loader.load_card(bundle)
    problems = prose.check_prose(
        bundle.card_md.read_text(), kind=bundle.kind, name=bundle.name
    )
    blocking = [
        p for p in problems if p.severity == "error" or card_.status == "validated"
    ]
    assert not blocking, "\n".join(f"{p.section}: {p.message}" for p in blocking)


@pytest.mark.parametrize("bundle", BUNDLES, ids=IDS)
def test_every_equation_in_every_card_actually_typesets(bundle):
    """Run each card through the documentation site's markdown pipeline.

    The rules in ``check_math`` are a proxy: they ban the constructs known to fail. This
    test is the real thing -- it converts the card and asserts that every equation was
    recognised as math and that no LaTeX command survived into the output as literal
    text, which is exactly how an unrenderable equation presents itself to a reader.

    Skipped where the docs toolchain is not installed, so the fast suite stays
    dependency-free; it runs in the docs job, where the toolchain is present by
    definition.
    """
    markdown = pytest.importorskip(
        "markdown", reason="the docs toolchain is not installed in this environment"
    )
    pytest.importorskip("pymdownx", reason="the docs toolchain is not installed")

    text = bundle.card_md.read_text()
    body = text.split("---", 2)[2] if text.startswith("---") else text

    # The strict reader is GitHub, which recognises only dollar delimiters. Restricting
    # arithmatex to those models it: anything GitHub would print as raw source is left as
    # raw source here too. Running the site's own permissive configuration instead would
    # give false assurance, because it happily typesets \begin{equation}, which GitHub
    # does not -- that difference is the whole failure mode this test exists to catch.
    for label, config in (
        ("GitHub", {"generic": True, "block_syntax": ["dollar"],
                    "inline_syntax": ["dollar"]}),
        ("the documentation site", {"generic": True}),
    ):
        html = markdown.markdown(
            body,
            extensions=["pymdownx.arithmatex", "tables", "fenced_code"],
            extension_configs={"pymdownx.arithmatex": config},
        )
        untypeset = re.sub(
            r'<(div|span) class="arithmatex">.*?</\1>', "", html, flags=re.DOTALL
        )
        untypeset = re.sub(r"<code>.*?</code>", "", untypeset, flags=re.DOTALL)

        leaked = sorted(set(re.findall(r"\\(?:begin|end|label|eqref)\{[^}]*\}", untypeset)))
        assert not leaked, (
            f"{bundle.name}: on {label} these commands are not typeset and are shown to "
            f"the reader as raw source: {leaked}"
        )
        assert "$$" not in untypeset, (
            f"{bundle.name}: on {label} a `$$` survives as literal text, so a display "
            "equation was not recognised as math."
        )


@pytest.mark.parametrize("bundle", BUNDLES, ids=IDS)
def test_every_degradation_a_card_links_to_exists(bundle):
    """A card's links out must land somewhere.

    A metric card sends the reader to the degradation bundles for what each test does,
    rather than repeating it. That only works while the targets exist, and a dead link
    is worse than no link -- it looks like the explanation is one click away.

    Missing targets are reported rather than tolerated. While the degradations are still
    being migrated into bundles this test will name the ones not yet moved, which is the
    intended signal.
    """
    degradations = pathlib.Path(__file__).resolve().parent.parent / "degradations"
    if not any(d.is_dir() and not d.name.startswith("_") for d in degradations.iterdir()):
        pytest.skip("no degradation bundles yet; the links are targets for the migration")

    text = bundle.card_md.read_text()
    targets = re.findall(r"\]\((\.\./\.\./degradations/[a-z0-9_]+/card\.md)\)", text)
    missing = sorted({
        target for target in targets
        if not (bundle.path / target).resolve().is_file()
    })
    assert not missing, (
        f"{bundle.name}: links to degradation bundles that do not exist yet: {missing}"
    )


@pytest.mark.parametrize("bundle", BUNDLES, ids=IDS)
def test_bundle_name_matches_the_registered_name(bundle):
    """The directory, the card and the decorator must agree on what this is called."""
    import degradations.registry as deg
    import metrics.registry as met

    registry = met if bundle.kind == "metric" else deg
    assert bundle.name in registry.available(), (
        f"{bundle.path} is a bundle, but nothing registers the name {bundle.name!r}. "
        f"Check the name= argument of its decorator."
    )


@pytest.mark.parametrize("kind", ["metric", "degradation"])
def test_template_is_valid_apart_from_its_sentinels(kind):
    """A template that has drifted out of validity is how systems like this die.

    Every bundle starts as a copy of the template, so if the template itself would fail a
    check, every new bundle inherits that failure and the author learns to ignore the
    checker. The template must therefore pass everything except the ``TODO`` markers,
    which are the one thing it is supposed to fail on.
    """
    template = loader.bundle_root(kind) / "_template"
    bundle = loader.Bundle(name=template.name, kind=kind, path=template)

    assert loader.check_bundle_files(bundle) == []

    text = bundle.card_md.read_text()
    placeholder = f"template_{'metric' if kind == 'metric' else 'degradation'}"
    problems = prose.check_prose(text, kind=kind, name=placeholder)
    unexpected = [
        p
        for p in problems
        if p.severity == "error" and not any(s in p.message for s in prose.SENTINELS)
    ]
    assert not unexpected, "\n".join(f"{p.section}: {p.message}" for p in unexpected)


@pytest.mark.parametrize("kind", ["metric", "degradation"])
def test_template_is_not_itself_a_bundle(kind):
    """The underscore keeps it out of discovery, the catalog and the registry."""
    assert all(b.name != "_template" for b in loader.iter_bundles())


def test_bundle_ids_are_unique():
    names = [f"{b.kind}:{b.name}" for b in BUNDLES]
    assert len(names) == len(set(names))


# --------------------------------------------------------------------------------------
# Evidence: the measured half of a card
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("bundle", [b for b in BUNDLES if b.kind == "metric"],
                         ids=[b.name for b in BUNDLES if b.kind == "metric"])
def test_a_fingerprint_never_cites_the_dev_dataset(bundle):
    """The dev dataset is the first 100 solver steps, before the flow develops.

    Its numbers mean nothing physically, and once written into a card they would be
    indistinguishable from ones that do. The generator refuses such a run; this checks
    nothing already committed slipped through by another route.
    """
    fingerprint = bundle.path / "_generated" / "fingerprint.json"
    if not fingerprint.is_file():
        pytest.skip(f"{bundle.name} has no measurements yet")
    recorded = json.loads(fingerprint.read_text())["dataset"]
    assert not recorded.endswith("_dev"), (
        f"{bundle.name} cites {recorded}, which is a smoke-test dataset"
    )


@pytest.mark.parametrize("bundle", [b for b in BUNDLES if b.kind == "metric"],
                         ids=[b.name for b in BUNDLES if b.kind == "metric"])
def test_a_signed_card_has_measurements_behind_it(bundle):
    """A signature stands behind claims about how the metric behaved.

    Most of a card's claims are measured ones, so there is nothing for a signature to
    stand behind until a run exists. `fmeval.cards sign` refuses in that case; this is the
    check on what is committed.
    """
    card = yaml.safe_load(bundle.card_yaml.read_text())
    if not card.get("review"):
        return
    assert (bundle.path / "_generated" / "fingerprint.json").is_file(), (
        f"{bundle.name} is signed but has no fingerprint.json: the signature stands "
        "behind claims nothing measured"
    )


def test_evidence_refuses_a_run_on_a_dataset_cards_may_not_cite(tmp_path):
    import pandas as pd

    from fmeval.cards import evidence

    folder = tmp_path / "comparison_1"
    (folder / "data").mkdir(parents=True)
    pd.DataFrame({"dataset": ["kinet_re5e4_dev"], "metric": ["mse"], "field": ["vorticity"],
                  "value": [1.0]}).to_csv(folder / "data" / "results.csv", index=False)

    with pytest.raises(ValueError, match="cards may not cite"):
        evidence.load_run(folder)


# --------------------------------------------------------------------------------------
# The catalog: the surface agents read instead of prose
# --------------------------------------------------------------------------------------


def test_the_catalog_covers_every_bundle():
    from fmeval.cards.catalog import build

    catalog = build()
    names = {e["name"] for e in catalog["entries"]}
    assert names == {b.name for b in BUNDLES}
    assert catalog["counts"]["metrics"] + catalog["counts"]["degradations"] == len(BUNDLES)


def test_the_catalog_reports_the_code_not_the_card():
    """Declared properties come from the registry, so a card cannot overstate them.

    A catalog entry is a contract an agent acts on. If it took `differentiable` from the
    prose half of a card, a metric could claim to be usable as a training loss because
    someone wrote that it was.
    """
    from metrics import registry

    from fmeval.cards.catalog import entry
    from fmeval.cards.loader import find_bundle

    e = entry(find_bundle("nrmse"))
    spec = registry.get("nrmse")
    assert e["declared"]["symmetric"] is spec.symmetric is False
    assert e["declared"]["units"] == spec.units == "dimensionless"


def test_an_unmeasured_bundle_says_so_rather_than_omitting_the_key():
    """A consumer must tell "not measured" from "measured and unremarkable"."""
    from fmeval.cards.catalog import entry
    from fmeval.cards.loader import find_bundle

    e = entry(find_bundle("gaussian_blur"))
    assert e["evidence"]["measured"] is False
    assert e["evidence"]["axes"] == []


def test_the_catalog_supports_the_query_it_exists_for():
    """"Which metrics are differentiable, cheap, and measured?" without reading prose."""
    from fmeval.cards.catalog import build

    answer = [
        e["name"] for e in build()["entries"]
        if e["kind"] == "metric"
        and e["declared"]["differentiable"]
        and e["declared"]["cost"] == "cheap"
        and e["evidence"]["measured"]
    ]
    assert set(answer) == {"mae", "mse", "rmse", "nrmse", "enstrophy", "kinetic_energy"}


# --------------------------------------------------------------------------------------
# The site
# --------------------------------------------------------------------------------------


def test_the_committed_catalog_matches_the_bundles():
    """`docs/catalog.json` is generated and committed, so it can go stale.

    CI rebuilds and diffs it; this fails locally first, which is where it is cheaper to
    notice.
    """
    from fmeval.cards.catalog import build

    committed = json.loads((REPO / "docs" / "catalog.json").read_text())
    assert committed == build(), (
        "docs/catalog.json is stale; run  python -m fmeval.cards catalog"
    )


@pytest.mark.slow
def test_the_site_builds_without_the_dataset(tmp_path):
    """The site must build on a machine with no CFS mount.

    Everything it needs -- cards, figures, fingerprints -- is committed, and the page
    generator reads those rather than running anything. If that stops being true the site
    becomes unbuildable by anyone without NERSC access, and CI is the first to find out.
    """
    import subprocess

    pytest.importorskip("mkdocs", reason="the docs toolchain is not installed")
    result = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(tmp_path)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    assert (tmp_path / "catalog.json").is_file(), "the machine surface is missing"
    assert (tmp_path / "llms.txt").is_file()
    assert (tmp_path / "metrics" / "mse" / "index.html").is_file()
    assert (tmp_path / "degradations" / "gallery" / "index.html").is_file()
