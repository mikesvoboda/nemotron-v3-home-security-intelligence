#!/usr/bin/env python3
"""Generate synthetic security scenarios using NeMo Data Designer.

This script uses NVIDIA NeMo Data Designer to generate synthetic scenarios
for testing the home security pipeline and evaluating Nemotron prompts.

Usage:
    # Preview the workflow configuration without generating
    uv run python tools/nemo_data_designer/generate_scenarios.py --preview

    # Generate 100 scenarios and save to fixtures
    uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 100

    # Generate full coverage (1,500+ scenarios) with all 24 columns
    uv run python tools/nemo_data_designer/generate_scenarios.py \\
        --generate \\
        --rows 1500 \\
        --full-columns \\
        --output backend/tests/fixtures/synthetic/scenarios.parquet

    # Generate with embeddings (requires NVIDIA API)
    uv run python tools/nemo_data_designer/generate_scenarios.py \\
        --generate \\
        --rows 1500 \\
        --full-columns \\
        --embeddings \\
        --output backend/tests/fixtures/synthetic/

    # Dry run to preview output without API calls
    uv run python tools/nemo_data_designer/generate_scenarios.py \\
        --generate \\
        --rows 10 \\
        --full-columns \\
        --dry-run

Requirements:
    - NVIDIA_API_KEY environment variable set (except for --dry-run)
    - data-designer package installed: uv sync --group nemo
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import pandas as pd
    from data_designer import DataDesigner

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.nemo_data_designer.config import (
    COLUMN_TYPES,
    EMBEDDING_DIM,
    ENRICHMENT_MODELS,
    ENTRY_POINTS,
    OBJECT_TYPES,
    RISK_RANGES,
    SAMPLER_COLUMNS,
    TOTAL_COLUMNS,
    Detection,
    EnrichmentContext,
    GroundTruth,
    JudgeScores,
    calculate_complexity_score,
    format_prompt_input,
    generate_default_judge_scores,
    generate_placeholder_embedding,
    generate_scenario_hash,
    validate_detection_schema,
    validate_temporal_consistency,
)

# Default output path for generated scenarios
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "backend" / "tests" / "fixtures" / "synthetic" / "scenarios.parquet"
)


def create_detection_schema() -> str:
    """Create JSON schema string for Detection model.

    Returns:
        JSON schema string for the Detection Pydantic model.
    """
    return json.dumps(Detection.model_json_schema(), indent=2)


def create_enrichment_schema() -> str:
    """Create JSON schema string for EnrichmentContext model.

    Returns:
        JSON schema string for the EnrichmentContext Pydantic model.
    """
    return json.dumps(EnrichmentContext.model_json_schema(), indent=2)


def create_ground_truth_schema() -> str:
    """Create JSON schema string for GroundTruth model.

    Returns:
        JSON schema string for the GroundTruth Pydantic model.
    """
    return json.dumps(GroundTruth.model_json_schema(), indent=2)


def get_detection_prompt() -> str:
    """Get the LLM prompt for generating detections.

    Returns:
        Prompt string for generating realistic detection data.
    """
    return """Generate realistic security camera detections for a home security scenario.

Context from sampler columns:
- time_of_day: {time_of_day}
- day_type: {day_type}
- camera_location: {camera_location}
- detection_count: {detection_count}
- primary_object: {primary_object}
- scenario_type: {scenario_type}

Generate a list of Detection objects matching the scenario. Each detection should have:
- object_type: one of "person", "car", "truck", "dog", "cat", "bicycle", "motorcycle", "bus"
- confidence: realistic confidence score between 0.5 and 1.0
- bbox: bounding box as (x, y, width, height) tuple with realistic pixel values (image is 1920x1080)
- timestamp_offset_seconds: spread across the 90-second batch window

Consider:
- Normal scenarios have expected activity (family, delivery, pets)
- Suspicious scenarios have unusual but not threatening activity
- Threat scenarios have clear security concerns
- Edge cases are ambiguous situations

Return ONLY valid JSON matching the Detection schema."""


def get_enrichment_prompt() -> str:
    """Get the LLM prompt for generating enrichment context.

    Returns:
        Prompt string for generating enrichment context data.
    """
    return """Generate enrichment context for a home security scenario.

Context:
- camera_location: {camera_location}
- scenario_type: {scenario_type}
- enrichment_level: {enrichment_level}
- detections: {detections}

For enrichment_level "none", return null.
For "basic" or "full", generate EnrichmentContext with:
- zone_name: use the camera_location value
- is_entry_point: True for front_door and side_gate, False otherwise
- baseline_expected_count: typical count for this time/location (0-5)
- baseline_deviation_score: z-score from -3 to +3 based on scenario_type
  - Normal: near 0
  - Suspicious: 1.0 to 2.0
  - Threat: 2.0 to 3.0
  - Edge case: varies
- cross_camera_matches: 0-2 for basic, 0-5 for full

Return ONLY valid JSON or null."""


def get_ground_truth_prompt() -> str:
    """Get the LLM prompt for generating ground truth.

    Returns:
        Prompt string for generating ground truth assessment.
    """
    risk_ranges_str = json.dumps(RISK_RANGES)
    return f"""Generate ground truth risk assessment for a home security scenario.

Context:
- scenario_type: {{scenario_type}}
- time_of_day: {{time_of_day}}
- camera_location: {{camera_location}}
- detections: {{detections}}
- enrichment_context: {{enrichment_context}}

Risk ranges by scenario type: {risk_ranges_str}

Generate GroundTruth with:
- risk_range: (min, max) tuple based on scenario_type from ranges above
- reasoning_key_points: 2-4 key factors that justify the risk score
- expected_enrichment_models: which models should contribute (florence_2, pose_estimation, reid, ocr)
- should_trigger_alert: True for suspicious/threat, False for most normal, varies for edge_case

Return ONLY valid JSON."""


def get_narrative_prompt() -> str:
    """Get the LLM prompt for generating scenario narrative.

    Returns:
        Prompt string for generating human-readable narrative.
    """
    return """Write a brief, natural language description of this security scenario.

Context:
- time_of_day: {time_of_day}
- day_type: {day_type}
- camera_location: {camera_location}
- scenario_type: {scenario_type}
- detections: {detections}

Write 1-2 sentences describing what a homeowner would see. Be specific about
the activity but don't explicitly state the risk level. Examples:
- "Two people approach the front door and ring the doorbell at 3pm"
- "Unknown vehicle idles in driveway for 10 minutes after midnight"
- "Family dog plays in backyard while children are at school"

Return ONLY the narrative text, no JSON."""


def get_summary_prompt() -> str:
    """Get the LLM prompt for generating expected summary.

    Returns:
        Prompt string for generating expected Nemotron summary.
    """
    return """Generate the expected summary text that Nemotron should produce for this scenario.

Context:
- scenario_type: {scenario_type}
- ground_truth: {ground_truth}
- scenario_narrative: {scenario_narrative}

Write a brief security assessment summary in the style of a home security system.
Format: "[Risk Level]: [Brief description of activity and key concerns]"

Risk levels:
- Low (0-25): Routine activity
- Medium (30-55): Warrants attention
- High (70-85): Security concern
- Critical (86-100): Immediate threat

Return ONLY the summary text, no JSON."""


def get_reasoning_prompt() -> str:
    """Get the LLM prompt for generating reasoning key points.

    Returns:
        Prompt string for generating detailed reasoning points.
    """
    return """Generate detailed reasoning key points for this security scenario assessment.

Context:
- scenario_type: {scenario_type}
- time_of_day: {time_of_day}
- camera_location: {camera_location}
- detections: {detections}
- enrichment_context: {enrichment_context}
- ground_truth: {ground_truth}

List 3-5 key reasoning points that justify the risk assessment. Each point should:
- Reference specific detected objects or behaviors
- Consider temporal context (time of day, day type)
- Account for location (entry points vs general areas)
- Note any anomalies from baseline expectations

Return as a JSON list of strings."""


def get_judge_scores_prompt() -> str:
    """Get the LLM prompt for generating judge scores.

    Returns:
        Prompt string for LLM-as-Judge evaluation.
    """
    return """Evaluate this security scenario response using the LLM-Judge rubric.

Scenario:
- scenario_type: {scenario_type}
- scenario_narrative: {scenario_narrative}
- expected_summary: {expected_summary}
- ground_truth: {ground_truth}

Score each dimension from 1-4:
- 1: Poor - fails to meet basic requirements
- 2: Fair - partially meets requirements
- 3: Good - meets requirements well
- 4: Excellent - exceeds requirements

Dimensions:
1. relevance: Does output address the actual security concern?
2. risk_calibration: Is score appropriate for scenario severity?
3. context_usage: Are enrichment inputs reflected in reasoning?
4. reasoning_quality: Is the explanation logical and complete?
5. threat_identification: Did it correctly identify/miss the actual threat?
6. actionability: Is the output useful for a homeowner to act on?

Return JSON: {{"relevance": N, "risk_calibration": N, "context_usage": N, "reasoning_quality": N, "threat_identification": N, "actionability": N}}"""


def create_judge_scores_schema() -> str:
    """Create JSON schema string for JudgeScores model.

    Returns:
        JSON schema string for the JudgeScores Pydantic model.
    """
    return json.dumps(JudgeScores.model_json_schema(), indent=2)


# =============================================================================
# Combinatorial Coverage Generation
# =============================================================================


def generate_combinatorial_samples(  # noqa: PLR0912
    num_rows: int,
    prioritize_coverage: bool = True,  # noqa: ARG001 - reserved for future coverage modes
) -> list[dict[str, str]]:
    """Generate sampler column combinations for diverse scenario coverage.

    Creates combinations that prioritize coverage of all scenario types,
    enrichment levels, and important sampler values.

    Args:
        num_rows: Target number of rows to generate
        prioritize_coverage: Whether to ensure all value combinations are covered

    Returns:
        List of dictionaries with sampler column values
    """
    samples = []

    # First, ensure full coverage of critical combinations
    # scenario_type x enrichment_level x camera_location = 4 x 3 x 4 = 48 combos
    critical_combos = list(
        itertools.product(
            SAMPLER_COLUMNS["scenario_type"]["values"],
            SAMPLER_COLUMNS["enrichment_level"]["values"],
            SAMPLER_COLUMNS["camera_location"]["values"],
        )
    )

    # Expand with other columns
    for scenario_type, enrichment_level, camera_location in critical_combos:
        for time_of_day in SAMPLER_COLUMNS["time_of_day"]["values"]:
            for day_type in SAMPLER_COLUMNS["day_type"]["values"]:
                for detection_count in SAMPLER_COLUMNS["detection_count"]["values"]:
                    for primary_object in SAMPLER_COLUMNS["primary_object"]["values"]:
                        samples.append(
                            {
                                "time_of_day": time_of_day,
                                "day_type": day_type,
                                "camera_location": camera_location,
                                "detection_count": detection_count,
                                "primary_object": primary_object,
                                "scenario_type": scenario_type,
                                "enrichment_level": enrichment_level,
                            }
                        )

    # If we have more than needed, sample down
    if len(samples) > num_rows:
        # Ensure at least some of each scenario_type
        samples_by_type: dict[str, list[dict]] = {}
        for sample in samples:
            st = sample["scenario_type"]
            if st not in samples_by_type:
                samples_by_type[st] = []
            samples_by_type[st].append(sample)

        # Take proportional samples from each type
        final_samples = []
        per_type = num_rows // 4
        for _st, st_samples in samples_by_type.items():
            random.shuffle(st_samples)
            final_samples.extend(st_samples[:per_type])

        # Fill remainder randomly
        remaining = num_rows - len(final_samples)
        all_remaining = [s for s in samples if s not in final_samples]
        random.shuffle(all_remaining)
        final_samples.extend(all_remaining[:remaining])

        samples = final_samples

    # If we have fewer than needed, add weighted random samples
    elif len(samples) < num_rows:
        additional_needed = num_rows - len(samples)
        for _ in range(additional_needed):
            sample = {}
            for col_name, col_config in SAMPLER_COLUMNS.items():
                values = col_config["values"]
                weights = col_config.get("weights")
                # S311: Using standard random for test data generation (not crypto)
                if weights:
                    sample[col_name] = random.choices(values, weights=weights)[0]  # noqa: S311
                else:
                    sample[col_name] = random.choice(values)  # noqa: S311
            samples.append(sample)

    return samples[:num_rows]


def generate_synthetic_detections(
    scenario_type: str,
    detection_count: str,
    primary_object: str,
    time_of_day: str,  # noqa: ARG001 - reserved for time-based detection patterns
) -> list[dict[str, Any]]:
    """Generate synthetic detection data for dry-run mode.

    Args:
        scenario_type: Type of scenario
        detection_count: Detection count range
        primary_object: Primary object type
        time_of_day: Time of day

    Returns:
        List of synthetic detection dictionaries
    """
    # Map detection count to actual count
    # S311: Using standard random for test data generation (not crypto)
    count_map = {
        "1": 1,
        "2-3": random.randint(2, 3),  # noqa: S311
        "4-6": random.randint(4, 6),  # noqa: S311
        "7+": random.randint(7, 10),  # noqa: S311
    }
    num_detections = count_map.get(detection_count, 1)

    # Map primary object to detection types
    object_types_map = OBJECT_TYPES
    detection_types = object_types_map.get(primary_object, ["person"])
    if not detection_types:
        detection_types = ["person"]  # Default for package

    # S311: Using standard random for synthetic test data generation (not crypto)
    detections = []
    for i in range(num_detections):
        # Select object type - primary object first, then random others
        if i == 0:
            obj_type = random.choice(detection_types)  # noqa: S311
        else:
            obj_type = random.choice(["person", "car", "dog", "cat"])  # noqa: S311

        # Confidence varies by scenario type
        base_confidence = {
            "normal": 0.85,
            "suspicious": 0.75,
            "threat": 0.90,
            "edge_case": 0.65,
        }.get(scenario_type, 0.8)
        confidence = min(1.0, max(0.5, base_confidence + random.uniform(-0.1, 0.1)))  # noqa: S311

        # Generate reasonable bounding box
        x = random.randint(100, 1600)  # noqa: S311
        y = random.randint(100, 800)  # noqa: S311
        w = random.randint(50, 200)  # noqa: S311
        h = random.randint(100, 400)  # noqa: S311

        # Spread timestamps across 90 second window
        if num_detections > 1:
            timestamp = int((i / max(1, num_detections - 1)) * 85)
        else:
            timestamp = random.randint(10, 80)  # noqa: S311

        detections.append(
            {
                "object_type": obj_type,
                "confidence": round(confidence, 2),
                "bbox": [x, y, w, h],
                "timestamp_offset_seconds": timestamp,
            }
        )

    return detections


def generate_synthetic_enrichment(
    camera_location: str,
    enrichment_level: str,
    scenario_type: str,
) -> dict[str, Any] | None:
    """Generate synthetic enrichment context for dry-run mode.

    Args:
        camera_location: Camera location
        enrichment_level: Level of enrichment
        scenario_type: Scenario type

    Returns:
        Enrichment context dictionary or None
    """
    if enrichment_level == "none":
        return None

    is_entry = ENTRY_POINTS.get(camera_location, False)

    # Baseline deviation varies by scenario type
    # S311: Using standard random for synthetic test data generation (not crypto)
    deviation_map = {
        "normal": random.uniform(-0.5, 0.5),  # noqa: S311
        "suspicious": random.uniform(1.0, 2.0),  # noqa: S311
        "threat": random.uniform(2.0, 3.0),  # noqa: S311
        "edge_case": random.uniform(-0.5, 2.0),  # noqa: S311
    }
    deviation = deviation_map.get(scenario_type, 0.0)

    cross_camera = random.randint(0, 2) if enrichment_level == "basic" else random.randint(0, 5)  # noqa: S311

    return {
        "zone_name": camera_location,
        "is_entry_point": is_entry,
        "baseline_expected_count": random.randint(0, 3),  # noqa: S311
        "baseline_deviation_score": round(deviation, 2),
        "cross_camera_matches": cross_camera,
    }


def generate_synthetic_ground_truth(
    scenario_type: str,
    camera_location: str,  # noqa: ARG001 - reserved for location-based risk weighting
    enrichment_level: str,
) -> dict[str, Any]:
    """Generate synthetic ground truth for dry-run mode.

    Args:
        scenario_type: Scenario type
        camera_location: Camera location
        enrichment_level: Enrichment level

    Returns:
        Ground truth dictionary
    """
    risk_range = RISK_RANGES.get(scenario_type, (30, 55))

    # Generate key points based on scenario type
    key_points_options = {
        "normal": ["expected activity", "known pattern", "routine behavior"],
        "suspicious": ["unusual timing", "unknown individual", "deviation from baseline"],
        "threat": ["security concern", "potential intrusion", "immediate attention required"],
        "edge_case": ["ambiguous situation", "context dependent", "requires review"],
    }
    key_points = random.sample(
        key_points_options.get(scenario_type, []),
        min(2, len(key_points_options.get(scenario_type, []))),
    )

    expected_models = ENRICHMENT_MODELS.get(enrichment_level, [])

    should_alert = scenario_type in ("suspicious", "threat")
    if scenario_type == "edge_case":
        should_alert = random.choice([True, False])  # noqa: S311 - synthetic test data

    return {
        "risk_range": list(risk_range),
        "reasoning_key_points": key_points,
        "expected_enrichment_models": expected_models,
        "should_trigger_alert": should_alert,
    }


def generate_synthetic_narrative(
    scenario_type: str,
    time_of_day: str,
    camera_location: str,
    primary_object: str,
) -> str:
    """Generate synthetic narrative for dry-run mode.

    Args:
        scenario_type: Scenario type
        time_of_day: Time of day
        camera_location: Camera location
        primary_object: Primary object

    Returns:
        Narrative string
    """
    time_phrases = {
        "morning": "early morning",
        "midday": "around noon",
        "evening": "in the evening",
        "night": "late at night",
        "late_night": "after midnight",
    }
    time_phrase = time_phrases.get(time_of_day, "during the day")

    location_phrases = {
        "front_door": "at the front door",
        "backyard": "in the backyard",
        "driveway": "in the driveway",
        "side_gate": "near the side gate",
    }
    location_phrase = location_phrases.get(camera_location, "on the property")

    templates = {
        "normal": [
            f"A {primary_object} is seen {location_phrase} {time_phrase}.",
            f"Routine activity detected: {primary_object} {location_phrase} {time_phrase}.",
        ],
        "suspicious": [
            f"Unknown {primary_object} lingering {location_phrase} {time_phrase}.",
            f"Unusual {primary_object} activity {location_phrase} {time_phrase}.",
        ],
        "threat": [
            f"Potential security concern: {primary_object} attempting access {location_phrase} {time_phrase}.",
            f"Alert: Suspicious {primary_object} behavior detected {location_phrase} {time_phrase}.",
        ],
        "edge_case": [
            f"Ambiguous activity involving {primary_object} {location_phrase} {time_phrase}.",
            f"Unusual but unclear {primary_object} activity {location_phrase} {time_phrase}.",
        ],
    }

    options = templates.get(scenario_type, templates["normal"])
    return random.choice(options)  # noqa: S311 - synthetic test data


def generate_synthetic_summary(scenario_type: str, narrative: str) -> str:
    """Generate synthetic expected summary for dry-run mode.

    Args:
        scenario_type: Scenario type
        narrative: Scenario narrative

    Returns:
        Expected summary string
    """
    risk_level_map = {
        "normal": "Low",
        "suspicious": "Medium",
        "threat": "High",
        "edge_case": "Medium",
    }
    risk_level = risk_level_map.get(scenario_type, "Medium")

    return f"{risk_level}: {narrative}"


def generate_dry_run_scenarios(num_rows: int) -> pd.DataFrame:
    """Generate scenarios without API calls for testing.

    Creates synthetic scenarios using local random generation instead of
    NVIDIA API calls. Useful for testing the pipeline structure.

    Args:
        num_rows: Number of scenarios to generate

    Returns:
        DataFrame with generated scenarios
    """
    import pandas as pd

    print(f"[DRY RUN] Generating {num_rows} synthetic scenarios locally...")

    # Generate sampler combinations
    samples = generate_combinatorial_samples(num_rows)

    rows = []
    for i, sample in enumerate(samples):
        scenario_id = f"scn_{i:05d}"

        # Generate base columns
        detections = generate_synthetic_detections(
            sample["scenario_type"],
            sample["detection_count"],
            sample["primary_object"],
            sample["time_of_day"],
        )

        enrichment = generate_synthetic_enrichment(
            sample["camera_location"],
            sample["enrichment_level"],
            sample["scenario_type"],
        )

        ground_truth = generate_synthetic_ground_truth(
            sample["scenario_type"],
            sample["camera_location"],
            sample["enrichment_level"],
        )

        narrative = generate_synthetic_narrative(
            sample["scenario_type"],
            sample["time_of_day"],
            sample["camera_location"],
            sample["primary_object"],
        )

        summary = generate_synthetic_summary(sample["scenario_type"], narrative)

        # Build the row
        row = {
            "scenario_id": scenario_id,
            **sample,
            "detections": detections,
            "enrichment_context": enrichment,
            "ground_truth": ground_truth,
            "scenario_narrative": narrative,
            "expected_summary": summary,
            "reasoning_key_points": json.dumps(ground_truth.get("reasoning_key_points", [])),
        }

        rows.append(row)

    df = pd.DataFrame(rows)
    print(f"[DRY RUN] Generated {len(df)} scenarios")
    return df


def add_full_columns(
    df: pd.DataFrame,
    include_embeddings: bool = False,
) -> pd.DataFrame:
    """Add all 24 columns including derived, judge, and validation columns.

    Args:
        df: DataFrame with base scenario columns
        include_embeddings: Whether to generate embedding vectors

    Returns:
        DataFrame with all 24 columns
    """
    print("Adding full column set (24 columns)...")

    # Add LLM-Judge columns (using defaults for now)
    judge_scores = []
    for _, row in df.iterrows():
        scores = generate_default_judge_scores(row.get("scenario_type", "normal"))
        judge_scores.append(scores.model_dump())

    # Flatten judge scores into columns
    for col in COLUMN_TYPES["llm_judge"]:
        df[col] = [s[col] for s in judge_scores]

    # Add Expression columns
    df["complexity_score"] = df.apply(
        lambda r: calculate_complexity_score(
            r.get("detection_count", "1"),
            r.get("enrichment_level", "none"),
            r.get("scenario_type", "normal"),
        ),
        axis=1,
    )

    df["scenario_hash"] = df.apply(lambda r: generate_scenario_hash(r.to_dict()), axis=1)

    df["formatted_prompt_input"] = df.apply(lambda r: format_prompt_input(r.to_dict()), axis=1)

    # Add Validation columns
    df["detection_schema_valid"] = df["detections"].apply(validate_detection_schema)
    df["temporal_consistency"] = df["detections"].apply(validate_temporal_consistency)

    # Add Embedding columns
    if include_embeddings:
        print("Generating placeholder embeddings...")
        df["scenario_embedding"] = df["scenario_narrative"].apply(
            lambda x: generate_placeholder_embedding(str(x), EMBEDDING_DIM)
        )
        df["reasoning_embedding"] = df["reasoning_key_points"].apply(
            lambda x: generate_placeholder_embedding(str(x), EMBEDDING_DIM)
        )
    else:
        # Add placeholder columns with None
        df["scenario_embedding"] = None
        df["reasoning_embedding"] = None

    print(f"Full column set complete: {len(df.columns)} columns")
    return df


def export_ground_truth(df: pd.DataFrame, output_dir: Path) -> Path:
    """Export ground truth data to JSON file.

    Args:
        df: DataFrame with scenario data
        output_dir: Output directory

    Returns:
        Path to exported JSON file
    """
    ground_truth_data = {
        "version": "1.0",
        "total_scenarios": len(df),
        "risk_ranges": RISK_RANGES,
        "scenarios": [],
    }

    for _, row in df.iterrows():
        scenario_gt = {
            "scenario_id": row.get("scenario_id", ""),
            "scenario_type": row.get("scenario_type", ""),
            "ground_truth": row.get("ground_truth", {}),
            "reasoning_key_points": row.get("reasoning_key_points", "[]"),
        }
        ground_truth_data["scenarios"].append(scenario_gt)

    output_path = output_dir / "ground_truth.json"
    # nosemgrep: path-traversal-open - output_dir is derived from CLI args, validated Path object
    with open(output_path, "w") as f:
        json.dump(ground_truth_data, f, indent=2)

    print(f"Exported ground truth to {output_path}")
    return output_path


def export_coverage_report(df: pd.DataFrame, output_dir: Path) -> Path:
    """Export coverage analysis report to JSON file.

    Args:
        df: DataFrame with scenario data
        output_dir: Output directory

    Returns:
        Path to exported JSON file
    """
    report = {
        "version": "1.0",
        "total_scenarios": len(df),
        "column_count": len(df.columns),
        "column_types": COLUMN_TYPES,
        "coverage": {},
    }

    # Analyze coverage for each sampler column
    for col in COLUMN_TYPES["samplers"]:
        if col in df.columns:
            value_counts = df[col].value_counts().to_dict()
            expected_values = SAMPLER_COLUMNS.get(col, {}).get("values", [])
            covered = [v for v in expected_values if v in value_counts]
            missing = [v for v in expected_values if v not in value_counts]

            report["coverage"][col] = {
                "expected_values": expected_values,
                "covered_values": covered,
                "missing_values": missing,
                "coverage_percent": round(len(covered) / len(expected_values) * 100, 1)
                if expected_values
                else 100,
                "distribution": value_counts,
            }

    # Cross-tabulation for key combinations
    if "scenario_type" in df.columns and "enrichment_level" in df.columns:
        cross_tab = df.groupby(["scenario_type", "enrichment_level"]).size().to_dict()
        report["cross_coverage"] = {
            "scenario_type_x_enrichment_level": {str(k): v for k, v in cross_tab.items()}
        }

    # Validation summary
    if "detection_schema_valid" in df.columns:
        report["validation"] = {
            "detection_schema_valid": int(df["detection_schema_valid"].sum()),
            "temporal_consistency": int(
                df.get("temporal_consistency", df["detection_schema_valid"]).sum()
            ),
            "total": len(df),
        }

    output_path = output_dir / "coverage_report.json"
    # nosemgrep: path-traversal-open - output_dir is derived from CLI args, validated Path object
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Exported coverage report to {output_path}")
    return output_path


def export_embeddings(df: pd.DataFrame, output_dir: Path) -> Path | None:
    """Export embeddings to numpy file.

    Args:
        df: DataFrame with embedding columns
        output_dir: Output directory

    Returns:
        Path to exported numpy file, or None if no embeddings
    """
    if "scenario_embedding" not in df.columns or df["scenario_embedding"].iloc[0] is None:
        print("No embeddings to export (use --embeddings flag)")
        return None

    # Stack embeddings into numpy array
    scenario_embeddings = np.array(df["scenario_embedding"].tolist())
    reasoning_embeddings = np.array(df["reasoning_embedding"].tolist())

    # Save as .npz file
    output_path = output_dir / "embeddings.npz"
    np.savez(
        output_path,
        scenario_embeddings=scenario_embeddings,
        reasoning_embeddings=reasoning_embeddings,
        scenario_ids=df["scenario_id"].values,
    )

    print(f"Exported embeddings to {output_path}")
    return output_path


def create_workflow(designer: DataDesigner) -> DataDesigner:
    """Configure the NeMo Data Designer workflow.

    Sets up sampler columns, LLM-structured columns, and LLM-text columns
    for generating complete security scenarios.

    Args:
        designer: DataDesigner instance to configure

    Returns:
        Configured DataDesigner instance
    """
    # Add sampler columns for statistical control
    for col_name, col_config in SAMPLER_COLUMNS.items():
        designer.add_sampler_column(
            name=col_name,
            values=col_config["values"],
            weights=col_config.get("weights"),
            description=col_config.get("description", ""),
        )

    # Add LLM-structured columns with Pydantic schema validation
    designer.add_llm_structured_column(
        name="detections",
        prompt=get_detection_prompt(),
        output_schema=create_detection_schema(),
        depends_on=[
            "time_of_day",
            "day_type",
            "camera_location",
            "detection_count",
            "primary_object",
            "scenario_type",
        ],
    )

    designer.add_llm_structured_column(
        name="enrichment_context",
        prompt=get_enrichment_prompt(),
        output_schema=create_enrichment_schema(),
        depends_on=["camera_location", "scenario_type", "enrichment_level", "detections"],
    )

    designer.add_llm_structured_column(
        name="ground_truth",
        prompt=get_ground_truth_prompt(),
        output_schema=create_ground_truth_schema(),
        depends_on=[
            "scenario_type",
            "time_of_day",
            "camera_location",
            "detections",
            "enrichment_context",
        ],
    )

    # Add LLM-text columns for narrative content
    designer.add_llm_text_column(
        name="scenario_narrative",
        prompt=get_narrative_prompt(),
        depends_on=["time_of_day", "day_type", "camera_location", "scenario_type", "detections"],
    )

    designer.add_llm_text_column(
        name="expected_summary",
        prompt=get_summary_prompt(),
        depends_on=["scenario_type", "ground_truth", "scenario_narrative"],
    )

    designer.add_llm_text_column(
        name="reasoning_key_points",
        prompt=get_reasoning_prompt(),
        depends_on=[
            "scenario_type",
            "time_of_day",
            "camera_location",
            "detections",
            "enrichment_context",
            "ground_truth",
        ],
    )

    return designer


def preview_workflow(full_columns: bool = False) -> None:
    """Preview the workflow configuration without generating data.

    Displays the column configuration and sample prompts to verify
    the workflow is correctly configured before running generation.

    Args:
        full_columns: Whether to show full 24-column configuration
    """
    print("=" * 70)
    print("NeMo Data Designer Workflow Configuration")
    print("=" * 70)

    print("\n### Sampler Columns (7)")
    print("-" * 40)
    for name, config in SAMPLER_COLUMNS.items():
        print(f"  {name}:")
        print(f"    values: {config['values']}")
        if "weights" in config:
            print(f"    weights: {config['weights']}")
        print(f"    description: {config.get('description', 'N/A')}")
    print()

    print("### LLM-Structured Columns (3)")
    print("-" * 40)
    print("  detections: list[Detection]")
    print("  enrichment_context: EnrichmentContext | None")
    print("  ground_truth: GroundTruth")
    print()

    print("### LLM-Text Columns (3)")
    print("-" * 40)
    print("  scenario_narrative: str")
    print("  expected_summary: str")
    print("  reasoning_key_points: str (JSON list)")
    print()

    if full_columns:
        print("### LLM-Judge Columns (6)")
        print("-" * 40)
        for col in COLUMN_TYPES["llm_judge"]:
            print(f"  {col}: int (1-4)")
        print()

        print("### Embedding Columns (2)")
        print("-" * 40)
        print(f"  scenario_embedding: vector[{EMBEDDING_DIM}]")
        print(f"  reasoning_embedding: vector[{EMBEDDING_DIM}]")
        print()

        print("### Expression Columns (3)")
        print("-" * 40)
        print("  formatted_prompt_input: str")
        print("  complexity_score: float (0.0-1.0)")
        print("  scenario_hash: str (16-char hex)")
        print()

        print("### Validation Columns (2)")
        print("-" * 40)
        print("  detection_schema_valid: bool")
        print("  temporal_consistency: bool")
        print()

        print(f"### Total Column Count: {TOTAL_COLUMNS}")
        print("-" * 40)
        for col_type, cols in COLUMN_TYPES.items():
            print(f"  {col_type}: {len(cols)} columns")
        print()

    print("### Pydantic Schemas")
    print("-" * 40)
    print("\nDetection schema:")
    print(create_detection_schema())
    print("\nEnrichmentContext schema:")
    print(create_enrichment_schema())
    print("\nGroundTruth schema:")
    print(create_ground_truth_schema())

    if full_columns:
        print("\nJudgeScores schema:")
        print(create_judge_scores_schema())
    print()

    print("### Configuration Constants")
    print("-" * 40)
    print(f"  Risk ranges: {RISK_RANGES}")
    print(f"  Entry points: {ENTRY_POINTS}")
    print(f"  Object types: {OBJECT_TYPES}")
    print(f"  Enrichment models: {ENRICHMENT_MODELS}")
    print()

    print("### Output Path")
    print("-" * 40)
    print(f"  {DEFAULT_OUTPUT_PATH}")
    print()

    # Show combinatorial coverage info
    if full_columns:
        print("### Combinatorial Coverage")
        print("-" * 40)
        total_combos = 1
        for col_name, col_config in SAMPLER_COLUMNS.items():
            num_values = len(col_config["values"])
            total_combos *= num_values
            print(f"  {col_name}: {num_values} values")
        print(f"  Total possible combinations: {total_combos:,}")
        print("  Recommended minimum rows: 1,500 (covers key combinations)")
        print()


def generate_scenarios(
    num_rows: int,
    output_path: Path | None = None,
    full_columns: bool = False,
    include_embeddings: bool = False,
    dry_run: bool = False,
) -> Path:
    """Generate synthetic scenarios and save to parquet.

    Args:
        num_rows: Number of scenarios to generate
        output_path: Optional custom output path (defaults to fixtures dir)
        full_columns: Whether to include all 24 columns
        include_embeddings: Whether to generate embedding vectors
        dry_run: If True, generate synthetic data without API calls

    Returns:
        Path to the generated parquet file

    Raises:
        ImportError: If data-designer package is not installed (when not dry_run)
        OSError: If NVIDIA_API_KEY is not set (when not dry_run)
    """

    # Determine output directory
    if output_path is None:
        output_path = DEFAULT_OUTPUT_PATH
    else:
        # If path ends with / or is an existing directory, treat as directory
        path_str = str(output_path)
        if path_str.endswith("/") or output_path.is_dir() or not output_path.suffix:
            output_path = output_path / "scenarios.parquet"

    output_dir = output_path.parent

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        # Generate synthetic scenarios locally
        df = generate_dry_run_scenarios(num_rows)
    else:
        # Check for NVIDIA API key
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            msg = (
                "NVIDIA_API_KEY environment variable not set.\n"
                "Get your API key from https://build.nvidia.com and set it:\n"
                "  export NVIDIA_API_KEY=nvapi-xxx\n"
                "\nOr use --dry-run for local generation without API."
            )
            raise OSError(msg)

        # Import data-designer (optional dependency)
        try:
            from data_designer import DataDesigner
            from data_designer.config import Config
        except ImportError as e:
            msg = (
                "data-designer package not installed.\n"
                "Install with: uv sync --group nemo\n"
                "\nOr use --dry-run for local generation without the package."
            )
            raise ImportError(msg) from e

        # Configure data designer with NVIDIA API
        config = Config(
            api_provider="nvidia",
            api_key=api_key,
            model="nvidia/nemotron-4-340b-instruct",  # Use Nemotron for consistency
        )

        designer = DataDesigner(config)

        # Configure the workflow
        designer = create_workflow(designer)

        # Generate scenarios
        print(f"Generating {num_rows} scenarios via NVIDIA API...")
        df = designer.generate(num_rows=num_rows)

        # Add scenario_id column if not present
        if "scenario_id" not in df.columns:
            df["scenario_id"] = [f"scn_{i:05d}" for i in range(len(df))]

    # Add full columns if requested
    if full_columns:
        df = add_full_columns(df, include_embeddings=include_embeddings)

    # Save main parquet file
    df.to_parquet(output_path, index=False)
    print(f"Saved {len(df)} scenarios to {output_path}")

    # Export additional files if full columns
    if full_columns:
        export_ground_truth(df, output_dir)
        export_coverage_report(df, output_dir)
        if include_embeddings:
            export_embeddings(df, output_dir)

    return output_path


def main() -> int:
    """Main entry point for CLI.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Generate synthetic security scenarios using NeMo Data Designer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview workflow configuration
  uv run python tools/nemo_data_designer/generate_scenarios.py --preview

  # Preview with full 24-column configuration
  uv run python tools/nemo_data_designer/generate_scenarios.py --preview --full-columns

  # Generate 100 scenarios (requires NVIDIA_API_KEY)
  uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 100

  # Generate 1500 scenarios with full columns (dry run - no API needed)
  uv run python tools/nemo_data_designer/generate_scenarios.py \\
      --generate --rows 1500 --full-columns --dry-run

  # Generate with embeddings and full columns
  uv run python tools/nemo_data_designer/generate_scenarios.py \\
      --generate --rows 1500 --full-columns --embeddings \\
      --output backend/tests/fixtures/synthetic/

Environment:
  NVIDIA_API_KEY  Required for generation (unless using --dry-run).
                  Get from https://build.nvidia.com
        """,
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview workflow configuration without generating",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate scenarios and save to parquet",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=100,
        help="Number of scenarios to generate (default: 100)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Output parquet path or directory (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--full-columns",
        action="store_true",
        help="Include all 24 columns (samplers, LLM, judge, embeddings, expression, validation)",
    )
    parser.add_argument(
        "--embeddings",
        action="store_true",
        help="Generate embedding vectors (placeholder unless using NVIDIA API)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate synthetic scenarios locally without API calls (for testing)",
    )

    args = parser.parse_args()

    # Require at least one action
    if not args.preview and not args.generate:
        parser.print_help()
        print("\nError: Must specify --preview or --generate")
        return 1

    # Preview mode
    if args.preview:
        preview_workflow(full_columns=args.full_columns)

    # Generate mode
    if args.generate:
        try:
            output_path = generate_scenarios(
                num_rows=args.rows,
                output_path=args.output,
                full_columns=args.full_columns,
                include_embeddings=args.embeddings,
                dry_run=args.dry_run,
            )
            print(f"\nGeneration complete: {output_path}")

            # Show summary of what was generated
            if args.full_columns:
                output_dir = output_path.parent
                print("\nGenerated files:")
                print(f"  - {output_path} (main scenarios)")
                print(f"  - {output_dir / 'ground_truth.json'}")
                print(f"  - {output_dir / 'coverage_report.json'}")
                if args.embeddings:
                    print(f"  - {output_dir / 'embeddings.npz'}")

        except (ImportError, OSError) as e:
            print(f"\nError: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
