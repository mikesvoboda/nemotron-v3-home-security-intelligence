"""Prompt evaluation harness for comparing Nemotron templates.

This module provides the PromptEvaluator class for running scenarios through
different prompt templates and capturing results for comparison.

The harness supports:
- Loading scenarios from parquet files or mock data
- Running 5 prompt templates against each scenario
- Async evaluation with progress reporting
- Both real Nemotron calls and mock mode for testing
- CLI interface for standalone execution

Usage:
    # Programmatic
    evaluator = PromptEvaluator(mock_mode=True)
    results = await evaluator.evaluate_all(scenarios_df)

    # CLI
    python -m backend.evaluation.harness --scenarios path.parquet --output results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from backend.evaluation.metrics import (
    calculate_key_point_coverage,
    calculate_reasoning_similarity,
    calculate_risk_deviation,
)

if TYPE_CHECKING:
    import pandas as pd


# Lazy import pandas to allow module import without pandas installed
# pandas is required for actual evaluation but not for type checking
def _get_pandas() -> Any:
    """Lazy import pandas.

    Returns:
        The pandas module.

    Raises:
        ImportError: If pandas is not installed.
    """
    try:
        import pandas

        return pandas
    except ImportError:
        raise ImportError(
            "pandas is required for evaluation harness. Install with: uv sync --extra nemo"
        ) from None


# Default Nemotron endpoint
DEFAULT_NEMOTRON_URL = "http://localhost:8091/v1/completions"

# Timeout configuration
NEMOTRON_CONNECT_TIMEOUT = 10.0
NEMOTRON_READ_TIMEOUT = 120.0

# Pre-compiled regex for JSON extraction
_JSON_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclass
class PromptTemplate:
    """Definition of a prompt template for evaluation.

    Attributes:
        name: Short identifier for the template
        description: Human-readable description
        template_key: Key used in prompts.py (e.g., "RISK_ANALYSIS_PROMPT")
        enrichment_required: Whether this template requires enrichment context
    """

    name: str
    description: str
    template_key: str
    enrichment_required: str  # "none", "basic", "full", "vision", "model_zoo"


# The 5 prompt templates from backend/services/prompts.py
PROMPT_TEMPLATES = [
    PromptTemplate(
        name="basic",
        description="Basic prompt without enrichment context",
        template_key="RISK_ANALYSIS_PROMPT",
        enrichment_required="none",
    ),
    PromptTemplate(
        name="enriched",
        description="Enriched prompt with zone/baseline context",
        template_key="ENRICHED_RISK_ANALYSIS_PROMPT",
        enrichment_required="basic",
    ),
    PromptTemplate(
        name="full_enriched",
        description="Full enriched with vision enrichment (plates, faces, OCR)",
        template_key="FULL_ENRICHED_RISK_ANALYSIS_PROMPT",
        enrichment_required="full",
    ),
    PromptTemplate(
        name="vision_enhanced",
        description="Vision-enhanced with Florence-2 attributes and re-ID",
        template_key="VISION_ENHANCED_RISK_ANALYSIS_PROMPT",
        enrichment_required="vision",
    ),
    PromptTemplate(
        name="model_zoo_enhanced",
        description="Model zoo enhanced with all enrichment models",
        template_key="MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT",
        enrichment_required="model_zoo",
    ),
]


@dataclass
class EvaluationResult:
    """Result from evaluating a single scenario with a single template.

    Attributes:
        scenario_id: Unique identifier for the scenario
        template_name: Name of the prompt template used
        scenario_type: Classification (normal, suspicious, threat, edge_case)
        enrichment_level: Level of enrichment in the scenario
        risk_score: Generated risk score (0-100)
        risk_level: Generated risk level (low, medium, high, critical)
        reasoning: Generated reasoning text
        summary: Generated summary text
        ground_truth_range: Expected risk score range
        risk_deviation: Deviation from ground truth range
        key_point_coverage: Fraction of key points mentioned
        reasoning_similarity: Similarity to expected reasoning
        latency_ms: Time taken for LLM call in milliseconds
        success: Whether the evaluation completed successfully
        error_message: Error message if evaluation failed
    """

    scenario_id: str
    template_name: str
    scenario_type: str
    enrichment_level: str
    risk_score: int = 0
    risk_level: str = ""
    reasoning: str = ""
    summary: str = ""
    ground_truth_range: tuple[int, int] = (0, 100)
    risk_deviation: float = 0.0
    key_point_coverage: float = 0.0
    reasoning_similarity: float = 0.0
    latency_ms: float = 0.0
    success: bool = True
    error_message: str = ""


@dataclass
class MockScenario:
    """Mock scenario for testing without real data.

    Provides minimal scenario data for testing the evaluation harness
    without requiring actual NeMo Data Designer output.
    """

    scenario_id: str
    scenario_type: str
    enrichment_level: str
    time_of_day: str
    camera_location: str
    detections_list: str
    ground_truth_range: tuple[int, int]
    reasoning_key_points: list[str]
    expected_summary: str


def generate_mock_scenarios(count: int = 20) -> pd.DataFrame:
    """Generate mock scenarios for testing.

    Creates a balanced set of scenarios across scenario types and
    enrichment levels for harness testing without NeMo Data Designer.

    Args:
        count: Number of scenarios to generate (default 20)

    Returns:
        DataFrame with mock scenario data matching the expected schema
    """
    # nosemgrep: insecure-random - Random is used for generating non-sensitive mock test data
    import random

    pd = _get_pandas()

    scenario_types = ["normal", "suspicious", "threat", "edge_case"]
    enrichment_levels = ["none", "basic", "full"]
    times_of_day = ["morning", "midday", "evening", "night", "late_night"]
    camera_locations = ["front_door", "backyard", "driveway", "side_gate"]

    # Ground truth risk ranges by scenario type
    risk_ranges = {
        "normal": (0, 25),
        "suspicious": (30, 55),
        "threat": (70, 100),
        "edge_case": (20, 60),
    }

    # Example detection lists by scenario type
    detection_templates = {
        "normal": [
            "1 person detected at 0s (confidence: 0.92)",
            "1 car detected at 5s (confidence: 0.88), 1 person at 10s (confidence: 0.95)",
            "1 dog detected at 0s (confidence: 0.85)",
        ],
        "suspicious": [
            "1 person detected at 0s (confidence: 0.78), lingering for 45s",
            "1 person at 0s near entry point, 1 person at 30s same location",
            "1 unknown vehicle at 0s (confidence: 0.82), idling for 60s",
        ],
        "threat": [
            "1 person at 0s attempting to open door, no vehicle nearby",
            "2 persons at 0s, masks detected, approaching entry point rapidly",
            "1 person at 0s with tool-like object near window",
        ],
        "edge_case": [
            "1 person at 0s with large package (delivery?), late night",
            "1 person at 0s wearing costume/unusual attire",
            "1 animal at 0s (large, possibly wildlife)",
        ],
    }

    # Key points by scenario type
    key_points_templates = {
        "normal": [["expected activity", "daytime", "known area"]],
        "suspicious": [
            ["unknown person", "lingering", "unusual time"],
            ["unusual behavior", "entry point"],
        ],
        "threat": [
            ["forced entry", "unauthorized access", "immediate concern"],
            ["multiple persons", "concealed identity", "threatening"],
        ],
        "edge_case": [
            ["ambiguous", "requires context", "possible delivery"],
            ["unusual appearance", "uncertain intent"],
        ],
    }

    scenarios = []
    for i in range(count):
        scenario_type = scenario_types[i % len(scenario_types)]
        enrichment_level = enrichment_levels[i % len(enrichment_levels)]

        # Generate random values for mock scenario (non-security-sensitive test data)
        time_of_day = random.choice(times_of_day)  # nosemgrep: insecure-random
        camera_loc = random.choice(camera_locations)  # nosemgrep: insecure-random
        day = random.choice(["weekday", "weekend"])  # nosemgrep: insecure-random
        detections = random.choice(detection_templates[scenario_type])  # nosemgrep: insecure-random
        # nosemgrep: insecure-random - test data generation
        key_points = random.choice(key_points_templates[scenario_type])

        scenarios.append(
            {
                "scenario_id": f"mock_{i:04d}",
                "scenario_type": scenario_type,
                "enrichment_level": enrichment_level,
                "time_of_day": time_of_day,
                "camera_location": camera_loc,
                "day_type": day,
                "detections_list": detections,
                "ground_truth_range": risk_ranges[scenario_type],
                "reasoning_key_points": key_points,
                "expected_summary": f"Mock {scenario_type} scenario for testing",
                # Add fields needed for prompt rendering
                "zone_analysis": "Zone: front_door (entry_point: true)",
                "baseline_comparison": "Expected: 2-5 detections, Actual: 1",
                "deviation_score": 0.3 if scenario_type == "normal" else 0.7,
                "cross_camera_summary": "No activity on other cameras",
                "enrichment_context": "No enrichment data available",
            }
        )

    return pd.DataFrame(scenarios)


class PromptEvaluator:
    """Evaluator for comparing prompt templates against scenarios.

    Runs each prompt template against a set of scenarios, captures the
    Nemotron output, and calculates evaluation metrics.

    Attributes:
        nemotron_url: URL of the Nemotron completions endpoint
        mock_mode: If True, generates mock responses instead of calling Nemotron
        timeout: httpx.Timeout configuration for Nemotron calls
        results: List of EvaluationResult objects after evaluation
    """

    def __init__(
        self,
        nemotron_url: str = DEFAULT_NEMOTRON_URL,
        mock_mode: bool = False,
        timeout: httpx.Timeout | None = None,
    ):
        """Initialize the prompt evaluator.

        Args:
            nemotron_url: URL of the Nemotron completions endpoint
            mock_mode: If True, generate mock responses (for testing)
            timeout: Optional httpx.Timeout configuration
        """
        self.nemotron_url = nemotron_url
        self.mock_mode = mock_mode
        self.timeout = timeout or httpx.Timeout(
            connect=NEMOTRON_CONNECT_TIMEOUT,
            read=NEMOTRON_READ_TIMEOUT,
            write=NEMOTRON_READ_TIMEOUT,
            pool=NEMOTRON_CONNECT_TIMEOUT,
        )
        self.results: list[EvaluationResult] = []
        self._templates = PROMPT_TEMPLATES

    def _render_prompt(
        self,
        template: PromptTemplate,
        scenario: dict[str, Any],
    ) -> str:
        """Render a prompt template with scenario data.

        Creates the full prompt text by substituting scenario values
        into the template placeholders.

        Args:
            template: The prompt template to render
            scenario: Dictionary containing scenario data

        Returns:
            Fully rendered prompt string
        """
        # Import the actual templates from prompts.py
        from backend.services.prompts import (
            ENRICHED_RISK_ANALYSIS_PROMPT,
            FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
            MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
            RISK_ANALYSIS_PROMPT,
            VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
        )

        template_map = {
            "RISK_ANALYSIS_PROMPT": RISK_ANALYSIS_PROMPT,
            "ENRICHED_RISK_ANALYSIS_PROMPT": ENRICHED_RISK_ANALYSIS_PROMPT,
            "FULL_ENRICHED_RISK_ANALYSIS_PROMPT": FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
            "VISION_ENHANCED_RISK_ANALYSIS_PROMPT": VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
            "MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT": MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
        }

        prompt_template = template_map[template.template_key]

        # Build substitution dict based on template requirements
        now = datetime.now(UTC)
        subs = {
            "camera_name": scenario.get("camera_location", "front_door"),
            "start_time": now.strftime("%H:%M:%S"),
            "end_time": now.strftime("%H:%M:%S"),
            "detections_list": scenario.get("detections_list", "No detections"),
        }

        # Add enriched context fields if needed
        if template.enrichment_required in ("basic", "full", "vision", "model_zoo"):
            subs.update(
                {
                    "day_of_week": scenario.get("day_type", "weekday"),
                    "hour": now.hour,
                    "zone_analysis": scenario.get("zone_analysis", "No zone data available"),
                    "baseline_comparison": scenario.get("baseline_comparison", "No baseline data"),
                    "deviation_score": scenario.get("deviation_score", 0.0),
                    "cross_camera_summary": scenario.get(
                        "cross_camera_summary", "No cross-camera data"
                    ),
                }
            )

        # Add full enrichment context if needed
        if template.enrichment_required in ("full", "vision", "model_zoo"):
            subs["enrichment_context"] = scenario.get(
                "enrichment_context", "No enrichment available"
            )

        # Add vision-enhanced fields if needed
        if template.enrichment_required in ("vision", "model_zoo"):
            subs.update(
                {
                    "timestamp": now.isoformat(),
                    "time_of_day": scenario.get("time_of_day", "daytime"),
                    "camera_health_context": "Camera health: OK",
                    "detections_with_attributes": scenario.get("detections_list", "No detections"),
                    "reid_context": "No re-identification matches",
                    "scene_analysis": "Standard residential scene",
                }
            )

        # Add model zoo fields if needed
        if template.enrichment_required == "model_zoo":
            subs.update(
                {
                    "household_context": "No household members identified",
                    "pose_analysis": "No pose data available",
                    "clothing_analysis": "No clothing analysis available",
                    "vehicle_classification": "No vehicles classified",
                    "vehicle_damage": "No damage detected",
                    "pet_classification": "No pets classified",
                    "weather_context": "Weather: Clear",
                    "depth_context": "No depth data available",
                    "image_quality_context": "Image quality: Good",
                    "action_recognition": "No actions recognized",
                    "violence_context": "No violence detected",
                }
            )

        # Render the template
        try:
            return prompt_template.format(**subs)
        except KeyError as e:
            # If a placeholder is missing, return a simplified version
            # This handles cases where the template has more placeholders than we provide
            return f"Error rendering template: missing {e}"

    def _parse_llm_response(self, response_text: str) -> dict[str, Any]:
        """Parse LLM response to extract risk assessment.

        Handles the Nemotron response format which may include <think>
        blocks before the JSON output.

        Args:
            response_text: Raw response text from Nemotron

        Returns:
            Dictionary with risk_score, risk_level, reasoning, summary
        """
        # Remove <think> blocks
        text = _THINK_PATTERN.sub("", response_text).strip()

        # Find JSON in response
        match = _JSON_PATTERN.search(text)
        if match:
            try:
                data = json.loads(match.group())
                return {
                    "risk_score": int(data.get("risk_score", 50)),
                    "risk_level": str(data.get("risk_level", "medium")),
                    "reasoning": str(data.get("reasoning", "")),
                    "summary": str(data.get("summary", "")),
                }
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback if JSON parsing fails
        return {
            "risk_score": 50,
            "risk_level": "medium",
            "reasoning": "Failed to parse response",
            "summary": "Parsing error",
        }

    def _generate_mock_response(
        self,
        scenario: dict[str, Any],
        template: PromptTemplate,  # noqa: ARG002 - reserved for future template-specific mock logic
    ) -> dict[str, Any]:
        """Generate a mock response for testing.

        Creates a plausible response based on the scenario type and
        ground truth range, with some random variation.

        Args:
            scenario: The scenario being evaluated
            template: The prompt template being used (reserved for future use)

        Returns:
            Dictionary with mock risk assessment
        """
        # nosemgrep: insecure-random - Random is used for generating non-sensitive mock test data
        import random

        ground_truth = scenario.get("ground_truth_range", (30, 60))
        min_score, max_score = ground_truth

        # Generate score within or slightly outside ground truth range
        # 80% chance of being within range (nosemgrep: insecure-random - test data)
        in_range = random.random() < 0.8  # nosemgrep: insecure-random
        if in_range:
            risk_score = random.randint(min_score, max_score)  # nosemgrep: insecure-random
        else:
            # 20% chance of deviation
            deviation = random.randint(5, 20)  # nosemgrep: insecure-random
            below = random.random() < 0.5  # nosemgrep: insecure-random
            risk_score = max(0, min_score - deviation) if below else min(100, max_score + deviation)

        # Determine risk level
        if risk_score < 30:
            risk_level = "low"
        elif risk_score < 60:
            risk_level = "medium"
        elif risk_score < 85:
            risk_level = "high"
        else:
            risk_level = "critical"

        # Generate reasoning using some key points
        key_points = scenario.get("reasoning_key_points", [])
        if key_points:
            reasoning_parts = [
                f"Analysis indicates {scenario.get('scenario_type', 'unknown')} activity."
            ]
            num_points = random.randint(1, len(key_points))  # nosemgrep: insecure-random
            for point in key_points[:num_points]:
                reasoning_parts.append(f"Detected: {point}.")
            reasoning = " ".join(reasoning_parts)
        else:
            reasoning = f"Mock reasoning for {scenario.get('scenario_type', 'unknown')} scenario."

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "reasoning": reasoning,
            "summary": scenario.get("expected_summary", "Mock summary"),
        }

    async def _call_nemotron(
        self,
        prompt: str,
        scenario: dict[str, Any],
        template: PromptTemplate,
    ) -> tuple[dict[str, Any], float]:
        """Call Nemotron API or generate mock response.

        Args:
            prompt: The rendered prompt text
            scenario: The scenario being evaluated
            template: The prompt template being used

        Returns:
            Tuple of (response_dict, latency_ms)
        """
        import time

        start_time = time.perf_counter()

        if self.mock_mode:
            # Simulate some latency
            await asyncio.sleep(0.01)
            response = self._generate_mock_response(scenario, template)
            latency_ms = (time.perf_counter() - start_time) * 1000
            return response, latency_ms

        # Real Nemotron call
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                http_response = await client.post(
                    self.nemotron_url,
                    json={
                        "prompt": prompt,
                        "max_tokens": 512,
                        "temperature": 0.1,
                        "stop": ["<|im_end|>"],
                    },
                )
                http_response.raise_for_status()
                data = http_response.json()

                # Extract completion text
                completion_text = ""
                if data.get("choices"):
                    completion_text = data["choices"][0].get("text", "")

                parsed = self._parse_llm_response(completion_text)
                latency_ms = (time.perf_counter() - start_time) * 1000
                return parsed, latency_ms

            except httpx.HTTPError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                return {
                    "risk_score": 50,
                    "risk_level": "medium",
                    "reasoning": f"HTTP error: {e}",
                    "summary": "Service unavailable",
                }, latency_ms

    async def evaluate_scenario(
        self,
        scenario: dict[str, Any],
        template: PromptTemplate,
    ) -> EvaluationResult:
        """Evaluate a single scenario with a single template.

        Args:
            scenario: Dictionary containing scenario data
            template: The prompt template to use

        Returns:
            EvaluationResult with all metrics
        """
        scenario_id = scenario.get("scenario_id", "unknown")
        scenario_type = scenario.get("scenario_type", "unknown")
        enrichment_level = scenario.get("enrichment_level", "none")
        ground_truth_range = scenario.get("ground_truth_range", (0, 100))
        key_points = scenario.get("reasoning_key_points", [])
        expected_summary = scenario.get("expected_summary", "")

        try:
            # Render and call
            prompt = self._render_prompt(template, scenario)
            response, latency_ms = await self._call_nemotron(prompt, scenario, template)

            # Calculate metrics
            risk_deviation = calculate_risk_deviation(response["risk_score"], ground_truth_range)
            key_point_coverage = calculate_key_point_coverage(response["reasoning"], key_points)
            reasoning_similarity = calculate_reasoning_similarity(
                response["reasoning"], expected_summary
            )

            return EvaluationResult(
                scenario_id=scenario_id,
                template_name=template.name,
                scenario_type=scenario_type,
                enrichment_level=enrichment_level,
                risk_score=response["risk_score"],
                risk_level=response["risk_level"],
                reasoning=response["reasoning"],
                summary=response["summary"],
                ground_truth_range=ground_truth_range,
                risk_deviation=risk_deviation,
                key_point_coverage=key_point_coverage,
                reasoning_similarity=reasoning_similarity,
                latency_ms=latency_ms,
                success=True,
                error_message="",
            )

        except Exception as e:
            return EvaluationResult(
                scenario_id=scenario_id,
                template_name=template.name,
                scenario_type=scenario_type,
                enrichment_level=enrichment_level,
                success=False,
                error_message=str(e),
            )

    async def evaluate_all(
        self,
        scenarios: pd.DataFrame,
        templates: list[PromptTemplate] | None = None,
        progress_callback: Any | None = None,
    ) -> pd.DataFrame:
        """Evaluate all scenarios with all templates.

        Runs each template against each scenario and returns a DataFrame
        with all results.

        Args:
            scenarios: DataFrame with scenario data
            templates: Optional list of templates to use (defaults to all 5)
            progress_callback: Optional callback for progress reporting.
                Called with (current, total) for each evaluation.

        Returns:
            DataFrame with evaluation results
        """
        templates = templates or self._templates
        self.results = []

        total_evaluations = len(scenarios) * len(templates)
        current = 0

        for _, scenario_row in scenarios.iterrows():
            scenario = scenario_row.to_dict()

            for template in templates:
                result = await self.evaluate_scenario(scenario, template)
                self.results.append(result)

                current += 1
                if progress_callback:
                    progress_callback(current, total_evaluations)

        # Convert to DataFrame
        return self.results_to_dataframe()

    def evaluate_all_sync(
        self,
        scenarios: pd.DataFrame,
        templates: list[PromptTemplate] | None = None,
        progress_callback: Any | None = None,
    ) -> pd.DataFrame:
        """Synchronous wrapper for evaluate_all.

        Args:
            scenarios: DataFrame with scenario data
            templates: Optional list of templates to use
            progress_callback: Optional callback for progress reporting

        Returns:
            DataFrame with evaluation results
        """
        return asyncio.run(self.evaluate_all(scenarios, templates, progress_callback))

    def results_to_dataframe(self) -> pd.DataFrame:
        """Convert results list to DataFrame.

        Returns:
            DataFrame with one row per evaluation result
        """
        pd = _get_pandas()
        if not self.results:
            return pd.DataFrame()

        records = []
        for r in self.results:
            records.append(
                {
                    "scenario_id": r.scenario_id,
                    "template_name": r.template_name,
                    "scenario_type": r.scenario_type,
                    "enrichment_level": r.enrichment_level,
                    "risk_score": r.risk_score,
                    "risk_level": r.risk_level,
                    "reasoning": r.reasoning,
                    "summary": r.summary,
                    "ground_truth_min": r.ground_truth_range[0],
                    "ground_truth_max": r.ground_truth_range[1],
                    "risk_deviation": r.risk_deviation,
                    "key_point_coverage": r.key_point_coverage,
                    "reasoning_similarity": r.reasoning_similarity,
                    "latency_ms": r.latency_ms,
                    "success": r.success,
                    "error_message": r.error_message,
                }
            )

        return pd.DataFrame(records)

    def get_metrics(self) -> dict:
        """Get aggregated metrics from evaluation results.

        Returns:
            Dictionary with aggregated metrics
        """
        from backend.evaluation.metrics import aggregate_metrics

        df = self.results_to_dataframe()
        return aggregate_metrics(df)


def _print_progress(current: int, total: int) -> None:
    """Print progress bar to stderr."""
    pct = current / total * 100
    bar_len = 40
    filled = int(bar_len * current / total)
    bar = "=" * filled + "-" * (bar_len - filled)
    sys.stderr.write(f"\r[{bar}] {pct:.1f}% ({current}/{total})")
    sys.stderr.flush()
    if current == total:
        sys.stderr.write("\n")


def main() -> int:
    """CLI entry point for the evaluation harness.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Evaluate Nemotron prompt templates against scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with mock data (no Nemotron required)
  python -m backend.evaluation.harness --mock --output reports/test.json

  # Run with real scenarios
  python -m backend.evaluation.harness --scenarios fixtures/scenarios.parquet --output results.json

  # Generate HTML report
  python -m backend.evaluation.harness --mock --output results.json --format html
        """,
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        help="Path to scenarios parquet file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for output report",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock mode (generate fake responses)",
    )
    parser.add_argument(
        "--mock-count",
        type=int,
        default=20,
        help="Number of mock scenarios to generate (default: 20)",
    )
    parser.add_argument(
        "--nemotron-url",
        type=str,
        default=DEFAULT_NEMOTRON_URL,
        help=f"Nemotron API URL (default: {DEFAULT_NEMOTRON_URL})",
    )
    parser.add_argument(
        "--format",
        choices=["json", "html"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Load or generate scenarios
    if args.scenarios:
        if not args.scenarios.exists():
            print(f"Error: Scenarios file not found: {args.scenarios}", file=sys.stderr)
            return 1
        print(f"Loading scenarios from {args.scenarios}...", file=sys.stderr)
        pd = _get_pandas()
        scenarios = pd.read_parquet(args.scenarios)
    elif args.mock:
        print(f"Generating {args.mock_count} mock scenarios...", file=sys.stderr)
        scenarios = generate_mock_scenarios(args.mock_count)
    else:
        print("Error: Either --scenarios or --mock must be specified", file=sys.stderr)
        return 1

    print(f"Loaded {len(scenarios)} scenarios", file=sys.stderr)

    # Create evaluator
    evaluator = PromptEvaluator(
        nemotron_url=args.nemotron_url,
        mock_mode=args.mock or not args.scenarios,
    )

    # Run evaluation
    progress_callback = None if args.quiet else _print_progress
    results_df = evaluator.evaluate_all_sync(scenarios, progress_callback=progress_callback)

    # Generate report
    from backend.evaluation.reports import (
        generate_html_report,
        generate_json_report,
        save_report,
    )

    metrics = evaluator.get_metrics()

    report: dict | str
    if args.format == "json":
        report = generate_json_report(results_df, metrics)
    else:
        report = generate_html_report(results_df, metrics)

    # Save report
    save_report(report, args.output, args.format)
    print(f"\nReport saved to {args.output}", file=sys.stderr)

    # Print summary
    print("\n=== Evaluation Summary ===", file=sys.stderr)
    print(f"Total scenarios evaluated: {metrics['overall']['total_scenarios']}", file=sys.stderr)
    print(f"Mean risk deviation: {metrics['overall']['mean_risk_deviation']:.2f}", file=sys.stderr)
    print(f"Within range: {metrics['overall']['within_range_pct']:.1f}%", file=sys.stderr)
    print(
        f"Mean key point coverage: {metrics['overall']['mean_key_point_coverage']:.2f}",
        file=sys.stderr,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
