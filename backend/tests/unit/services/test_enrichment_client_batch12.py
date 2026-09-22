"""S2 batch-12 — enrichment_client pure-function kill battery.

Targets the frozen-feed TEST-GAP clusters that need NO endpoint-mock surgery:
GAP-parse-unified-fields (dossier cluster 6: .get defaults/guards that "wrongly
corrupt every enriched LLM prompt" invisibly), the to_context_string family
(cluster 11: shipped suite asserts SUBSTRINGS, so case/XX text mutants pass —
this battery pins EXACT strings), GAP-retry-branch pieces reachable purely
(_calculate_backoff_delay jitter/cap math, _is_retryable_error 5xx boundary
at 499/500 — the shipped retry suite only probes 503/400), plus every
to_dict/has_security_alerts in the pure cluster via WHOLE-DICT equality.

Every assert is whole-value (exact dict/string/object equality) so a
single-field mutant cannot hide inside a subset assert.
"""

from __future__ import annotations

import httpx
import pytest

from backend.services.enrichment_client import (
    ActionClassificationResult,
    ClothingClassificationResult,
    DepthEstimationResult,
    EnrichmentClient,
    KeypointData,
    ObjectDistanceResult,
    PetClassificationResult,
    PoseAnalysisResult,
    UnifiedClothingResult,
    UnifiedDemographicsResult,
    UnifiedEnrichmentResult,
    UnifiedPoseResult,
    UnifiedThreatResult,
    UnifiedVehicleResult,
    VehicleClassificationResult,
)

pytestmark = [pytest.mark.unit]


def bare_client() -> EnrichmentClient:
    """Instance without __init__ — the three methods probed here touch no
    instance state (verified: no self.* reads in their shipped bodies)."""
    return EnrichmentClient.__new__(EnrichmentClient)


class TestParseUnifiedResponseDefaults:
    """Cluster 6: the .get() defaults and presence-gates of _parse_unified_
    response — wrong defaults flow into every LLM prompt built from them."""

    def test_empty_payload_full_object(self) -> None:
        r = bare_client()._parse_unified_response({})
        assert r == UnifiedEnrichmentResult(
            pose=None,
            clothing=None,
            demographics=None,
            vehicle=None,
            pet=None,
            threat=None,
            reid_embedding=None,
            action=None,
            depth=None,
            models_loaded=None,
            inference_time_ms=0.0,
        )

    def test_top_level_defaults_exact(self) -> None:
        r = bare_client()._parse_unified_response({"pose": None, "inference_time_ms": None})
        assert (r.models_loaded, r.inference_time_ms) == (None, None)
        # falsy-but-present pose stays unparsed (guard reads truthiness, not key presence)
        assert r.pose is None

    # MEASURED: the section guard is truthiness — {"pose": {}} is FALSY and
    # skips the branch (pose stays None). The .get() defaults only surface
    # when the section is TRUTHY but a key is missing, so every defaults
    # probe below uses a truthy dict that carries none of the read keys.

    def test_pose_branch_defaults(self) -> None:
        r = bare_client()._parse_unified_response({"pose": {"models_loaded": []}})
        assert r.pose == UnifiedPoseResult(
            keypoints=[], pose_class="unknown", confidence=0.0, is_suspicious=False
        )

    def test_clothing_branch_defaults(self) -> None:
        r = bare_client()._parse_unified_response({"clothing": {"x": 1}})
        assert r.clothing == UnifiedClothingResult(categories=[], is_suspicious=False)

    def test_demographics_branch_defaults(self) -> None:
        r = bare_client()._parse_unified_response({"demographics": {"x": 1}})
        assert r.demographics == UnifiedDemographicsResult(
            age_range="unknown", age_confidence=0.0, gender="unknown", gender_confidence=0.0
        )

    def test_vehicle_branch_defaults(self) -> None:
        r = bare_client()._parse_unified_response({"vehicle": {"x": 1}})
        assert r.vehicle == UnifiedVehicleResult(
            make=None, model=None, color=None, type="unknown", confidence=0.0
        )

    def test_threat_branch_defaults(self) -> None:
        r = bare_client()._parse_unified_response({"threat": {"x": 1}})
        assert r.threat == UnifiedThreatResult(threats=[], has_threat=False, max_severity="none")

    def test_full_payload_whole_object(self) -> None:
        payload = {
            "models_loaded": ["pose", "threat"],
            "inference_time_ms": 12.5,
            "pose": {
                "keypoints": [{"x": 1, "y": 2}],
                "pose_class": "crouching",
                "confidence": 0.9,
                "is_suspicious": True,
            },
            "clothing": {"categories": [{"category": "hoodie"}], "is_suspicious": True},
            "demographics": {
                "age_range": "25-35",
                "age_confidence": 0.7,
                "gender": "male",
                "gender_confidence": 0.8,
            },
            "vehicle": {
                "make": "Toyota",
                "model": "Camry",
                "color": "red",
                "type": "sedan",
                "confidence": 0.6,
            },
            "threat": {
                "threats": [{"type": "knife"}],
                "has_threat": True,
                "max_severity": "high",
            },
            "reid_embedding": [0.25, -0.5],
            "pet": {"pet_type": "dog"},
            "action": {"top_action": "loitering"},
            "depth": {"mean_depth": 0.4},
        }
        r = bare_client()._parse_unified_response(payload)
        assert r == UnifiedEnrichmentResult(
            pose=UnifiedPoseResult(
                keypoints=[{"x": 1, "y": 2}],
                pose_class="crouching",
                confidence=0.9,
                is_suspicious=True,
            ),
            clothing=UnifiedClothingResult(categories=[{"category": "hoodie"}], is_suspicious=True),
            demographics=UnifiedDemographicsResult(
                age_range="25-35",
                age_confidence=0.7,
                gender="male",
                gender_confidence=0.8,
            ),
            vehicle=UnifiedVehicleResult(
                make="Toyota", model="Camry", color="red", type="sedan", confidence=0.6
            ),
            pet={"pet_type": "dog"},
            threat=UnifiedThreatResult(
                threats=[{"type": "knife"}], has_threat=True, max_severity="high"
            ),
            reid_embedding=[0.25, -0.5],
            action={"top_action": "loitering"},
            depth={"mean_depth": 0.4},
            models_loaded=["pose", "threat"],
            inference_time_ms=12.5,
        )

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("reid_embedding", [0.1, 0.2]),
            ("pet", {"a": 1}),
            ("action", {"b": 2}),
            ("depth", {"c": 3}),
        ],
    )
    def test_passthrough_fields_carry_value(self, key: str, value: object) -> None:
        r = bare_client()._parse_unified_response({key: value})
        assert getattr(r, key) == value

    def test_falsy_sections_stay_unparsed(self) -> None:
        # MEASURED: EVERY field — parsed sections AND the passthrough four —
        # sits behind a truthiness guard, so a falsy value leaves the field
        # at its None default (an empty list/dict never reaches the result).
        r = bare_client()._parse_unified_response(
            {"pose": {}, "clothing": {}, "threat": {}, "reid_embedding": [], "action": {}}
        )
        assert (r.pose, r.clothing, r.threat) == (None, None, None)
        assert (r.reid_embedding, r.action) == (None, None)


class TestToDictWholeDict:
    """Whole-dict equality per dataclass: a key rename, value swap, dropped
    entry, or conversion bypass fails exact comparison."""

    def test_unified_pose(self) -> None:
        r = UnifiedPoseResult(
            keypoints=[{"x": 1}], pose_class="standing", confidence=0.5, is_suspicious=True
        )
        assert r.to_dict() == {
            "keypoints": [{"x": 1}],
            "pose_class": "standing",
            "confidence": 0.5,
            "is_suspicious": True,
        }

    def test_unified_clothing(self) -> None:
        r = UnifiedClothingResult(categories=[{"c": 1}], is_suspicious=False)
        assert r.to_dict() == {"categories": [{"c": 1}], "is_suspicious": False}

    def test_unified_demographics(self) -> None:
        r = UnifiedDemographicsResult(
            age_range="25-35", age_confidence=0.3, gender="female", gender_confidence=0.4
        )
        assert r.to_dict() == {
            "age_range": "25-35",
            "age_confidence": 0.3,
            "gender": "female",
            "gender_confidence": 0.4,
        }

    def test_unified_vehicle(self) -> None:
        r = UnifiedVehicleResult(
            make=None, model="F-150", color="black", type="truck", confidence=0.2
        )
        assert r.to_dict() == {
            "make": None,
            "model": "F-150",
            "color": "black",
            "type": "truck",
            "confidence": 0.2,
        }

    def test_unified_threat(self) -> None:
        r = UnifiedThreatResult(threats=[{"type": "gun"}], has_threat=True, max_severity="critical")
        assert r.to_dict() == {
            "threats": [{"type": "gun"}],
            "has_threat": True,
            "max_severity": "critical",
        }

    def test_unified_enrichment_all_fields(self) -> None:
        r = UnifiedEnrichmentResult(
            pose=UnifiedPoseResult([], "p", 0.1, False),
            clothing=UnifiedClothingResult([], True),
            demographics=UnifiedDemographicsResult("a", 0.2, "g", 0.3),
            vehicle=UnifiedVehicleResult("m", "mo", "c", "t", 0.4),
            pet={"p": 1},
            threat=UnifiedThreatResult([], False, "none"),
            reid_embedding=[0.9],
            action={"a": 1},
            depth={"d": 2},
            models_loaded=["x"],
            inference_time_ms=7.5,
        )
        assert r.to_dict() == {
            "pose": {"keypoints": [], "pose_class": "p", "confidence": 0.1, "is_suspicious": False},
            "clothing": {"categories": [], "is_suspicious": True},
            "demographics": {
                "age_range": "a",
                "age_confidence": 0.2,
                "gender": "g",
                "gender_confidence": 0.3,
            },
            "vehicle": {"make": "m", "model": "mo", "color": "c", "type": "t", "confidence": 0.4},
            "threat": {"threats": [], "has_threat": False, "max_severity": "none"},
            "pet": {"p": 1},
            "reid_embedding": [0.9],
            "action": {"a": 1},
            "depth": {"d": 2},
            "models_loaded": ["x"],
            "inference_time_ms": 7.5,
        }

    def test_unified_enrichment_none_fields_absent(self) -> None:
        # only inference_time_ms is unconditional; every None field must be ABSENT
        r = UnifiedEnrichmentResult()
        assert r.to_dict() == {"inference_time_ms": 0.0}

    def test_vehicle_classification(self) -> None:
        r = VehicleClassificationResult(
            vehicle_type="van",
            display_name="Delivery van",
            confidence=0.75,
            is_commercial=True,
            all_scores={"van": 0.75},
            inference_time_ms=3.5,
        )
        assert r.to_dict() == {
            "vehicle_type": "van",
            "display_name": "Delivery van",
            "confidence": 0.75,
            "is_commercial": True,
            "all_scores": {"van": 0.75},
            "inference_time_ms": 3.5,
        }

    def test_pet_classification(self) -> None:
        r = PetClassificationResult(
            pet_type="dog",
            breed="lab",
            confidence=0.6,
            is_household_pet=True,
            inference_time_ms=1.5,
        )
        assert r.to_dict() == {
            "pet_type": "dog",
            "breed": "lab",
            "confidence": 0.6,
            "is_household_pet": True,
            "inference_time_ms": 1.5,
        }

    def test_clothing_classification(self) -> None:
        r = ClothingClassificationResult(
            clothing_type="hoodie",
            color="black",
            style="casual",
            confidence=0.5,
            top_category="upper",
            description="dark hoodie",
            is_suspicious=True,
            is_service_uniform=False,
            inference_time_ms=2.0,
        )
        assert r.to_dict() == {
            "clothing_type": "hoodie",
            "color": "black",
            "style": "casual",
            "confidence": 0.5,
            "top_category": "upper",
            "description": "dark hoodie",
            "is_suspicious": True,
            "is_service_uniform": False,
            "inference_time_ms": 2.0,
        }

    def test_depth_estimation(self) -> None:
        r = DepthEstimationResult(
            depth_map_base64="AAA",
            min_depth=0.1,
            max_depth=0.9,
            mean_depth=0.5,
            inference_time_ms=9.0,
        )
        assert r.to_dict() == {
            "depth_map_base64": "AAA",
            "min_depth": 0.1,
            "max_depth": 0.9,
            "mean_depth": 0.5,
            "inference_time_ms": 9.0,
        }

    def test_object_distance(self) -> None:
        r = ObjectDistanceResult(
            estimated_distance_m=3.4,
            relative_depth=0.3,
            proximity_label="close",
            inference_time_ms=1.0,
        )
        assert r.to_dict() == {
            "estimated_distance_m": 3.4,
            "relative_depth": 0.3,
            "proximity_label": "close",
            "inference_time_ms": 1.0,
        }

    def test_action_classification(self) -> None:
        r = ActionClassificationResult(
            action="loitering",
            confidence=0.8,
            is_suspicious=True,
            risk_weight=0.9,
            all_scores={"loitering": 0.8},
            inference_time_ms=4.0,
        )
        assert r.to_dict() == {
            "action": "loitering",
            "confidence": 0.8,
            "is_suspicious": True,
            "risk_weight": 0.9,
            "all_scores": {"loitering": 0.8},
            "inference_time_ms": 4.0,
        }

    def test_keypoint(self) -> None:
        r = KeypointData(name="nose", x=0.5, y=0.25, confidence=0.75)
        assert r.to_dict() == {"name": "nose", "x": 0.5, "y": 0.25, "confidence": 0.75}

    def test_pose_analysis_comprehension(self) -> None:
        # to_dict runs a KeypointData.to_dict comprehension — pin its output too
        r = PoseAnalysisResult(
            keypoints=[KeypointData("nose", 0.1, 0.2, 0.9)],
            posture="standing",
            alerts=["hands_raised"],
            inference_time_ms=5.0,
        )
        assert r.to_dict() == {
            "keypoints": [{"name": "nose", "x": 0.1, "y": 0.2, "confidence": 0.9}],
            "posture": "standing",
            "alerts": ["hands_raised"],
            "inference_time_ms": 5.0,
        }


class TestToContextStringExact:
    """Cluster 11: shipped tests assert substrings, so mutated casing/wording
    survives them. Every string here is pinned EXACT (including % formatting)."""

    def test_pose_plain_and_alert(self) -> None:
        plain = UnifiedPoseResult([], "standing", 0.85, False)
        assert plain.to_context_string() == "Pose: standing (confidence: 85%)"
        alert = UnifiedPoseResult([], "crouching", 0.9, True)
        assert alert.to_context_string() == (
            "Pose: crouching (confidence: 90%)\n  [ALERT: Suspicious posture detected]"
        )

    def test_clothing_empty_and_top_defaults(self) -> None:
        assert UnifiedClothingResult([], False).to_context_string() == (
            "Clothing: No classification available"
        )
        # top dict missing both keys -> 'unknown' / 0 -> '0%' defaults
        partial = UnifiedClothingResult([{}], False)
        assert partial.to_context_string() == "Clothing: unknown (confidence: 0%)"
        full = UnifiedClothingResult([{"category": "hoodie", "confidence": 0.9}], True)
        assert full.to_context_string() == (
            "Clothing: hoodie (confidence: 90%)\n  [ALERT: Potentially suspicious attire]"
        )

    def test_demographics_field_order(self) -> None:
        r = UnifiedDemographicsResult("25-35", 0.8, "male", 0.6)
        assert r.to_context_string() == ("Demographics: male (60%), age 25-35 (80%)")

    def test_vehicle_optional_parts_order(self) -> None:
        full = UnifiedVehicleResult("Toyota", "Camry", "red", "sedan", 0.7)
        assert full.to_context_string() == "Vehicle: red Toyota Camry sedan (confidence: 70%)"
        no_make = UnifiedVehicleResult(None, "Camry", "red", "sedan", 0.7)
        assert no_make.to_context_string() == "Vehicle: red Camry sedan (confidence: 70%)"
        only_type = UnifiedVehicleResult(None, None, None, "sedan", 0.7)
        assert only_type.to_context_string() == "Vehicle: sedan (confidence: 70%)"

    def test_threat_strings(self) -> None:
        quiet = UnifiedThreatResult([], False, "none")
        assert quiet.to_context_string() == "Threat detection: No threats detected"
        loud = UnifiedThreatResult(
            [{"type": "knife"}, {"label": "no-type-key"}, {"type": "gun"}],
            True,
            "critical",
        )
        # second entry lacks "type" -> 'unknown' default; order preserved
        assert loud.to_context_string() == (
            "THREAT DETECTED: knife, unknown, gun (severity: critical)"
        )

    def test_vehicle_classification_commercial(self) -> None:
        r = VehicleClassificationResult("van", "Delivery van", 0.9, True, {}, 1.0)
        assert r.to_context_string() == (
            "Vehicle type: Delivery van (90% confidence) [Commercial/delivery vehicle]"
        )
        r2 = VehicleClassificationResult("car", "Sedan", 0.5, False, {}, 1.0)
        assert r2.to_context_string() == "Vehicle type: Sedan (50% confidence)"

    def test_pet_string(self) -> None:
        r = PetClassificationResult("dog", "lab", 0.7, True, 1.0)
        assert r.to_context_string() == "Household pet detected: dog (70% confidence)"

    def test_clothing_classification_three_branches(self) -> None:
        base = {
            "clothing_type": "hoodie",
            "color": "black",
            "style": "casual",
            "confidence": 0.9,
            "top_category": "upper",
            "description": "dark hoodie",
            "inference_time_ms": 1.0,
        }
        susp = ClothingClassificationResult(**base, is_suspicious=True, is_service_uniform=False)
        assert susp.to_context_string() == (
            "Clothing: dark hoodie\n"
            "  [ALERT: Potentially suspicious attire detected]\n"
            "  Confidence: 90.0%"
        )
        uniform = ClothingClassificationResult(**base, is_suspicious=False, is_service_uniform=True)
        assert uniform.to_context_string() == (
            "Clothing: dark hoodie\n"
            "  [Service/delivery worker uniform detected]\n"
            "  Confidence: 90.0%"
        )
        neither = ClothingClassificationResult(
            **base, is_suspicious=False, is_service_uniform=False
        )
        assert neither.to_context_string() == ("Clothing: dark hoodie\n  Confidence: 90.0%")
        # suspicious WINS over uniform (elif order)
        both = ClothingClassificationResult(**base, is_suspicious=True, is_service_uniform=True)
        assert both.to_context_string() == (
            "Clothing: dark hoodie\n"
            "  [ALERT: Potentially suspicious attire detected]\n"
            "  Confidence: 90.0%"
        )

    def test_action_classification_alert_and_risk(self) -> None:
        susp = ActionClassificationResult("loitering", 0.9, True, 0.8, {}, 1.0)
        assert susp.to_context_string() == (
            "Detected action: loitering\n"
            "  [ALERT: Suspicious behavior detected - risk weight 80%]\n"
            "  Confidence: 90.0%"
        )
        calm = ActionClassificationResult("walking", 0.5, False, 0.3, {}, 1.0)
        assert calm.to_context_string() == (
            "Detected action: walking\n  Risk weight: 30%\n  Confidence: 50.0%"
        )

    def test_pose_analysis_alert_branches(self) -> None:
        expected = {
            "crouching": "  [ALERT: Person crouching - potential hiding/break-in]",
            "lying_down": "  [ALERT: Person lying down - possible medical emergency]",
            "hands_raised": "  [ALERT: Hands raised - possible surrender/robbery]",
            "fighting_stance": "  [ALERT: Fighting stance detected - potential aggression]",
            "backflip": "  [ALERT: backflip]",  # else-branch echoes unknown alert
        }
        for alert, line in expected.items():
            r = PoseAnalysisResult(
                keypoints=[KeypointData("a", 0, 0, 0), KeypointData("b", 1, 1, 1)],
                posture="unknown",
                alerts=[alert],
                inference_time_ms=1.0,
            )
            assert r.to_context_string() == (
                "Person posture: unknown\n" + line + "\n  Keypoints detected: 2/17"
            )
        no_alert = PoseAnalysisResult([], "standing", [], 1.0)
        assert no_alert.to_context_string() == (
            "Person posture: standing\n  Keypoints detected: 0/17"
        )

    def test_unified_enrichment_context_order_and_gates(self) -> None:
        full = UnifiedEnrichmentResult(
            pose=UnifiedPoseResult([], "standing", 0.5, False),
            clothing=UnifiedClothingResult([{"category": "coat", "confidence": 0.5}], False),
            demographics=UnifiedDemographicsResult("30", 0.5, "female", 0.5),
            vehicle=UnifiedVehicleResult(None, None, None, "sedan", 0.5),
            threat=UnifiedThreatResult([{"type": "knife"}], True, "high"),
            action={"top_action": "running", "confidence": 0.5},
        )
        assert full.to_context_string() == "\n".join(
            [
                "THREAT DETECTED: knife (severity: high)",
                "Pose: standing (confidence: 50%)",
                "Demographics: female (50%), age 30 (50%)",
                "Clothing: coat (confidence: 50%)",
                "Vehicle: sedan (confidence: 50%)",
                "Action: running (confidence: 50%)",
            ]
        )
        # threat object present but INACTIVE -> no threat line (has_threat gate)
        inactive = UnifiedEnrichmentResult(
            threat=UnifiedThreatResult([], False, "none"),
        )
        assert inactive.to_context_string() == "No enrichment data available"
        # action dict missing keys -> 'unknown' / 0 defaults
        act = UnifiedEnrichmentResult(action={})
        assert act.to_context_string() == "Action: unknown (confidence: 0%)"

    def test_depth_and_distance_strings(self) -> None:
        # to_dict-only clusters per feed, but strings pin the f-format too
        d = DepthEstimationResult("", 0.25, 0.75, 0.5, 1.0)
        assert d.to_context_string() == "Scene depth: avg=0.50 (min=0.25, max=0.75)"
        o = ObjectDistanceResult(4.25, 0.4, "close", 1.0)
        assert o.to_context_string() == "Object distance: ~4.2m (close)"
        assert o.is_close() is True
        far = ObjectDistanceResult(10.0, 0.9, "far", 1.0)
        assert far.is_close() is False


class TestHasSecurityAlertsTruthTable:
    """Boolean gates: every operand flips a whole-result verdict."""

    @pytest.mark.parametrize(
        ("threat", "pose_suspicious", "clothing_suspicious", "want"),
        [
            (None, None, None, False),
            (True, None, None, True),
            (False, None, None, False),
            (None, True, None, True),
            (None, False, None, False),
            (None, None, True, True),
            (None, None, False, False),
            (False, False, True, True),
        ],
    )
    def test_unified_enrichment(self, threat, pose_suspicious, clothing_suspicious, want):
        r = UnifiedEnrichmentResult(
            threat=None if threat is None else UnifiedThreatResult([], threat, "none"),
            pose=None
            if pose_suspicious is None
            else UnifiedPoseResult([], "p", 0.0, pose_suspicious),
            clothing=None
            if clothing_suspicious is None
            else UnifiedClothingResult([], clothing_suspicious),
        )
        assert r.has_security_alerts() is want

    @pytest.mark.parametrize(
        ("suspicious", "risk", "want"),
        [
            (False, 0.0, False),
            (True, 0.0, True),
            (False, 0.69, False),
            (False, 0.7, True),
            (False, 0.71, True),
        ],
    )
    def test_action_boundary_at_seven_tenths(self, suspicious, risk, want) -> None:
        r = ActionClassificationResult("a", 0.5, suspicious, risk, {}, 1.0)
        assert r.has_security_alerts() is want

    def test_pose_analysis_alerts_len(self) -> None:
        assert PoseAnalysisResult([], "s", [], 1.0).has_security_alerts() is False
        assert PoseAnalysisResult([], "s", ["anything"], 1.0).has_security_alerts() is True


class TestBackoffDelay:
    """_calculate_backoff_delay: base 2**attempt, +/-10% jitter, cap 30s."""

    @staticmethod
    def _stub_jitter(monkeypatch, value: float) -> list[tuple[float, float]]:
        """Patch the module's random.uniform to return `value`, recording calls."""
        import backend.services.enrichment_client as ec

        calls: list[tuple[float, float]] = []

        def fake_uniform(lo: float, hi: float) -> float:
            calls.append((lo, hi))
            return value

        monkeypatch.setattr(ec.random, "uniform", fake_uniform)
        return calls

    @pytest.mark.parametrize(
        ("attempt", "jitter", "want"),
        [
            (0, 0.0, 1.0),
            (1, 0.0, 2.0),
            (2, 0.0, 4.0),
            (3, 0.0, 8.0),
            (4, 0.0, 16.0),  # not capped — pins min() (a max() flip gives 30)
            (2, 0.1, 4.4),
            (2, -0.1, 3.6),
            (5, 0.0, 30.0),  # 32 -> capped at exactly 30.0
            (10, 0.1, 30.0),
        ],
    )
    def test_exact_values(self, monkeypatch, attempt, jitter, want) -> None:
        self._stub_jitter(monkeypatch, jitter)
        assert bare_client()._calculate_backoff_delay(attempt) == want

    def test_jitter_range_is_ten_percent(self, monkeypatch) -> None:
        calls = self._stub_jitter(monkeypatch, 0.0)
        bare_client()._calculate_backoff_delay(0)
        assert calls == [(-0.1, 0.1)]


class TestIsRetryableError:
    """5xx boundary at 499/500 — shipped retry suite probes only 503/400, so
    >=500 -> >500 / >=499 flips hide in the gap (dossier cluster 9-adjacent)."""

    @staticmethod
    def _status_error(code: int) -> httpx.HTTPStatusError:
        req = httpx.Request("POST", "http://enrich.local/enrich")
        resp = httpx.Response(code, request=req)
        return httpx.HTTPStatusError("boom", request=req, response=resp)

    @pytest.mark.parametrize(
        ("error", "want"),
        [
            (httpx.ConnectError("down"), True),
            (httpx.TimeoutException("slow"), True),
            (_status_error(499), False),
            (_status_error(500), True),
            (_status_error(503), True),
            (_status_error(400), False),
            (ValueError("programming"), False),
        ],
    )
    def test_matrix(self, error, want) -> None:
        assert bare_client()._is_retryable_error(error) is want
