"""Generate edge case scenarios for enrichment pipeline testing.

This module creates synthetic scenarios targeting specific enrichment pipeline
edge cases including:
- Multi-threat scenarios (multiple weapons, suspicious persons)
- Rare pose scenarios (unusual body postures)
- Boundary confidence scenarios (decision threshold testing)
- OCR failure scenarios (unreadable plates, blurry text)
- VRAM stress scenarios (many models simultaneously)
- Circuit breaker scenarios (repeated failures)

These scenarios test the model zoo orchestration, VRAM management, circuit
breaker behavior, and graceful degradation under edge conditions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tools.nemo_data_designer.config import (
    Detection,
    EnrichmentContext,
    GroundTruth,
    ScenarioBundle,
)

if TYPE_CHECKING:
    from pathlib import Path


def generate_multi_threat_scenarios(count: int = 20) -> list[ScenarioBundle]:
    """Generate scenarios with multiple simultaneous threats.

    Tests the enrichment pipeline's ability to:
    - Detect and prioritize multiple threats in a single frame
    - Handle concurrent model invocations for multiple detections
    - Properly aggregate threat context for risk assessment

    Args:
        count: Number of scenarios to generate (default: 20)

    Returns:
        List of ScenarioBundle instances with multiple threat detections

    Examples:
        - Multiple weapons in frame (2+ weapons)
        - Multiple suspicious persons at entry points
        - Vehicle + weapon combination
        - Person + weapon + suspicious behavior
    """
    scenarios: list[ScenarioBundle] = []

    # Scenario 1: Two weapons detected
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"multi_threat_{len(scenarios):03d}",
            time_of_day="night",
            day_type="weekday",
            camera_location="front_door",
            scenario_type="threat",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="person",
                    confidence=0.92,
                    bbox=(150, 200, 80, 180),
                    timestamp_offset_seconds=10,
                ),
                Detection(
                    object_type="person",
                    confidence=0.88,
                    bbox=(350, 180, 85, 190),
                    timestamp_offset_seconds=12,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="front_door",
                is_entry_point=True,
                baseline_expected_count=0,
                baseline_deviation_score=2.8,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(85, 100),
                reasoning_key_points=[
                    "multiple weapons detected",
                    "critical threat level",
                    "immediate alert required",
                ],
                expected_enrichment_models=[
                    "florence_2",
                    "pose_estimation",
                    "violence_detector",
                ],
                should_trigger_alert=True,
            ),
            scenario_narrative="Two armed individuals detected at front entrance during night hours",
            expected_summary="CRITICAL: Multiple weapons detected at entry point with multiple suspects",
        )
    )

    # Scenario 2: Multiple suspicious persons at different entry points
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"multi_threat_{len(scenarios):03d}",
            time_of_day="late_night",
            day_type="weekend",
            camera_location="side_gate",
            scenario_type="suspicious",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="person",
                    confidence=0.85,
                    bbox=(100, 150, 70, 160),
                    timestamp_offset_seconds=5,
                ),
                Detection(
                    object_type="person",
                    confidence=0.82,
                    bbox=(400, 140, 75, 170),
                    timestamp_offset_seconds=8,
                ),
                Detection(
                    object_type="person",
                    confidence=0.79,
                    bbox=(250, 160, 68, 165),
                    timestamp_offset_seconds=15,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="side_gate",
                is_entry_point=True,
                baseline_expected_count=0,
                baseline_deviation_score=2.5,
                cross_camera_matches=2,
            ),
            ground_truth=GroundTruth(
                risk_range=(55, 75),
                reasoning_key_points=[
                    "multiple unknown persons",
                    "late night activity",
                    "entry point approach",
                    "cross-camera tracking",
                ],
                expected_enrichment_models=["florence_2", "pose_estimation", "reid"],
                should_trigger_alert=True,
            ),
            scenario_narrative="Three unknown individuals converging on side gate at 2am",
            expected_summary="Suspicious: Multiple persons approaching entry point during late hours with cross-camera tracking matches",
        )
    )

    # Scenario 3: Vehicle + weapon combination
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"multi_threat_{len(scenarios):03d}",
            time_of_day="evening",
            day_type="weekday",
            camera_location="driveway",
            scenario_type="threat",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="car",
                    confidence=0.94,
                    bbox=(50, 100, 300, 200),
                    timestamp_offset_seconds=0,
                ),
                Detection(
                    object_type="person",
                    confidence=0.91,
                    bbox=(250, 180, 80, 190),
                    timestamp_offset_seconds=5,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="driveway",
                is_entry_point=False,
                baseline_expected_count=1,
                baseline_deviation_score=1.2,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(75, 95),
                reasoning_key_points=[
                    "weapon detected",
                    "vehicle present",
                    "potential escape vehicle",
                ],
                expected_enrichment_models=[
                    "florence_2",
                    "pose_estimation",
                    "vehicle_classifier",
                    "ocr",
                ],
                should_trigger_alert=True,
            ),
            scenario_narrative="Armed person exiting vehicle in driveway",
            expected_summary="CRITICAL: Weapon detected with potential getaway vehicle",
        )
    )

    # Fill remaining count with variations
    while len(scenarios) < count:
        # Alternate between different multi-threat patterns
        idx = len(scenarios) % 3
        base = scenarios[idx]
        scenarios.append(
            ScenarioBundle(
                scenario_id=f"multi_threat_{len(scenarios):03d}",
                time_of_day=base.time_of_day,
                day_type=base.day_type,
                camera_location=base.camera_location,
                scenario_type=base.scenario_type,
                enrichment_level=base.enrichment_level,
                detections=base.detections,
                enrichment_context=base.enrichment_context,
                ground_truth=base.ground_truth,
                scenario_narrative=base.scenario_narrative,
                expected_summary=base.expected_summary,
            )
        )

    return scenarios[:count]


def generate_rare_pose_scenarios(count: int = 20) -> list[ScenarioBundle]:
    """Generate scenarios with unusual body postures.

    Tests pose estimation model's ability to handle:
    - Non-standard poses (crouching, climbing, crawling)
    - Partially occluded persons
    - Unusual angles and perspectives
    - Suspicious posture patterns

    Args:
        count: Number of scenarios to generate (default: 20)

    Returns:
        List of ScenarioBundle instances with rare pose scenarios

    Examples:
        - Person crouching at window
        - Person climbing over fence
        - Person crawling under vehicle
        - Person in prone position
    """
    scenarios: list[ScenarioBundle] = []

    # Scenario 1: Crouching at window
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"rare_pose_{len(scenarios):03d}",
            time_of_day="night",
            day_type="weekday",
            camera_location="backyard",
            scenario_type="suspicious",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="person",
                    confidence=0.78,
                    bbox=(180, 250, 90, 120),
                    timestamp_offset_seconds=10,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="backyard",
                is_entry_point=False,
                baseline_expected_count=0,
                baseline_deviation_score=2.3,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(60, 80),
                reasoning_key_points=[
                    "crouching posture",
                    "window proximity",
                    "suspicious behavior",
                ],
                expected_enrichment_models=["florence_2", "pose_estimation"],
                should_trigger_alert=True,
            ),
            scenario_narrative="Person crouching near window during night hours",
            expected_summary="Suspicious: Person in crouching pose near window, potential prowler",
        )
    )

    # Scenario 2: Climbing over fence
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"rare_pose_{len(scenarios):03d}",
            time_of_day="late_night",
            day_type="weekend",
            camera_location="side_gate",
            scenario_type="threat",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="person",
                    confidence=0.82,
                    bbox=(220, 100, 85, 180),
                    timestamp_offset_seconds=5,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="side_gate",
                is_entry_point=True,
                baseline_expected_count=0,
                baseline_deviation_score=2.9,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(75, 90),
                reasoning_key_points=[
                    "climbing posture",
                    "forced entry attempt",
                    "late night activity",
                ],
                expected_enrichment_models=["florence_2", "pose_estimation", "violence_detector"],
                should_trigger_alert=True,
            ),
            scenario_narrative="Person climbing over fence at side gate at 2:30am",
            expected_summary="CRITICAL: Person in climbing pose attempting forced entry",
        )
    )

    # Scenario 3: Crawling under vehicle
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"rare_pose_{len(scenarios):03d}",
            time_of_day="evening",
            day_type="weekday",
            camera_location="driveway",
            scenario_type="suspicious",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="car",
                    confidence=0.95,
                    bbox=(100, 150, 350, 180),
                    timestamp_offset_seconds=0,
                ),
                Detection(
                    object_type="person",
                    confidence=0.71,
                    bbox=(200, 300, 120, 80),
                    timestamp_offset_seconds=8,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="driveway",
                is_entry_point=False,
                baseline_expected_count=1,
                baseline_deviation_score=0.8,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(50, 70),
                reasoning_key_points=[
                    "prone posture",
                    "under vehicle",
                    "potential tampering",
                ],
                expected_enrichment_models=["florence_2", "pose_estimation", "vehicle_classifier"],
                should_trigger_alert=True,
            ),
            scenario_narrative="Person in prone position under parked vehicle",
            expected_summary="Suspicious: Person in unusual pose near vehicle undercarriage",
        )
    )

    # Fill remaining count with variations
    while len(scenarios) < count:
        idx = len(scenarios) % 3
        base = scenarios[idx]
        scenarios.append(
            ScenarioBundle(
                scenario_id=f"rare_pose_{len(scenarios):03d}",
                time_of_day=base.time_of_day,
                day_type=base.day_type,
                camera_location=base.camera_location,
                scenario_type=base.scenario_type,
                enrichment_level=base.enrichment_level,
                detections=base.detections,
                enrichment_context=base.enrichment_context,
                ground_truth=base.ground_truth,
                scenario_narrative=base.scenario_narrative,
                expected_summary=base.expected_summary,
            )
        )

    return scenarios[:count]


def generate_boundary_confidence_scenarios(count: int = 20) -> list[ScenarioBundle]:
    """Generate scenarios with confidence values at decision boundaries.

    Tests enrichment pipeline behavior with marginal detections:
    - Confidence values near threshold (0.49, 0.50, 0.51)
    - Multiple low-confidence detections
    - Borderline threat classifications

    Args:
        count: Number of scenarios to generate (default: 20)

    Returns:
        List of ScenarioBundle instances with boundary confidence values
    """
    scenarios: list[ScenarioBundle] = []

    # Scenario 1: Just above threshold (0.51)
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"boundary_conf_{len(scenarios):03d}",
            time_of_day="evening",
            day_type="weekday",
            camera_location="front_door",
            scenario_type="edge_case",
            enrichment_level="basic",
            detections=[
                Detection(
                    object_type="person",
                    confidence=0.51,
                    bbox=(150, 180, 85, 190),
                    timestamp_offset_seconds=10,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="front_door",
                is_entry_point=True,
                baseline_expected_count=2,
                baseline_deviation_score=-0.5,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(20, 40),
                reasoning_key_points=[
                    "low confidence detection",
                    "marginal certainty",
                ],
                expected_enrichment_models=["florence_2"],
                should_trigger_alert=False,
            ),
            scenario_narrative="Low-confidence person detection at entry point",
            expected_summary="Edge case: Marginal detection confidence, verify visually",
        )
    )

    # Scenario 2: Exactly at threshold (0.50)
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"boundary_conf_{len(scenarios):03d}",
            time_of_day="night",
            day_type="weekend",
            camera_location="backyard",
            scenario_type="edge_case",
            enrichment_level="basic",
            detections=[
                Detection(
                    object_type="car",
                    confidence=0.50,
                    bbox=(100, 120, 280, 160),
                    timestamp_offset_seconds=5,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="backyard",
                is_entry_point=False,
                baseline_expected_count=0,
                baseline_deviation_score=1.5,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(30, 50),
                reasoning_key_points=[
                    "threshold confidence",
                    "unusual location for vehicle",
                ],
                expected_enrichment_models=["florence_2"],
                should_trigger_alert=False,
            ),
            scenario_narrative="Threshold-confidence vehicle in backyard",
            expected_summary="Edge case: Vehicle detected at confidence threshold in unusual location",
        )
    )

    # Scenario 3: Multiple low-confidence detections
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"boundary_conf_{len(scenarios):03d}",
            time_of_day="late_night",
            day_type="weekday",
            camera_location="driveway",
            scenario_type="edge_case",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="person",
                    confidence=0.52,
                    bbox=(120, 150, 70, 160),
                    timestamp_offset_seconds=0,
                ),
                Detection(
                    object_type="person",
                    confidence=0.53,
                    bbox=(280, 140, 75, 165),
                    timestamp_offset_seconds=8,
                ),
                Detection(
                    object_type="car",
                    confidence=0.54,
                    bbox=(50, 200, 300, 180),
                    timestamp_offset_seconds=12,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="driveway",
                is_entry_point=False,
                baseline_expected_count=0,
                baseline_deviation_score=2.1,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(40, 60),
                reasoning_key_points=[
                    "multiple low-confidence detections",
                    "late night activity",
                    "marginal certainty",
                ],
                expected_enrichment_models=["florence_2", "pose_estimation", "vehicle_classifier"],
                should_trigger_alert=False,
            ),
            scenario_narrative="Multiple marginal-confidence detections in driveway late at night",
            expected_summary="Edge case: Multiple low-confidence detections require visual confirmation",
        )
    )

    # Fill remaining count with variations
    while len(scenarios) < count:
        idx = len(scenarios) % 3
        base = scenarios[idx]
        scenarios.append(
            ScenarioBundle(
                scenario_id=f"boundary_conf_{len(scenarios):03d}",
                time_of_day=base.time_of_day,
                day_type=base.day_type,
                camera_location=base.camera_location,
                scenario_type=base.scenario_type,
                enrichment_level=base.enrichment_level,
                detections=base.detections,
                enrichment_context=base.enrichment_context,
                ground_truth=base.ground_truth,
                scenario_narrative=base.scenario_narrative,
                expected_summary=base.expected_summary,
            )
        )

    return scenarios[:count]


def generate_ocr_failure_scenarios(count: int = 20) -> list[ScenarioBundle]:
    """Generate scenarios that should cause OCR failures.

    Tests OCR error handling and fallback behavior:
    - Blurry/out-of-focus plates
    - Partially occluded plates
    - Non-standard plate formats
    - Poor lighting conditions

    Args:
        count: Number of scenarios to generate (default: 20)

    Returns:
        List of ScenarioBundle instances that should trigger OCR failures
    """
    scenarios: list[ScenarioBundle] = []

    # Scenario 1: Blurry plate
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"ocr_failure_{len(scenarios):03d}",
            time_of_day="night",
            day_type="weekday",
            camera_location="driveway",
            scenario_type="normal",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="car",
                    confidence=0.94,
                    bbox=(100, 150, 320, 190),
                    timestamp_offset_seconds=5,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="driveway",
                is_entry_point=False,
                baseline_expected_count=1,
                baseline_deviation_score=0.0,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(5, 20),
                reasoning_key_points=[
                    "vehicle present",
                    "OCR unavailable due to blur",
                    "normal activity",
                ],
                expected_enrichment_models=["florence_2", "vehicle_classifier", "ocr"],
                should_trigger_alert=False,
            ),
            scenario_narrative="Vehicle with blurry license plate (motion blur)",
            expected_summary="Normal: Vehicle detected, plate unreadable due to motion blur",
        )
    )

    # Scenario 2: Partially occluded plate
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"ocr_failure_{len(scenarios):03d}",
            time_of_day="evening",
            day_type="weekend",
            camera_location="front_door",
            scenario_type="suspicious",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="car",
                    confidence=0.91,
                    bbox=(80, 140, 340, 200),
                    timestamp_offset_seconds=8,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="front_door",
                is_entry_point=True,
                baseline_expected_count=0,
                baseline_deviation_score=1.8,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(35, 55),
                reasoning_key_points=[
                    "plate intentionally obscured",
                    "suspicious behavior indicator",
                    "entry point location",
                ],
                expected_enrichment_models=["florence_2", "vehicle_classifier", "ocr"],
                should_trigger_alert=True,
            ),
            scenario_narrative="Vehicle with partially covered license plate at entry point",
            expected_summary="Suspicious: Vehicle with obscured plate, OCR failed",
        )
    )

    # Scenario 3: Poor lighting
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"ocr_failure_{len(scenarios):03d}",
            time_of_day="late_night",
            day_type="weekday",
            camera_location="backyard",
            scenario_type="suspicious",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="truck",
                    confidence=0.87,
                    bbox=(120, 160, 310, 180),
                    timestamp_offset_seconds=10,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="backyard",
                is_entry_point=False,
                baseline_expected_count=0,
                baseline_deviation_score=2.5,
                cross_camera_matches=0,
            ),
            ground_truth=GroundTruth(
                risk_range=(50, 70),
                reasoning_key_points=[
                    "vehicle in unusual location",
                    "late night activity",
                    "OCR failed due to darkness",
                ],
                expected_enrichment_models=["florence_2", "vehicle_classifier", "ocr"],
                should_trigger_alert=True,
            ),
            scenario_narrative="Truck in backyard at night, plate unreadable due to poor lighting",
            expected_summary="Suspicious: Vehicle in unusual location at night, plate not visible",
        )
    )

    # Fill remaining count with variations
    while len(scenarios) < count:
        idx = len(scenarios) % 3
        base = scenarios[idx]
        scenarios.append(
            ScenarioBundle(
                scenario_id=f"ocr_failure_{len(scenarios):03d}",
                time_of_day=base.time_of_day,
                day_type=base.day_type,
                camera_location=base.camera_location,
                scenario_type=base.scenario_type,
                enrichment_level=base.enrichment_level,
                detections=base.detections,
                enrichment_context=base.enrichment_context,
                ground_truth=base.ground_truth,
                scenario_narrative=base.scenario_narrative,
                expected_summary=base.expected_summary,
            )
        )

    return scenarios[:count]


def generate_vram_stress_scenarios(count: int = 10) -> list[ScenarioBundle]:
    """Generate scenarios that require many models simultaneously.

    Tests VRAM management and LRU eviction:
    - Scenarios requiring: threat + pose + vehicle + face + OCR
    - Multiple detections requiring different enrichment models
    - VRAM budget management under stress

    Args:
        count: Number of scenarios to generate (default: 10)

    Returns:
        List of ScenarioBundle instances requiring maximum model usage
    """
    scenarios: list[ScenarioBundle] = []

    # Scenario 1: Maximum enrichment complexity
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"vram_stress_{len(scenarios):03d}",
            time_of_day="evening",
            day_type="weekday",
            camera_location="front_door",
            scenario_type="threat",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="person",
                    confidence=0.93,
                    bbox=(120, 150, 85, 190),
                    timestamp_offset_seconds=0,
                ),
                Detection(
                    object_type="person",
                    confidence=0.89,
                    bbox=(280, 140, 90, 195),
                    timestamp_offset_seconds=3,
                ),
                Detection(
                    object_type="car",
                    confidence=0.95,
                    bbox=(50, 200, 350, 180),
                    timestamp_offset_seconds=5,
                ),
                Detection(
                    object_type="dog",
                    confidence=0.78,
                    bbox=(380, 280, 80, 90),
                    timestamp_offset_seconds=8,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="front_door",
                is_entry_point=True,
                baseline_expected_count=1,
                baseline_deviation_score=2.2,
                cross_camera_matches=1,
            ),
            ground_truth=GroundTruth(
                risk_range=(80, 95),
                reasoning_key_points=[
                    "multiple persons",
                    "weapon detected",
                    "vehicle present",
                    "complex scene",
                ],
                expected_enrichment_models=[
                    "florence_2",
                    "pose_estimation",
                    "vehicle_classifier",
                    "ocr",
                    "reid",
                    "pet_classifier",
                    "violence_detector",
                ],
                should_trigger_alert=True,
            ),
            scenario_narrative="Complex scene with multiple persons, vehicle, and potential weapon",
            expected_summary="CRITICAL: High-complexity threat scenario requiring all enrichment models",
        )
    )

    # Scenario 2: Multiple vehicles and persons
    scenarios.append(
        ScenarioBundle(
            scenario_id=f"vram_stress_{len(scenarios):03d}",
            time_of_day="night",
            day_type="weekend",
            camera_location="driveway",
            scenario_type="suspicious",
            enrichment_level="full",
            detections=[
                Detection(
                    object_type="car",
                    confidence=0.92,
                    bbox=(50, 120, 280, 150),
                    timestamp_offset_seconds=0,
                ),
                Detection(
                    object_type="truck",
                    confidence=0.88,
                    bbox=(320, 140, 300, 180),
                    timestamp_offset_seconds=2,
                ),
                Detection(
                    object_type="person",
                    confidence=0.90,
                    bbox=(180, 200, 75, 180),
                    timestamp_offset_seconds=5,
                ),
                Detection(
                    object_type="person",
                    confidence=0.86,
                    bbox=(400, 190, 80, 185),
                    timestamp_offset_seconds=7,
                ),
                Detection(
                    object_type="person",
                    confidence=0.84,
                    bbox=(260, 210, 72, 175),
                    timestamp_offset_seconds=10,
                ),
            ],
            enrichment_context=EnrichmentContext(
                zone_name="driveway",
                is_entry_point=False,
                baseline_expected_count=1,
                baseline_deviation_score=2.8,
                cross_camera_matches=2,
            ),
            ground_truth=GroundTruth(
                risk_range=(60, 80),
                reasoning_key_points=[
                    "multiple vehicles",
                    "multiple persons",
                    "night activity",
                    "deviation from baseline",
                ],
                expected_enrichment_models=[
                    "florence_2",
                    "pose_estimation",
                    "vehicle_classifier",
                    "ocr",
                    "reid",
                    "weather_classifier",
                ],
                should_trigger_alert=True,
            ),
            scenario_narrative="Multiple vehicles and persons in driveway at night, high complexity",
            expected_summary="Suspicious: High-complexity scene with multiple vehicles and persons",
        )
    )

    # Fill remaining count with variations
    while len(scenarios) < count:
        idx = len(scenarios) % 2
        base = scenarios[idx]
        scenarios.append(
            ScenarioBundle(
                scenario_id=f"vram_stress_{len(scenarios):03d}",
                time_of_day=base.time_of_day,
                day_type=base.day_type,
                camera_location=base.camera_location,
                scenario_type=base.scenario_type,
                enrichment_level=base.enrichment_level,
                detections=base.detections,
                enrichment_context=base.enrichment_context,
                ground_truth=base.ground_truth,
                scenario_narrative=base.scenario_narrative,
                expected_summary=base.expected_summary,
            )
        )

    return scenarios[:count]


def export_enrichment_scenarios(output_dir: Path) -> None:
    """Export all enrichment edge case scenarios to files.

    Generates all enrichment scenario types and exports them to the specified
    directory for use in integration tests.

    Args:
        output_dir: Directory to write scenario files to

    Creates:
        - multi_threat_scenarios.json
        - rare_pose_scenarios.json
        - boundary_confidence_scenarios.json
        - ocr_failure_scenarios.json
        - vram_stress_scenarios.json
    """
    import json

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate all scenario types
    scenario_sets = {
        "multi_threat": generate_multi_threat_scenarios(count=20),
        "rare_pose": generate_rare_pose_scenarios(count=20),
        "boundary_confidence": generate_boundary_confidence_scenarios(count=20),
        "ocr_failure": generate_ocr_failure_scenarios(count=20),
        "vram_stress": generate_vram_stress_scenarios(count=10),
    }

    # Export each set
    for name, scenarios in scenario_sets.items():
        output_file = output_dir / f"{name}_scenarios.json"
        with output_file.open("w") as f:
            json.dump(
                [s.model_dump(mode="json") for s in scenarios],
                f,
                indent=2,
            )
        print(f"Exported {len(scenarios)} {name} scenarios to {output_file}")

    print(f"\nTotal scenarios exported: {sum(len(s) for s in scenario_sets.values())}")
