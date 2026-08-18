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

import pytest
import yaml

from fmeval.cards import loader, prose, review
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
    assert parsed.applicability.regimes == ("any",)


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


def test_an_expectation_must_carry_a_reason():
    """A prediction without a rationale cannot be argued with, only believed."""
    with pytest.raises(CardError, match="rationale"):
        parse(card(expectations=[{"axis": "translate_x", "response": "increasing",
                                  "rationale": "grows"}]))


def test_an_expectation_names_a_statistic_the_analysis_actually_computes():
    with pytest.raises(CardError, match="statistic"):
        parse(card(expectations=[{"axis": "translate_x", "response": "increasing",
                                  "statistic": "vibes",
                                  "rationale": "a rationale long enough to pass"}]))


def test_a_full_expectation_round_trips():
    parsed = parse(card(expectations=[{
        "axis": "translate_x", "field": "vorticity", "response": "increasing",
        "statistic": "rho_median", "threshold": 0.9,
        "rationale": "Pointwise differences grow with displacement below the field scale.",
    }]))
    (expectation,) = parsed.expectations
    assert expectation.axis == "translate_x"
    assert expectation.field == "vorticity"
    assert expectation.dataset is None, "an unrestricted prediction applies to every dataset"


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
    with pytest.raises(CardError, match="weakest first"):
        parse({**base, "exemplars": {"mode": "severity", "levels": [16.0, 4.0, 1.0],
                                     "rationale": rationale}})


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
    defaults["Evidence"] = "{{ include _generated/evidence.md }}"
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
    claim = text.index("## Claim")
    intuition = text.index("## Intuition")
    reading = text.index("## Reading the output")
    swapped = text[:claim] + text[intuition:reading] + text[claim:intuition] + text[reading:]
    assert any("out of order" in p.message for p in problems_for(swapped))


def test_the_undergraduate_section_may_not_contain_notation():
    """Intuition is the one section a reader from another field is guaranteed to read."""
    text = build_prose(Intuition="The error is $\\sum (a-b)^2$ over cells. " * 30
                       + "\n\n```\n1 2\n```\n")
    assert any("mathematical notation" in p.message for p in problems_for(text))


def test_the_undergraduate_section_must_show_a_worked_example():
    text = build_prose(Intuition="Words about the idea, but no numbers anywhere. " * 30)
    assert any("worked example" in p.message for p in problems_for(text))


def test_a_short_section_is_a_warning_not_an_error():
    """Word floors are guesses. A section that says what it needs to in fewer words is a
    signal that the floor is wrong, not that the prose is."""
    text = build_prose(Limitations="Too short.")
    short = [p for p in problems_for(text) if "words" in p.message]
    assert short and all(p.severity == "warning" for p in short)


def test_a_hand_written_evidence_section_is_refused():
    """Prose here would be a claim about measurements that nothing checks."""
    text = build_prose(Evidence="MSE rises steeply with displacement, as predicted.")
    assert any("generated" in p.message for p in problems_for(text))


@pytest.mark.parametrize("sentinel", prose.SENTINELS)
def test_template_sentinels_block_completion(sentinel):
    text = build_prose(Claim=f"{sentinel} say what this detects.")
    assert any(sentinel in p.message for p in problems_for(text))


def test_front_matter_must_agree_with_the_bundle_name():
    assert any("front matter" in p.message for p in problems_for(build_prose(name="other")))


# --------------------------------------------------------------------------------------
# Review ledger
# --------------------------------------------------------------------------------------


def test_signing_is_insensitive_to_line_endings_and_trailing_space(tmp_path):
    """A colleague opening the file on another platform must not appear to have edited it."""
    bundle = loader.Bundle(name="example", kind="metric", path=tmp_path)
    (tmp_path / "card.md").write_text("## Claim\n\nSomething.\n")
    first = review.prose_digest(bundle)
    (tmp_path / "card.md").write_text("## Claim\r\n\r\nSomething.   \r\n")
    assert review.prose_digest(bundle) == first


def test_editing_prose_makes_a_signature_stale(tmp_path):
    bundle = loader.Bundle(name="example", kind="metric", path=tmp_path)
    (tmp_path / "card.md").write_text("## Claim\n\nOriginal.\n")
    signature = review.sign(bundle, "khegazy")
    assert review.review_state(bundle, signature["prose_sha256"]) == "current"
    (tmp_path / "card.md").write_text("## Claim\n\nRewritten by something.\n")
    assert review.review_state(bundle, signature["prose_sha256"]) == "stale"


def test_an_unsigned_card_reports_unsigned(tmp_path):
    bundle = loader.Bundle(name="example", kind="metric", path=tmp_path)
    (tmp_path / "card.md").write_text("## Claim\n\nSomething.\n")
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
def test_bundle_name_matches_the_registered_name(bundle):
    """The directory, the card and the decorator must agree on what this is called."""
    import degradations.registry as deg
    import metrics.registry as met

    registry = met if bundle.kind == "metric" else deg
    assert bundle.name in registry.available(), (
        f"{bundle.path} is a bundle, but nothing registers the name {bundle.name!r}. "
        f"Check the name= argument of its decorator."
    )


def test_bundle_ids_are_unique():
    names = [f"{b.kind}:{b.name}" for b in BUNDLES]
    assert len(names) == len(set(names))
