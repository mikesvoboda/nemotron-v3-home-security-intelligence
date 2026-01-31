"""Unit tests for scenario_classifier module.

Tests cover:
- Scenario classification from keywords, actions, and text
- Floor score application for property crimes
- Hysteresis at threshold boundaries
- Tailgating detection
- Complete risk score adjustment pipeline

See NEM-4522 for feature requirements.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from backend.services.scenario_classifier import (
    DEFAULT_HYSTERESIS,
    SCENARIO_FLOOR_SCORES,
    HysteresisConfig,
    ScenarioType,
    adjust_risk_score,
    apply_hysteresis,
    apply_scenario_floor,
    classify_scenario,
    detect_tailgating,
    get_scenario_floor_score,
)


class TestScenarioType:
    """Tests for ScenarioType enum."""

    def test_graffiti_type_exists(self) -> None:
        """Verify GRAFFITI scenario type exists."""
        assert ScenarioType.GRAFFITI == "graffiti"

    def test_tailgating_type_exists(self) -> None:
        """Verify TAILGATING scenario type exists."""
        assert ScenarioType.TAILGATING == "tailgating"

    def test_vandalism_type_exists(self) -> None:
        """Verify VANDALISM scenario type exists."""
        assert ScenarioType.VANDALISM == "vandalism"

    def test_all_scenario_types_have_floor_scores(self) -> None:
        """Verify all non-UNCLASSIFIED scenarios have floor score configs."""
        for scenario_type in ScenarioType:
            if scenario_type != ScenarioType.UNCLASSIFIED:
                assert scenario_type in SCENARIO_FLOOR_SCORES, (
                    f"Missing floor score config for {scenario_type}"
                )


class TestScenarioFloorScores:
    """Tests for SCENARIO_FLOOR_SCORES configuration."""

    def test_graffiti_floor_score_is_high(self) -> None:
        """Graffiti should have HIGH floor score (65+)."""
        config = SCENARIO_FLOOR_SCORES[ScenarioType.GRAFFITI]
        assert config.floor_score >= 65
        assert "graffiti" in config.keywords

    def test_tailgating_floor_score_is_medium(self) -> None:
        """Tailgating should have MEDIUM floor score (55+)."""
        config = SCENARIO_FLOOR_SCORES[ScenarioType.TAILGATING]
        assert config.floor_score >= 55
        assert "tailgat" in config.keywords

    def test_vandalism_floor_score_is_high(self) -> None:
        """Vandalism should have HIGH floor score (65+)."""
        config = SCENARIO_FLOOR_SCORES[ScenarioType.VANDALISM]
        assert config.floor_score >= 65
        assert "vandalism" in config.keywords

    def test_vehicle_tampering_floor_score(self) -> None:
        """Vehicle tampering should have HIGH floor score."""
        config = SCENARIO_FLOOR_SCORES[ScenarioType.VEHICLE_TAMPERING]
        assert config.floor_score >= 60
        assert "checking car doors" in config.keywords

    def test_all_configs_have_required_fields(self) -> None:
        """All floor score configs must have keywords and description."""
        for scenario_type, config in SCENARIO_FLOOR_SCORES.items():
            assert config.scenario_type == scenario_type
            assert config.floor_score >= 0
            assert config.floor_score <= 100
            assert len(config.keywords) > 0
            assert config.description


class TestClassifyScenario:
    """Tests for classify_scenario function."""

    def test_classify_graffiti_from_summary(self) -> None:
        """Graffiti mentioned in summary should be classified."""
        scenarios = classify_scenario(summary="Person detected spraying graffiti on wall")
        assert ScenarioType.GRAFFITI in scenarios

    def test_classify_graffiti_from_reasoning(self) -> None:
        """Graffiti mentioned in reasoning should be classified."""
        scenarios = classify_scenario(
            reasoning="The person appears to be spray painting on the fence"
        )
        assert ScenarioType.GRAFFITI in scenarios

    def test_classify_vandalism_from_keywords(self) -> None:
        """Vandalism keywords should trigger classification."""
        scenarios = classify_scenario(summary="Person smashing windows of parked vehicle")
        assert ScenarioType.VANDALISM in scenarios

    def test_classify_tailgating_from_action(self) -> None:
        """Tailgating action should trigger classification."""
        scenarios = classify_scenario(action_result={"detected_action": "tailgating through door"})
        assert ScenarioType.TAILGATING in scenarios

    def test_classify_vehicle_tampering_from_action(self) -> None:
        """Vehicle tampering action should trigger classification."""
        scenarios = classify_scenario(action_result={"detected_action": "checking_car_doors"})
        assert ScenarioType.VEHICLE_TAMPERING in scenarios

    def test_classify_from_detection_object_type(self) -> None:
        """Detection object types should be searched for keywords."""
        scenarios = classify_scenario(detections=[{"object_type": "spray can", "label": "tool"}])
        # spray is in graffiti keywords
        assert ScenarioType.GRAFFITI in scenarios

    def test_classify_multiple_scenarios(self) -> None:
        """Multiple scenarios can be identified from rich context."""
        scenarios = classify_scenario(
            summary="Person with spray paint vandalizing property",
            reasoning="Clear vandalism and graffiti activity",
        )
        assert ScenarioType.GRAFFITI in scenarios
        assert ScenarioType.VANDALISM in scenarios

    def test_classify_returns_empty_for_normal_activity(self) -> None:
        """Normal activity should not classify any scenarios."""
        scenarios = classify_scenario(
            summary="Delivery driver dropping off package",
            reasoning="Routine delivery activity observed",
        )
        assert len(scenarios) == 0

    def test_classify_fence_climbing(self) -> None:
        """Fence climbing should be classified."""
        scenarios = classify_scenario(summary="Person climbing over fence into backyard")
        assert ScenarioType.FENCE_CLIMBING in scenarios

    def test_classify_case_insensitive(self) -> None:
        """Classification should be case insensitive."""
        scenarios = classify_scenario(summary="GRAFFITI DETECTED ON WALL")
        assert ScenarioType.GRAFFITI in scenarios


class TestGetScenarioFloorScore:
    """Tests for get_scenario_floor_score function."""

    def test_returns_zero_for_empty_list(self) -> None:
        """Empty scenario list should return 0."""
        assert get_scenario_floor_score([]) == 0

    def test_returns_single_floor_score(self) -> None:
        """Single scenario returns its floor score."""
        floor = get_scenario_floor_score([ScenarioType.GRAFFITI])
        expected = SCENARIO_FLOOR_SCORES[ScenarioType.GRAFFITI].floor_score
        assert floor == expected

    def test_returns_max_floor_for_multiple(self) -> None:
        """Multiple scenarios return the maximum floor score."""
        scenarios = [ScenarioType.TRESPASSING, ScenarioType.GRAFFITI]
        floor = get_scenario_floor_score(scenarios)
        # Graffiti (65) > Trespassing (45)
        assert floor == SCENARIO_FLOOR_SCORES[ScenarioType.GRAFFITI].floor_score


class TestApplyScenarioFloor:
    """Tests for apply_scenario_floor function."""

    def test_applies_floor_when_score_below(self) -> None:
        """Floor should be applied when raw score is below."""
        # Raw score 35, graffiti floor is 65
        adjusted, was_adjusted = apply_scenario_floor(35, [ScenarioType.GRAFFITI])
        assert was_adjusted is True
        assert adjusted == 65

    def test_no_change_when_score_above_floor(self) -> None:
        """No change when raw score is already above floor."""
        # Raw score 70, graffiti floor is 65
        adjusted, was_adjusted = apply_scenario_floor(70, [ScenarioType.GRAFFITI])
        assert was_adjusted is False
        assert adjusted == 70

    def test_no_change_for_empty_scenarios(self) -> None:
        """No change when no scenarios identified."""
        adjusted, was_adjusted = apply_scenario_floor(35, [])
        assert was_adjusted is False
        assert adjusted == 35

    def test_graffiti_never_scores_below_65(self) -> None:
        """Graffiti scenario should ALWAYS score at least 65."""
        # Test various raw scores
        for raw_score in [0, 25, 35, 50, 60, 64]:
            adjusted, _ = apply_scenario_floor(raw_score, [ScenarioType.GRAFFITI])
            assert adjusted >= 65, f"Raw score {raw_score} should be elevated to 65+"


class TestHysteresisConfig:
    """Tests for HysteresisConfig."""

    def test_default_boundaries(self) -> None:
        """Default boundaries should match severity thresholds."""
        config = DEFAULT_HYSTERESIS
        assert config.low_medium_boundary == 29
        assert config.medium_high_boundary == 59
        assert config.high_critical_boundary == 84
        assert config.buffer_size == 3

    def test_custom_config(self) -> None:
        """Custom config should be creatable."""
        config = HysteresisConfig(
            low_medium_boundary=25,
            medium_high_boundary=50,
            high_critical_boundary=75,
            buffer_size=5,
        )
        assert config.buffer_size == 5


class TestApplyHysteresis:
    """Tests for apply_hysteresis function."""

    def test_no_change_without_previous_score(self) -> None:
        """No hysteresis without previous score."""
        result = apply_hysteresis(31, None)
        assert result == 31

    def test_no_change_outside_buffer_zone(self) -> None:
        """No change when score is outside buffer zones."""
        # Score 50 is not near any boundary
        result = apply_hysteresis(50, 45)
        assert result == 50

    def test_prevents_upward_oscillation_at_low_medium(self) -> None:
        """Prevents crossing from LOW to MEDIUM within buffer."""
        # Previous was 27 (LOW), new is 31 (MEDIUM but in buffer)
        result = apply_hysteresis(31, 27)
        # Should stay at boundary (29) instead of crossing
        assert result == 29

    def test_prevents_downward_oscillation_at_low_medium(self) -> None:
        """Prevents crossing from MEDIUM to LOW within buffer."""
        # Previous was 32 (MEDIUM), new is 28 (LOW but in buffer)
        result = apply_hysteresis(28, 32)
        # Should stay at boundary+1 (30) instead of crossing
        assert result == 30

    def test_prevents_oscillation_at_medium_high(self) -> None:
        """Prevents oscillation at MEDIUM-HIGH boundary."""
        # Previous was 57 (MEDIUM), new is 61 (HIGH but in buffer)
        result = apply_hysteresis(61, 57)
        # Should stay at boundary (59) instead of crossing
        assert result == 59

    def test_prevents_oscillation_at_high_critical(self) -> None:
        """Prevents oscillation at HIGH-CRITICAL boundary."""
        # Previous was 82 (HIGH), new is 86 (CRITICAL but in buffer)
        result = apply_hysteresis(86, 82)
        # Should stay at boundary (84) instead of crossing
        assert result == 84

    def test_allows_large_changes(self) -> None:
        """Large score changes should pass through when outside buffer zones."""
        # Previous was 20 (LOW), new is 70 (HIGH) - well outside buffer
        result = apply_hysteresis(70, 20)
        assert result == 70

        # Also test crossing multiple boundaries
        result = apply_hysteresis(90, 10)
        assert result == 90

    def test_custom_buffer_size(self) -> None:
        """Custom buffer size should be respected."""
        config = HysteresisConfig(
            low_medium_boundary=29,
            medium_high_boundary=59,
            high_critical_boundary=84,
            buffer_size=5,  # Larger buffer
        )
        # Previous was 24 (LOW), new is 33 (MEDIUM but in 5-point buffer)
        result = apply_hysteresis(33, 24, config)
        # Should stay at boundary with larger buffer
        assert result == 29


class TestDetectTailgating:
    """Tests for detect_tailgating function."""

    def test_no_tailgating_with_single_person(self) -> None:
        """Single person should not trigger tailgating."""
        detections = [{"object_type": "person", "detected_at": datetime.now()}]
        result = detect_tailgating(detections)
        assert result.detected is False

    def test_detects_rapid_succession_entries(self) -> None:
        """Multiple persons entering quickly should trigger tailgating."""
        now = datetime.now()
        detections = [
            {"object_type": "person", "detected_at": now},
            {"object_type": "person", "detected_at": now + timedelta(seconds=2)},
        ]
        result = detect_tailgating(detections)
        assert result.detected is True
        assert result.persons_involved == 2
        assert result.confidence > 0.5

    def test_no_tailgating_with_large_gap(self) -> None:
        """Large time gap between persons should not trigger tailgating."""
        now = datetime.now()
        detections = [
            {"object_type": "person", "detected_at": now},
            {"object_type": "person", "detected_at": now + timedelta(seconds=30)},
        ]
        result = detect_tailgating(detections)
        assert result.detected is False

    def test_higher_confidence_at_entry_zone(self) -> None:
        """Entry point zones should boost confidence."""
        now = datetime.now()
        detections = [
            {"object_type": "person", "detected_at": now},
            {"object_type": "person", "detected_at": now + timedelta(seconds=3)},
        ]
        result_no_zone = detect_tailgating(detections, zone_type=None)
        result_entry = detect_tailgating(detections, zone_type="entry_point")

        assert result_entry.confidence > result_no_zone.confidence

    def test_ignores_non_person_detections(self) -> None:
        """Non-person detections should be ignored."""
        now = datetime.now()
        detections = [
            {"object_type": "car", "detected_at": now},
            {"object_type": "car", "detected_at": now + timedelta(seconds=2)},
        ]
        result = detect_tailgating(detections)
        assert result.detected is False

    def test_multiple_persons_increases_confidence(self) -> None:
        """More persons in succession should increase confidence."""
        now = datetime.now()
        detections_2 = [
            {"object_type": "person", "detected_at": now},
            {"object_type": "person", "detected_at": now + timedelta(seconds=2)},
        ]
        detections_3 = [
            {"object_type": "person", "detected_at": now},
            {"object_type": "person", "detected_at": now + timedelta(seconds=2)},
            {"object_type": "person", "detected_at": now + timedelta(seconds=4)},
        ]

        result_2 = detect_tailgating(detections_2)
        result_3 = detect_tailgating(detections_3)

        assert result_3.persons_involved > result_2.persons_involved
        assert result_3.confidence >= result_2.confidence


class TestAdjustRiskScore:
    """Tests for the complete adjust_risk_score pipeline."""

    def test_graffiti_adjusts_to_floor(self) -> None:
        """Graffiti scenario should adjust score to floor."""
        adjusted, meta = adjust_risk_score(
            raw_score=35,
            summary="Person spraying graffiti on wall",
        )
        assert adjusted >= 65
        assert meta["floor_applied"] is True
        assert "graffiti" in meta["scenarios"]

    def test_tailgating_adjusts_to_floor(self) -> None:
        """Tailgating scenario should adjust score."""
        adjusted, meta = adjust_risk_score(
            raw_score=30,
            summary="Person tailgating through secure door",
        )
        assert adjusted >= 55
        assert "tailgating" in meta["scenarios"]

    def test_no_adjustment_for_normal_activity(self) -> None:
        """Normal activity should not be adjusted."""
        adjusted, meta = adjust_risk_score(
            raw_score=15,
            summary="Delivery driver dropping off package",
        )
        assert adjusted == 15
        assert meta["floor_applied"] is False
        assert len(meta["scenarios"]) == 0

    def test_preserves_high_scores(self) -> None:
        """Already high scores should not be reduced."""
        adjusted, meta = adjust_risk_score(
            raw_score=85,
            summary="Active break-in in progress",
        )
        assert adjusted == 85
        # May identify scenarios but not reduce score

    def test_returns_metadata(self) -> None:
        """Adjustment should return comprehensive metadata."""
        adjusted, meta = adjust_risk_score(
            raw_score=35,
            summary="Vandalism detected",
        )
        assert "original_score" in meta
        assert "scenarios" in meta
        assert "floor_applied" in meta
        assert "hysteresis_applied" in meta
        assert meta["original_score"] == 35

    def test_score_bounds_enforced(self) -> None:
        """Final score should always be 0-100."""
        # Even with extreme scenarios, score should be bounded
        adjusted, _ = adjust_risk_score(
            raw_score=150,  # Invalid raw score
            summary="Test scenario",
        )
        assert 0 <= adjusted <= 100

    def test_hysteresis_disabled_by_default(self) -> None:
        """Hysteresis should respect the disable flag."""
        adjusted, meta = adjust_risk_score(
            raw_score=31,
            previous_score=27,
            apply_hysteresis_adjustment=False,
        )
        # Without hysteresis, score should not be adjusted for boundary
        assert meta["hysteresis_applied"] is False

    def test_action_result_triggers_classification(self) -> None:
        """Action recognition results should trigger classification."""
        adjusted, meta = adjust_risk_score(
            raw_score=40,
            action_result={"detected_action": "a person vandalizing property"},
        )
        assert "vandalism" in meta["scenarios"]

    def test_combined_detection_and_summary(self) -> None:
        """Both detection data and summary should be searched."""
        adjusted, meta = adjust_risk_score(
            raw_score=30,
            detections=[{"object_type": "person", "label": "trespasser"}],
            summary="Unauthorized person on property",
        )
        # Should identify trespassing from keywords
        assert "trespassing" in meta["scenarios"] or "unauthorized_access" in meta["scenarios"]


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_inputs(self) -> None:
        """Empty inputs should not crash."""
        adjusted, meta = adjust_risk_score(
            raw_score=50,
            detections=None,
            action_result=None,
            summary=None,
            reasoning=None,
        )
        assert adjusted == 50
        assert meta["original_score"] == 50

    def test_none_detection_fields(self) -> None:
        """None fields in detections should be handled."""
        adjusted, meta = adjust_risk_score(
            raw_score=50,
            detections=[{"object_type": None, "label": None}],
        )
        assert adjusted == 50

    def test_empty_strings(self) -> None:
        """Empty strings should not trigger false positives."""
        adjusted, meta = adjust_risk_score(
            raw_score=20,
            summary="",
            reasoning="",
        )
        assert len(meta["scenarios"]) == 0

    def test_score_at_exact_boundary(self) -> None:
        """Score exactly at boundary should be handled correctly."""
        # Score at exactly 29 (LOW/MEDIUM boundary)
        adjusted, meta = adjust_risk_score(
            raw_score=29,
            previous_score=25,
            apply_hysteresis_adjustment=True,
        )
        # Should not trigger hysteresis since not crossing
        assert adjusted == 29

    def test_floor_score_exactly_at_current(self) -> None:
        """Floor score equal to current should not be marked as adjusted."""
        adjusted, meta = apply_scenario_floor(65, [ScenarioType.GRAFFITI])
        assert adjusted == 65
        assert meta is False  # was_adjusted should be False


class TestPropertyCrimeConsistency:
    """Tests ensuring property crimes are consistently scored.

    This addresses NEM-4522: graffiti scenarios were inconsistently
    scored (sometimes 35, sometimes 70).
    """

    def test_graffiti_always_high_risk(self) -> None:
        """Graffiti should ALWAYS be classified as HIGH risk (60+)."""
        test_cases = [
            "graffiti on wall",
            "spray painting property",
            "tagging the fence",
            "person with spray can",
            "defacing building",
        ]
        for summary in test_cases:
            adjusted, _ = adjust_risk_score(raw_score=35, summary=summary)
            assert adjusted >= 60, f"'{summary}' should score >= 60, got {adjusted}"

    def test_vandalism_always_high_risk(self) -> None:
        """Vandalism should ALWAYS be classified as HIGH risk (65+)."""
        test_cases = [
            "vandalism detected",
            "smashing windows",
            "destroying property",
            "damaging vehicle",
        ]
        for summary in test_cases:
            adjusted, _ = adjust_risk_score(raw_score=40, summary=summary)
            assert adjusted >= 60, f"'{summary}' should score >= 60, got {adjusted}"

    def test_vehicle_tampering_always_elevated(self) -> None:
        """Vehicle tampering should ALWAYS be elevated risk (65+)."""
        test_cases = [
            "checking car doors",
            "trying door handles",
            "tampering with vehicle",
        ]
        for summary in test_cases:
            adjusted, _ = adjust_risk_score(raw_score=30, summary=summary)
            assert adjusted >= 65, f"'{summary}' should score >= 65, got {adjusted}"


class TestTailgatingEscalation:
    """Tests ensuring tailgating is properly escalated.

    This addresses NEM-4522: tailgating scenarios not escalated appropriately.
    """

    def test_tailgating_keyword_escalation(self) -> None:
        """Tailgating keyword should trigger escalation."""
        adjusted, meta = adjust_risk_score(
            raw_score=25,
            summary="Person tailgating through secure entrance",
        )
        assert adjusted >= 55
        assert "tailgating" in meta["scenarios"]

    def test_piggybacking_escalation(self) -> None:
        """Piggybacking should trigger escalation."""
        adjusted, meta = adjust_risk_score(
            raw_score=25,
            summary="Unauthorized person piggybacking through door",
        )
        assert adjusted >= 55
        assert "piggybacking" in meta["scenarios"]

    def test_rapid_entry_detection_escalation(self) -> None:
        """Rapid successive entries should escalate via tailgating detection."""
        now = datetime.now()
        detections = [
            {"object_type": "person", "detected_at": now},
            {"object_type": "person", "detected_at": now + timedelta(seconds=2)},
            {"object_type": "person", "detected_at": now + timedelta(seconds=4)},
        ]
        adjusted, meta = adjust_risk_score(
            raw_score=25,
            detections=detections,
            zone_type="entry_point",
        )
        # Should detect tailgating from rapid succession
        assert meta.get("tailgating") is not None or adjusted > 25
