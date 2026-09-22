"""Batch-8 mutation-kill battery: prompts.py feed-scope survivors (WP4.4 feed).

Targets the 218 per-mutant diff shapes recorded in
``archive/wp25-feed/wp44-triage/prompts-diffs.txt`` across 12 functions:
``_format_time_gap``, ``_infer_movement_pattern``, ``check_member_schedule``,
``format_household_context``, ``format_enhanced_clothing_context``,
``format_florence_scene_context``, ``format_pose_scene_conflict_warning``,
``resolve_pose_scene_conflict``, ``format_scene_context``,
``format_enhanced_reid_context``, ``format_florence_attributes``, and
``format_ondemand_enrichment_context``.

Every assert is written against the SHIPPED contract (exact whole-string
equality where the mutants are text swaps), so a decoration mutant that the
dossier filed LOW-VALUE still dies here — the battery kills shapes, not
classes. Feed shapes proven unreachable/unobservable against the shipped
code are justified per-mutant in the ledger (L) row, not skipped silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import ClassVar

import pytest

from backend.services import prompts as prompts_module
from backend.services.prompts import (
    _format_time_gap,
    _infer_movement_pattern,
    check_member_schedule,
    format_enhanced_clothing_context,
    format_enhanced_reid_context,
    format_florence_attributes,
    format_florence_scene_context,
    format_household_context,
    format_ondemand_enrichment_context,
    format_pose_scene_conflict_warning,
    format_scene_context,
    resolve_pose_scene_conflict,
)


@dataclass
class ZoneCtx:
    """Minimal ZoneContext stand-in (only zone_type is read by the shipped code)."""

    zone_name: str
    zone_type: str


# ---------------------------------------------------------------------------
# _format_time_gap — feed shapes 4, 5, 7, 8, 12
# ---------------------------------------------------------------------------
class TestTimeGapBoundaries:
    def test_exact_minute_boundary_is_minutes_not_seconds(self):
        # `minutes < 1` -> `<= 1` would render 60 s as "60 seconds ago"
        assert _format_time_gap(60.0) == "1 minutes ago"

    def test_ninety_seconds_is_minutes(self):
        # `< 1` -> `< 2` renders 90 s via the SECONDS path "90 seconds ago"
        assert _format_time_gap(90.0) == "1 minutes ago"

    def test_exact_hour_boundary_is_hours_not_minutes(self):
        # `minutes < 60` -> `<= 60` renders 3600 s as "60 minutes ago"
        assert _format_time_gap(3600.0) == "1.0 hours ago"

    def test_sixty_and_half_minutes_is_hours(self):
        # `< 60` -> `< 61` renders 3630 s (60.5 min) as "60 minutes ago"
        assert _format_time_gap(3630.0) == "1.0 hours ago"

    def test_hours_divisor_is_sixty(self):
        # `minutes / 60` -> `/ 61` renders 12600 s as "3.4 hours ago"
        assert _format_time_gap(12600.0) == "3.5 hours ago"


# ---------------------------------------------------------------------------
# _infer_movement_pattern — feed shapes 1, 5, 6, 11, 14, 18, 29-59
# ---------------------------------------------------------------------------
class TestInferMovementPatternExact:
    def test_missing_current_camera_returns_empty(self):
        # `or` -> `and` lets a None current_camera fall through to a partial narrative
        assert _infer_movement_pattern("driveway", None, None, 60.0) == ""
        assert _infer_movement_pattern(None, "front_door", None, 60.0) == ""

    def test_no_zone_rapid_exact(self):
        # kills join-XX, label case/XX swaps, and `has_entry_point = True`
        result = _infer_movement_pattern("driveway", "front_door", None, 60.0)
        assert result == "moved from driveway to front_door, in rapid succession"

    def test_two_minute_boundary_is_not_rapid(self):
        # `< 2` -> `<= 2` / `< 3` render 120 s as "in rapid succession"
        assert _infer_movement_pattern("a", "b", None, 120.0) == "moved from a to b, over 2 minutes"

    def test_ten_minute_boundary_is_extended(self):
        # `< 10` -> `<= 10` / `< 11` drop "(extended presence)" at 600 s
        assert _infer_movement_pattern("a", "b", None, 600.0) == (
            "moved from a to b, over 10 minutes (extended presence)"
        )

    def test_entry_point_exact(self):
        zone = ZoneCtx(zone_name="Front Door", zone_type="entry_point")
        assert _infer_movement_pattern("street", "porch", [zone], 60.0) == (
            "moved from street to porch, in rapid succession, "
            "now at entry point (approaching property access)"
        )

    def test_driveway_exact(self):
        # kills membership XX/case/`not in` flips, label swaps, and append(None)
        # (which drops the zone tail entirely)
        zone = ZoneCtx(zone_name="Driveway", zone_type="driveway")
        assert _infer_movement_pattern("street", "driveway_cam", [zone], 180.0) == (
            "moved from street to driveway_cam, over 3 minutes, now in driveway area"
        )

    def test_yard_exact(self):
        zone = ZoneCtx(zone_name="Back Yard", zone_type="yard")
        assert _infer_movement_pattern("street", "backyard_cam", [zone], 900.0) == (
            "moved from street to backyard_cam, over 15 minutes (extended presence), "
            "now in yard/private area"
        )

    def test_zone_without_zone_type_attribute_does_not_crash(self):
        # default DELETED (`getattr(zc, "zone_type", )`) raises AttributeError here
        zone = SimpleNamespace(zone_name="Mystery")
        assert (
            _infer_movement_pattern("a", "b", [zone], 180.0) == "moved from a to b, over 3 minutes"
        )

    def test_driveway_wins_over_yard_precedence(self):
        zones = [
            ZoneCtx(zone_name="Yard", zone_type="yard"),
            ZoneCtx(zone_name="Drive", zone_type="driveway"),
        ]
        assert _infer_movement_pattern("a", "b", zones, 180.0).endswith("now in driveway area")


# ---------------------------------------------------------------------------
# check_member_schedule — day-name lookup, arithmetic, range comparisons
# ---------------------------------------------------------------------------
class TestCheckMemberScheduleDayNames:
    DAY_KEYS: ClassVar[list[str]] = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    @pytest.mark.parametrize("idx", list(range(7)))
    def test_each_lowercase_day_key_is_honored(self, idx: int):
        # day_names XX-wrap / case-flip breaks that day's lookup -> None, not True
        monday = datetime(2026, 9, 21, 10, 0)  # a Monday
        day = monday + timedelta(days=idx)
        assert check_member_schedule({self.DAY_KEYS[idx]: "09:00-17:00"}, day) is True

    @pytest.mark.parametrize("idx", list(range(7)))
    def test_day_key_outside_hours_is_false(self, idx: int):
        monday = datetime(2026, 9, 21, 20, 0)  # Monday evening
        day = monday + timedelta(days=idx)
        assert check_member_schedule({self.DAY_KEYS[idx]: "09:00-17:00"}, day) is False

    def test_sunday_falls_to_weekends_without_keyerror(self):
        # `is_sunday and` -> `or` selects typical_schedule["sunday"] which does not
        # exist in this fixture -> KeyError; shipped reads "weekends"
        sunday = datetime(2026, 9, 27, 10, 0)
        assert check_member_schedule({"weekends": "all_day"}, sunday) is True


class TestCheckMemberScheduleParsing:
    def test_start_minutes_uses_plus(self):
        # `* 60 + mm` -> `-` turns 17:30 into 990 (16:30) -> True at 17:00
        assert (
            check_member_schedule({"daily": "17:30-18:00"}, datetime(2026, 9, 21, 17, 0)) is False
        )

    def test_end_minutes_uses_plus(self):
        # end "18:15" with `-` becomes 1065 (17:45) -> False at 18:05
        assert check_member_schedule({"daily": "17:00-18:15"}, datetime(2026, 9, 21, 18, 5)) is True

    def test_equal_start_end_is_not_overnight(self):
        # `end < start` -> `<=` treats 09:00-09:00 as overnight -> True at 10:00
        assert (
            check_member_schedule({"daily": "09:00-09:00"}, datetime(2026, 9, 21, 10, 0)) is False
        )

    def test_inclusive_range_boundaries(self):
        sched = {"weekdays": "09:00-17:00"}
        assert check_member_schedule(sched, datetime(2026, 9, 21, 9, 0)) is True
        assert check_member_schedule(sched, datetime(2026, 9, 21, 17, 0)) is True
        assert check_member_schedule(sched, datetime(2026, 9, 21, 8, 59)) is False

    def test_overnight_range_boundaries(self):
        sched = {"weekdays": "22:00-06:00"}
        # `>= start` -> `>` fails exactly at 22:00; `<= end` -> `<` fails exactly at 06:00
        assert check_member_schedule(sched, datetime(2026, 9, 21, 22, 0)) is True
        assert check_member_schedule(sched, datetime(2026, 9, 22, 6, 0)) is True
        assert check_member_schedule(sched, datetime(2026, 9, 21, 12, 0)) is False

    def test_all_day_missing_key_invalid_shape(self):
        assert check_member_schedule({"weekdays": "all_day"}, datetime(2026, 9, 21, 3, 0)) is True
        assert check_member_schedule({"nothing": "x"}, datetime(2026, 9, 21, 3, 0)) is None
        assert (
            check_member_schedule({"weekdays": "not-a-time"}, datetime(2026, 9, 21, 3, 0)) is None
        )
        assert check_member_schedule(None, datetime(2026, 9, 21, 3, 0)) is None


# ---------------------------------------------------------------------------
# format_household_context — borders, headers, similarity math, risk branches
# ---------------------------------------------------------------------------
def _pm(**kw):
    base = {
        "member_id": 1,
        "member_name": "Mike",
        "vehicle_id": None,
        "vehicle_description": None,
        "similarity": 0.95,
        "match_type": "person",
    }
    base.update(kw)
    return SimpleNamespace(**base)


class TestFormatHouseholdContextExact:
    BORDER = "+" + "-" * 64 + "+"
    NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)

    def test_unknown_person_exact(self):
        # kills header XX/case swaps, every border-char XX wrap, box_width 64->65,
        # the no-match line swaps, and the final join-XX
        assert format_household_context([], [], self.NOW) == "\n".join(
            [
                "## RISK MODIFIERS (Apply These First)",
                self.BORDER,
                "| KNOWN PERSON MATCH: None (unknown individual)",
                self.BORDER,
                "-> Calculated base risk: 50",
            ]
        )

    def test_similarity_truncation_is_floor_of_hundred_x(self):
        # `* 100` -> `* 101` lifts 49.9% into "50%"
        assert "| KNOWN PERSON: Mike (49% match)" in format_household_context(
            [_pm(similarity=0.499)], [], self.NOW
        )

    def test_role_line_exact(self):
        assert "| KNOWN PERSON: Mike (resident, 95% match)" in format_household_context(
            [_pm(member_role="resident")], [], self.NOW
        )

    def test_schedule_within_line_and_risk(self):
        result = format_household_context([_pm(schedule_status=True)], [], self.NOW)
        assert "|   Schedule: Within expected hours" in result
        assert result.endswith("-> Calculated base risk: 5")

    def test_schedule_outside_line_and_risk(self):
        result = format_household_context([_pm(schedule_status=False)], [], self.NOW)
        assert "|   Schedule: Outside normal hours" in result
        assert result.endswith("-> Calculated base risk: 20")

    def test_similarity_risk_boundary_is_strictly_above_nine(self):
        # `and False` (always 15), 5->6, `>=` at exactly 0.9, `> 1.9` (always 15)
        assert format_household_context([_pm(similarity=0.95)], [], self.NOW).endswith(
            "-> Calculated base risk: 5"
        )
        assert format_household_context([_pm(similarity=0.9)], [], self.NOW).endswith(
            "-> Calculated base risk: 15"
        )

    def test_vehicle_caps_risk_at_ten(self):
        veh = _pm(
            vehicle_id=1,
            vehicle_description="Silver Tesla",
            similarity=1.0,
            match_type="license_plate",
        )
        result = format_household_context([], [veh], self.NOW)
        assert "| REGISTERED VEHICLE: Silver Tesla" in result
        assert result.endswith("-> Calculated base risk: 10")


# ---------------------------------------------------------------------------
# format_enhanced_clothing_context — all 53 feed shapes
# ---------------------------------------------------------------------------
class TestFormatEnhancedClothingContextKillBattery:
    HDR = "### Person Appearance Analysis"

    def test_alert_exact_and_multiline_join(self):
        # kills header XX/case swaps and the "\n".join XX wrap
        out = format_enhanced_clothing_context(
            {
                "suspicious": {"confidence": 0.8, "top_match": "mask"},
                "casual": {"top_match": "jacket"},
            }
        )
        assert out == f"{self.HDR}\n- **ALERT**: mask (confidence: 80%)\n- General attire: jacket"

    def test_suspicious_missing_confidence_returns_empty(self):
        # defaults None / deleted -> TypeError on {confidence:.0%}; 0.0->1.0 emits ALERT
        assert format_enhanced_clothing_context({"suspicious": {"top_match": "balaclava"}}) == ""

    def test_suspicious_threshold_is_strictly_above_0_6(self):
        assert (
            format_enhanced_clothing_context({"suspicious": {"confidence": 0.6, "top_match": "m"}})
            == ""
        )

    def test_suspicious_top_match_default_exact(self):
        out = format_enhanced_clothing_context({"suspicious": {"confidence": 0.9}})
        assert out == f"{self.HDR}\n- **ALERT**: suspicious attire (confidence: 90%)"

    def test_suspicious_non_dict_uses_getattr_and_str(self):
        # isinstance -> `or True` crashes (.get on object); str(None) prints "None"
        out = format_enhanced_clothing_context({"suspicious": SimpleNamespace(confidence=0.9)})
        assert out == f"{self.HDR}\n- **ALERT**: namespace(confidence=0.9) (confidence: 90%)"

    def test_delivery_branch_exact_defaults_and_threshold(self):
        out = format_enhanced_clothing_context(
            {"delivery": {"confidence": 0.6, "top_match": "UPS uniform"}}
        )
        assert out == f"{self.HDR}\n- Service worker identified: UPS uniform (60%)"
        out_default = format_enhanced_clothing_context({"delivery": {"confidence": 0.7}})
        assert out_default == f"{self.HDR}\n- Service worker identified: delivery uniform (70%)"
        assert format_enhanced_clothing_context({"delivery": {"confidence": 0.5}}) == ""

    def test_utility_branch_exact_defaults_and_threshold(self):
        out = format_enhanced_clothing_context(
            {"utility": {"confidence": 0.6, "top_match": "hi-vis vest"}}
        )
        assert out == f"{self.HDR}\n- Utility worker identified: hi-vis vest (60%)"
        out_default = format_enhanced_clothing_context({"utility": {"confidence": 0.7}})
        assert out_default == f"{self.HDR}\n- Utility worker identified: utility worker (70%)"
        assert format_enhanced_clothing_context({"utility": {"confidence": 0.5}}) == ""

    def test_carrying_always_appended_with_defaults(self):
        # carrying has NO confidence gate — the (0%) render is contractual
        out = format_enhanced_clothing_context({"carrying": {"top_match": "backpack"}})
        assert out == f"{self.HDR}\n- Carrying: backpack (0%)"
        out2 = format_enhanced_clothing_context({"carrying": {"confidence": 0.4}})
        assert out2 == f"{self.HDR}\n- Carrying: carrying item (40%)"

    def test_casual_branch_exact(self):
        # casual {} is falsy — branch skipped; only truthy dicts render
        out = format_enhanced_clothing_context({"casual": {"foo": 1}})
        assert out == f"{self.HDR}\n- General attire: casual attire"
        out2 = format_enhanced_clothing_context({"casual": {"top_match": "jacket"}})
        assert out2 == f"{self.HDR}\n- General attire: jacket"

    def test_non_dict_objects_stringified_in_every_branch(self):
        # exercises the getattr-confidence + str(value) path for delivery, utility,
        # carrying — every isinstance `or True` mutant crashes, every str(None) prints None
        out = format_enhanced_clothing_context(
            {
                "delivery": SimpleNamespace(confidence=0.7),
                "utility": SimpleNamespace(confidence=0.6),
                "carrying": 42,
            }
        )
        assert out == "\n".join(
            [
                self.HDR,
                "- Service worker identified: namespace(confidence=0.7) (70%)",
                "- Utility worker identified: namespace(confidence=0.6) (60%)",
                "- Carrying: 42 (0%)",
            ]
        )

    def test_empty_and_falsy_inputs(self):
        assert format_enhanced_clothing_context({}) == ""
        assert format_enhanced_clothing_context(None) == ""


# ---------------------------------------------------------------------------
# format_florence_scene_context — 40 feed shapes
# ---------------------------------------------------------------------------
class TestFormatFlorenceSceneContextExact:
    HDR = "### Scene Analysis (Florence-2)"

    def test_full_document_exact(self):
        # whole-string equality mows: header swap, objects join XX, every high_risk
        # set-member XX/case flip, the `in`->`not in` flip, risk-list join, every
        # .get key swap (dense_captions/phrase_grounding/region_descriptions/
        # security_vqa), their None-call twins, and the final join XX
        result = {
            "scene": "A porch at dusk",
            "security_objects": {"labels": ["a gun on the step", "knife", "person"]},
            "dense_captions": [
                {"caption": "dark figure near door"},
                {"caption": "vehicle in driveway"},
                {"caption": ""},  # blank caption is skipped
            ],
            "text_regions": {"labels": ["STOP", "742"]},
            "phrase_grounding": [
                {"matched": True, "phrase": "weapon", "bboxes": [1, 2]},
                {"matched": True, "phrase": "person", "bboxes": [3]},
                {"matched": False, "phrase": "ignored", "bboxes": [9]},
            ],
            "region_descriptions": {"1": "first desc", "2": "second desc"},
            "security_vqa": {"5": {"armed?": "yes", "carrying?": "no"}},
        }
        assert format_florence_scene_context(result) == "\n".join(
            [
                self.HDR,
                "\n**Scene Description:**\nA porch at dusk",
                "\n**Security Objects Detected:** a gun on the step, knife, person",
                "- **HIGH RISK OBJECTS**: a gun on the step, knife",
                "\n**Region Descriptions:**",
                "- dark figure near door",
                "- vehicle in driveway",
                "\n**Visible Text:** STOP, 742",
                "\n**Phrase Grounding Matches:** weapon (2 location(s)), person (1 location(s))",
                "\n**Detection Region Descriptions:**",
                "- [1] first desc",
                "- [2] second desc",
                "\n**Security Assessment (VQA):**",
                "\n[Detection 5]:",
                "  Q: armed?",
                "  A: yes",
                "  Q: carrying?",
                "  A: no",
            ]
        )

    def test_non_dict_objects_and_texts_are_skipped(self):
        # isinstance -> `or True` makes "gun".get crash; shipped yields ""
        assert format_florence_scene_context({"security_objects": "gun"}) == ""
        assert format_florence_scene_context({"text_regions": "STOP"}) == ""

    def test_only_header_returns_empty(self):
        assert format_florence_scene_context({}) == ""
        assert format_florence_scene_context(None) == ""
        assert format_florence_scene_context({"scene": ""}) == ""

    def test_no_high_risk_labels_omits_alert(self):
        out = format_florence_scene_context({"security_objects": {"labels": ["bicycle", "plant"]}})
        assert out == f"{self.HDR}\n\n**Security Objects Detected:** bicycle, plant"


# ---------------------------------------------------------------------------
# format_pose_scene_conflict_warning — scene keyword extraction
# ---------------------------------------------------------------------------
class TestFormatPoseSceneConflictWarningExact:
    @staticmethod
    def _expected(pose: str, scene_pose: str) -> str:
        return (
            f'**SIGNAL CONFLICT**: Pose model detected "{pose}" '
            f'but scene shows "{scene_pose}".\n'
            f"Confidence is LOW for behavioral analysis. Weight other evidence."
        )

    def test_no_conflict_returns_none(self):
        assert (
            format_pose_scene_conflict_warning("running", "x", {"conflict_detected": False}) is None
        )

    @pytest.mark.parametrize(
        ("scene", "found"),
        [
            ("a person sitting on a bench", "sitting"),
            ("someone standing near the door", "standing"),
            ("a subject walking the path", "walking"),
            ("running across the yard", "running"),
            ("lying on the grass", "lying"),
        ],
    )
    def test_each_scene_keyword_extracted_exact(self, scene: str, found: str):
        # XX/case flips in scene_keywords silently fall through to "unknown"
        out = format_pose_scene_conflict_warning(
            "running", scene, {"conflict_detected": True, "resolved_pose": "unknown"}
        )
        assert out == self._expected("running", found)

    def test_no_keyword_scene_falls_back_to_lowercase_unknown(self):
        # scene_pose -> None prints "None"; XX/UNKNOWN swaps break exact equality
        out = format_pose_scene_conflict_warning(
            "running", "a person near the bench", {"conflict_detected": True}
        )
        assert out == self._expected("running", "unknown")


# ---------------------------------------------------------------------------
# resolve_pose_scene_conflict — resolution string swaps
# ---------------------------------------------------------------------------
class TestResolvePoseSceneConflictExact:
    def test_running_vs_sitting_prefers_scene(self):
        assert resolve_pose_scene_conflict(
            "running", 0.9, "a person sitting on a bench", False
        ) == {
            "resolved_pose": "unknown",
            "conflict_detected": True,
            "resolution": "Preferred scene interpretation",
        }

    def test_conditional_with_motion_blur_prefers_pose(self):
        assert resolve_pose_scene_conflict("running", 0.9, "person standing still", True) == {
            "resolved_pose": "running",
            "conflict_detected": True,
            "resolution": "Preferred pose interpretation",
        }

    def test_crouching_vs_walking_prefers_pose(self):
        assert resolve_pose_scene_conflict("crouching", 0.5, "someone walking by", False) == {
            "resolved_pose": "crouching",
            "conflict_detected": True,
            "resolution": "Preferred pose interpretation",
        }

    def test_no_conflict_passthrough(self):
        assert resolve_pose_scene_conflict("standing", 0.5, "", False) == {
            "resolved_pose": "standing",
            "conflict_detected": False,
        }
        assert resolve_pose_scene_conflict("standing", 0.5, "empty yard", False) == {
            "resolved_pose": "standing",
            "conflict_detected": False,
        }


# ---------------------------------------------------------------------------
# format_scene_context — truncation geometry
# ---------------------------------------------------------------------------
class TestFormatSceneContextTruncation:
    def test_word_boundary_rfind_and_reserve_three(self):
        # spaces at 2, 16, 17; max_length 20 -> reserve 3 -> rfind ends before 17.
        # rfind->find truncates at 2; " "-pattern "XX XX" hard-truncates at 17;
        # reserve 3->4 (truncate_at 16) truncates at the space at index 2.
        cap = "ab cdefghijklmno  p q"
        assert format_scene_context(cap, max_length=20) == "ab cdefghijklmno..."

    def test_space_at_index_one_still_truncates_there(self):
        # `last_space > 1` would hard-truncate instead of cutting at index 1
        cap = "a " + "b" * 18 + " qr"
        assert format_scene_context(cap, max_length=20) == "a..."

    def test_short_caption_untouched(self):
        assert format_scene_context("A residential driveway at night.") == (
            "A residential driveway at night."
        )
        assert format_scene_context(None) == ""
        assert format_scene_context("   ") == ""


# ---------------------------------------------------------------------------
# format_enhanced_reid_context — risk-modifier line swaps
# ---------------------------------------------------------------------------
class TestFormatEnhancedReidContextExact:
    @staticmethod
    def _entity(count: int, days: int, trust: str) -> SimpleNamespace:
        # first_seen anchored to real now so (now - first_seen).days == days exactly
        return SimpleNamespace(
            first_seen_at=datetime.now(UTC) - timedelta(days=days),
            detection_count=count,
            trust_status=trust,
        )

    def test_first_time_seen_exact(self):
        assert format_enhanced_reid_context(7, None, []) == (
            "## Person 7 Re-Identification\nPerson 7: FIRST TIME SEEN (unknown)\n-> Base risk: 50"
        )

    def test_trusted_frequent_exact(self):
        out = format_enhanced_reid_context(3, self._entity(25, 8, "trusted"), [])
        assert out == "\n".join(
            [
                "## Person 3 Re-Identification",
                "FREQUENT VISITOR: Seen 25x over 8 days",
                "Trust status: trusted",
                "-> RISK MODIFIER: -40 points (established trusted entity)",
            ]
        )

    def test_untrusted_frequent_exact(self):
        out = format_enhanced_reid_context(3, self._entity(21, 7, "unknown"), [])
        assert out == "\n".join(
            [
                "## Person 3 Re-Identification",
                "FREQUENT VISITOR: Seen 21x over 7 days",
                "Trust status: unknown",
                "-> RISK MODIFIER: -20 points (familiar but unverified)",
            ]
        )

    def test_returning_exact(self):
        out = format_enhanced_reid_context(3, self._entity(5, 1, "unknown"), [])
        assert out == "\n".join(
            [
                "## Person 3 Re-Identification",
                "RETURNING VISITOR: Seen 5x",
                "-> RISK MODIFIER: -10 points (repeat visitor)",
            ]
        )

    def test_recent_exact(self):
        out = format_enhanced_reid_context(3, self._entity(2, 0, "unknown"), [])
        assert out == "\n".join(
            [
                "## Person 3 Re-Identification",
                "RECENT VISITOR: Seen 2x (first: 0d ago)",
                "-> No risk modifier (insufficient history)",
            ]
        )


# ---------------------------------------------------------------------------
# format_florence_attributes — valid_count + join
# ---------------------------------------------------------------------------
class TestFormatFlorenceAttributesValidCount:
    def test_valid_lines_joined_with_newline(self):
        # join "\n" -> "XX\nXX" — validator lowercases, so fixtures are lowercase
        out = format_florence_attributes({"clothing": "dark hoodie", "action": "walking"}, "")
        assert out == "clothing: dark hoodie\naction: walking"

    def test_all_invalid_falls_back_to_caption(self):
        # valid_count =1 / -=1 / +=2 only diverge if the 0-check flips while
        # lines exist — assert BOTH sides of the fallback branch
        assert (
            format_florence_attributes({"garbage": "<loc_200>"}, "Person in blue jacket")
            == "Scene context: Person in blue jacket"
        )
        assert format_florence_attributes({"a": "ok", "b": "fine"}, "fallback") == "a: ok\nb: fine"

    def test_none_attributes_caption_and_empty_paths(self):
        assert format_florence_attributes(None, "a caption") == "Scene context: a caption"
        assert format_florence_attributes(None, "") == ""


# ---------------------------------------------------------------------------
# format_ondemand_enrichment_context — section join + sentinel filtering
# ---------------------------------------------------------------------------
class TestFormatOndemandEnrichmentJoin:
    def test_sections_joined_with_double_newline(self, monkeypatch):
        monkeypatch.setattr(prompts_module, "build_threat_section", lambda _e: "T")
        monkeypatch.setattr(prompts_module, "build_person_analysis_section", lambda _e: "P")
        monkeypatch.setattr(prompts_module, "build_vehicle_section", lambda _e: "V")
        out = format_ondemand_enrichment_context(SimpleNamespace())
        assert out == "### THREAT DETECTION\nT\n\n## Person Analysis\nP\n\n### Vehicle Analysis\nV"

    def test_sentinel_sections_yield_empty(self, monkeypatch):
        monkeypatch.setattr(
            prompts_module, "build_threat_section", lambda _e: "No threats detected."
        )
        monkeypatch.setattr(
            prompts_module,
            "build_person_analysis_section",
            lambda _e: "No person analysis available.",
        )
        monkeypatch.setattr(
            prompts_module, "build_vehicle_section", lambda _e: "No vehicle detected."
        )
        assert format_ondemand_enrichment_context(SimpleNamespace()) == ""
