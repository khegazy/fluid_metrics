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
    "category": "pointwise",
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
    """`rejected` is absent on purpose: nothing here reduces a metric to pass or fail.

    `control` is absent too, and for a different reason. It answered "what kind of thing is
    this" while the other values answer "how far has the work got", so a metric could not be
    both a familiar baseline and unreviewed -- the field had to pick one. What kind of
    measurement a metric makes is `category`, which is orthogonal to this and is what the
    navigation groups by.
    """
    from fmeval.cards.schema import STATUSES

    assert "rejected" not in STATUSES
    assert "control" not in STATUSES
    assert set(STATUSES) == {"candidate", "validated", "deprecated"}
    with pytest.raises(CardError, match="status"):
        parse(card(status="rejected"))


def test_every_metric_type_can_be_said_in_words_on_the_site():
    """A type with no plain-language rendering reaches the reader as a bare code.

    `docs/gen_pages.py` prints the type in words in three places -- the header table on
    every metric page, the catalogue, and the navigation group label -- falling back to the
    raw code when it has no entry. That fallback is silent, so adding a value to CATEGORIES
    and forgetting the wording ships `functional` to a reader who has been told nothing.

    Skipped where the docs toolchain is not installed: `gen_pages` imports
    `mkdocs_gen_files` at module scope. It runs in the docs job, where the toolchain is
    present by definition.
    """
    import sys

    pytest.importorskip("mkdocs_gen_files", reason="the docs toolchain is not installed")

    sys.path.insert(0, str(REPO / "docs"))
    try:
        import gen_pages
    finally:
        sys.path.pop(0)

    from fmeval.cards.schema import CATEGORIES

    missing = sorted(set(CATEGORIES) - set(gen_pages._METRIC_CATEGORY))
    assert not missing, (
        f"docs/gen_pages.py:_METRIC_CATEGORY has no wording for {missing}; those types "
        "would appear on the site as their bare code"
    )
    unknown = sorted(set(gen_pages._METRIC_CATEGORY) - set(CATEGORIES))
    assert not unknown, (
        f"docs/gen_pages.py:_METRIC_CATEGORY describes {unknown}, which no card may "
        "declare; the schema and the site have come apart"
    )


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
        "What the degradation looks like",
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
    import os

    result = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(tmp_path)],
        cwd=REPO, capture_output=True, text=True,
        # Material's advisory about a future MkDocs 2 release is not about this site and
        # would otherwise fail --strict.
        env={**os.environ, "DISABLE_MKDOCS_2_WARNING": "true"},
    )
    assert result.returncode == 0, result.stderr[-3000:]
    assert (tmp_path / "catalog.json").is_file(), "the machine surface is missing"
    assert (tmp_path / "llms.txt").is_file()
    assert (tmp_path / "metrics" / "mse" / "index.html").is_file()
    assert (tmp_path / "degradations" / "gallery" / "index.html").is_file()


# --------------------------------------------------------------------------------------
# The generators, tested end to end on synthetic data
# --------------------------------------------------------------------------------------
#
# These functions rewrite committed files, so they were verified by hand when written and
# then trusted. That is backwards: the failure modes here -- unstable ordering between
# regenerations, a block swallowing its neighbour, regex escapes corrupting a body, silent
# key drift between writer and reader -- are all quiet, and every one of them would put
# wrong content into a card that looks exactly like right content.


def _synthetic_run(tmp_path):
    """A results folder small enough to analyse in milliseconds.

    Built from the analysis suite's own fixture so the columns are exactly what
    fmeval.analysis expects, then stamped with the canonical dataset name so
    `load_run` accepts it as citable evidence.
    """
    from tests.test_analysis import make_frame

    df = make_frame(
        metric="mse",
        axes={
            "gaussian_blur": [1.0, 2.0, 3.0, 4.0],
            "translate_x": [0.5, 1.0, 2.0, 4.0],
            "uncorrelated": [10.0, 10.0, 10.0],
            "gaussian_impostor": [8.0],
        },
    )
    df["dataset"] = "kinet_re5e4"
    folder = tmp_path / "comparison_synthetic"
    (folder / "data").mkdir(parents=True)
    df.to_csv(folder / "data" / "results.csv", index=False)
    return folder


def _bundle_copy(tmp_path, monkeypatch):
    """A throwaway copy of the mse bundle, so generators never touch tracked files."""
    import shutil

    from fmeval.cards import loader as loader_module

    dst = tmp_path / "mse"
    shutil.copytree(REPO / "metrics" / "mse", dst,
                    ignore=shutil.ignore_patterns("__pycache__"))
    bundle = loader.Bundle(name="mse", kind="metric", path=dst)
    monkeypatch.setattr(loader_module, "find_bundle", lambda *a, **k: bundle)
    return bundle


def test_evidence_generation_is_idempotent(tmp_path, monkeypatch):
    """Generating twice from the same run must change nothing the second time.

    The card and the fingerprint are committed, so any instability -- a dict whose
    ordering varies, a timestamp sneaking in, a DataFrame serialised in group order --
    shows up as a meaningless diff on every regeneration, and reviewers learn to ignore
    exactly the files where a real change matters most.
    """
    from fmeval.cards import evidence

    bundle = _bundle_copy(tmp_path, monkeypatch)
    run = evidence.load_run(_synthetic_run(tmp_path))

    evidence.generate("mse", run)
    first_card = bundle.card_md.read_bytes()
    first_print = (bundle.path / "_generated" / "fingerprint.json").read_bytes()

    evidence.generate("mse", run)
    assert bundle.card_md.read_bytes() == first_card
    assert (bundle.path / "_generated" / "fingerprint.json").read_bytes() == first_print


def test_evidence_fills_every_block_the_card_carries(tmp_path, monkeypatch):
    """Every generated block in the card must be written, not silently skipped.

    The generator only writes blocks whose marker it finds, which is right for family
    blocks a card legitimately lacks -- but it means a typo in a marker name would leave
    that block permanently saying "not generated yet" with no error anywhere. This pins
    the count: after generating, no block in the mse card still carries the placeholder.
    """
    from fmeval.cards import evidence

    bundle = _bundle_copy(tmp_path, monkeypatch)
    run = evidence.load_run(_synthetic_run(tmp_path))
    evidence.generate("mse", run)

    text = bundle.card_md.read_text()
    assert "Not generated yet" not in text, (
        "a generated block kept its placeholder; its marker name and the generator's "
        "block name disagree"
    )
    # And the numbers written are the synthetic run's, not leftovers.
    assert "comparison_synthetic" in text


def test_the_catalog_reads_what_the_evidence_writes(tmp_path, monkeypatch):
    """The fingerprint's keys are a contract between two modules; pin it.

    `evidence.py` writes `rho`; `catalog.py` reads `row.get("rho")` and publishes it as
    `rank_correlation`. `.get` means a renamed key would not raise -- it would publish
    null for every metric and the catalog would look measured-but-empty, which is worse
    than an error.
    """
    from fmeval.cards import catalog, evidence

    bundle = _bundle_copy(tmp_path, monkeypatch)
    run = evidence.load_run(_synthetic_run(tmp_path))
    evidence.generate("mse", run)

    measured = catalog._measured(bundle)
    assert measured["measured"] is True
    ordinary = [a for a in measured["axes"] if not a["is_probe"]]
    assert ordinary, "no ordinary axes surfaced from the fingerprint"
    for axis in ordinary:
        assert axis["rank_correlation"] is not None, (
            f"{axis['axis']}: rank_correlation is null -- the key contract between "
            "evidence.py and catalog.py has drifted"
        )
        assert axis["levels"] is not None
    probes = measured["probes"]
    assert probes and probes[0]["unrelated_field_value"] is not None


def test_write_block_replaces_only_its_block(tmp_path):
    """One block's rewrite must not disturb its neighbours or mangle its body.

    The body goes through a regex substitution, where a bare `\\1` or `$` in the
    replacement is interpreted rather than written. Measured tables contain dollar signs
    and backslashes routinely, so corruption here would be routine too.
    """
    from fmeval.cards.exemplars import write_block

    card = tmp_path / "card.md"
    card.write_text(
        "prose above\n\n"
        "<!-- GENERATED alpha: written by `cmd`, do not edit -->\n\nold alpha\n\n"
        "<!-- END GENERATED alpha -->\n\nprose between\n\n"
        "<!-- GENERATED beta: written by `cmd`, do not edit -->\n\nold beta\n\n"
        "<!-- END GENERATED beta -->\n\nprose below\n"
    )
    tricky = "a table with $ and \\1 and \\g<0> and $$maths$$"
    write_block(card, "alpha", tricky, command="cmd")

    text = card.read_text()
    assert tricky in text, "regex escapes corrupted the body"
    assert "old beta" in text, "writing alpha disturbed beta"
    assert "old alpha" not in text
    assert text.startswith("prose above") and text.rstrip().endswith("prose below")


def test_write_block_refuses_a_missing_marker_and_leaves_the_file_alone(tmp_path):
    from fmeval.cards.exemplars import write_block

    card = tmp_path / "card.md"
    original = "no markers here\n"
    card.write_text(original)
    with pytest.raises(KeyError, match="no 'alpha' generated block"):
        write_block(card, "alpha", "body", command="cmd")
    assert card.read_text() == original


def test_the_review_ledger_through_a_real_regeneration(tmp_path, monkeypatch):
    """The signature's whole point, exercised on files rather than strings.

    Regenerating evidence must not invalidate a human's signature -- they signed the
    prose, not the tables. Editing the prose must invalidate it. Both directions were
    tested on strings at the unit level; this drives them through sign, generate and
    review_state on a real bundle copy, which is the path production takes.
    """
    from fmeval.cards import evidence
    from fmeval.cards.review import review_state, sign

    bundle = _bundle_copy(tmp_path, monkeypatch)
    run = evidence.load_run(_synthetic_run(tmp_path))
    evidence.generate("mse", run)                      # the gate: evidence before signing

    assert review_state(bundle, None) == "unsigned"
    signature = sign(bundle, "someone")["prose_sha256"]
    assert review_state(bundle, signature) == "current"

    evidence.generate("mse", run)                      # regeneration: signature survives
    assert review_state(bundle, signature) == "current"

    bundle.card_md.write_text(bundle.card_md.read_text() + "\nA new sentence of prose.\n")
    assert review_state(bundle, signature) == "stale"  # prose edit: signature dies


def test_evidence_survives_a_run_whose_ladder_skipped_a_probe(tmp_path, monkeypatch):
    """A ladder without the impostor is legitimate; the generator must not crash on it.

    `probe_summary` only emits columns for probes that ran, so a run produced with
    `degradation.skip=[gaussian_impostor]` has no impostor columns at all. This used to
    raise a bare KeyError naming a column. Absent probes are "not measured", rendered as
    an em dash, never an error.
    """
    from tests.test_analysis import make_frame

    from fmeval.cards import evidence

    df = make_frame(metric="mse",
                    axes={"gaussian_blur": [1.0, 2.0], "uncorrelated": [10.0, 10.0]})
    df["dataset"] = "kinet_re5e4"
    folder = tmp_path / "comparison_noimpostor"
    (folder / "data").mkdir(parents=True)
    df.to_csv(folder / "data" / "results.csv", index=False)

    bundle = _bundle_copy(tmp_path, monkeypatch)
    evidence.generate("mse", evidence.load_run(folder))

    text = bundle.card_md.read_text()
    assert "comparison_noimpostor" in text
    assert "gaussian_blur" in text


def test_exemplar_panels_are_byte_identical_within_one_environment(tmp_path):
    """Rendering the same panel twice must produce the same bytes.

    The panels are committed, so nondeterminism here -- a timestamp in the PNG metadata,
    an unseeded jitter, an unordered iteration -- turns every regeneration into a diff on
    unchanged figures, and reviewers learn to skim exactly the files where a real change
    matters. Byte identity is only promised within one matplotlib version, which is what
    a single test run is.
    """
    import numpy as np
    from scipy.ndimage import gaussian_filter

    from fmeval.cards.figures import Column, exemplar_panel

    base = np.random.default_rng(0).normal(size=(48, 48))
    columns = [Column("original", base)] + [
        Column(f"sigma = {s} cells", gaussian_filter(base, s, mode="wrap"))
        for s in (1.0, 2.0, 4.0)
    ]
    rows = ["difference", "radial_spectrum", "pdf"]

    first = exemplar_panel(columns, rows, path=tmp_path / "a.png", title="determinism")
    second = exemplar_panel(columns, rows, path=tmp_path / "b.png", title="determinism")

    assert (tmp_path / "a.png").read_bytes() == (tmp_path / "b.png").read_bytes()
    # Compared through the sanitiser, because a NaN statistic -- "not measured" -- is
    # never equal to itself, and comparing raw dicts would fail on unchanged output.
    from fmeval.cards.exemplars import sanitize_json

    assert sanitize_json(first.statistics) == sanitize_json(second.statistics)


def test_every_panel_row_shares_one_set_of_limits(tmp_path):
    """The rule that keeps a strong degradation from looking like the original.

    Per-panel autoscaling is the single most effective way to make a severe degradation
    invisible, and it fails silently -- the figure looks fine. The difference row's limits
    must come from the strongest column, so the weak column reads as faint; a weak
    difference drawn on its own scale would look as severe as the strong one.
    """
    import numpy as np

    from fmeval.cards.figures import Column, _row_limits

    base = np.zeros((16, 16))
    weak, strong = base.copy(), base.copy()
    weak[8, 8] = 0.1
    strong[8, 8] = 10.0
    columns = [Column("original", base), Column("weak", weak), Column("strong", strong)]

    low, high = _row_limits("difference", columns, base)
    assert high == 10.0 and low == -10.0, (
        "difference limits must span the strongest severity, not each panel's own range"
    )


@pytest.mark.parametrize("bundle", BUNDLES, ids=IDS)
def test_every_generated_json_is_strict_json(bundle):
    """A committed fingerprint must be readable by an ordinary JSON parser.

    These files exist for machine readers. `json.dumps` writes float('nan') as a bare
    `NaN` token, which is not JSON and which a strict parser refuses -- so a single
    unmeasured statistic made a whole fingerprint unreadable. Thirteen committed files
    were in that state before this test existed. "Not a number" means "not measured", and
    null is how JSON says that.
    """
    def refuse(token):
        raise AssertionError(
            f"{bundle.name}: non-standard JSON token {token!r}. Regenerate: the writers "
            "sanitise NaN to null, so this file predates that fix."
        )

    for path in sorted((bundle.path / "_generated").glob("*.json")):
        json.loads(path.read_text(), parse_constant=refuse)


@pytest.mark.parametrize("bundle", BUNDLES, ids=IDS)
def test_a_committed_figure_has_its_numbers_beside_it(bundle):
    """Every panel must ship the statistics behind it.

    An agent reading the site cannot open a PNG. A figure with no numeric counterpart is
    unreadable to half this repository's intended audience, and the rule is easy to break
    by adding a figure without extending the generator that records its numbers.
    """
    for panel in sorted((bundle.path / "_generated").glob("*.png")):
        numbers = panel.with_suffix(".json")
        assert numbers.is_file(), (
            f"{bundle.name}: {panel.name} has no {numbers.name} beside it"
        )
        recorded = json.loads(numbers.read_text())
        assert recorded.get("panels"), f"{bundle.name}: {numbers.name} records no panels"
