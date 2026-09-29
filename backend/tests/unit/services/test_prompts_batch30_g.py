# TARGET-MODULE: backend.services.prompts
"""Batch-30 kill battery (fragment G): prompts.py classifier-context renderers.

Scope — the 89 surviving mutant keys triaged for
``format_vehicle_classification_context`` (23 — note the triage excerpt lists 22,
it omits mutmut_20 ``sorted_scores = None``, which the gate grid below kills),
``format_pet_classification_context`` (20), ``format_age_classification_context``
(16), ``format_florence_scene_context`` (15) and ``format_weather_context`` (15).

Method. Every assert is an exact whole-string equality against the SHIPPED
contract, so the three note/sentinel families (``"XX...XX"`` wrap, lower-case
flip, UPPER-case flip) and every ``"\\n".join`` -> ``"XX\\nXX".join`` swap die on
the rendered text rather than on an ``in`` check — the ``in`` form is exactly
what let the XX-wrapped variants survive, since ``"XX  Consider reducing..."``
still contains the un-wrapped sentence. The ``.get(key, default)`` families die
on inputs crafted so the key is PRESENT (a key-string mutant falls off the map
and surfaces the default) or ABSENT (a default mutant surfaces ``None`` /
``"XXXX"``). Threshold mutants get the EXACT boundary value *plus* both flanking
anchors, so no boundary assert is vacuous.

Equivalence honesty: 75 of the 89 keys are killed. The other 14 are the two
redundant ``len(sorted_scores)``/``len(all_scores)`` guards inside
``format_vehicle_classification_context``'s alternative branch, the three
falsy-initial-value keys in ``format_pet_classification_context`` (its note
chain has an ``else`` arm, so the note initialiser is always overwritten, and
``has_confirmed_pets = None`` is falsy exactly like ``False``), the one
falsy-init twin in ``format_age_classification_context``, and the eight
redundant/None-equivalent ``.get`` defaults in
``format_florence_scene_context`` — all inputs where shipped and mutant render
byte-identically. Each is itemised with its one-line reason in the ledger at the
bottom of this file, derived from the mutant bodies in the bank rather than from
the triage prose.
"""

from __future__ import annotations

import os
import sys

# This fragment lives OUTSIDE the repo tree (/home/agent/runs/b30-frags), so
# pytest gives it no sys.path entry for the repo. The harness always invokes it
# with the repo root (or the mutant home) as cwd — mirror that so the import
# below resolves in both worlds.
_ROOT = os.getcwd()
if os.path.isfile(os.path.join(_ROOT, "backend", "services", "prompts.py")):
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from types import SimpleNamespace  # noqa: E402

from backend.services.prompts import (  # noqa: E402
    format_age_classification_context,
    format_florence_scene_context,
    format_pet_classification_context,
    format_vehicle_classification_context,
    format_weather_context,
)

# ---------------------------------------------------------------------------
# Shared contract fragments + input builders. All five renderers are pure
# attribute readers, so the namespaces below are exactly the attribute surface
# the shipped code touches (the real vehicle/pet/age/weather dataclasses are
# slots=True and carry nothing else the formatter reads).
# ---------------------------------------------------------------------------
VEH_SENTINEL = "Vehicle classification: No vehicles analyzed"
PET_SENTINEL = "Pet classification: No animals detected"
AGE_SENTINEL = "Age estimation: No persons analyzed"
HDR2 = "### Scene Analysis (Florence-2)"
PET_FALSE_POSITIVE_BLOCK = (
    "",
    "  **FALSE POSITIVE NOTE**: High-confidence household pets detected.",
    "  Consider reducing risk score if no other suspicious activity present.",
)
AGE_MINOR_BLOCK = (
    "",
    "  **NOTE**: Minor(s) detected - may indicate lost/unaccompanied child",
    "  Consider context and presence of adults when assessing risk",
)
FOGGY_NOTE = " - Visibility significantly reduced, detection confidence may be lower"


def _vc(**kw):
    """VehicleClassificationResult stand-in (vehicle_type is never rendered)."""
    base = {
        "display_name": "sedan",
        "confidence": 0.9,
        "is_commercial": False,
        "all_scores": {"sedan": 0.9, "suv": 0.07, "truck": 0.03},
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _pet(animal_type="dog", confidence=0.9):
    """PetClassificationResult stand-in (cat/dog scores + is_household_pet unused)."""
    return SimpleNamespace(animal_type=animal_type, confidence=confidence)


def _age(**kw):
    """AgeClassificationResult stand-in (age_group / all_scores are never rendered)."""
    base = {"display_name": "adult (25-40 years)", "confidence": 0.8, "is_minor": False}
    base.update(kw)
    return SimpleNamespace(**base)


def _wx(simple_condition, confidence=0.9):
    """WeatherResult stand-in (only simple_condition + confidence are rendered)."""
    return SimpleNamespace(
        condition=f"{simple_condition}/mixed",
        simple_condition=simple_condition,
        confidence=confidence,
        all_scores={simple_condition: confidence},
    )


# ===========================================================================
# format_vehicle_classification_context — 23 keys (21 killed; 18/30 equivalent)
# ===========================================================================
def test_vehicle_empty_and_none_sentinel_exact():
    # mutmut_1 (`if not vehicle_classifications:` -> `if`: the guard stops
    # working, the empty dict falls into the loop and the render is the bare ""),
    # mutmut_2 (XX wrap), mutmut_3 (lower-case), mutmut_4 (UPPER-case). The
    # sentinel IS the whole return value, so no .lower()/substring containment
    # can soften a case flip — whole-string equality kills all three.
    assert format_vehicle_classification_context({}) == VEH_SENTINEL
    assert format_vehicle_classification_context(None) == VEH_SENTINEL


def test_vehicle_line_layout_and_multiline_join_exact():
    # mutmut_5 (`lines = None` -> AttributeError on .append), mutmut_6
    # (`vehicle_line = None` -> TypeError on `+=`), mutmut_7 (`vehicle_line +=`
    # -> `=`: the line renders as " (90% confidence)" with no "Vehicle d1:"
    # prefix), mutmut_8 (`+=` -> `-=`: TypeError), mutmut_36 ("\\n".join ->
    # "XX\\nXX".join, killed by the two-entry render).
    one = format_vehicle_classification_context({"d1": _vc(display_name="sedan", confidence=0.9)})
    assert one == "Vehicle d1: sedan (90% confidence)"
    two = format_vehicle_classification_context(
        {
            "d1": _vc(display_name="sedan", confidence=0.9),
            "d2": _vc(display_name="pickup truck", confidence=0.95),
        }
    )
    assert two == "\n".join(
        ["Vehicle d1: sedan (90% confidence)", "Vehicle d2: pickup truck (95% confidence)"]
    )


def test_vehicle_commercial_tail_operator_and_case_exact():
    # mutmut_9 (`vehicle_line += " [Commercial...]"` -> `=`: the tail REPLACES
    # the whole line), mutmut_10 (`+=` -> `-=`: TypeError), mutmut_11 wraps the
    # tail as `XX [Commercial/delivery vehicle]XX`, mutmut_12 lower-cases it to
    # ` [commercial/delivery vehicle]`, mutmut_13 upper-cases it, mutmut_14
    # swaps `lines.append(vehicle_line)` for `append(None)` so "\\n".join raises
    # TypeError. The second assert pins that a NON-commercial vehicle gets no
    # tail, so a mutant that always appended it dies too.
    out = format_vehicle_classification_context(
        {"d1": _vc(display_name="work van", confidence=0.95, is_commercial=True)}
    )
    assert out == "Vehicle d1: work van (95% confidence) [Commercial/delivery vehicle]"
    assert (
        format_vehicle_classification_context({"d1": _vc(display_name="sedan", confidence=0.95)})
        == "Vehicle d1: sedan (95% confidence)"
    )


def test_vehicle_alternative_gate_grid_kills_every_threshold_mutant():
    # The gate `confidence < 0.6 and len(all_scores) > 1` survives as eight
    # keys, six of them killable (mutmut_15/16/17/19/20/21 — the ledger
    # itemises the equivalent 18/30); the cells below are chosen from
    # the (confidence, score-count) grid so each pair is separated, and the two
    # "HAS it" cells are the non-vacuity anchors for the "NO line" cells — a
    # body with the alternative permanently off cannot pass them:
    #   0.59 + 2 scores -> HAS the line   kills mutmut_19 (`>1` -> `>2` drops it
    #                                      at exactly two scores), mutmut_20
    #                                      (`sorted_scores = None`) and mutmut_21
    #                                      (`all_scores.items() -> None`) — both
    #                                      raise TypeError inside the branch
    #   0.59 + 3 scores -> HAS the line   boundary anchor above mutmut_19's cut
    #   0.60 + 2 scores -> NO line         kills mutmut_16 (`<` -> `<=`), mutmut_17
    #   0.61 + 2 scores -> NO line         kills mutmut_17 (`< 0.6` -> `< 1.6`)
    #   0.90 + 2 scores -> NO line         kills mutmut_15 (`and` -> `or`), 17
    # The three all-off shapes (0.59/0.90 + 1 score) pin the shipped contract at
    # score-count 1, where even the `>= 1` mutants are silent — see the ledger
    # entries for mutmut_18 / mutmut_30.
    two_scores = {"truck": 0.59, "sedan": 0.35}
    assert format_vehicle_classification_context(
        {"d1": _vc(display_name="truck", confidence=0.59, all_scores=two_scores)}
    ) == "\n".join(["Vehicle d1: truck (59% confidence)", "    Alternative: sedan (35.0%)"])
    assert format_vehicle_classification_context(
        {
            "d1": _vc(
                display_name="truck",
                confidence=0.59,
                all_scores={"truck": 0.59, "sedan": 0.35, "van": 0.06},
            )
        }
    ) == "\n".join(["Vehicle d1: truck (59% confidence)", "    Alternative: sedan (35.0%)"])
    assert (
        format_vehicle_classification_context(
            {
                "d1": _vc(
                    display_name="truck", confidence=0.6, all_scores={"truck": 0.6, "sedan": 0.35}
                )
            }
        )
        == "Vehicle d1: truck (60% confidence)"
    )
    assert (
        format_vehicle_classification_context(
            {
                "d1": _vc(
                    display_name="truck", confidence=0.61, all_scores={"truck": 0.61, "sedan": 0.3}
                )
            }
        )
        == "Vehicle d1: truck (61% confidence)"
    )
    assert (
        format_vehicle_classification_context(
            {
                "d1": _vc(
                    display_name="truck", confidence=0.9, all_scores={"truck": 0.9, "sedan": 0.07}
                )
            }
        )
        == "Vehicle d1: truck (90% confidence)"
    )
    assert (
        format_vehicle_classification_context(
            {"d1": _vc(display_name="truck", confidence=0.59, all_scores={"truck": 0.59})}
        )
        == "Vehicle d1: truck (59% confidence)"
    )
    assert (
        format_vehicle_classification_context(
            {
                "d1": _vc(
                    display_name="truck",
                    confidence=0.9,
                    all_scores={"truck": 0.9, "sedan": 0.07, "van": 0.03},
                )
            }
        )
        == "Vehicle d1: truck (90% confidence)"
    )


def test_vehicle_alternative_is_score_runner_up_not_dict_order():
    # The sorter inside the alternative branch (`key=lambda x: x[1]`,
    # `reverse=True`) is the body mutmut_20/21 replace with None, so it is
    # entered by the grid's HAS-it cells; this cell additionally pins WHICH
    # entry is picked. The dict is deliberately ordered so the first-inserted
    # and alphabetically-smallest key is NOT the score runner-up: shipped names
    # "van" (0.25), an index/key-ordered sort would name "sedan", a reversed
    # sort would name "bicycle". No additional in-scope key depends on it.
    out = format_vehicle_classification_context(
        {
            "d1": _vc(
                display_name="truck",
                confidence=0.5,
                all_scores={"sedan": 0.5, "van": 0.25, "bicycle": 0.02},
            )
        }
    )
    assert out == "\n".join(["Vehicle d1: truck (50% confidence)", "    Alternative: van (25.0%)"])


# ===========================================================================
# format_pet_classification_context — 20 keys (17 killed; 6/8/9 equivalent)
# ===========================================================================
def test_pet_empty_and_none_sentinel_exact():
    # mutmut_1 (`if not pet_classifications:` -> `if` -> the bare ""), mutmut_2
    # (XX wrap), mutmut_3 (lower-case), mutmut_4 (UPPER-case).
    assert format_pet_classification_context({}) == PET_SENTINEL
    assert format_pet_classification_context(None) == PET_SENTINEL


def test_pet_high_confidence_boundary_and_false_positive_block_exact():
    # Confidence EXACTLY 0.85 is the boundary cell:
    #   mutmut_10 (`>= 0.85` -> `> 0.85`) demotes this animal to "[Probable
    #     household pet]" and never sets has_confirmed_pets, so the three-line
    #     false-positive block disappears;
    #   mutmut_13 wraps the note as `XX [HIGH CONFIDENCE - likely household
    #     pet]XX`; mutmut_30 turns `lines.append("")` into "XXXX"; mutmut_32 /
    #     36 XX-wrap the two NOTE lines and mutmut_34 / 37 / 38 case-flip them;
    #     mutmut_40 swaps "\n".join for "XX\nXX".join. All die on this one
    #     whole-string equality.
    assert format_pet_classification_context({"a1": _pet("dog", 0.85)}) == "\n".join(
        [
            "Pet classification (1 animals):",
            "  Animal a1: dog (85%) [HIGH CONFIDENCE - likely household pet]",
            *PET_FALSE_POSITIVE_BLOCK,
        ]
    )


def test_pet_probable_band_boundary_exact_and_flanking_anchors():
    # mutmut_18 (`>= 0.70` -> `> 0.70`) sends EXACTLY 0.70 into the wildlife
    # arm, and mutmut_21 ("XX [Probable household pet]XX") dies on all three
    # probable renders. The 0.72 / 0.69 flanks prove both neighbouring arms are
    # live, so the boundary assert cannot be satisfied by a body that renders
    # one fixed note.
    assert format_pet_classification_context({"a1": _pet("cat", 0.7)}) == "\n".join(
        ["Pet classification (1 animals):", "  Animal a1: cat (70%) [Probable household pet]"]
    )
    assert format_pet_classification_context({"a1": _pet("cat", 0.72)}) == "\n".join(
        ["Pet classification (1 animals):", "  Animal a1: cat (72%) [Probable household pet]"]
    )
    assert format_pet_classification_context({"a1": _pet("cat", 0.69)}) == "\n".join(
        [
            "Pet classification (1 animals):",
            "  Animal a1: cat (69%) [Low confidence - may be wildlife]",
        ]
    )


def test_pet_low_band_exact_and_block_suppressed_below_each_boundary():
    # mutmut_25 (XX wrap) and mutmut_26 (" [low confidence - may be wildlife]")
    # die on the wildlife render. The two flanks re-pin that the false-positive
    # block is gated strictly on has_confirmed_pets: neither 0.84 (probable, one
    # tick under the high band) nor 0.4 (wildlife) emits it.
    assert format_pet_classification_context({"a1": _pet("dog", 0.4)}) == "\n".join(
        [
            "Pet classification (1 animals):",
            "  Animal a1: dog (40%) [Low confidence - may be wildlife]",
        ]
    )
    assert format_pet_classification_context({"a1": _pet("cat", 0.84)}) == "\n".join(
        ["Pet classification (1 animals):", "  Animal a1: cat (84%) [Probable household pet]"]
    )


def test_pet_mixed_bands_count_header_and_join_exact():
    # `len(pet_classifications)` -> -1 / +1 / 1 breaks the "(3 animals)" header;
    # this one join re-kills every note-variant key (mutmut_13 / 21 / 25 / 26),
    # the XX-vs-newline separator swap (mutmut_40) and the whole false-positive
    # block (mutmut_30/32/34/36/37/38) with a different animal set.
    assert format_pet_classification_context(
        {"a1": _pet("dog", 0.92), "a2": _pet("cat", 0.75), "a3": _pet("raccoon", 0.3)}
    ) == "\n".join(
        [
            "Pet classification (3 animals):",
            "  Animal a1: dog (92%) [HIGH CONFIDENCE - likely household pet]",
            "  Animal a2: cat (75%) [Probable household pet]",
            "  Animal a3: raccoon (30%) [Low confidence - may be wildlife]",
            *PET_FALSE_POSITIVE_BLOCK,
        ]
    )


# ===========================================================================
# format_age_classification_context — 16 keys (15 killed; mutmut_6 equivalent)
# ===========================================================================
def test_age_empty_and_none_sentinel_exact():
    # Contract pin, not an in-scope key (the age sentinel mutants were already
    # killed): it stops a body rewritten to "always return the sentinel" from
    # passing the band tests below.
    assert format_age_classification_context({}) == AGE_SENTINEL
    assert format_age_classification_context(None) == AGE_SENTINEL


def test_age_unmarked_render_and_minor_block_suppression_exact():
    # Confidence 0.8 clears both thresholds, so the shipped note tail is EMPTY —
    # which is what makes the note/marker initialisers observable here (the age
    # chain has if/elif with NO else, unlike the pet chain):
    #   mutmut_8 (`confidence_note = ""` -> `None`) renders "None" and mutmut_9
    #     (`= "XXXX"`) renders "XXXX" on every unmarked person;
    #   mutmut_20 (`minor_marker = ""` -> `None`) renders "None" and mutmut_21
    #     (`= "XXXX"`) renders "XXXX" for every NON-minor;
    #   mutmut_7 (`has_minors = False` -> `True`) is separated from shipped by
    #     the ABSENCE of the minor block (see the ledger for mutmut_6).
    #   mutmut_39 ("\\n".join -> "XX\\nXX".join) and the "(2 persons)" header
    #     count die on the same equality.
    assert format_age_classification_context(
        {"p1": _age(confidence=0.8), "p2": _age(display_name="senior (65+ years)", confidence=0.8)}
    ) == "\n".join(
        [
            "Age estimation (2 persons):",
            "  Person p1: adult (25-40 years) (80%)",
            "  Person p2: senior (65+ years) (80%)",
        ]
    )


def test_age_confidence_band_boundaries_exact_with_anchors():
    # Two comparisons carry three surviving thresholds:
    #   mutmut_10 (`< 0.5` -> `<= 0.5`) renders 0.5 as "[LOW CONFIDENCE]" where
    #     shipped puts it in the medium band;
    #   mutmut_15 (`< 0.7` -> `<= 0.7`) renders 0.7 as medium where shipped
    #     renders NO note;
    #   mutmut_16 (`< 0.7` -> `< 1.7`) renders 0.8 as medium.
    # mutmut_13 (XX wrap on " [LOW CONFIDENCE]") and mutmut_18 (XX wrap on
    # " [medium confidence]") die on the marked renders. The 0.45 / 0.6 / 0.8
    # anchors prove all three arms are separately live.
    assert format_age_classification_context({"p1": _age(confidence=0.45)}) == "\n".join(
        [
            "Age estimation (1 persons):",
            "  Person p1: adult (25-40 years) (45%) [LOW CONFIDENCE]",
        ]
    )
    assert format_age_classification_context({"p1": _age(confidence=0.5)}) == "\n".join(
        [
            "Age estimation (1 persons):",
            "  Person p1: adult (25-40 years) (50%) [medium confidence]",
        ]
    )
    assert format_age_classification_context({"p1": _age(confidence=0.6)}) == "\n".join(
        [
            "Age estimation (1 persons):",
            "  Person p1: adult (25-40 years) (60%) [medium confidence]",
        ]
    )
    assert format_age_classification_context({"p1": _age(confidence=0.7)}) == "\n".join(
        ["Age estimation (1 persons):", "  Person p1: adult (25-40 years) (70%)"]
    )
    assert format_age_classification_context({"p1": _age(confidence=0.8)}) == "\n".join(
        ["Age estimation (1 persons):", "  Person p1: adult (25-40 years) (80%)"]
    )


def test_age_minor_marker_and_note_block_exact():
    # mutmut_23 (" **MINOR**" -> "XX **MINOR**XX"), mutmut_29
    # (`lines.append("")` -> "XXXX"), mutmut_31 / mutmut_35 (XX wrap on the two
    # NOTE lines). The boundary twin — a minor at EXACTLY 0.5, i.e. medium
    # band — re-kills mutmut_10/13/15/18/23/29/31/35/39 with the marker on.
    assert format_age_classification_context(
        {"p9": _age(display_name="child (5-12 years)", confidence=0.45, is_minor=True)}
    ) == "\n".join(
        [
            "Age estimation (1 persons):",
            "  Person p9: child (5-12 years) (45%) [LOW CONFIDENCE] **MINOR**",
            *AGE_MINOR_BLOCK,
        ]
    )
    assert format_age_classification_context(
        {"p9": _age(display_name="teenager (13-17 years)", confidence=0.5, is_minor=True)}
    ) == "\n".join(
        [
            "Age estimation (1 persons):",
            "  Person p9: teenager (13-17 years) (50%) [medium confidence] **MINOR**",
            *AGE_MINOR_BLOCK,
        ]
    )


def test_age_mixed_bands_and_minor_join_exact():
    # One render carrying all three note states, the minor marker and the block
    # — re-kills mutmut_18 (the medium-band XX wrap in a different person line),
    # mutmut_39 (join swap) and the "(3 persons)" header count.
    assert format_age_classification_context(
        {
            "p1": _age(confidence=0.4),
            "p2": _age(display_name="senior (65+ years)", confidence=0.65),
            "p3": _age(display_name="child (5-12 years)", confidence=0.9, is_minor=True),
        }
    ) == "\n".join(
        [
            "Age estimation (3 persons):",
            "  Person p1: adult (25-40 years) (40%) [LOW CONFIDENCE]",
            "  Person p2: senior (65+ years) (65%) [medium confidence]",
            "  Person p3: child (5-12 years) (90%) **MINOR**",
            *AGE_MINOR_BLOCK,
        ]
    )


# ===========================================================================
# format_florence_scene_context — 15 keys (7 killed; 8 equivalent, see ledger)
# ===========================================================================
def test_florence_dense_caption_loop_types_and_cap_exact():
    # The caption list mixes five region shapes ahead of the last two captions:
    #   mutmut_57 (`isinstance(region, dict)` -> `(isinstance(region, dict)) or
    #     True`) takes the dict arm for the plain-string and None regions and
    #     raises AttributeError on "a-string".get;
    #   mutmut_64 (`region.get("caption", "XXXX")`) surfaces "XXXX" for the
    #     region that has NO "caption" key — the key-ABSENT shape is required,
    #     because a present-but-empty/None caption is default-independent;
    #   mutmut_65 (false arm `""` -> `"XXXX"`) surfaces "- XXXX" for the string
    #     region;
    #   mutmut_71 (`caption_texts[:10]` -> `[:11]`) keeps the 11th caption.
    # Shipped skips the non-dicts and the keyless/empty captions and renders
    # exactly c1..c10.
    captions = [{"caption": f"c{i}"} for i in range(1, 10)]
    captions += [{}, "a-string", None, {"caption": None}, {"caption": ""}]
    captions += [{"caption": "c10"}, {"caption": "c11"}]
    assert format_florence_scene_context({"dense_captions": captions}) == "\n".join(
        [HDR2, "\n**Region Descriptions:**"] + [f"- c{i}" for i in range(1, 11)]
    )


def test_florence_region_description_cap_and_blank_entries_exact():
    # Twelve truthy descriptions plus one blank: `if desc` drops the blank, so
    # shipped renders the first ten and mutmut_125 (`desc_entries[:10]` ->
    # `[:11]`) additionally renders "- [r11] d11".
    descs = {f"r{i}": f"d{i}" for i in range(1, 13)}
    descs["blank"] = ""
    assert format_florence_scene_context({"region_descriptions": descs}) == "\n".join(
        [HDR2, "\n**Detection Region Descriptions:**"] + [f"- [r{i}] d{i}" for i in range(1, 11)]
    )


def test_florence_security_objects_labels_absent_and_empty_exact():
    # Pins the shipped contract around the mutmut_23 / mutmut_25 default site
    # (`objects.get("labels", [])`): both default-reading shapes collapse to the
    # header-only "". The truthy-list assert is the non-vacuity anchor proving
    # the section is live, so the two "" asserts are about the labels default
    # and not about a dead branch. (The two default mutants themselves are
    # equivalent — see the ledger.)
    assert format_florence_scene_context({"security_objects": {"other": 1}}) == ""
    assert format_florence_scene_context({"security_objects": {"labels": []}}) == ""
    assert (
        format_florence_scene_context({"security_objects": {"labels": ["bicycle", "plant"]}})
        == f"{HDR2}\n\n**Security Objects Detected:** bicycle, plant"
    )


def test_florence_text_regions_labels_absent_and_empty_exact():
    # Same three-shape pin for the mutmut_83 / mutmut_85 default site
    # (`texts.get("labels", [])`).
    assert format_florence_scene_context({"text_regions": {"other": 1}}) == ""
    assert format_florence_scene_context({"text_regions": {"labels": []}}) == ""
    assert format_florence_scene_context({"text_regions": {"labels": ["STOP", "742"]}}) == (
        f"{HDR2}\n\n**Visible Text:** STOP, 742"
    )


def test_florence_phrase_grounding_matched_shapes_exact():
    # `phrase = pg.get("phrase", "")` — mutmut_108 (default -> "XXXX"): a
    # MATCHED entry that has no "phrase" key renders "XXXX (1 location(s))"
    # under the mutant and is dropped by `if phrase` in shipped, so the
    # single-entry render is the kill. The key-CARRYING entry is the non-vacuity
    # anchor (and kills the key-string siblings: a swapped key means the entry
    # reads the default and disappears). The tail asserts pin the zero-bbox
    # render and the explicitly-empty-phrase skip.
    result = {
        "phrase_grounding": [
            {"matched": True, "phrase": "weapon", "bboxes": [1, 2]},
            {"matched": True, "bboxes": [3]},
            {"matched": False, "phrase": "ignored", "bboxes": [9]},
        ]
    }
    assert format_florence_scene_context(result) == (
        f"{HDR2}\n\n**Phrase Grounding Matches:** weapon (2 location(s))"
    )
    assert (
        format_florence_scene_context(
            {"phrase_grounding": [{"matched": True, "phrase": "person", "bboxes": []}]}
        )
        == f"{HDR2}\n\n**Phrase Grounding Matches:** person (0 location(s))"
    )
    assert (
        format_florence_scene_context(
            {"phrase_grounding": [{"matched": True, "phrase": "", "bboxes": [1]}]}
        )
        == ""
    )


def test_florence_vqa_non_dict_answers_are_skipped_not_crashed():
    # mutmut_133 (`isinstance(answers, dict) and answers` -> `or answers`)
    # enters the loop body for the truthy NON-dict answer "yes" and raises
    # AttributeError on .items(); shipped skips it and renders detection 2 only.
    # The second assert pins the collapse-to-"" path, so a mutant that emitted a
    # partial render instead of crashing also dies.
    assert (
        format_florence_scene_context({"security_vqa": {"1": "yes", "2": {"armed?": "yes"}}})
        == f"{HDR2}\n\n**Security Assessment (VQA):**\n\n[Detection 2]:\n  Q: armed?\n  A: yes"
    )
    assert format_florence_scene_context({"security_vqa": {"1": "yes", "2": 5}}) == ""


# ===========================================================================
# format_weather_context — 15 keys, all killed
# ===========================================================================
def test_weather_none_returns_empty_string():
    # mutmut_2 (`return ""` -> `return "XXXX"`).
    assert format_weather_context(None) == ""


def test_weather_foggy_render_exact():
    # The foggy literal site survives as seven keys. mutmut_6 (`== "foggy"` ->
    # `!=`), mutmut_7 (`"XXfoggyXX"`) and mutmut_8 (`"FOGGY"`) all fail to
    # SELECT the foggy note for condition "foggy"; mutmut_9 (`visibility_notes =
    # None` — the f-string stringifies it, so the render gains the literal text
    # "None" rather than raising), mutmut_10 (XX wrap), mutmut_11 (lower-case
    # "visibility") and mutmut_12 (UPPER-case) die on this equality.
    assert (
        format_weather_context(_wx("foggy", 0.88)) == "Weather: foggy (88% confidence)" + FOGGY_NOTE
    )


def test_weather_each_condition_note_exact():
    # Under mutmut_6 (`!=`) EVERY non-foggy condition inherits the foggy note,
    # so these four renders are four independent kills for it; mutmut_3 (the
    # `visibility_notes = ""` initialiser -> `None`) prints "None" on all four
    # as well, and mutmut_17 / mutmut_24 / mutmut_31 / mutmut_38 (the XX wraps
    # on the rainy / snowy / cloudy / clear notes) die on their own line.
    assert format_weather_context(_wx("rainy", 0.8)) == (
        "Weather: rainy (80% confidence) - Rain may affect visibility and detection accuracy"
    )
    assert format_weather_context(_wx("snowy", 0.9)) == (
        "Weather: snowy (90% confidence)"
        " - Snow conditions may obscure objects and affect image quality"
    )
    assert format_weather_context(_wx("cloudy", 0.75)) == (
        "Weather: cloudy (75% confidence) - Overcast conditions, lighting may vary"
    )
    assert format_weather_context(_wx("clear", 0.95)) == (
        "Weather: clear (95% confidence) - Good visibility, high confidence in detections"
    )


def test_weather_condition_match_is_case_sensitive_and_exact():
    # mutmut_4 (`visibility_notes = "XXXX"`) leaks "XXXX" into every UNMATCHED
    # condition, so the three renders below kill it; mutmut_5 (`condition =
    # None`) strips every note (killed by the foggy test) and these re-pin the
    # shipped case-sensitivity from the other side: "FOGGY" must carry NO note,
    # so a mutant whose literal is "FOGGY" (mutmut_8) cannot satisfy both this
    # test and test_weather_foggy_render_exact. Same cross-lock for mutmut_7.
    assert format_weather_context(_wx("FOGGY", 0.9)) == "Weather: FOGGY (90% confidence)"
    assert format_weather_context(_wx("", 0.9)) == "Weather:  (90% confidence)"
    assert format_weather_context(_wx("windy", 0.5)) == "Weather: windy (50% confidence)"


# ===========================================================================
# EQUIVALENCE LEDGER — 14 of the 89 in-scope keys are not killable.
# ===========================================================================
# format_vehicle_classification_context (2) — the inner `if len(sorted_scores)
# > 1:` re-tests the outer `len(classification.all_scores) > 1` (sorted()
# preserves length), so the two length checks are the same predicate and neither
# `>= 1` twin can change any render:
#   mutmut_18 outer `> 1` -> `>= 1` — a conf<0.6 + len==1 entry ENTERS the
#             branch, but the unchanged INNER `len(sorted_scores) > 1` still
#             blocks the append; the 0.59/1-score cell of the gate grid pins the
#             shipped (identical) render there.
#   mutmut_30 inner `> 1` -> `>= 1` — whenever the branch is entered the outer
#             gate has already proven len>1, so the inner test is always True
#             under both spellings.
#
# format_pet_classification_context (3) — falsy initial values:
#   mutmut_6  `has_confirmed_pets = False` -> `None` — None is falsy exactly
#             like False for `if has_confirmed_pets`, and the True-assignment
#             path is unmutated; identical control flow on every input.
#   mutmut_8  `confidence_note = ""` -> `None` — the note chain is
#             if/elif/ELSE, so confidence_note is ALWAYS reassigned before the
#             f-string reads it; the initialiser's value never surfaces.
#   mutmut_9  `confidence_note = ""` -> `"XXXX"` — same unreachable-value reason.
#   (contrast the AGE chain, which has NO else arm: age mutmut_8/9 leak the
#   initialiser into every conf >= 0.7 render and ARE killed.)
#
# format_age_classification_context (1):
#   mutmut_6  `has_minors = False` -> `None` — the same None-vs-False falsy
#             twin as pet mutmut_6; the `= True` mutant (mutmut_7) IS killed.
#
# format_florence_scene_context (8) — the redundant .get-default family. Each
# mutated default is either never read, or read only on inputs where [] and None
# are both falsy and the `if` skips identically in shipped and mutant:
#   mutmut_23  `objects.get("labels", [])` -> None — the enclosing
#              `if florence_result.get("security_objects")` already guarantees a
#              TRUTHY dict; the only default-reading shapes are labels-absent and
#              labels-empty, pinned "" in both worlds by
#              test_florence_security_objects_labels_absent_and_empty_exact.
#   mutmut_25  same site, default DELETED -> dict.get re-supplies None.
#   mutmut_59  `region.get("caption", "")` -> None — a caption-less region is
#              skipped by `if caption` for both defaults, and a region WITH a
#              caption never reads it (its "XXXX" twin, mutmut_64, is read via a
#              key-ABSENT region and IS killed).
#   mutmut_61  same site, default DELETED -> dict.get re-supplies None, so it is
#              the same observable as mutmut_59. (Its guard-mutating sibling is
#              mutmut_57, which crashes on the plain-string region fed by
#              test_florence_dense_caption_loop_types_and_cap_exact and IS
#              killed.)
#   mutmut_83  `texts.get("labels", [])` -> None — redundant default, as 23.
#   mutmut_85  same site, default DELETED -> None — as 25.
#   mutmut_103 `pg.get("phrase", "")` -> None — read only when the matched entry
#              has no "phrase" key, where "" and None are both falsy and
#              `if phrase` skips in both worlds (its "XXXX" twin, mutmut_108, IS
#              killed on exactly that shape).
#   mutmut_105 same site, default DELETED -> None — as 103.
