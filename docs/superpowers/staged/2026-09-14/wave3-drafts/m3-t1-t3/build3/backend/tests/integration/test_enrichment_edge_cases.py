"""Integration tests for enrichment pipeline edge case scenarios.

These tests verify that enrichment edge case scenarios are correctly generated
and structured for testing model zoo orchestration, VRAM management, circuit
breaker behavior, and graceful degradation.

The scenarios themselves serve as fixtures for manual and automated testing of:
- Multi-threat detection (multiple simultaneous threats)
- Rare pose scenarios (unusual body postures)
- Boundary confidence scenarios (decision threshold testing)
- OCR failure scenarios (unreadable plates, error handling)
- VRAM stress scenarios (many models simultaneously)
- Circuit breaker behavior (failure recovery)
- Graceful degradation (partial results on model failures)

These tests focus on scenario quality and structure, not on actual enrichment
logic (which is tested in unit tests for the enrichment pipeline itself).
"""

from __future__ import annotations

import pytest
from tools.nemo_data_designer.enrichment_scenarios import (
    generate_boundary_confidence_scenarios,
    generate_multi_threat_scenarios,
    generate_ocr_failure_scenarios,
    generate_rare_pose_scenarios,
    generate_vram_stress_scenarios,
)


@pytest.mark.integration
@pytest.mark.enrichment
class TestMultipleThreatScenarios:
    """Test generation and structure of multi-threat scenarios."""

    def test_generates_correct_count(self):
        """Should generate exactly the requested number of scenarios."""
        scenarios = generate_multi_threat_scenarios(count=10)
        assert len(scenarios) == 10

    def test_all_have_multiple_detections(self):
        """All scenarios should have multiple detections."""
        scenarios = generate_multi_threat_scenarios(count=5)
        for scenario in scenarios:
            assert len(scenario.detections) >= 2, (
                f"Scenario {scenario.scenario_id} has too few detections"
            )

    def test_all_are_threats_or_suspicious(self):
        """All scenarios should be classified as threat or suspicious."""
        scenarios = generate_multi_threat_scenarios(count=5)
        for scenario in scenarios:
            assert scenario.scenario_type in ("threat", "suspicious"), (
                f"Scenario {scenario.scenario_id} has wrong type: {scenario.scenario_type}"
            )

    def test_all_should_trigger_alerts(self):
        """All multi-threat scenarios should trigger alerts."""
        scenarios = generate_multi_threat_scenarios(count=5)
        for scenario in scenarios:
            assert scenario.ground_truth.should_trigger_alert is True, (
                f"Scenario {scenario.scenario_id} should trigger alert"
            )

    def test_has_high_risk_scores(self):
        """All scenarios should have high risk score ranges."""
        scenarios = generate_multi_threat_scenarios(count=5)
        for scenario in scenarios:
            min_score, max_score = scenario.ground_truth.risk_range
            assert min_score >= 55, (
                f"Scenario {scenario.scenario_id} has too low min risk: {min_score}"
            )
            assert max_score >= 75, (
                f"Scenario {scenario.scenario_id} has too low max risk: {max_score}"
            )

    def test_specifies_expected_enrichment_models(self):
        """All scenarios should specify expected enrichment models."""
        scenarios = generate_multi_threat_scenarios(count=5)
        for scenario in scenarios:
            assert len(scenario.ground_truth.expected_enrichment_models) > 0, (
                f"Scenario {scenario.scenario_id} has no expected models"
            )


@pytest.mark.integration
@pytest.mark.enrichment
class TestRarePoseScenarios:
    """Test generation and structure of rare pose scenarios."""

    def test_generates_correct_count(self):
        """Should generate exactly the requested number of scenarios."""
        scenarios = generate_rare_pose_scenarios(count=10)
        assert len(scenarios) == 10

    def test_all_have_person_detections(self):
        """All scenarios should have at least one person detection."""
        scenarios = generate_rare_pose_scenarios(count=5)
        for scenario in scenarios:
            has_person = any(det.object_type == "person" for det in scenario.detections)
            assert has_person, f"Scenario {scenario.scenario_id} has no person detection"

    def test_all_mention_pose_in_reasoning(self):
        """All scenarios should mention pose-related keywords."""
        scenarios = generate_rare_pose_scenarios(count=5)
        for scenario in scenarios:
            # Check narrative or key points for pose-related terms
            narrative_lower = scenario.scenario_narrative.lower()
            key_points_lower = " ".join(scenario.ground_truth.reasoning_key_points).lower()
            has_pose_keyword = any(
                keyword in narrative_lower or keyword in key_points_lower
                for keyword in ["pose", "posture", "crouch", "climb", "crawl", "prone"]
            )
            assert has_pose_keyword, (
                f"Scenario {scenario.scenario_id} doesn't mention pose: {scenario.scenario_narrative}"
            )

    def test_all_include_pose_estimation_model(self):
        """All scenarios should expect pose estimation model."""
        scenarios = generate_rare_pose_scenarios(count=5)
        for scenario in scenarios:
            assert "pose_estimation" in scenario.ground_truth.expected_enrichment_models, (
                f"Scenario {scenario.scenario_id} doesn't include pose_estimation model"
            )


@pytest.mark.integration
@pytest.mark.enrichment
class TestBoundaryConfidenceScenarios:
    """Test generation and structure of boundary confidence scenarios."""

    def test_generates_correct_count(self):
        """Should generate exactly the requested number of scenarios."""
        scenarios = generate_boundary_confidence_scenarios(count=10)
        assert len(scenarios) == 10

    def test_all_have_low_confidence_detections(self):
        """All scenarios should have detections near confidence threshold."""
        scenarios = generate_boundary_confidence_scenarios(count=5)
        for scenario in scenarios:
            for det in scenario.detections:
                assert 0.50 <= det.confidence <= 0.55, (
                    f"Scenario {scenario.scenario_id} detection has confidence {det.confidence} outside boundary range"
                )

    def test_all_are_edge_cases(self):
        """All scenarios should be classified as edge cases."""
        scenarios = generate_boundary_confidence_scenarios(count=5)
        for scenario in scenarios:
            assert scenario.scenario_type == "edge_case", (
                f"Scenario {scenario.scenario_id} has wrong type: {scenario.scenario_type}"
            )

    def test_risk_scores_in_medium_range(self):
        """Edge cases should have medium risk scores."""
        scenarios = generate_boundary_confidence_scenarios(count=5)
        for scenario in scenarios:
            min_score, max_score = scenario.ground_truth.risk_range
            assert 20 <= min_score <= 50, (
                f"Scenario {scenario.scenario_id} has unexpected min risk: {min_score}"
            )
            assert 30 <= max_score <= 60, (
                f"Scenario {scenario.scenario_id} has unexpected max risk: {max_score}"
            )


@pytest.mark.integration
@pytest.mark.enrichment
class TestOCRFailureScenarios:
    """Test generation and structure of OCR failure scenarios."""

    def test_generates_correct_count(self):
        """Should generate exactly the requested number of scenarios."""
        scenarios = generate_ocr_failure_scenarios(count=10)
        assert len(scenarios) == 10

    def test_all_have_vehicle_detections(self):
        """All scenarios should have vehicle detections that would trigger OCR."""
        scenarios = generate_ocr_failure_scenarios(count=5)
        for scenario in scenarios:
            has_vehicle = any(
                det.object_type in ("car", "truck", "bus", "motorcycle")
                for det in scenario.detections
            )
            assert has_vehicle, f"Scenario {scenario.scenario_id} has no vehicle detection"

    def test_all_expect_ocr_model(self):
        """All scenarios should expect OCR in enrichment models."""
        scenarios = generate_ocr_failure_scenarios(count=5)
        for scenario in scenarios:
            assert "ocr" in scenario.ground_truth.expected_enrichment_models, (
                f"Scenario {scenario.scenario_id} doesn't include OCR model"
            )

    def test_narratives_mention_plate_issues(self):
        """All scenarios should mention plate readability issues."""
        scenarios = generate_ocr_failure_scenarios(count=5)
        for scenario in scenarios:
            narrative_lower = scenario.scenario_narrative.lower()
            has_plate_issue = any(
                keyword in narrative_lower
                for keyword in ["blur", "obscured", "covered", "unreadable", "lighting", "plate"]
            )
            assert has_plate_issue, (
                f"Scenario {scenario.scenario_id} doesn't mention plate issue: {scenario.scenario_narrative}"
            )


@pytest.mark.integration
@pytest.mark.enrichment
class TestVRAMStressScenarios:
    """Test generation and structure of VRAM stress scenarios."""

    def test_generates_correct_count(self):
        """Should generate exactly the requested number of scenarios."""
        scenarios = generate_vram_stress_scenarios(count=5)
        assert len(scenarios) == 5

    def test_all_have_many_detections(self):
        """All scenarios should have many detections."""
        scenarios = generate_vram_stress_scenarios(count=3)
        for scenario in scenarios:
            assert len(scenario.detections) >= 4, (
                f"Scenario {scenario.scenario_id} has too few detections: {len(scenario.detections)}"
            )

    def test_all_require_many_models(self):
        """All scenarios should require many enrichment models."""
        scenarios = generate_vram_stress_scenarios(count=3)
        for scenario in scenarios:
            model_count = len(scenario.ground_truth.expected_enrichment_models)
            assert model_count >= 5, (
                f"Scenario {scenario.scenario_id} requires too few models: {model_count}"
            )

    def test_all_have_mixed_detection_types(self):
        """All scenarios should have diverse detection types."""
        scenarios = generate_vram_stress_scenarios(count=3)
        for scenario in scenarios:
            detection_types = {det.object_type for det in scenario.detections}
            assert len(detection_types) >= 2, (
                f"Scenario {scenario.scenario_id} lacks detection diversity: {detection_types}"
            )

    def test_all_have_high_risk_or_suspicious(self):
        """VRAM stress scenarios should be high-risk situations."""
        scenarios = generate_vram_stress_scenarios(count=3)
        for scenario in scenarios:
            assert scenario.scenario_type in ("threat", "suspicious"), (
                f"Scenario {scenario.scenario_id} has wrong type: {scenario.scenario_type}"
            )


@pytest.mark.integration
@pytest.mark.enrichment
class TestScenarioStructureValidation:
    """Test that all scenario types have valid structure."""

    @pytest.mark.parametrize(
        "generator_fn,count",
        [
            (generate_multi_threat_scenarios, 3),
            (generate_rare_pose_scenarios, 3),
            (generate_boundary_confidence_scenarios, 3),
            (generate_ocr_failure_scenarios, 3),
            (generate_vram_stress_scenarios, 2),
        ],
    )
    def test_all_scenarios_have_required_fields(self, generator_fn, count):
        """All scenarios should have all required fields populated."""
        scenarios = generator_fn(count=count)
        for scenario in scenarios:
            # Basic scenario fields
            assert scenario.scenario_id
            assert scenario.time_of_day
            assert scenario.day_type
            assert scenario.camera_location
            assert scenario.scenario_type
            assert scenario.enrichment_level

            # Must have detections
            assert len(scenario.detections) > 0

            # Ground truth must be complete
            assert len(scenario.ground_truth.risk_range) == 2
            assert scenario.ground_truth.risk_range[0] <= scenario.ground_truth.risk_range[1]
            assert 0 <= scenario.ground_truth.risk_range[0] <= 100
            assert 0 <= scenario.ground_truth.risk_range[1] <= 100

            # Must have narrative
            assert scenario.scenario_narrative
            assert len(scenario.scenario_narrative) > 0

    @pytest.mark.parametrize(
        "generator_fn,count",
        [
            (generate_multi_threat_scenarios, 3),
            (generate_rare_pose_scenarios, 3),
            (generate_boundary_confidence_scenarios, 3),
            (generate_ocr_failure_scenarios, 3),
            (generate_vram_stress_scenarios, 2),
        ],
    )
    def test_all_detections_have_valid_structure(self, generator_fn, count):
        """All detections should have valid bounding boxes and metadata."""
        scenarios = generator_fn(count=count)
        for scenario in scenarios:
            for det in scenario.detections:
                # Valid confidence
                assert 0.5 <= det.confidence <= 1.0, (
                    f"Detection confidence {det.confidence} out of range"
                )

                # Valid bbox
                assert len(det.bbox) == 4
                x, y, w, h = det.bbox
                assert x >= 0 and y >= 0 and w > 0 and h > 0

                # Valid timestamp
                assert 0 <= det.timestamp_offset_seconds <= 90

                # Valid object type
                assert det.object_type in (
                    "person",
                    "car",
                    "truck",
                    "dog",
                    "cat",
                    "bicycle",
                    "motorcycle",
                    "bus",
                )
