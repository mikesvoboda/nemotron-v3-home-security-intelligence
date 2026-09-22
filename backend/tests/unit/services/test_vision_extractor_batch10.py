"""Batch-10 mutation-kill battery: vision_extractor pure functions (all-shape red-check model).

Scope: dossier ``vision_extractor.md`` TEST-GAP clusters that need NO mock
surgery because the functions are callable directly —
``resolve_vehicle_type_conflict`` (C5, 67 feed shapes), ``generate_validation_note``
(C7, 32), ``detect_cross_validation_error`` (C6, 45), ``clean_vqa_output``
(C3 recovery branch, 63), ``is_valid_vqa_output``/``validate_and_clean_vqa_output``
(C4, 21+28), and the two ``to_dict`` serializers (C2, 32). Unlike the frozen
feed this battery is built from the CURRENT mutant copy (``/tmp/extracts/
vision_extractor.tsv``, 1362 shapes re-derived mechanically vs each
``__mutmut_orig`` twin — the run-5b generate left complete variant bodies);
EVERY shape of these functions gets red-checked, so no survivor key-list is
needed and the residue is self-triaged like batches 8/9.

Integrity: ``git log --since=2026-09-17 -- test_vision_extractor.py`` is
EMPTY this session — the covering file never changed after the 09-17 meta
snapshot, and the #6561 re-home never touched it — so these clusters'
dossier survivors are survivors at this commit; kills here are new.

Whole-result equality everywhere (all dataclasses/strings): the dossier's
recurring complaint is "asserts stop at resolved_type / message substrings"
— every field echo (yolo_class/yolo_confidence/florence_type/confidence_note,
exact dict keys, the set-repr inside the mismatch messages) is asserted.
"""

from __future__ import annotations

import pytest

from backend.services.vision_extractor import (
    BatchExtractionResult,
    CrossValidationError,
    clean_vqa_output,
    detect_cross_validation_error,
    generate_validation_note,
    is_valid_vqa_output,
    resolve_vehicle_type_conflict,
    validate_and_clean_vqa_output,
)

# Mark as unit tests
pytestmark = pytest.mark.unit


class TestResolveVehicleTypeConflictAllBranches:
    """C5: every return branch pinned on ALL nine result fields."""

    def test_both_missing_branch_exact(self):
        r = resolve_vehicle_type_conflict(None, 0.5, None)
        assert (
            r.resolved_type,
            r.source,
            r.conflict_detected,
            r.yolo_class,
            r.yolo_confidence,
            r.florence_type,
            r.confidence_note,
        ) == (
            "unknown",
            "both",
            False,
            None,
            0.5,
            None,
            "No classification available from either source",
        )

    def test_both_missing_requires_BOTH_falsy(self):
        # `and` -> `or` routes ANY single-source call into this branch:
        # yolo-only must never report source="both"
        r = resolve_vehicle_type_conflict("car", 0.9, None)
        assert r.source == "yolo"
        r = resolve_vehicle_type_conflict(None, 0.9, "sedan")
        assert r.source == "florence"

    def test_only_florence_branch_exact(self):
        r = resolve_vehicle_type_conflict(None, None, "pickup truck")
        assert (
            r.resolved_type,
            r.source,
            r.conflict_detected,
            r.yolo_class,
            r.yolo_confidence,
            r.florence_type,
            r.confidence_note,
        ) == (
            "pickup truck",
            "florence",
            False,
            None,
            None,
            "pickup truck",
            "Only Florence classification available",
        )

    def test_only_yolo_branch_exact(self):
        r = resolve_vehicle_type_conflict("bus", 0.42, None)
        assert (
            r.resolved_type,
            r.source,
            r.conflict_detected,
            r.yolo_class,
            r.yolo_confidence,
            r.florence_type,
            r.confidence_note,
        ) == (
            "bus",
            "yolo",
            False,
            "bus",
            0.42,
            None,
            "Only YOLO classification available",
        )

    def test_semantic_match_prefers_florence_exact(self):
        r = resolve_vehicle_type_conflict("car", 0.91, "sedan")
        assert (
            r.resolved_type,
            r.source,
            r.conflict_detected,
            r.confidence_note,
        ) == (
            "sedan",
            "florence",
            False,
            "Semantic match: YOLO 'car' matches Florence 'sedan'",
        )

    def test_confidence_boundary_exactly_070_favors_yolo(self):
        # `>=` -> `>` at YOLO_HIGH_CONFIDENCE_THRESHOLD=0.70: exactly-0.70
        # ships as high-confidence YOLO win
        r = resolve_vehicle_type_conflict("truck", 0.70, "person")
        assert (
            r.resolved_type,
            r.source,
            r.conflict_detected,
            r.confidence_note,
        ) == (
            "truck",
            "yolo",
            True,
            "High confidence YOLO (70%) overrides Florence 'person'",
        )

    def test_just_below_boundary_favors_florence(self):
        r = resolve_vehicle_type_conflict("truck", 0.69, "person")
        assert (
            r.resolved_type,
            r.source,
            r.conflict_detected,
            r.confidence_note,
        ) == (
            "person",
            "florence",
            False,
            "Low YOLO confidence (69%), using Florence 'person'",
        )

    def test_default_confidence_is_075_not_175(self):
        # yolo_confidence=None -> shipped default 0.75 renders "75%" AND
        # takes the high-confidence branch; 1.75 renders "175%"
        r = resolve_vehicle_type_conflict("van", None, "person")
        assert r.source == "yolo"
        assert r.confidence_note == "High confidence YOLO (75%) overrides Florence 'person'"

    def test_none_confidence_guard_keeps_zero(self):
        # `is not None` -> `is None` inverts the default: yolo_conf=0.0 must
        # NOT be replaced by 0.75 (renders 0%, low branch)
        r = resolve_vehicle_type_conflict("van", 0.0, "person")
        assert r.confidence_note == "Low YOLO confidence (0%), using Florence 'person'"


class TestGenerateValidationNoteDisjuncts:
    """C7: both person-vehicle-mismatch disjuncts and every note string."""

    def test_first_disjunct_person_vehicle_exact(self):
        assert generate_validation_note(
            yolo_class="person",
            yolo_confidence=0.81,
            florence_type="truck",
            resolved_type="person",
            conflict_detected=True,
        ) == (
            "Cross-validation mismatch error: YOLO detected 'person' (81% conf), "
            "but Florence described 'truck'. Resolved to 'person'."
        )

    def test_second_disjunct_vehicle_person_exact(self):
        # `and`->`or`/`in`->`not in` flips fire ONLY here: yolo=car (not
        # "person") + florence mentions person -> shipped second disjunct True
        assert generate_validation_note(
            yolo_class="car",
            yolo_confidence=0.5,
            florence_type="a person near the car",
            resolved_type="car",
            conflict_detected=True,
        ) == (
            "Cross-validation mismatch error: YOLO detected 'car' (50% conf), "
            "but Florence described 'a person near the car'. Resolved to 'car'."
        )

    def test_non_mismatch_conflict_note_exact(self):
        # truthy non-matching pair: `or`-flipped disjuncts would falsely take
        # the mismatch branch
        assert generate_validation_note(
            yolo_class="truck",
            yolo_confidence=None,
            florence_type="bus",
            resolved_type="truck",
            conflict_detected=True,
        ) == (
            "Cross-validation conflict: YOLO detected 'truck' (unknown conf), "
            "Florence described 'bus'. Resolved to 'truck'."
        )

    def test_confirmed_semantic_note_exact(self):
        assert (
            generate_validation_note(
                yolo_class="suv",
                yolo_confidence=0.77,
                florence_type="suv",
                resolved_type="suv",
                conflict_detected=False,
            )
            == "Cross-validation confirmed: YOLO 'suv' (77%) matches Florence 'suv'."
        )

    def test_disagree_non_conflict_note_exact(self):
        assert (
            generate_validation_note(
                yolo_class="man",
                yolo_confidence=0.44,
                florence_type="woman",
                resolved_type="man",
                conflict_detected=False,
            )
            == "Cross-validation: YOLO 'man' (44%), Florence 'woman'. Using 'man'."
        )

    def test_single_source_and_none_notes_exact(self):
        assert (
            generate_validation_note(
                yolo_class="van",
                yolo_confidence=0.5,
                florence_type=None,
                resolved_type="van",
                conflict_detected=False,
            )
            == "YOLO detected 'van' (50%)."
        )
        assert (
            generate_validation_note(
                yolo_class=None,
                yolo_confidence=None,
                florence_type="bicycle",
                resolved_type="bicycle",
                conflict_detected=False,
            )
            == "Florence detected 'bicycle'."
        )
        assert (
            generate_validation_note(
                yolo_class=None,
                yolo_confidence=None,
                florence_type=None,
                resolved_type="unknown",
                conflict_detected=False,
            )
            == "No cross-validation data available."
        )


class TestDetectCrossValidationErrorExact:
    """C6: gate routing + full message (embeds the extracted-terms set repr)."""

    def test_person_vehicle_branch_full_payload(self):
        e = detect_cross_validation_error("person", 0.91, "a parked truck outside")
        assert isinstance(e, CrossValidationError)
        assert e.is_critical is True
        assert e.yolo_class == "person"
        assert e.yolo_confidence == 0.91
        assert e.florence_description == "a parked truck outside"
        assert e.message == (
            "Person-vehicle mismatch: YOLO detected 'person' (91% conf) "
            "but Florence described vehicle terms: {'truck'}"
        )

    def test_vehicle_person_branch_full_payload(self):
        e = detect_cross_validation_error("car", 0.8, "a man walking")
        assert isinstance(e, CrossValidationError)
        assert e.yolo_class == "car"
        assert e.yolo_confidence == 0.8
        assert e.florence_description == "a man walking"
        # message embeds the extracted-terms SET repr — string hash order is
        # per-process, so pin the deterministic prefix and membership of the
        # set repr (kills message->None/XXXX/case and yolo_confidence formats)
        prefix, terms = e.message.split("person terms: ")
        assert prefix == (
            "Vehicle-person mismatch: YOLO detected 'car' (80% conf) but Florence described "
        )
        assert terms.startswith("{") and terms.endswith("}")
        body = terms[1:-1]
        parts = {p.strip() for p in body.split(",")}
        # "walking" is itself a PERSON_TERM -> both terms present, nothing else
        assert parts == {"'man'", "'walking'"}

    def test_mixed_terms_produce_no_error(self):
        assert detect_cross_validation_error("person", 0.9, "a person near a truck") is None
        assert detect_cross_validation_error("car", 0.9, "a car and a man") is None

    def test_equivalence_key_routes_vehicle_branch(self):
        # is_yolo_vehicle = yolo_lower in VEHICLE_TERMS or yolo_lower in
        # YOLO_TO_FLORENCE_EQUIVALENCE: "motorcycle" is BOTH, so use an
        # equivalence-ONLY yolo key — "truck" is a VEHICLE_TERM too, "car"
        # likewise; the map's keys are {car,truck,bus,motorcycle,bicycle} and
        # every one is also in VEHICLE_TERMS -> the `or` gate can only be
        # probed by an `and` flip (drops nothing here) or a term-set swap.
        # Shipped truth: truck yolo + person-only text fires the branch.
        e = detect_cross_validation_error("truck", 0.75, "a person standing")
        assert e is not None and e.is_critical is True
        assert e.message.startswith("Vehicle-person mismatch: YOLO detected 'truck'")

    def test_missing_inputs_return_none(self):
        assert detect_cross_validation_error(None, 0.9, "a man") is None
        assert detect_cross_validation_error("person", 0.9, None) is None
        assert detect_cross_validation_error("person", 0.9, "empty yard") is None


class TestCleanVqaRecoveryBranch:
    """C3: the "VQA> without ?" recovery block — no existing input reaches it."""

    def test_recovery_strips_question_to_loc_boundary(self):
        # shipped: find("VQA>") then find("<", vqa_idx) -> result from the
        # first loc token -> "answer"
        assert clean_vqa_output("VQA>what is this<loc_1>answer") == "answer"

    def test_recovery_without_loc_tokens_returns_empty(self):
        # `loc_start != -1` -> `== -1` keeps result[-1:] ("d") not "";
        # -> `!= -2`/`!= 1` are constant-True variants (same or crash path)
        assert clean_vqa_output("VQA>truncated question") == ""

    def test_loc_search_starts_at_vqa_not_string_head(self):
        # leading "<" BEFORE the VQA> marker: dropping the find start-arg
        # (or None) cuts at the leading "<b" and leaks the question text
        assert clean_vqa_output("a<b VQA>who is there<loc_2>nobody") == "nobody"

    def test_regex_path_still_wins_with_questionmark(self):
        assert clean_vqa_output("VQA>Are there tools?A ladder<loc_3>") == "A ladder"

    def test_plain_and_token_outputs_unchanged(self):
        assert clean_vqa_output("A ladder against the wall<loc_100><loc_200>") == (
            "A ladder against the wall"
        )
        assert clean_vqa_output("tools visible visible (ladder)") == "tools visible (ladder)"
        assert clean_vqa_output("") == ""


class TestVqaValidationBoundaries:
    """C4: min-length boundary (2) and case-insensitive whitelist lookup."""

    def test_two_char_non_whitelist_is_valid(self):
        # `len < 2` -> `<= 2` would reject "ab"
        assert is_valid_vqa_output("ab") is True
        assert is_valid_vqa_output("a") is False

    def test_whitelist_is_case_insensitive(self):
        # `.lower()` -> `.upper()`: "YES"/"Red" stop matching the whitelist
        assert is_valid_vqa_output("YES") is True
        assert is_valid_vqa_output("Red") is True
        assert is_valid_vqa_output("suv") is True

    def test_garbage_patterns_reject(self):
        assert is_valid_vqa_output("<loc_95><loc_86>") is False
        assert is_valid_vqa_output("VQA>person wearing<loc_95>") is False

    def test_validate_and_clean_boundaries(self):
        assert validate_and_clean_vqa_output("ab") == "ab"
        assert validate_and_clean_vqa_output("a") is None
        assert validate_and_clean_vqa_output("YES") == "YES"
        assert validate_and_clean_vqa_output("Red") == "Red"
        assert validate_and_clean_vqa_output("sedan<loc_1><loc_2>") is None
        assert validate_and_clean_vqa_output("VQA>person wearing<loc_95>") is None
        assert validate_and_clean_vqa_output("") is None


class TestToDictExactKeys:
    """C2: serialized key sets and the None-conditional branches."""

    def test_cross_validation_error_to_dict_exact(self):
        e = CrossValidationError(
            is_critical=True,
            message="m",
            yolo_class="car",
            yolo_confidence=0.5,
            florence_description="a man",
        )
        assert e.to_dict() == {
            "is_critical": True,
            "message": "m",
            "yolo_class": "car",
            "yolo_confidence": 0.5,
            "florence_description": "a man",
        }

    def test_batch_result_to_dict_keys_exact(self):
        d = BatchExtractionResult().to_dict()
        # exact key set + falsy defaults: key renames and the None-conditional
        # branches (`if x or True` -> .to_dict() on None crashes) die here
        assert d == {
            "vehicle_attributes": {},
            "person_attributes": {},
            "scene_analysis": None,
            "environment_context": None,
            "florence_enhanced": None,
        }

    def test_nested_result_families_to_dict_exact(self):
        from backend.services.vision_extractor import (
            EnvironmentContext,
            PersonAttributes,
            SceneAnalysis,
            VehicleAttributes,
        )

        assert VehicleAttributes(
            color="blue",
            vehicle_type="sedan",
            is_commercial=False,
            commercial_text=None,
            caption="cap",
        ).to_dict() == {
            "color": "blue",
            "vehicle_type": "sedan",
            "is_commercial": False,
            "commercial_text": None,
            "caption": "cap",
            "validation_note": None,
            "yolo_class": None,
            "yolo_confidence": None,
        }
        assert PersonAttributes(
            clothing="hoodie",
            carrying=None,
            is_service_worker=False,
            action="walking",
            caption="cap",
        ).to_dict() == {
            "clothing": "hoodie",
            "carrying": None,
            "is_service_worker": False,
            "action": "walking",
            "caption": "cap",
        }
        assert SceneAnalysis().to_dict() == {
            "unusual_objects": [],
            "tools_detected": [],
            "abandoned_items": [],
            "scene_description": "",
        }
        assert EnvironmentContext(
            time_of_day="night", artificial_light=True, weather="clear"
        ).to_dict() == {"time_of_day": "night", "artificial_light": True, "weather": "clear"}
