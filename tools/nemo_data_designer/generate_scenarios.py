#!/usr/bin/env python3
"""Generate synthetic security scenarios using NeMo Data Designer.

This script uses NVIDIA NeMo Data Designer to generate synthetic scenarios
for testing the home security pipeline and evaluating Nemotron prompts.

Usage:
    # Preview the workflow configuration without generating
    uv run python tools/nemo_data_designer/generate_scenarios.py --preview

    # Generate 100 scenarios and save to fixtures
    uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 100

    # Generate with custom output path
    uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 500 \\
        --output /path/to/output.parquet

Requirements:
    - NVIDIA_API_KEY environment variable set
    - data-designer package installed: uv sync --group nemo
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data_designer import DataDesigner

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.nemo_data_designer.config import (
    ENRICHMENT_MODELS,
    ENTRY_POINTS,
    OBJECT_TYPES,
    RISK_RANGES,
    SAMPLER_COLUMNS,
    Detection,
    EnrichmentContext,
    GroundTruth,
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


def preview_workflow() -> None:
    """Preview the workflow configuration without generating data.

    Displays the column configuration and sample prompts to verify
    the workflow is correctly configured before running generation.
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

    print("### Pydantic Schemas")
    print("-" * 40)
    print("\nDetection schema:")
    print(create_detection_schema())
    print("\nEnrichmentContext schema:")
    print(create_enrichment_schema())
    print("\nGroundTruth schema:")
    print(create_ground_truth_schema())
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


def generate_scenarios(num_rows: int, output_path: Path | None = None) -> Path:
    """Generate synthetic scenarios and save to parquet.

    Args:
        num_rows: Number of scenarios to generate
        output_path: Optional custom output path (defaults to fixtures dir)

    Returns:
        Path to the generated parquet file

    Raises:
        ImportError: If data-designer package is not installed
        OSError: If NVIDIA_API_KEY is not set
    """
    # Check for NVIDIA API key
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        msg = (
            "NVIDIA_API_KEY environment variable not set.\n"
            "Get your API key from https://build.nvidia.com and set it:\n"
            "  export NVIDIA_API_KEY=nvapi-xxx"
        )
        raise OSError(msg)

    # Import data-designer (optional dependency)
    try:
        from data_designer import DataDesigner
        from data_designer.config import Config
    except ImportError as e:
        msg = "data-designer package not installed.\nInstall with: uv sync --group nemo"
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
    print(f"Generating {num_rows} scenarios...")
    df = designer.generate(num_rows=num_rows)

    # Determine output path
    if output_path is None:
        output_path = DEFAULT_OUTPUT_PATH

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to parquet
    df.to_parquet(output_path, index=False)
    print(f"Saved {len(df)} scenarios to {output_path}")

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

  # Generate 100 scenarios
  uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 100

  # Generate with custom output
  uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 500 \\
      --output custom_scenarios.parquet

Environment:
  NVIDIA_API_KEY  Required for generation. Get from https://build.nvidia.com
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
        help=f"Output parquet path (default: {DEFAULT_OUTPUT_PATH})",
    )

    args = parser.parse_args()

    # Require at least one action
    if not args.preview and not args.generate:
        parser.print_help()
        print("\nError: Must specify --preview or --generate")
        return 1

    # Preview mode
    if args.preview:
        preview_workflow()

    # Generate mode
    if args.generate:
        try:
            output_path = generate_scenarios(args.rows, args.output)
            print(f"\nGeneration complete: {output_path}")
        except (ImportError, OSError) as e:
            print(f"\nError: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
