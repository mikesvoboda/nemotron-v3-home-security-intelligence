# TARGET-MODULE: backend.services.prompts
"""Batch-30 lane-e mutation-kill battery: prompts.py OCR + cross-camera tracking.

Targets the surviving diff shapes of ``format_scene_ocr_context``,
``_build_tracking_narratives``, ``_infer_movement_pattern`` and
``format_cross_camera_person_tracking`` (batch-30 lane e, 99 survivor keys; the
``_infer_movement_pattern`` shapes already pinned by ``test_prompts_batch8.py``
are NOT repeated here).

Every assert is exact whole-string equality against the SHIPPED contract, so
label-case swaps (``"Person"`` -> ``"person"``), key renames
(``"texts"`` -> ``"TEXTS"``), joiner swaps (``", "`` -> ``"XX, XX"``) and
``indent=2`` -> ``indent=3`` die on the same assert that pins the healthy
output, while mutants that raise (``round(None, 2)``, ``json.dumps(indent=2)``,
a deleted ``getattr`` default, ``detection_ocr_output = None``) die because the
shipped call returns a value. The per-test comments below name the survivor
keys the batch-30 trampoline sweep actually turned RED through that test
(``/home/agent/runs/scratch/b30e-sweep.log``), not merely the shapes the input
touches.

Nothing here patches wallclock: every timestamp/gap reaching these four
functions arrives as an argument (``time_gap_seconds`` on the ``EntityMatch``
objects and on ``_infer_movement_pattern``), so the narratives are pure
functions of their inputs and need no mocking.

The 12 keys this battery leaves GREEN are provably unkillable and are itemised
in the closing comment block: each edit is absorbed by a downstream ``or`` /
membership fold, or sits on a path the function's own guards make
unreachable, so no input can separate shipped from mutated output.
"""

from __future__ import annotations

import os
import sys

# This fragment lives OUTSIDE the repo tree (/home/agent/runs/b30-frags), so
# pytest gives it no sys.path entry for the repo. The harness always invokes it
# with the repo root (or the mutant home) as cwd, and the batch-30 sweep helper
# inserts cwd itself — mirror that so the import below resolves in both worlds.
_ROOT = os.getcwd()
if os.path.isfile(os.path.join(_ROOT, "backend", "services", "prompts.py")):
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from types import SimpleNamespace  # noqa: E402
from typing import Any  # noqa: E402

from backend.services.prompts import (  # noqa: E402
    _build_tracking_narratives,
    format_cross_camera_person_tracking,
    format_scene_ocr_context,
)
from backend.services.scene_ocr_service import (  # noqa: E402
    DetectionOCRResult,
    SceneOCRResult,
    SceneTextResult,
)
from backend.services.service_provider_matcher import ServiceMatch  # noqa: E402

# ---------------------------------------------------------------------------
# input builders (plain namespaces: some tests deliberately OMIT an attribute
# so a deleted ``getattr(x, "name", default)`` default raises under mutation)
# ---------------------------------------------------------------------------


def _entity(**fields: Any) -> Any:
    """An EntityEmbedding stand-in carrying exactly ``fields``."""
    return SimpleNamespace(**fields)


def _match(entity: Any, similarity: float, time_gap_seconds: float) -> Any:
    """An EntityMatch stand-in."""
    return SimpleNamespace(entity=entity, similarity=similarity, time_gap_seconds=time_gap_seconds)


def _zone(zone_name: Any = "Front Walk", zone_type: Any = "entry_point") -> Any:
    """A ZoneContext stand-in (both attributes present)."""
    return SimpleNamespace(zone_name=zone_name, zone_type=zone_type)


def _scene_ocr(
    scene_texts: list[SceneTextResult], detection_ocr: dict[str, DetectionOCRResult]
) -> SceneOCRResult:
    return SceneOCRResult(scene_texts=scene_texts, detection_ocr=detection_ocr)


# ---------------------------------------------------------------------------
# format_scene_ocr_context — JSON shape, confidence rounding + 0.50 gate
# ---------------------------------------------------------------------------


def test_scene_ocr_none_returns_empty_string() -> None:
    # sole killer of mutmut_2 (`return ""` -> `"XXXX"` on the
    # `scene_ocr is None` guard); the function's second `return ""` ->
    # `"XXXX"` (mutmut_38) is unreachable for this input and goes red in the
    # all-below-threshold / missing-confidence tests instead.
    assert format_scene_ocr_context(None) == ""


def test_scene_ocr_scene_text_keys_rounding_and_indent_exact() -> None:
    # 0.9126 pins round(...,2): a 2-arg round renders 1, ndigits None or a
    # deleted default and `round(None, 2)`/`round(2)` raise, ndigits 3 renders
    # 0.913. Kills mutmut_3 (filtered_scene_texts = None), 4/5 ("value" key),
    # 6/7 ("type"), 8/9 ("confidence"), 10-14 (the round call), 16
    # (detection_ocr_output = None), 35/36 (empty-payload guard flips),
    # 39 (output = None), 40/41 ("scene_text"), 42/43 ("detection_ocr") and
    # 44-48 (json.dumps arg/indent mutants).
    scene_ocr = _scene_ocr(
        [
            SceneTextResult(
                value="1234 Oak St",
                confidence=0.9126,
                bbox=(10, 20, 240, 70),
                text_type="street_sign",
            )
        ],
        {},
    )
    assert format_scene_ocr_context(scene_ocr) == "\n".join(
        [
            "{",
            '  "scene_text": [',
            "    {",
            '      "value": "1234 Oak St",',
            '      "type": "street_sign",',
            '      "confidence": 0.91',
            "    }",
            "  ],",
            '  "detection_ocr": {}',
            "}",
        ]
    )


def test_scene_ocr_confidence_exactly_at_threshold_is_kept() -> None:
    # sole killer of mutmut_15 (`t.confidence >= _SCENE_OCR_MIN_CONFIDENCE`
    # -> `>` drops the 0.50 text and collapses the payload to ""); the 0.50
    # text also keeps every L4304-4309/4334-4335/dumps mutant honest here
    # (3-14, 16, 35, 36, 39-48 as in the test above).
    scene_ocr = _scene_ocr(
        [SceneTextResult(value="OPEN", confidence=0.50, bbox=(0, 0, 5, 5), text_type="sign")],
        {},
    )
    assert format_scene_ocr_context(scene_ocr) == "\n".join(
        [
            "{",
            '  "scene_text": [',
            "    {",
            '      "value": "OPEN",',
            '      "type": "sign",',
            '      "confidence": 0.5',
            "    }",
            "  ],",
            '  "detection_ocr": {}',
            "}",
        ]
    )


def test_scene_ocr_all_scene_texts_below_threshold_returns_empty() -> None:
    # kills mutmut_37 (`if not filtered_scene_texts and
    # detection_ocr_output` -> the sub-threshold-only payload now renders
    # JSON instead of ""; 37 also goes red in ...detection_only_entry_exact)
    # and mutmut_38 (`return ""` -> `"XXXX"` — the other `return ""` (2) is
    # unreachable for this input).
    scene_ocr = _scene_ocr(
        [SceneTextResult(value="SHADOW", confidence=0.49, bbox=(0, 0, 5, 5), text_type="sign")],
        {},
    )
    assert format_scene_ocr_context(scene_ocr) == ""


def test_scene_ocr_detection_only_entry_exact() -> None:
    # Detection-only payload (no scene text, no service match): kills 17
    # (filtered_texts = None), 18/20/22/23 (the `"confidence"` get-key swaps),
    # 25 (get-line `>=` -> `>` on the 0.50 text), 26 (`filtered_texts or
    # service_match` -> `and`), 27 (the entry assignment -> None), 28/29
    # ("texts"), 30/31 ("service_match"), 33 (`... or True` -> asdict(None))
    # and 37 (`if not filtered_scene_texts and detection_ocr_output` empties
    # the guard's second operand).
    scene_ocr = _scene_ocr(
        [],
        {
            "3": DetectionOCRResult(
                detection_id="3",
                texts=[
                    {"value": "FEDEX", "confidence": 0.952, "region": "chest"},
                    {"value": "EXPRESS", "confidence": 0.5, "region": "door"},
                ],
                service_match=None,
            )
        },
    )
    assert format_scene_ocr_context(scene_ocr) == "\n".join(
        [
            "{",
            '  "scene_text": [],',
            '  "detection_ocr": {',
            '    "3": {',
            '      "texts": [',
            "        {",
            '          "value": "FEDEX",',
            '          "confidence": 0.952,',
            '          "region": "chest"',
            "        },",
            "        {",
            '          "value": "EXPRESS",',
            '          "confidence": 0.5,',
            '          "region": "door"',
            "        }",
            "      ],",
            '      "service_match": null',
            "    }",
            "  }",
            "}",
        ]
    )


def test_scene_ocr_service_match_only_entry_is_kept_without_texts() -> None:
    # Every text is sub-threshold, so ONLY the service match keeps the entry:
    # kills 32 (`... if (result.service_match) and False` nulls the match) and
    # 34 (`asdict(None) if result.service_match` raises); also red under 17,
    # 20, 26-31 (entry dropped / texts-or-match flips / key renames).
    scene_ocr = _scene_ocr(
        [],
        {
            "7": DetectionOCRResult(
                detection_id="7",
                texts=[{"value": "noise", "confidence": 0.11, "region": "crop"}],
                service_match=ServiceMatch(
                    provider="FedEx",
                    category="DELIVERY",
                    confidence=1.0,
                    risk_modifier="low_risk_service",
                    matched_alias="FDX",
                ),
            )
        },
    )
    assert format_scene_ocr_context(scene_ocr) == "\n".join(
        [
            "{",
            '  "scene_text": [],',
            '  "detection_ocr": {',
            '    "7": {',
            '      "texts": [],',
            '      "service_match": {',
            '        "provider": "FedEx",',
            '        "category": "DELIVERY",',
            '        "confidence": 1.0,',
            '        "risk_modifier": "low_risk_service",',
            '        "matched_alias": "FDX"',
            "      }",
            "    }",
            "  }",
            "}",
        ]
    )


def test_scene_ocr_detection_text_without_confidence_is_dropped() -> None:
    # The default of `text.get("confidence", 0.0)`: sole killer of 19 (`None`
    # default -> TypeError on the comparison), 21 (deleted default -> 2-arg
    # dict.get TypeError) and 24 (`1.0` default keeps the text, so the entry
    # and its JSON appear); also red under 38.
    scene_ocr = _scene_ocr(
        [],
        {
            "9": DetectionOCRResult(
                detection_id="9",
                texts=[{"value": "GHOST", "region": "crop"}],
                service_match=None,
            )
        },
    )
    assert format_scene_ocr_context(scene_ocr) == ""


def test_scene_ocr_scene_and_detection_sections_together_exact() -> None:
    # Both sections populated at once (the belt-and-braces payload): the
    # sweep turns this red under 14 (round ndigits 3 -> 0.7778 renders 0.778),
    # 18/22/23 (`text.get(None/XXconfidenceXX/CONFIDENCE, 0.0)` drop the
    # 0.68 text, leaving `"texts": []`), and 33 (`... or True` makes
    # `asdict(None)` raise). It pins the joint scene+detection rendering the
    # single-section payloads cannot: the guard AND at L4330 only has both
    # operands False-ish under a mutant when both sections are live.
    scene_ocr = _scene_ocr(
        [
            SceneTextResult(
                value="MAPLE AVE", confidence=0.7778, bbox=(0, 4, 90, 40), text_type="street_sign"
            )
        ],
        {
            "2": DetectionOCRResult(
                detection_id="2",
                texts=[{"value": "UPS", "confidence": 0.68}],
                service_match=None,
            )
        },
    )
    assert format_scene_ocr_context(scene_ocr) == "\n".join(
        [
            "{",
            '  "scene_text": [',
            "    {",
            '      "value": "MAPLE AVE",',
            '      "type": "street_sign",',
            '      "confidence": 0.78',
            "    }",
            "  ],",
            '  "detection_ocr": {',
            '    "2": {',
            '      "texts": [',
            "        {",
            '          "value": "UPS",',
            '          "confidence": 0.68',
            "        }",
            "      ],",
            '      "service_match": null',
            "    }",
            "  }",
            "}",
        ]
    )


# ---------------------------------------------------------------------------
# _build_tracking_narratives — cross-camera / same-camera narrative assembly
# ---------------------------------------------------------------------------


def test_narratives_cross_camera_no_zones_no_attrs_exact() -> None:
    # Single other camera, no zones, no attributes: kills 119/120 (the
    # prev_camera / current_camera_id args of _infer_movement_pattern -> None
    # blank the movement tail), 118 (`movement = None`), 127/128
    # (`movement_str = None` / `and False`), 134/135/137 (the multi-camera
    # note gate `> 1` -> `or True` / `>= 1` / `else "XXXX"`), 88/91
    # (`prev_attrs_str` gate `or True` -> `" ()"` / `else "XXXX"`) and 92/93
    # (`zone_str = None` raises in the f-string / `= "XXXX"` leaks).
    matches = {
        "7": [_match(_entity(camera_id="back_yard", attributes={}), 0.826, 90.0)],
    }
    assert _build_tracking_narratives(matches, "Vehicle", "front_door", None) == [
        '- Vehicle (detection 7): SAME VEHICLE seen on "back_yard" camera '
        "1 minutes ago (83% similarity). Movement pattern: moved from back_yard "
        "to front_door, in rapid succession."
    ]


def test_narratives_all_attributes_three_zones_three_cameras_exact() -> None:
    # Kills 71/72/73 (the `"carrying"` lookup -> None/`"XXcarryingXX"`/
    # `"CARRYING"` drop the carrying clause), 90 (the attr joiner
    # `", "` -> `"XX, XX"`), 116 (the location joiner), 117
    # (`zone_names[:2]` -> `[:3]` appends "Side Yard (yard)"), 121 (the
    # zone_context arg -> None drops the entry-point movement clause) and, as
    # in the test above, 116-121/127/128/118/71-73/90 across the whole line.
    # 0.912 also pins the cross-camera `similarity * 100` -> "%.0f" rounding
    # (3 of the *101/*100 mutants render 92%).
    matches = {
        "5": [
            _match(
                _entity(
                    camera_id="garage_cam",
                    attributes={
                        "clothing": "red hoodie",
                        "carrying": "cardboard box",
                        "color": "blue",
                        "vehicle_type": "van",
                    },
                ),
                0.912,
                600.0,
            ),
            _match(_entity(camera_id="gate_cam", attributes={}), 0.7, 30.0),
            _match(_entity(camera_id="porch_cam", attributes={}), 0.6, 20.0),
        ],
    }
    zones = [
        _zone("Front Walk", "entry_point"),
        _zone("Driveway", "driveway"),
        _zone("Side Yard", "yard"),
    ]
    assert _build_tracking_narratives(matches, "Person", "back_door", zones) == [
        '- Person (detection 5): SAME PERSON seen on "garage_cam" camera '
        "10 minutes ago (91% similarity) (wearing red hoodie, carrying "
        "cardboard box, color: blue, type: van). Current location: Front Walk "
        "(entry_point), Driveway (driveway). Movement pattern: moved from "
        "garage_cam to back_door, over 10 minutes (extended presence), now at "
        "entry point (approaching property access). Seen on 3 other camera(s) total."
    ]


def test_narratives_empty_match_list_does_not_stop_later_detections() -> None:
    # sole killer of mutmut_5 (L2900 `continue` -> `break` truncates the list
    # after detection "0"); also red under 144/147 because detection "1" is a
    # SAME-CAMERA match (its time_str / `similarity * 100` render here too).
    matches = {
        "0": [],
        "1": [_match(_entity(camera_id="same_cam", attributes={}), 0.5, 120.0)],
        "2": [],
    }
    assert _build_tracking_narratives(matches, "Person", "same_cam", None) == [
        "- Person (detection 0): First time seen on any camera (no re-ID matches).",
        "- Person (detection 1): Previously seen on this same camera 2 minutes ago "
        "(50% similarity). No cross-camera movement.",
        "- Person (detection 2): First time seen on any camera (no re-ID matches).",
    ]


def test_narratives_matches_without_entity_attribute_are_skipped() -> None:
    # sole killer of mutmut_13: shipped `getattr(match, "entity", None)`
    # yields None -> the match is skipped and nothing is emitted; deleting the
    # default turns this input into an AttributeError.
    matches = {"1": [SimpleNamespace(similarity=0.9, time_gap_seconds=60.0)]}
    assert _build_tracking_narratives(matches, "Person", "cam_a", None) == []


def test_narratives_same_camera_only_exact() -> None:
    # The same-camera branch (L2977-2986) carries the L2982
    # `similarity * 100` line; kills 148 (`* 101` renders 0.8734 as 88% —
    # 148 also goes red in ...entity_without_camera_id..., which has no
    # sharper assertion), 144 (`time_str = None` raises in the f-string) and
    # 147 (`/ 100` -> "0%").
    matches = {"1": [_match(_entity(camera_id="same_cam", attributes={}), 0.8734, 45.0)]}
    assert _build_tracking_narratives(matches, "Vehicle", "same_cam", None) == [
        "- Vehicle (detection 1): Previously seen on this same camera 45 seconds ago "
        "(87% similarity). No cross-camera movement."
    ]


def test_narratives_entity_without_camera_id_falls_to_same_camera() -> None:
    # sole killer of mutmut_22: deleting the `getattr(match_entity,
    # "camera_id", None)` default raises on this entity; shipped treats the
    # match as same-camera. Also red under 148 (0.88 * 101 renders 89%).
    matches = {"4": [_match(_entity(attributes={}), 0.88, 5400.0)]}
    assert _build_tracking_narratives(matches, "Person", None, None) == [
        "- Person (detection 4): Previously seen on this same camera 1.5 hours ago "
        "(88% similarity). No cross-camera movement."
    ]


def test_narratives_cross_camera_entity_without_attributes_uses_empty_attrs() -> None:
    # sole killer of mutmut_61: the entity has no `attributes` attribute, so
    # the 2-arg `getattr(match_entity, "attributes", )` raises while shipped's
    # `{}` (and the `None or {}` variant) render no attribute tail. Also red
    # under 88/91/92/93 and 134/135/137 (this is a cross-camera match with
    # exactly one other camera).
    matches = {"3": [_match(_entity(camera_id="gate_cam"), 0.8, 90.0)]}
    assert _build_tracking_narratives(matches, "Person", "side_yard", None) == [
        '- Person (detection 3): SAME PERSON seen on "gate_cam" camera '
        "1 minutes ago (80% similarity). Movement pattern: moved from gate_cam "
        "to side_yard, in rapid succession."
    ]


def test_narratives_zone_without_zone_type_renders_name_alone() -> None:
    # sole killer of mutmut_108 (deleted `getattr(zc, "zone_type", None)`
    # default raises on "Open Lawn") and 113 (`if ztype or True` renders
    # "Open Lawn (None)"); also the only zone-shape red for 116 (the ", "
    # location joiner) and 121 (zone_context -> None drops the entry-point
    # clause shipped renders here).
    zones = [_zone("Patio", "entry_point"), SimpleNamespace(zone_name="Open Lawn")]
    matches = {"7": [_match(_entity(camera_id="back_yard", attributes={}), 0.826, 90.0)]}
    assert _build_tracking_narratives(matches, "Person", "front_door", zones) == [
        '- Person (detection 7): SAME PERSON seen on "back_yard" camera '
        "1 minutes ago (83% similarity). Current location: Patio (entry_point), "
        "Open Lawn. Movement pattern: moved from back_yard to front_door, in "
        "rapid succession, now at entry point (approaching property access)."
    ]


def test_narratives_zone_without_zone_name_is_skipped() -> None:
    # sole killer of mutmut_100: the second zone has no `zone_name`
    # attribute, so the deleted `getattr(zc, "zone_name", None)` default
    # raises there; shipped skips it and lists exactly one location.
    zones = [_zone("Front Walk", "entry_point"), SimpleNamespace(zone_type="yard")]
    matches = {"7": [_match(_entity(camera_id="back_yard", attributes={}), 0.826, 90.0)]}
    assert _build_tracking_narratives(matches, "Person", "front_door", zones) == [
        '- Person (detection 7): SAME PERSON seen on "back_yard" camera '
        "1 minutes ago (83% similarity). Current location: Front Walk "
        "(entry_point). Movement pattern: moved from back_yard to front_door, in "
        "rapid succession, now at entry point (approaching property access)."
    ]


def test_narratives_all_zone_names_falsy_omits_location_clause() -> None:
    # A zone list whose names are all falsy keeps `zone_str` at its initial
    # value: `zone_str = None` (92) raises in the f-string join and
    # `zone_str = "XXXX"` (93) appends the sentinel, while the movement tail
    # still carries the entry-point clause (so 118-121/127/128 are red here
    # too, alongside 88/91 and 134/135/137).
    zones = [SimpleNamespace(zone_name="", zone_type="entry_point")]
    matches = {"7": [_match(_entity(camera_id="back_yard", attributes={}), 0.826, 90.0)]}
    assert _build_tracking_narratives(matches, "Person", "front_door", zones) == [
        '- Person (detection 7): SAME PERSON seen on "back_yard" camera '
        "1 minutes ago (83% similarity). Movement pattern: moved from back_yard "
        "to front_door, in rapid succession, now at entry point (approaching "
        "property access)."
    ]


# ---------------------------------------------------------------------------
# format_cross_camera_person_tracking — header / labels / guidance assembly
# ---------------------------------------------------------------------------


def test_cross_camera_no_data_message_exact() -> None:
    # sole killer of mutmut_29 (the `"XX...XX"`-wrapped no-tracking sentinel)
    assert format_cross_camera_person_tracking(None) == (
        "Cross-camera person tracking: No cross-camera movement detected."
    )


def test_cross_camera_person_narrative_exact() -> None:
    # Kills 12/13 (the "Person" label -> "person"/"PERSON" changes the
    # "- <label> (detection 42)" prefix), 33 (header XX-wrap), and 37/38/39
    # (the guidance block's XX-wrap / lowercase / uppercase variants).
    matches = {"42": [_match(_entity(camera_id="back_yard", attributes={}), 0.826, 90.0)]}
    assert format_cross_camera_person_tracking(matches, None, "front_door", None) == "\n".join(
        [
            "## Cross-Camera Person Tracking",
            '- Person (detection 42): SAME PERSON seen on "back_yard" camera '
            "1 minutes ago (83% similarity). Movement pattern: moved from "
            "back_yard to front_door, in rapid succession.",
            "",
            "Cross-camera tracking context: A person moving from property "
            "perimeter toward an entry point is more concerning than someone "
            "passing through. Multiple camera sightings of the same unknown "
            "person suggest deliberate movement through the property.",
        ]
    )


def test_cross_camera_person_and_vehicle_sections_exact() -> None:
    # Two narratives pin the "\n" joiner — sole killer of mutmut_43
    # (`"XX\nXX".join`) — and of 19 (the vehicle call's `zone_context` -> None
    # strips the vehicle line's Current location clause while the person line
    # keeps its own) and 25/26 (the "Vehicle" label -> "vehicle"/"VEHICLE").
    # 12/13/33/37/38/39 are red here as well.
    person = {"42": [_match(_entity(camera_id="back_yard", attributes={}), 0.826, 90.0)]}
    vehicle = {"v7": [_match(_entity(camera_id="street", attributes={}), 0.8734, 130.0)]}
    zones = [_zone("Front Walk", "entry_point")]
    assert format_cross_camera_person_tracking(person, vehicle, "front_door", zones) == "\n".join(
        [
            "## Cross-Camera Person Tracking",
            '- Person (detection 42): SAME PERSON seen on "back_yard" camera '
            "1 minutes ago (83% similarity). Current location: Front Walk "
            "(entry_point). Movement pattern: moved from back_yard to front_door, "
            "in rapid succession, now at entry point (approaching property access).",
            '- Vehicle (detection v7): SAME VEHICLE seen on "street" camera '
            "2 minutes ago (87% similarity). Current location: Front Walk "
            "(entry_point). Movement pattern: moved from street to front_door, "
            "over 2 minutes, now at entry point (approaching property access).",
            "",
            "Cross-camera tracking context: A person moving from property "
            "perimeter toward an entry point is more concerning than someone "
            "passing through. Multiple camera sightings of the same unknown "
            "person suggest deliberate movement through the property.",
        ]
    )


# ---------------------------------------------------------------------------
# EQUIVALENCE LEDGER — the 12 lane-e keys this battery does not kill (and why
# no assert can). Each was fuzzed (1116 input configurations x 4 functions)
# against shipped with the exact edit applied: zero observable difference.
#
#   _infer_movement_pattern__mutmut_5   `has_entry_point = False` -> `None`:
#       only ever read by `if has_entry_point`, and it is REASSIGNED to True
#       inside the zone loop whenever an entry_point zone exists.
#   _infer_movement_pattern__mutmut_11  `getattr(zc, "zone_type", "")` ->
#       `None`: both falsy, so `ztype == "entry_point"` and the
#       `"driveway"/"yard" in current_zone_types` membership folds agree;
#       None "" "XXXX" never equal a zone-type literal, and a zone_type that
#       IS a literal is an attribute that exists (default unused).
#   _infer_movement_pattern__mutmut_17  same default -> `"XXXX"`: same fold.
#   _infer_movement_pattern__mutmut_56  `if parts or True`: `parts` already
#       got a `parts.append(...)` two statements above, so it is always
#       truthy whenever the return runs — the else arm is unreachable.
#   _infer_movement_pattern__mutmut_59  else arm `""` -> `"XXXX"`: same
#       unreachable arm.
#   _build_tracking_narratives__mutmut_46/49  `getattr(match_entity,
#       "camera_id", "unknown camera")` -> None / deleted default: on the
#       cross-camera branch the SAME shipped line 2910 already required
#       `match_camera` truthy for the match to qualify, so the L2931 default
#       is never consulted (49 raising on a missing camera_id likewise can
#       never be reached with a cross-camera match).
#   _build_tracking_narratives__mutmut_52/53  that default ->
#       "XXunknown cameraXX" / "UNKNOWN CAMERA": dead for the same reason.
#   _build_tracking_narratives__mutmut_58  `getattr(..., "attributes", {})` ->
#       `None`: the trailing `or {}` absorbs it exactly.
#   _build_tracking_narratives__mutmut_129  `if movement or True`: the only
#       caller passes a zone_context whose truthiness implies movement != ""
#       (the L3032 previous/current camera guard fires only when a camera id
#       is missing, which the same L2912 gate already excluded), so the arm is
#       always taken with a non-empty movement.
#   _build_tracking_narratives__mutmut_130  else arm `""` -> `"XXXX"`: same
#       unreachable arm.
# ---------------------------------------------------------------------------
