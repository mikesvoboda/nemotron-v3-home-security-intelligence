# TARGET-MODULE: backend.services.prompts
"""Batch-30 kill battery (fragment C): prompts.py detection-view renderers.

Scope — the 106 surviving mutant keys triaged for
``_collect_detection_ids_from_enrichment`` (56),
``format_detections_with_all_enrichment`` (49) and
``format_ondemand_enrichment_context`` (1).

Method. ``_collect_detection_ids_from_enrichment`` unions six
``getattr(result, "<field>", {}) or {}`` sources plus two Florence-2 sources, so
it is attacked from both sides: a fixture where EVERY source carries ids (a
field-name swap, a ``getattr(None, ...)`` blinding or a label swap then changes
the returned mapping), and a fixture where the sources are ABSENT from the
object (``types.SimpleNamespace()``) so the ``getattr(x, "f", )`` family — which
silently drops the third argument — raises ``AttributeError`` instead of falling
back to ``{}``. ``format_detections_with_all_enrichment`` is attacked with exact
whole-string equality on the rendered per-detection block: synthesized
detections, the ``UNKNOWN``/0%/``[]`` default row, quality tiers at their exact
tier values, garbage-VQA filtering, and every enrichment line
(``**SUSPICIOUS**``, ``**HIGH SECURITY**``, the pet confirmation tail, the
Scene OCR tail). The mutual-exclusion tail additionally feeds a real
``coverage_percentages`` conflict so the ``getattr(seg, "coverage_percentages",
...)`` family changes the emitted garment instead of silently returning ``{}``.

Honesty ledger — the 15 keys that are NOT killed, each proven EQUIVALENT by
construction (mutation-verified: the battery is green with every other edit
applied and these 15 survive even against crafted discriminating inputs):

* ``getattr(x, "field", {}) or {}`` -> ``getattr(x, "field", None) or {}``
  (collect mutmut_5/17/29/38/47/60, format mutmut_153): the trailing ``or {}``
  already normalises ``None``, so both spellings evaluate to ``{}`` for a
  present attribute and for a missing one — no input can separate them.
* The synthesized-detection key renames (format mutmut_15/16/18/19:
  ``"confidence"`` -> ``"XXconfidenceXX"``/``"CONFIDENCE"``, ``"bbox"`` ->
  ``"XXbboxXX"``/``"BBOX"``): the only reader of a synthesized dict is the same
  loop's ``det.get("confidence", 0.0)`` / ``det.get("bbox", [])``, whose
  defaults are value-identical to the stored ``0.0`` / ``[]``, so dropping the
  key is invisible. mutmut_17 (``confidence: 1.0``) is the control that proves
  the key IS read.
* ``det.get("object_type", "unknown")`` -> ``"UNKNOWN"`` (format mutmut_54):
  the shipped ``class_name.upper()`` erases the case change; the
  ``"XXunknownXX"`` sibling (mutmut_53) is killed, which proves the default is
  reached.
* ``bbox = det.get("bbox", [])`` -> ``None`` / dropped default (format
  mutmut_67/69): ``bbox``'s only consumer is ``... if bbox else "[]"`` and
  ``[]``/``None`` are both falsy, so the render is identical. The
  ``if (bbox) or True`` flip (mutmut_85) is killed by an explicit
  ``"bbox": None`` row, which is the discriminating input for that guard.
* ``if sections else ""`` -> ``if (sections) or True else ""`` (ondemand
  mutmut_24): ``"\\n\\n".join([]) == ""``, so the dead ``else`` arm is
  value-identical to the taken arm.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

# This fragment lives OUTSIDE the repo tree (/home/agent/runs/b30-frags), so
# pytest gives it no sys.path entry for the repo. The harness always invokes it
# with the repo root (or the mutant home) as cwd, and the batch-30 sweep helper
# inserts cwd itself — mirror that so the imports below resolve in both worlds.
_ROOT = os.getcwd()
if os.path.isfile(os.path.join(_ROOT, "backend", "services", "prompts.py")):
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.services import prompts as prompts_module  # noqa: E402
from backend.services.prompts import (  # noqa: E402
    _collect_detection_ids_from_enrichment,
    format_detections_with_all_enrichment,
    format_ondemand_enrichment_context,
)


# ---------------------------------------------------------------------------
# _collect_detection_ids_from_enrichment — all-sources union
# ---------------------------------------------------------------------------
def _full_enrichment() -> SimpleNamespace:
    """Enrichment object with an id in every one of the six sources."""
    return SimpleNamespace(
        clothing_classifications={"cc-1": {}},
        clothing_segmentation={"cs-1": {}},
        pose_results={"pose-1": {}},
        vehicle_classifications={"vc-1": {}},
        vehicle_damage={"vd-1": {}},
        pet_classifications={"pet-1": SimpleNamespace(animal_type="dog")},
    )


def test_collect_maps_every_source_to_its_inferred_class():
    # Field-name swaps (mutmut_21/22 clothing_segmentation, 33/34 pose_results,
    # 42/43 vehicle_classifications), the ``getattr(None, ...)`` blinding
    # (15/27/36/45/58), the ``or``->``and`` flips (14/26/35/44/57), the
    # ``getattr(obj, None, ...)`` / ``getattr("literal", {})`` type errors
    # (46/48/61/70/71), the pet deref chain (66/67/68/69), the ``pet_
    # classifications = None`` drop (56) and every label swap
    # (13/23/24/25/53/54/55/75/76/77/78) all move this mapping.
    result = _collect_detection_ids_from_enrichment(_full_enrichment(), None)
    assert result == {
        "cc-1": "person",
        "cs-1": "person",
        "pose-1": "person",
        "vc-1": "vehicle",
        "vd-1": "vehicle",
        "pet-1": "dog",
    }


def test_collect_pet_without_animal_type_uses_animal_label():
    # ``animal_type or "animal"`` tail: the "XXanimalXX"/"ANIMAL" swaps
    # (mutmut_77/78) only surface when animal_type is falsy, and mutmut_75
    # (``= None``) drops the key entirely.
    enrichment = SimpleNamespace(pet_classifications={"pet-9": SimpleNamespace()})
    assert _collect_detection_ids_from_enrichment(enrichment, None) == {"pet-9": "animal"}


def test_collect_pet_truthy_animal_type_wins_over_fallback():
    # Complement of the fallback test: mutmut_76 (``or`` -> ``and``) renders
    # "animal" for a real animal_type, mutmut_67/68/69 (animal_type = None /
    # getattr(None, ...) / getattr(pet, None, ...)) likewise collapse to
    # "animal" instead of "cat".
    enrichment = SimpleNamespace(pet_classifications={"pet-3": SimpleNamespace(animal_type="cat")})
    assert _collect_detection_ids_from_enrichment(enrichment, None) == {"pet-3": "cat"}


# ---------------------------------------------------------------------------
# _collect_detection_ids_from_enrichment — Florence-2 sources
# ---------------------------------------------------------------------------
def test_collect_vision_person_attributes_when_enrichment_absent():
    # person_attributes loop only: mutmut_79 (``or`` -> ``and``) and mutmut_80
    # (``getattr(None, ...)``) empty the source, mutmut_81
    # (``getattr(vision, None, {})``) raises TypeError, and mutmut_88
    # (``if det_id not in`` -> ``in``) suppresses every insert because the
    # mapping is still empty here.
    vision = SimpleNamespace(person_attributes={"vp-1": {}, "vp-2": {}})
    assert _collect_detection_ids_from_enrichment(None, vision) == {
        "vp-1": "person",
        "vp-2": "person",
    }


def test_collect_vision_vehicle_attributes_when_enrichment_absent():
    # vehicle_attributes loop only: mutmut_94 (``getattr(vision, None, {})``
    # -> TypeError) and mutmut_101 (the inverted membership guard that only
    # inserts ids ALREADY present, so an empty map stays empty).
    vision = SimpleNamespace(vehicle_attributes={"vv-1": {}})
    assert _collect_detection_ids_from_enrichment(None, vision) == {"vv-1": "vehicle"}


def test_collect_enrichment_class_beats_vision_class_for_shared_id():
    # The precedence guard: with an id present in enrichment AND in both vision
    # maps, mutmut_88/101 (``not in`` -> ``in``) delete "vd-shared" and drop
    # every vision-only id, and the vision-source blinding/emptiness mutants
    # (80/94) lose "vp-only"/"vv-only".
    enrichment = SimpleNamespace(vehicle_damage={"vd-shared": {}})
    vision = SimpleNamespace(
        person_attributes={"vd-shared": {}, "vp-only": {}},
        vehicle_attributes={"vd-shared": {}, "vv-only": {}},
    )
    assert _collect_detection_ids_from_enrichment(enrichment, vision) == {
        "vd-shared": "vehicle",
        "vp-only": "person",
        "vv-only": "vehicle",
    }


# ---------------------------------------------------------------------------
# _collect_detection_ids_from_enrichment — missing attributes hit the defaults
# ---------------------------------------------------------------------------
def test_collect_bare_objects_default_every_source_to_empty():
    # The discriminating input for the ``getattr(x, "field", )`` family
    # (mutmut_8/20/41/50/63 enrichment side, 85/98 vision side): dropping the
    # third argument silently becomes the two-argument form, so it raises
    # AttributeError the moment the attribute is ABSENT — which is exactly what
    # the shipped ``{}`` default exists to absorb. The vision
    # ``getattr(vision, None, ...)`` TypeErrors (81/94), the
    # ``getattr(enrichment_result, None, ...)`` TypeError (46) and the
    # string-as-object shapes (48/61) also blow up here instead of returning {}.
    assert _collect_detection_ids_from_enrichment(SimpleNamespace(), SimpleNamespace()) == {}


def test_collect_bare_enrichment_object_only_iterates_nothing():
    # Same default-absorbing path with vision_extraction falsy (the shipped
    # ``if enrichment_result:`` / ``if vision_extraction:`` guards stay live),
    # and mutmut_56/61 (``pet_classifications = None`` /
    # ``getattr("pet_classifications", {})``) still fail instead.
    assert _collect_detection_ids_from_enrichment(SimpleNamespace(), None) == {}


# ---------------------------------------------------------------------------
# format_detections_with_all_enrichment — guards and synthesized detections
# ---------------------------------------------------------------------------
def test_format_no_detections_anywhere_returns_sentinel():
    # The empty-guard tail the synth block is written around; also the anchor
    # that keeps the synth-gate test honest (mutmut_8).
    assert format_detections_with_all_enrichment([], None, None) == "No detections in this batch."


def test_format_synthesizes_detections_from_enrichment_ids():
    # The synthesized rows must read confidence 0.0 / bbox [] and take their
    # class from the inferred mapping (DOG for the pet id, PERSON for the
    # clothing id): mutmut_17 (stored confidence 1.0) renders
    # "100% EXCELLENT", mutmut_74/76 (``>= 0`` / ``or True``) light a quality
    # tier on the 0% rows, mutmut_204 (``XX\nXX`` join) collapses the block and
    # mutmut_189 (pet ``not in``) raises KeyError on "det-q". NOTE the key
    # RENAMES mutmut_15/16/18/19 are NOT killed here or anywhere — see the
    # ledger: the consumer's ``det.get`` default is value-identical to the
    # stored 0.0/[].
    out = format_detections_with_all_enrichment(
        [],
        SimpleNamespace(
            clothing_classifications={
                "det-p": SimpleNamespace(
                    raw_description="dark hoodie",
                    confidence=0.42,
                    is_suspicious=False,
                    is_service_uniform=False,
                )
            },
            clothing_segmentation={},
            pose_results={},
            vehicle_classifications={},
            vehicle_damage={},
            pet_classifications={"det-q": SimpleNamespace(animal_type="dog", confidence=0.5)},
            scene_ocr=None,
        ),
        None,
    )
    assert out == (
        "### PERSON (ID: det-p)\n"
        "Confidence: 0%, Location: []\n"
        "Attire: dark hoodie (42%)\n"
        "\n"
        "### DOG (ID: det-q)\n"
        "Confidence: 0%, Location: []\n"
        "Pet: dog (50%)"
    )


# ---------------------------------------------------------------------------
# format_detections_with_all_enrichment — base row defaults
# ---------------------------------------------------------------------------
def test_format_bare_detection_falls_back_to_unknown_defaults():
    # Key-ABSENT row: mutmut_34/36/39 (the ``det.get("id", <default>)``
    # variants render "None"/""/"XXXX" once BOTH id keys are missing),
    # mutmut_48/50 (``object_type`` default None) render an empty class,
    # mutmut_53 ("XXunknownXX") swaps the header, mutmut_64 (confidence
    # default 1.0) renders "100% EXCELLENT", mutmut_74/76 light up a quality
    # tier on the 0% row and mutmut_82 (``else "XXXX"``) appends XXXX after the
    # percentage. mutmut_54 ("UNKNOWN") is the ledger's case-swap EQUIVALENT.
    assert format_detections_with_all_enrichment([{}]) == (
        "### UNKNOWN (ID: )\nConfidence: 0%, Location: []"
    )


def test_format_uses_id_key_when_detection_id_absent():
    # Key-PRESENT row: proves the ``detection_id`` -> ``id`` fallback chain is
    # live, which is what makes mutmut_34/36 (the ``id`` default swaps)
    # unreachable rather than merely untested.
    out = format_detections_with_all_enrichment([{"id": "alt-9", "class_name": "person"}])
    assert out == "### PERSON (ID: alt-9)\nConfidence: 0%, Location: []"


def test_format_object_type_key_is_the_class_name_fallback():
    # class_name absent / object_type present: the shipped code must read the
    # fallback key and upper-case the result via ``class_name.upper()``. This
    # row cannot reach the ``"unknown"`` default (object_type is present), so
    # the default mutants (48/50/53) are decided by the key-ABSENT row above;
    # this one anchors the fallback key itself plus the sanitizer/upper-case
    # contract that mutmut_54's "UNKNOWN" swap cannot cross.
    out = format_detections_with_all_enrichment(
        [{"detection_id": "d2", "object_type": "delivery van"}]
    )
    assert out == "### DELIVERY VAN (ID: d2)\nConfidence: 0%, Location: []"


# ---------------------------------------------------------------------------
# format_detections_with_all_enrichment — confidence quality + bbox
# ---------------------------------------------------------------------------
def test_format_confidence_quality_tiers_render_uppercased():
    # mutmut_72/73 (``quality_tier = None`` / ``and False``) drop the tier,
    # mutmut_79 (``if (quality_tier) and False``) drops the label, mutmut_81
    # (``.value.lower()``) renders " excellent" and mutmut_77
    # (``if confidence > 1``) nulls the tier for every in-range score.
    out = format_detections_with_all_enrichment(
        [
            {
                "detection_id": "q-1",
                "class_name": "person",
                "confidence": 0.95,
                "bbox": [10, 20, 30, 40],
            }
        ]
    )
    assert out == "### PERSON (ID: q-1)\nConfidence: 95% EXCELLENT, Location: [10, 20, 30, 40]"


def test_format_marginal_and_good_tiers_are_exact():
    # Tier VALUES (not just presence): a MODERATE -> GOOD label swap or a
    # boundary shift changes these two rows, and mutmut_74/76 (``or True`` /
    # ``>= 0``) would light up a tier on the 0% row asserted elsewhere.
    out = format_detections_with_all_enrichment(
        [
            {
                "detection_id": "q-2",
                "class_name": "person",
                "confidence": 0.65,
                "bbox": [1, 2, 3, 4],
            },
            {
                "detection_id": "q-3",
                "class_name": "person",
                "confidence": 0.75,
                "bbox": [5, 6, 7, 8],
            },
        ]
    )
    assert out == (
        "### PERSON (ID: q-2)\nConfidence: 65% MODERATE, Location: [1, 2, 3, 4]\n"
        "\n"
        "### PERSON (ID: q-3)\nConfidence: 75% GOOD, Location: [5, 6, 7, 8]"
    )


def test_format_bbox_members_render_as_truncated_ints():
    # ``str(int(b))`` is part of the contract: a float-filled box must render
    # as truncated ints, so the whole row (and its EXCELLENT label) dies to the
    # quality-tier mutants mutmut_72/73/77/78/79/81 — an int-filled box would
    # mask nothing here, but floats prove ``int()`` is applied rather than
    # ``str()``. (The bbox DEFAULT mutants 67/69 are ledger equivalents; the
    # ``if bbox`` guard flip 85 needs the None-bbox row below.)
    out = format_detections_with_all_enrichment(
        [
            {
                "detection_id": "b1",
                "class_name": "car",
                "confidence": 0.95,
                "bbox": [10.7, 20.2, 30.9, 40.1],
            }
        ]
    )
    assert out == "### CAR (ID: b1)\nConfidence: 95% EXCELLENT, Location: [10, 20, 30, 40]"


def test_format_none_bbox_renders_empty_brackets():
    # An explicit ``"bbox": None`` (the serialized "no box" shape) keeps the
    # ``if bbox else "[]"`` truthiness guard load-bearing: mutmut_85
    # (``if (bbox) or True``) takes the formatting branch anyway and raises
    # TypeError iterating None, while the shipped code short-circuits to "[]".
    out = format_detections_with_all_enrichment(
        [{"detection_id": "n1", "class_name": "person", "bbox": None}]
    )
    assert out == "### PERSON (ID: n1)\nConfidence: 0%, Location: []"


# ---------------------------------------------------------------------------
# format_detections_with_all_enrichment — Florence-2 vehicle branch
# ---------------------------------------------------------------------------
def _vehicle_vision(det_id: str, attrs: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        vehicle_attributes={det_id: attrs}, person_attributes={}, florence_enhanced=None
    )


def test_format_florence_vehicle_drops_garbage_vqa_fields():
    # color="<loc_1>" and commercial_text="<pad>" are invalid VQA: mutmut_108
    # (``and`` -> ``or``) and mutmut_109 (``is_valid_vqa_output(None)``) both
    # let " (<pad>)" into the commercial tail, mutmut_105 swaps the
    # "Commercial vehicle" label and mutmut_115 joins with "XX, XX".
    out = format_detections_with_all_enrichment(
        [{"detection_id": "v1", "class_name": "car", "confidence": 0.95, "bbox": [0, 0, 5, 5]}],
        None,
        _vehicle_vision(
            "v1",
            SimpleNamespace(
                color="<loc_1>",
                vehicle_type="van",
                is_commercial=True,
                commercial_text="<pad>",
                caption="A delivery van stopped at a driveway",
            ),
        ),
    )
    assert out == (
        "### CAR (ID: v1)\n"
        "Confidence: 95% EXCELLENT, Location: [0, 0, 5, 5]\n"
        "Florence-2: Type: van, Commercial vehicle\n"
        "Description: A delivery van stopped at a driveway"
    )


def test_format_florence_vehicle_commercial_label_without_text():
    # Single attr_part: kills the ``if attr_parts:`` emptiness flips and keeps
    # the "Commercial vehicle" label anchored on its own (mutmut_105).
    out = format_detections_with_all_enrichment(
        [{"detection_id": "v1", "class_name": "car", "confidence": 0.95, "bbox": [0, 0, 5, 5]}],
        None,
        _vehicle_vision(
            "v1",
            SimpleNamespace(
                color=None, vehicle_type="", is_commercial=True, commercial_text="", caption=""
            ),
        ),
    )
    assert out == (
        "### CAR (ID: v1)\n"
        "Confidence: 95% EXCELLENT, Location: [0, 0, 5, 5]\n"
        "Florence-2: Commercial vehicle"
    )


def test_format_florence_vehicle_all_valid_attributes_in_order():
    # All-valid path: the ", " join (mutmut_115) and the
    # ``commercial += f" ({text})"`` tail both need at least two parts to be
    # observable, and the attribute ORDER is part of the contract.
    out = format_detections_with_all_enrichment(
        [{"detection_id": "v1", "class_name": "car", "confidence": 0.95, "bbox": [0, 0, 5, 5]}],
        None,
        _vehicle_vision(
            "v1",
            SimpleNamespace(
                color="white",
                vehicle_type="box truck",
                is_commercial=True,
                commercial_text="FedEx",
                caption="",
            ),
        ),
    )
    assert out == (
        "### CAR (ID: v1)\n"
        "Confidence: 95% EXCELLENT, Location: [0, 0, 5, 5]\n"
        "Florence-2: Color: white, Type: box truck, Commercial vehicle (FedEx)"
    )


# ---------------------------------------------------------------------------
# format_detections_with_all_enrichment — Florence-2 person branch
# ---------------------------------------------------------------------------
def _person_vision(det_id: str, attrs: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        vehicle_attributes={}, person_attributes={det_id: attrs}, florence_enhanced=None
    )


def test_format_florence_person_service_worker_and_join():
    # clothing/carrying are garbage tokens, so the parts left are
    # "Action: walking" + "Service worker": mutmut_130 swaps the "Service
    # worker" literal, mutmut_135 swaps the ", " join, mutmut_124
    # (``is_valid_vqa_output(None)``) admits the garbage carrying token and
    # the GOOD-quality header row carries the quality-label kills (78/79/81).
    out = format_detections_with_all_enrichment(
        [{"detection_id": "p1", "class_name": "person", "confidence": 0.8, "bbox": [1, 1, 2, 2]}],
        None,
        _person_vision(
            "p1",
            SimpleNamespace(
                clothing="<pad>",
                carrying="<pad>",
                action="walking",
                is_service_worker=True,
                caption="A person near the door",
            ),
        ),
    )
    assert out == (
        "### PERSON (ID: p1)\n"
        "Confidence: 80% GOOD, Location: [1, 1, 2, 2]\n"
        "Florence-2: Action: walking, Service worker\n"
        "Description: A person near the door"
    )


def test_format_florence_person_with_no_valid_parts_emits_caption_only():
    # Every part falsy/invalid: mutmut_123 (``p_attrs.carrying or
    # is_valid_vqa_output(...)``) turns the None carrying into a literal
    # "Carrying: None" line, while the shipped short-circuit emits no
    # "Florence-2:" prefix at all.
    out = format_detections_with_all_enrichment(
        [{"detection_id": "p2", "class_name": "person", "confidence": 0.5, "bbox": [4, 5, 6, 7]}],
        None,
        _person_vision(
            "p2",
            SimpleNamespace(
                clothing=None,
                carrying=None,
                action="<loc_7>",
                is_service_worker=False,
                caption="A person near the door",
            ),
        ),
    )
    assert out == (
        "### PERSON (ID: p2)\n"
        "Confidence: 50% MARGINAL, Location: [4, 5, 6, 7]\n"
        "Description: A person near the door"
    )


def test_format_florence_enhanced_region_and_security_vqa():
    # florence_enhanced block: the region-detail and security-VQA lines (their
    # labels, the "; " join and the ``question.rstrip("?").split("?")[0]``
    # abbreviation that strips the trailing "?"), the MARGINAL tier label and
    # the ``XX\nXX`` join (mutmut_204).
    out = format_detections_with_all_enrichment(
        [{"detection_id": "e1", "class_name": "person", "confidence": 0.5, "bbox": [3, 4, 5, 6]}],
        None,
        SimpleNamespace(
            vehicle_attributes={},
            person_attributes={},
            florence_enhanced=SimpleNamespace(
                region_descriptions={"e1": "Person in dark jacket holding a package"},
                security_vqa={
                    "e1": {
                        "Is the person carrying a package?": "Yes",
                        "Do they have a face covering?": "No",
                    }
                },
            ),
        ),
    )
    assert out == (
        "### PERSON (ID: e1)\n"
        "Confidence: 50% MARGINAL, Location: [3, 4, 5, 6]\n"
        "Region detail: Person in dark jacket holding a package\n"
        "Security VQA: Is the person carrying a package: Yes; Do they have a face covering: No"
    )


# ---------------------------------------------------------------------------
# format_detections_with_all_enrichment — enrichment pipeline block
# ---------------------------------------------------------------------------
def test_format_clothing_enrichment_block_with_conflict_and_alerts():
    # Real detections + non-empty enrichment ids: mutmut_8 (``and`` -> ``or``
    # in the synth gate) appends two duplicate synthesized blocks, mutmut_142
    # swaps " **SUSPICIOUS**", mutmut_170/174 swap the face-covering and bag
    # lines, mutmut_204 (``XX\nXX`` join) collapses the rows, and the
    # coverage_percentages family (149/150/151/157/158/161) is decided here:
    # jeans (80) must beat pants (20) under mutual exclusion, so a
    # ``getattr(seg, "COVERAGE_PERCENTAGES", {})`` field swap (157/158), the
    # ``or``->``and`` flip (150) and the ``getattr(None, ...)`` blinding (151)
    # all leave confidences empty and let PANTS win instead; ``= None`` (149)
    # and the ``validate_clothing_items(raw, None)`` swap (161) raise TypeError
    # inside the validator. mutmut_153 (``{}`` -> ``None`` default) is the
    # ledger's ``or {}`` EQUIVALENT.
    enrichment = SimpleNamespace(
        clothing_classifications={
            "e0": SimpleNamespace(
                raw_description="dark hoodie and jeans",
                confidence=0.83,
                is_suspicious=True,
                is_service_uniform=False,
            ),
            "e1": SimpleNamespace(
                raw_description="dark hoodie and jeans",
                confidence=0.83,
                is_suspicious=True,
                is_service_uniform=False,
            ),
        },
        clothing_segmentation={
            "e0": SimpleNamespace(clothing_items=[], has_face_covered=False, has_bag=False),
            "e1": SimpleNamespace(
                clothing_items=["pants", "jeans", "hat"],
                coverage_percentages={"jeans": 80.0, "pants": 20.0},
                has_face_covered=True,
                has_bag=True,
            ),
        },
        pose_results={},
        vehicle_classifications={},
        vehicle_damage={},
        pet_classifications={},
        scene_ocr=None,
    )
    out = format_detections_with_all_enrichment(
        [
            {"detection_id": "e0", "class_name": "person"},
            {"detection_id": "e1", "class_name": "person", "confidence": 0.4, "bbox": [3, 4, 5, 6]},
        ],
        enrichment,
        None,
    )
    assert out == (
        "### PERSON (ID: e0)\n"
        "Confidence: 0%, Location: []\n"
        "Attire: dark hoodie and jeans (83%) **SUSPICIOUS**\n"
        "\n"
        "### PERSON (ID: e1)\n"
        "Confidence: 40% MARGINAL, Location: [3, 4, 5, 6]\n"
        "Attire: dark hoodie and jeans (83%) **SUSPICIOUS**\n"
        "Clothing items: hat, jeans\n"
        "Face covering: DETECTED **ALERT**\n"
        "Bag/backpack: Detected"
    )


def test_format_clothing_service_uniform_branch():
    # The ``elif clothing.is_service_uniform`` arm: a suspicious/uniform flag
    # flip moves the row between " **SUSPICIOUS**" and " [Service uniform]".
    enrichment = SimpleNamespace(
        clothing_classifications={
            "u": SimpleNamespace(
                raw_description="hi-vis vest",
                confidence=0.71,
                is_suspicious=False,
                is_service_uniform=True,
            )
        },
        clothing_segmentation={},
        pose_results={},
        vehicle_classifications={},
        vehicle_damage={},
        pet_classifications={},
        scene_ocr=None,
    )
    out = format_detections_with_all_enrichment(
        [{"detection_id": "u", "class_name": "person"}], enrichment, None
    )
    assert out == (
        "### PERSON (ID: u)\n"
        "Confidence: 0%, Location: []\n"
        "Attire: hi-vis vest (71%) [Service uniform]"
    )


def test_format_vehicle_damage_high_security_tail():
    # mutmut_185 (``damage_line +=`` -> ``-=``) raises TypeError on str
    # subtraction, and the commercial flag / high-security flag flips change
    # the emitted suffixes.
    enrichment = SimpleNamespace(
        clothing_classifications={},
        clothing_segmentation={},
        pose_results={},
        vehicle_classifications={
            "vd": SimpleNamespace(display_name="Sedan", confidence=0.78, is_commercial=False)
        },
        vehicle_damage={
            "vd": SimpleNamespace(
                has_damage=True,
                damage_types=["broken_window", "dent"],
                has_high_security_damage=True,
            )
        },
        pet_classifications={},
        scene_ocr=None,
    )
    out = format_detections_with_all_enrichment(
        [{"detection_id": "vd", "class_name": "car", "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
        enrichment,
        None,
    )
    assert out == (
        "### CAR (ID: vd)\n"
        "Confidence: 90% EXCELLENT, Location: [0, 0, 1, 1]\n"
        "Vehicle type: Sedan (78%)\n"
        "Damage: broken_window, dent **HIGH SECURITY**"
    )


def test_format_vehicle_damage_omitted_and_low_security_variants():
    # has_damage=False suppresses the row entirely and
    # has_high_security_damage=False drops only the tail: the emptiness flips
    # and the ``if damage.has_damage`` inversion both surface here.
    enrichment = SimpleNamespace(
        clothing_classifications={},
        clothing_segmentation={},
        pose_results={},
        vehicle_classifications={},
        vehicle_damage={
            "quiet": SimpleNamespace(
                has_damage=False, damage_types=[], has_high_security_damage=True
            )
        },
        pet_classifications={},
        scene_ocr=None,
    )
    out = format_detections_with_all_enrichment(
        [{"detection_id": "quiet", "class_name": "car"}], enrichment, None
    )
    assert out == "### CAR (ID: quiet)\nConfidence: 0%, Location: []"

    low_security = SimpleNamespace(
        clothing_classifications={},
        clothing_segmentation={},
        pose_results={},
        vehicle_classifications={
            "vd": SimpleNamespace(display_name="Sedan", confidence=0.78, is_commercial=True)
        },
        vehicle_damage={
            "vd": SimpleNamespace(
                has_damage=True, damage_types=["scratch"], has_high_security_damage=False
            )
        },
        pet_classifications={},
        scene_ocr=None,
    )
    out2 = format_detections_with_all_enrichment(
        [{"detection_id": "vd", "class_name": "car", "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
        low_security,
        None,
    )
    assert out2 == (
        "### CAR (ID: vd)\n"
        "Confidence: 90% EXCELLENT, Location: [0, 0, 1, 1]\n"
        "Vehicle type: Sedan (78%) [Commercial]\n"
        "Damage: scratch"
    )


def test_format_pet_confirmation_threshold_and_appended_line():
    # mutmut_189 (``if det_id not in pet_classifications``) raises KeyError for
    # every id absent from the map, mutmut_195 (``pet_line +=`` -> ``-=``)
    # raises TypeError on the confirmed pet and mutmut_199
    # (``lines.append(None)``) breaks the "\n".join — all three need a pet
    # entry that IS rendered, which is also why the 0.84 pet (below the 0.85
    # threshold) is asserted alongside it.
    enrichment = SimpleNamespace(
        clothing_classifications={},
        clothing_segmentation={},
        pose_results={},
        vehicle_classifications={},
        vehicle_damage={},
        pet_classifications={
            "p1": SimpleNamespace(animal_type="dog", confidence=0.91),
            "p2": SimpleNamespace(animal_type="cat", confidence=0.84),
        },
        scene_ocr=None,
    )
    out = format_detections_with_all_enrichment(
        [{"detection_id": "p1", "class_name": "dog"}, {"detection_id": "p2", "class_name": "dog"}],
        enrichment,
        None,
    )
    assert out == (
        "### DOG (ID: p1)\n"
        "Confidence: 0%, Location: []\n"
        "Pet: dog (91%) [Confirmed household pet - low risk]\n"
        "\n"
        "### DOG (ID: p2)\n"
        "Confidence: 0%, Location: []\n"
        "Pet: cat (84%)"
    )


def test_format_scene_ocr_tail_after_detections():
    # Scene OCR tail: the "## Scene OCR" header, the JSON body (confidence
    # filter drops the 0.31 text) and mutmut_204's "XX\nXX" join, which would
    # glue the header, the JSON and the rows into one line.
    scene_ocr = SimpleNamespace(
        scene_texts=[
            SimpleNamespace(value="House 42", text_type="sign", confidence=0.92),
            SimpleNamespace(value="shadow", text_type="noise", confidence=0.31),
        ],
        detection_ocr={},
    )
    enrichment = SimpleNamespace(
        clothing_classifications={},
        clothing_segmentation={},
        pose_results={},
        vehicle_classifications={},
        vehicle_damage={},
        pet_classifications={},
        scene_ocr=scene_ocr,
    )
    out = format_detections_with_all_enrichment(
        [{"detection_id": "o1", "class_name": "person"}], enrichment, None
    )
    assert out == (
        "### PERSON (ID: o1)\n"
        "Confidence: 0%, Location: []\n"
        "\n"
        "## Scene OCR\n"
        '{\n  "scene_text": [\n    {\n'
        '      "value": "House 42",\n      "type": "sign",\n      "confidence": 0.92\n    }\n'
        '  ],\n  "detection_ocr": {}\n}'
    )


# ---------------------------------------------------------------------------
# format_ondemand_enrichment_context — section wrapping + join
# ---------------------------------------------------------------------------
def test_ondemand_context_wraps_and_joins_non_sentinel_sections():
    # "### THREAT DETECTION" / "## Person Analysis" / "### Vehicle Analysis"
    # headers and the "\n\n" join between the three sections.
    with (
        patch.object(
            prompts_module,
            "build_threat_section",
            return_value="Threat: gun detected",
            autospec=True,
        ),
        patch.object(
            prompts_module,
            "build_person_analysis_section",
            return_value="Pose: standing",
            autospec=True,
        ),
        patch.object(
            prompts_module, "build_vehicle_section", return_value="Vehicle: sedan", autospec=True
        ),
    ):
        out = format_ondemand_enrichment_context(SimpleNamespace())
    assert out == (
        "### THREAT DETECTION\nThreat: gun detected\n\n"
        "## Person Analysis\nPose: standing\n\n"
        "### Vehicle Analysis\nVehicle: sedan"
    )


def test_ondemand_context_all_sentinels_return_empty_string():
    # The three sentinel comparisons ("No threats detected.",
    # "No person analysis available.", "No vehicle detected.") each drop their
    # section; all three dropping yields "".
    with (
        patch.object(
            prompts_module,
            "build_threat_section",
            return_value="No threats detected.",
            autospec=True,
        ),
        patch.object(
            prompts_module,
            "build_person_analysis_section",
            return_value="No person analysis available.",
            autospec=True,
        ),
        patch.object(
            prompts_module,
            "build_vehicle_section",
            return_value="No vehicle detected.",
            autospec=True,
        ),
    ):
        out = format_ondemand_enrichment_context(SimpleNamespace())
    assert out == ""


def test_ondemand_context_partial_sections_join_in_order():
    # Threat + vehicle only: the surviving pair still joins with a single "\n\n"
    # and keeps header/newline structure. NOTE: the single survivor key
    # (x_format_ondemand_enrichment_context__mutmut_24,
    # ``if sections else ""`` -> ``if (sections) or True else ""``) is
    # EQUIVALENT here and everywhere — ``"\\n\\n".join([]) == ""``, so the
    # dead ``else ""`` arm is value-identical to the taken arm for the empty
    # case and the join is untouched when non-empty.
    with (
        patch.object(prompts_module, "build_threat_section", return_value="T", autospec=True),
        patch.object(
            prompts_module,
            "build_person_analysis_section",
            return_value="No person analysis available.",
            autospec=True,
        ),
        patch.object(prompts_module, "build_vehicle_section", return_value="V", autospec=True),
    ):
        out = format_ondemand_enrichment_context(SimpleNamespace())
    assert out == "### THREAT DETECTION\nT\n\n### Vehicle Analysis\nV"
