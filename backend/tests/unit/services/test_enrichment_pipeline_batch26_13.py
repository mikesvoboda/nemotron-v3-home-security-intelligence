"""Batch-26 chunk-13 kill battery — EnrichmentResult.to_context_string,
EnrichmentResult.get_summary_flags, EnrichmentPipeline._classify_vehicle_via_service.

Shipped source of truth: backend/services/enrichment_pipeline.py (HEAD copy
snapshot: probes/c13_shipped.py). Relevant shipped regions:
  to_context_string             : lines 1162-1396
  get_summary_flags             : lines 1750-1852
  _classify_vehicle_via_service : lines 4212-4352

EVERY asserted value below was MEASURED against the pristine shipped module
(probes/c13/probe_shipped.py + probes/c13/probe_out.py output). Measured facts
relied on:
  * `format_full_reid_context` is imported INSIDE to_context_string (ship 1171)
    from backend.services.reid_service, so that module is the binding shipped
    AND variant bodies resolve — patch it there.
  * person_reid_matches={"p1": []} (truthy dict, empty match list) makes the
    real formatter return "No entities matched with previous sightings." which
    the shipped gate (ship 1185) drops -> output is exactly
    "No additional context extracted."
  * get_action_risk_weight (ship 282-315): "breaking in" -> 1.0, "loitering"
    -> 0.7, "walking normally" -> 0.2, unmatched -> 0.5. The 0.7/0.5 thresholds
    at ship 1281-1288 are therefore boundary-reachable (inclusive).
  * weather notes measured: foggy/snowy ->
    "  **NOTE**: {cond.capitalize()} conditions may reduce visibility",
    rainy -> "  **NOTE**: Rain may affect detection accuracy", clear -> no note.
  * suspicious-pose gate (ship 1270) is strict `> 0.5` (measured: 0.5 is NOT
    suspicious) and membership is case-sensitive against
    {"crouching","running","lying"}.
  * _classify_vehicle_via_service success path with a MagicMock model_manager +
    AsyncMock client runs unmodified (measured: exactly TWO time.perf_counter()
    calls per vehicle). Seams used so the pins bind BOTH shipped code and
    exec'd variant bodies (the plugin snapshots M.__dict__, so patching module
    ATTRS on M would be invisible to variants): patch the shared `time` module
    object (`TIME_MODULE.perf_counter` -> 10.0 then 15.0 => duration exactly
    5.0 => extra["duration_ms"] == 5000) and the prometheus objects
    `MET.ENRICHMENT_MODEL_CALLS_TOTAL` / `MET.ENRICHMENT_MODEL_DURATION`, which
    record_enrichment_model_call / observe_enrichment_model_duration close over
    (measured: labels(model=...).inc() / labels(model=...).observe(5.0)).
  * `vehicle.bbox` falsy-but-usable (x1..y2 + to_tuple, __bool__ False): crop
    still succeeds (200x200) but shipped passes bbox_tuple=None to
    client.classify_vehicle (measured).
  * log call shapes measured: success -> logger.debug at level 10 with record
    attrs service/detection_id/duration_ms; unavailable -> logger.warning level
    30 with service/error_type/detection_id and exc_info None; unexpected ->
    logger.error level 40 with service/error_type/detection_id and exc_info set.

No sleeps, no network, no real DB.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time as TIME_MODULE
from types import SimpleNamespace
from unittest import mock

import pytest
from PIL import Image

import backend.core.metrics as MET
import backend.services.enrichment_pipeline as M
from backend.services.vehicle_damage_loader import DamageDetection

BOX = M.BoundingBox
DET = M.DetectionInput
REID_FMT = "backend.services.reid_service.format_full_reid_context"
EMPTY = "No additional context extracted."


# --------------------------------------------------------------------- helpers


def stub(**kw):
    """Plain attribute bag — only the listed attributes exist (no MagicMock
    magic-attribute leak), so hasattr() gates behave honestly."""
    return SimpleNamespace(**kw)


def image():
    return Image.new("RGB", (640, 480), color=(128, 128, 128))


def remote_vehicle():
    return stub(
        vehicle_type="sedan",
        confidence=0.92,
        display_name="Sedan",
        is_commercial=False,
        all_scores={"sedan": 0.92},
    )


def pipeline_with_client(client):
    return M.EnrichmentPipeline(
        model_manager=mock.MagicMock(),
        use_enrichment_service=True,
        enrichment_client=client,
    )


def car(det_id=7, bbox=(100.0, 150.0, 300.0, 350.0)):
    return DET(class_name="car", confidence=0.9, bbox=BOX(*bbox), id=det_id)


class Clock:
    """time.perf_counter stand-in: yields the scripted values, then keeps
    ticking so a mutant that calls perf_counter an extra time cannot crash the
    suite with StopIteration (the pin is the observed duration, not the count)."""

    def __init__(self, *values):
        self.values = list(values)
        self.calls = 0

    def __call__(self):
        i = self.calls
        self.calls += 1
        if i < len(self.values):
            return self.values[i]
        return self.values[-1] + (i - len(self.values) + 1) * 1e-3


@contextlib.contextmanager
def instrumented(clock):
    """Patch the SHARED seams the (variant) body resolves through:
    time.perf_counter on the real time module + the two prometheus objects.
    Yields (clock, calls_labels, duration_labels)."""
    calls_obj = mock.MagicMock()
    dur_obj = mock.MagicMock()
    with (
        mock.patch.object(TIME_MODULE, "perf_counter", autospec=True, side_effect=clock),
        mock.patch.object(MET, "ENRICHMENT_MODEL_CALLS_TOTAL", calls_obj),
        mock.patch.object(MET, "ENRICHMENT_MODEL_DURATION", dur_obj),
    ):
        yield clock, calls_obj, dur_obj


def damage(damage_types):
    return M.VehicleDamageResult(
        detections=[
            DamageDetection(damage_type=t, confidence=0.9, bbox=(0.0, 0.0, 1.0, 1.0))
            for t in damage_types
        ]
    )


def find_record(records, msg):
    for r in records:
        if r.getMessage() == msg:
            return r
    raise AssertionError(f"record {msg!r} not found; got {[r.getMessage() for r in records]}")


# =============================================================================
# to_context_string — Re-identification (gate + call shape + heading)
# =============================================================================


def test_c13_tcs_reid_call_args():
    """Shipped forwards BOTH match dicts positionally to
    format_full_reid_context and puts the result under "## Re-Identification"."""
    person = {"p1": ["person-sentinel"]}
    vehicle = {"v1": ["vehicle-sentinel"]}
    res = M.EnrichmentResult(person_reid_matches=person, vehicle_reid_matches=vehicle)
    with mock.patch(REID_FMT, return_value="REID-SENTINEL") as fmt:
        out = res.to_context_string()
    assert fmt.call_count == 1
    args, kwargs = fmt.call_args
    assert args == (person, vehicle), (args, kwargs)
    assert kwargs == {}
    assert out == "## Re-Identification\n\nREID-SENTINEL"


def test_c13_tcs_reid_gate_and_heading():
    """Measured with the REAL formatter: exact section text when matches exist;
    the "No entities" sentinel plus the empty-string case both produce NO
    section (ship 1185 gate)."""
    match = M.EntityMatch(
        entity=stub(camera_id="camA", attributes={}),
        similarity=0.88,
        time_gap_seconds=300.0,
    )
    assert M.EnrichmentResult(person_reid_matches={"p1": [match]}).to_context_string() == (
        "## Re-Identification\n\n"
        "## Person Re-Identification\n"
        "- [p1] Seen 1 time(s) before:\n"
        "  - Camera: camA, Time: 5 minutes ago (similarity: 88%)"
    )
    # truthy dict, empty match list -> formatter emits the "No entities" line ->
    # shipped gate drops the section entirely (measured).
    assert M.EnrichmentResult(person_reid_matches={"p1": []}).to_context_string() == EMPTY
    # and the empty-string return must also be suppressed (measured via patch)
    with mock.patch(REID_FMT, return_value=""):
        assert M.EnrichmentResult(person_reid_matches={"p1": [match]}).to_context_string() == EMPTY


# -------------------------------------------------------------- other sections


def test_c13_tcs_scene_change_heading():
    res = M.EnrichmentResult(
        scene_change=M.SceneChangeResult(
            change_detected=True, similarity_score=0.42, is_first_frame=False
        )
    )
    assert res.to_context_string() == (
        "## Scene Change\n\nScene change detected (similarity: 0.42)"
    )


def test_c13_tcs_violence_heading_and_line():
    res = M.EnrichmentResult(violence_detection=stub(is_violent=True, confidence=0.88))
    assert res.to_context_string() == (
        "## Violence Detection\n\n**VIOLENCE DETECTED** (confidence: 88%)"
    )


def test_c13_tcs_security_alert_line_exact():
    """Whole measured output for a high-security-damage vehicle, including the
    trailing security-alert line pinned verbatim."""
    res = M.EnrichmentResult(vehicle_damage={"4": damage(["glass_shatter"])})
    assert res.to_context_string() == (
        "## Vehicle Damage (1 vehicles with damage)\n\n"
        "  Vehicle 4:\n\n"
        "    Vehicle Damage Detected (1 instances):\n"
        "  - glass_shatter: 1 instance(s) (avg conf: 90%)\n"
        "  **HIGH SECURITY ALERT**: Suspicious damage types detected\n\n"
        "    **SECURITY ALERT**: High-priority damage detected"
    )


def test_c13_tcs_plate_and_face_numbering():
    """enumerate(..., 1): numbering starts at 1 for plates and faces."""
    plates = [
        M.LicensePlateResult(
            bbox=BOX(1.0, 2.0, 3.0, 4.0), text="ABC123", confidence=0.9, ocr_confidence=0.83
        ),
        M.LicensePlateResult(bbox=BOX(5.0, 6.0, 7.0, 8.0), text="", ocr_confidence=0.0),
    ]
    faces = [
        M.FaceResult(bbox=BOX(1.0, 1.0, 2.0, 2.0), confidence=0.71),
        M.FaceResult(bbox=BOX(3.0, 3.0, 4.0, 4.0), confidence=0.45),
    ]
    assert M.EnrichmentResult(license_plates=plates).to_context_string() == (
        "## License Plates (2 detected)\n\n"
        "  - Plate 1: ABC123 (OCR confidence: 83%)\n\n"
        "  - Plate 2: [unreadable]"
    )
    assert M.EnrichmentResult(faces=faces).to_context_string() == (
        "## Faces (2 detected)\n\n  - Face 1: confidence 71%\n\n  - Face 2: confidence 45%"
    )


def test_c13_tcs_pet_line_and_pet_only_note():
    """format_pet_for_nemotron(pet_result) real output + pet-only note verbatim
    (pet_only_event measured True for this result)."""
    pet = M.PetClassificationResult(
        animal_type="dog", confidence=0.92, cat_score=0.03, dog_score=0.92
    )
    res = M.EnrichmentResult(pet_classifications={"2": pet})
    assert res.pet_only_event is True  # measured precondition
    assert res.to_context_string() == (
        "## Pet Classifications (1 animals)\n\n"
        "  - Animal 2: Pet classification: dog (92% confidence) - household pet, "
        "low security risk\n\n"
        "  **NOTE**: Pet-only event - low security risk"
    )


def test_c13_tcs_pose_matrix():
    """Measured: ' [SUSPICIOUS]' suffix only for pose_class in
    {"crouching","running","lying"} AND pose_confidence strictly > 0.5."""

    def line(pose_class, conf):
        return M.EnrichmentResult(
            pose_results={"3": stub(pose_class=pose_class, pose_confidence=conf)}
        ).to_context_string()

    for suspect in ("crouching", "running", "lying"):
        assert line(suspect, 0.9) == (
            f"## Pose Analysis (1 persons)\n\n  Person 3: {suspect} (90%) [SUSPICIOUS]"
        )
    # strict > 0.5 boundary (measured: 0.5 is NOT suspicious)
    assert line("running", 0.5) == "## Pose Analysis (1 persons)\n\n  Person 3: running (50%)"
    # pose_class values outside the shipped set -> empty risk_note (measured)
    for other in ("walking", "XXrunningXX", "XXlyingXX", "RUNNING", "LYING"):
        assert line(other, 0.9) == (f"## Pose Analysis (1 persons)\n\n  Person 3: {other} (90%)")


def test_c13_tcs_action_section_matrix():
    """Measured: heading, default action "unknown", default confidence 0.0,
    risk_level wording and the >= 0.7 inclusive concern-line gate."""

    def out(ar):
        return M.EnrichmentResult(action_results=ar).to_context_string()

    assert out({"detected_action": "loitering", "confidence": 0.8}) == (
        "## Action Recognition\n\n"
        "  Detected action: loitering (80%)\n\n"
        "  **HIGH RISK**: This action indicates potential security concern"
    )
    assert out({"confidence": 0.4}) == ("## Action Recognition\n\n  Detected action: unknown (40%)")
    assert out({"detected_action": "walking normally"}) == (
        "## Action Recognition\n\n  Detected action: walking normally (0%)"
    )
    # exact 0.7 boundary INCLUDES the concern line (risk weight 1.0 for
    # "breaking in", confidence 0.7)
    assert out({"detected_action": "breaking in", "confidence": 0.7}) == (
        "## Action Recognition\n\n"
        "  Detected action: breaking in (70%)\n\n"
        "  **HIGH RISK**: This action indicates potential security concern"
    )
    # neutral action -> risk weight 0.5 -> no concern line, level "suspicious"
    assert out({"detected_action": "standing still", "confidence": 0.5}) == (
        "## Action Recognition\n\n  Detected action: standing still (50%)"
    )


def test_c13_tcs_action_risk_levels_wording(caplog):
    """The shipped risk_level ternary (ship 1280-1285) is LOCAL to the section
    and reaches the emitted text only through the f"  **{risk_level}**: ..."
    line, which is appended only when risk_weight >= 0.7 (ship 1288). Measured:
    every appended concern line carries the literal "HIGH RISK" token, and the
    "suspicious"/"normal" arms NEVER appear anywhere in the output (the
    Detected-action line never contains them)."""
    client_cases = [
        {"detected_action": "breaking in", "confidence": 1.0},  # weight 1.0
        {"detected_action": "loitering", "confidence": 0.3},  # weight 0.7
        {"detected_action": "taking photos", "confidence": 0.3},  # weight 0.7
        {"detected_action": "hiding", "confidence": 0.5},  # weight 1.0
        {"detected_action": "checking windows", "confidence": 0.9},  # weight 0.7
    ]
    caplog.set_level(logging.DEBUG)
    for ar in client_cases:
        out = M.EnrichmentResult(action_results=ar).to_context_string()
        head, _, concern = out.partition(
            "  **HIGH RISK**: This action indicates potential security concern"
        )
        assert concern == "", out  # concern line present, verbatim
        # risk_level token interpolated into the concern line == "HIGH RISK"
        assert head.endswith("\n\n")
        assert "suspicious" not in out and "normal" not in out, out
    # and the low-weight actions emit NO concern line at all (measured):
    for ar in (
        {"detected_action": "walking normally", "confidence": 0.9},  # 0.2
        {"detected_action": "standing still", "confidence": 0.9},  # 0.5 neutral
    ):
        out = M.EnrichmentResult(action_results=ar).to_context_string()
        assert "potential security concern" not in out, out


def test_c13_tcs_action_high_risk_concern_line():
    """Concern-line gate `if risk_weight >= 0.7` (ship 1288) is INCLUSIVE:
    "loitering" -> risk weight exactly 0.7 (measured via
    M.get_action_risk_weight) and shipped DOES append the concern line;
    weight-0.5 and weight-0.2 actions do not."""
    assert M.get_action_risk_weight("loitering") == 0.7  # measured
    out = M.EnrichmentResult(
        action_results={"detected_action": "loitering", "confidence": 0.8}
    ).to_context_string()
    assert out == (
        "## Action Recognition\n\n"
        "  Detected action: loitering (80%)\n\n"
        "  **HIGH RISK**: This action indicates potential security concern"
    )
    near_below = M.EnrichmentResult(
        action_results={"detected_action": "loiter", "confidence": 0.8}
    ).to_context_string()
    # "loiter" matches no keyword -> neutral 0.5 -> no concern line (measured)
    assert M.get_action_risk_weight("loiter") == 0.5
    assert near_below == ("## Action Recognition\n\n  Detected action: loiter (80%)")


def test_c13_tcs_threat_gate():
    """Measured gate: threat_detection truthy AND hasattr(has_threats) AND
    has_threats; otherwise no section at all."""
    assert M.EnrichmentResult(threat_detection=stub()).to_context_string() == EMPTY
    assert M.EnrichmentResult(threat_detection=stub(has_threats=False)).to_context_string() == EMPTY
    threat = stub(
        has_threats=True,
        has_high_priority=True,
        threat_summary="gun",
        threats=[stub(class_name="gun", confidence=0.9, is_high_priority=True)],
    )
    assert M.EnrichmentResult(threat_detection=threat).to_context_string() == (
        "## **THREAT DETECTION**\n\n"
        "  **CRITICAL**: High-priority weapon detected!\n\n"
        "  Threats: gun\n\n"
        "    - gun (90%) **HIGH PRIORITY**"
    )


def test_c13_tcs_iqa_heading():
    res = M.EnrichmentResult(image_quality=stub(format_context=lambda: "blur 0.1"))
    assert res.to_context_string() == "## Image Quality Assessment\n\n  blur 0.1"


def test_c13_tcs_weather_matrix():
    """Measured weather note branch table."""

    def out(cond):
        wc = stub(simple_condition=cond, confidence=0.9, to_context_string=lambda: "wx")
        return M.EnrichmentResult(weather_classification=wc).to_context_string()

    assert out("foggy") == (
        "## Weather Conditions\n\n  wx\n\n  **NOTE**: Foggy conditions may reduce visibility"
    )
    assert out("snowy") == (
        "## Weather Conditions\n\n  wx\n\n  **NOTE**: Snowy conditions may reduce visibility"
    )
    assert out("rainy") == (
        "## Weather Conditions\n\n  wx\n\n  **NOTE**: Rain may affect detection accuracy"
    )
    assert out("clear") == "## Weather Conditions\n\n  wx"


def test_c13_tcs_join_separator():
    """Measured section separator is exactly "\\n\\n"."""
    res = M.EnrichmentResult(
        violence_detection=stub(is_violent=True, confidence=0.88),
        weather_classification=stub(
            simple_condition="clear", confidence=0.9, to_context_string=lambda: "wx"
        ),
    )
    assert res.to_context_string() == (
        "## Violence Detection\n\n**VIOLENCE DETECTED** (confidence: 88%)\n\n"
        "## Weather Conditions\n\n  wx"
    )


# =============================================================================
# get_summary_flags
# =============================================================================


def test_c13_gsf_flags_exact():
    """Measured flag dicts pinned verbatim (type/description/severity)."""
    vio = M.EnrichmentResult(
        violence_detection=stub(is_violent=True, confidence=0.88)
    ).get_summary_flags()
    assert vio == [
        {
            "type": "violence",
            "description": "Violence detected (88% confidence)",
            "severity": "critical",
        }
    ]

    attire = M.EnrichmentResult(
        clothing_classifications={"3": stub(is_suspicious=True, top_category="balaclava")}
    ).get_summary_flags()
    assert attire == [
        {
            "type": "suspicious_attire",
            "description": "Person 3: balaclava",
            "severity": "alert",
        }
    ]

    face = M.EnrichmentResult(
        clothing_segmentation={"5": stub(has_face_covered=True)}
    ).get_summary_flags()
    assert face == [
        {
            "type": "face_covered",
            "description": "Person 5: Face obscured by hat/sunglasses/scarf",
            "severity": "alert",
        }
    ]

    # vehicle damage flags: emitted ONLY when has_high_security_damage (ship
    # 1796 gate), so severity is always "critical" there (measured).
    dmg = M.EnrichmentResult(
        vehicle_damage={"10": damage(["glass_shatter"]), "9": damage(["glass_shatter", "scratch"])}
    ).get_summary_flags()
    assert [f["type"] for f in dmg] == ["vehicle_damage", "vehicle_damage"]
    assert dmg[0] == {
        "type": "vehicle_damage",
        "description": "Vehicle 10: glass_shatter",
        "severity": "critical",
    }
    for f in dmg:
        assert f["severity"] == "critical"
        assert "description" in f
    # damage_types is a set -> pin membership and the ', ' separator (measured)
    assert dmg[1]["description"].startswith("Vehicle 9: ")
    assert sorted(dmg[1]["description"][len("Vehicle 9: ") :].split(", ")) == [
        "glass_shatter",
        "scratch",
    ]
    # non-high-security damage produces no flag at all (measured)
    assert M.EnrichmentResult(vehicle_damage={"7": damage(["scratch"])}).get_summary_flags() == []


# =============================================================================
# _classify_vehicle_via_service
# =============================================================================


def test_c13_cvs_metrics_call_and_duration():
    """Shipped: record_enrichment_model_call("vehicle-via-service") once, then
    observe_enrichment_model_duration("vehicle-via-service",
    time.perf_counter() - start_time) — exactly 5.0 under the scripted clock
    (10.0 -> 15.0). Seams are the SHARED objects (time.perf_counter,
    MET.ENRICHMENT_MODEL_*), which variant bodies resolve too."""
    client = mock.AsyncMock()
    client.classify_vehicle.return_value = remote_vehicle()
    pip = pipeline_with_client(client)
    with instrumented(Clock(10.0, 15.0)) as (clock, calls_obj, dur_obj):
        res = asyncio.run(pip._classify_vehicle_via_service([car(7)], image()))
    assert list(res) == ["7"]
    assert calls_obj.mock_calls == [
        mock.call.labels(model="vehicle-via-service"),
        mock.call.labels().inc(),
    ]
    assert dur_obj.mock_calls == [
        mock.call.labels(model="vehicle-via-service"),
        mock.call.labels().observe(5.0),
    ]


def test_c13_cvs_det_id_fallback():
    """Shipped `str(vehicle.id) if vehicle.id else str(i)`: id 0 and id None are
    falsy -> positional indices '0' and '1'."""
    client = mock.AsyncMock()
    client.classify_vehicle.return_value = remote_vehicle()
    pip = pipeline_with_client(client)
    res = asyncio.run(
        pip._classify_vehicle_via_service(
            [
                car(0, bbox=(1.0, 1.0, 20.0, 20.0)),
                car(None, bbox=(30.0, 30.0, 50.0, 50.0)),
            ],
            image(),
        )
    )
    assert sorted(res) == ["0", "1"]


def test_c13_cvs_crop_failure_skips_only_that_vehicle():
    """Shipped `continue` on a None crop: the out-of-frame vehicle is skipped
    and iteration continues to the next detection."""
    client = mock.AsyncMock()
    client.classify_vehicle.return_value = remote_vehicle()
    pip = pipeline_with_client(client)
    bad = car(3, bbox=(700.0, 500.0, 800.0, 600.0))  # outside the 640x480 frame
    res = asyncio.run(pip._classify_vehicle_via_service([bad, car(5)], image()))
    assert list(res) == ["5"]
    assert client.classify_vehicle.await_count == 1


def test_c13_cvs_service_call_arguments():
    """Shipped (bbox truthy): `await client.classify_vehicle(vehicle_crop,
    bbox_tuple)` — positional crop (200x200 PIL image for the measured bbox)
    plus bbox_tuple = vehicle.bbox.to_tuple() == (100.0, 150.0, 300.0, 350.0)."""
    client = mock.AsyncMock()
    client.classify_vehicle.return_value = remote_vehicle()
    pip = pipeline_with_client(client)
    res = asyncio.run(pip._classify_vehicle_via_service([car(7)], image()))
    assert list(res) == ["7"]
    args, kwargs = client.classify_vehicle.call_args
    assert kwargs == {}
    assert len(args) == 2, args
    assert isinstance(args[0], Image.Image)
    assert args[0].size == (200, 200)
    assert args[1] == (100.0, 150.0, 300.0, 350.0)


def test_c13_cvs_falsy_bbox_sends_none_bbox():
    """Shipped `vehicle.bbox.to_tuple() if vehicle.bbox else None`: with a
    FALSY-but-usable bbox (crop still succeeds — measured), the shipped call
    passes bbox_tuple=None as the 2nd positional argument."""
    client = mock.AsyncMock()
    client.classify_vehicle.return_value = remote_vehicle()
    pip = pipeline_with_client(client)

    class FalsyBBox:
        def __init__(self):
            self.x1, self.y1, self.x2, self.y2 = 100.0, 150.0, 300.0, 350.0

        def __bool__(self):
            return False

        def to_tuple(self):
            return (self.x1, self.y1, self.x2, self.y2)

    v = DET(class_name="car", confidence=0.9, bbox=FalsyBBox(), id=9)
    res = asyncio.run(pip._classify_vehicle_via_service([v], image()))
    assert list(res) == ["9"]
    args, kwargs = client.classify_vehicle.call_args
    assert kwargs == {} and len(args) == 2
    assert isinstance(args[0], Image.Image)
    assert args[1] is None


def test_c13_cvs_result_field_mapping():
    """Shipped copies every remote field into VehicleClassificationResult."""
    client = mock.AsyncMock()
    client.classify_vehicle.return_value = remote_vehicle()
    pip = pipeline_with_client(client)
    got = asyncio.run(pip._classify_vehicle_via_service([car(7)], image()))["7"]
    assert got.vehicle_type == "sedan"
    assert got.confidence == 0.92
    assert got.display_name == "Sedan"
    assert got.is_commercial is False
    assert got.all_scores == {"sedan": 0.92}


def test_c13_cvs_debug_log_payload(caplog):
    """Shipped success log: DEBUG message
    "Vehicle 7 type (via service): sedan (92%)" with record attrs
    service='vehicle-via-service', detection_id='7',
    duration_ms=int(duration*1000)==5000 (scripted clock)."""
    client = mock.AsyncMock()
    client.classify_vehicle.return_value = remote_vehicle()
    pip = pipeline_with_client(client)
    caplog.set_level(logging.DEBUG)
    with instrumented(Clock(10.0, 15.0)):
        asyncio.run(pip._classify_vehicle_via_service([car(7)], image()))
    rec = find_record(caplog.records, "Vehicle 7 type (via service): sedan (92%)")
    assert rec.levelno == logging.DEBUG
    assert rec.service == "vehicle-via-service"
    assert rec.detection_id == "7"
    assert rec.duration_ms == 5000


def test_c13_cvs_unavailable_error_log(caplog):
    """Shipped unavailable path: returns {} and logs WARNING
    "Enrichment service unavailable for vehicle 7" with record attrs
    service/error_type/detection_id."""
    client = mock.AsyncMock()
    client.classify_vehicle.side_effect = M.EnrichmentUnavailableError("service down")
    pip = pipeline_with_client(client)
    caplog.set_level(logging.DEBUG)
    with instrumented(Clock(10.0, 15.0)):
        res = asyncio.run(pip._classify_vehicle_via_service([car(7)], image()))
    assert res == {}
    rec = find_record(caplog.records, "Enrichment service unavailable for vehicle 7")
    assert rec.levelno == logging.WARNING
    assert rec.service == "vehicle-via-service"
    assert rec.error_type == "EnrichmentUnavailableError"
    assert rec.detection_id == "7"


def test_c13_cvs_unexpected_error_log(caplog):
    """Shipped catch-all: returns {} and logs ERROR
    "Vehicle classification unexpected error for 7: boom" with
    service/error_type/detection_id attrs and exc_info populated."""
    client = mock.AsyncMock()
    client.classify_vehicle.side_effect = RuntimeError("boom")
    pip = pipeline_with_client(client)
    caplog.set_level(logging.DEBUG)
    with instrumented(Clock(10.0, 15.0)):
        res = asyncio.run(pip._classify_vehicle_via_service([car(7)], image()))
    assert res == {}
    rec = find_record(caplog.records, "Vehicle classification unexpected error for 7: boom")
    assert rec.levelno == logging.ERROR
    assert rec.service == "vehicle-via-service"
    assert rec.error_type == "RuntimeError"
    assert rec.detection_id == "7"
    assert rec.exc_info is not None and rec.exc_info[0] is RuntimeError
