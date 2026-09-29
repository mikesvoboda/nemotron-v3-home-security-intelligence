"""The prompt rules `check` enforces (agent-driven design §3.1)."""

from __future__ import annotations

import pytest
from synthbench.contract.spec import Cell, Prop, Spec, Subject
from synthbench.prompt import rules
from synthbench.taxonomy.model import load_taxonomy

TAX = load_taxonomy()
GOOD = "A delivery man in a navy rain jacket carries a cardboard parcel up the porch steps."


def _spec() -> Spec:
    return Spec(
        event_id="B-pilot-1-000",
        tier="B",
        corpus_version="tierb-v0",
        batch="pilot-1",
        cell=Cell(
            scenario="delivery_driver",
            group="benign",
            property_type="suburban_house",
            zone="front_porch",
            camera="doorbell_fisheye",
            lighting="day",
            weather="clear",
        ),
        scene_time="10:00",
        label="benign",
        risk_band=(0, 20),
        subjects=(Subject(id="S1", cls="person", role="delivery_driver"),),
        props=(Prop(id="X1", cls="package", held_by="S1"),),
    )


def test_a_prompt_naming_every_subject_and_prop_passes() -> None:
    assert rules.problems(_spec(), GOOD, TAX) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A man walks to the door.", "rule 1: mention prop X1 (package)"),
        ("A parcel sits by the door.", "rule 1: mention subject S1 (person)"),
        ("   ", "rule 1: the prompt is empty"),
    ],
)
def test_rule_1_needs_every_subject_and_prop(text: str, expected: str) -> None:
    found = rules.problems(_spec(), text, TAX)
    assert any(problem.startswith(expected) for problem in found), found


def test_terms_match_whole_words_in_any_order_with_plurals() -> None:
    assert rules.mentions("two guns on the table", ["gun"])
    assert not rules.mentions("a gunmetal gray car", ["gun"])
    assert rules.mentions("the frame of the window is bent", ["bent frame"])
    assert rules.mentions("boxes stacked by the door", ["box"])


@pytest.mark.parametrize(
    ("phrase", "rule"),
    [
        ("blood", "rule 2"),
        ("dead body", "rule 2"),
        ("celebrity", "rule 2"),
        ("security camera", "rule 4"),
        ("timestamp", "rule 4"),
        ("CCTV", "rule 4"),
    ],
)
def test_blocklisted_phrases_break_rules_2_and_4(phrase: str, rule: str) -> None:
    found = rules.problems(_spec(), f"{GOOD} {phrase}.", TAX)
    assert any(p.startswith(rule) and f"'{phrase.lower()}'" in p for p in found), found


def test_phrases_match_in_order_only() -> None:
    assert rules.contains_phrase("a dead body on the lawn", "dead body")
    assert not rules.contains_phrase("a dead leaf on the body of the car", "dead body")
    assert rules.contains_phrase("two wounds", "wound")


def test_rule_3_caps_the_length() -> None:
    long = GOOD + " The sky is gray." * 80
    assert len(long) > rules.MAX_PROMPT_CHARS
    assert any(p.startswith("rule 3:") for p in rules.problems(_spec(), long, TAX))


def test_the_prompt_and_suffix_fit_flux2s_512_tokens() -> None:
    # Plan ruling P3-R4: 512 tokens, 33 of them the chat template, 3.5 characters per token
    # at worst (English scene text measured 4.6-4.9).
    assert len(rules.CAMERA_SUFFIX) + 1 + rules.MAX_PROMPT_CHARS <= (512 - 33) * 3.5


def test_the_suffix_ends_by_forbidding_overlay_text() -> None:
    assert rules.CAMERA_SUFFIX.endswith("no on-screen text, no timestamp, no watermark.")


def test_no_fact_term_is_blocklisted() -> None:
    clashes = [
        (term, phrase)
        for terms in TAX.terms.values()
        for term in terms
        for phrases in rules.blocklist().values()
        for phrase in phrases
        if rules.contains_phrase(term, phrase)
    ]
    assert clashes == []


def test_the_blocklist_has_exactly_the_rule_categories() -> None:
    assert set(rules.blocklist()) == set(rules.RULE_OF_CATEGORY)


def test_render_text_is_the_prompt_then_the_suffix() -> None:
    spec = _spec().with_prompt(GOOD, rules.CAMERA_SUFFIX)
    assert rules.render_text(spec) == f"{GOOD} {rules.CAMERA_SUFFIX}"
    assert len(rules.prompt_sha256(spec)) == 64
    with pytest.raises(ValueError, match="no frozen prompt"):
        rules.render_text(_spec())
