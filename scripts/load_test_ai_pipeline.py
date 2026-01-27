#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
#     "rich",
#     "pillow",
# ]
# ///
# ABOUTME: Load testing script for AI pipeline using synthetic data.
# ABOUTME: Exercises YOLO26, Florence, Enrichment, and Nemotron services.
"""
AI Pipeline Load Testing with Synthetic Data.

This script exercises the end-to-end AI pipeline using synthetic data with
known ground truth labels. It helps identify:
- Prompt adjustments needed
- Malfunctioning models
- Risk score calibration issues
- False positives/negatives

Usage:
    # Test all synthetic data
    uv run scripts/load_test_ai_pipeline.py --all

    # Test specific category
    uv run scripts/load_test_ai_pipeline.py --category threats

    # Test specific scenario
    uv run scripts/load_test_ai_pipeline.py --scenario break_in_attempt

    # Quick sanity check (first sample of each category)
    uv run scripts/load_test_ai_pipeline.py --quick

    # Verbose output with detailed diffs
    uv run scripts/load_test_ai_pipeline.py --all --verbose

    # Save detailed report
    uv run scripts/load_test_ai_pipeline.py --all --output report.json
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.synthetic.comparison_engine import ComparisonEngine, ComparisonResult

console = Console()

# AI Service endpoints
YOLO26_URL = "http://localhost:8095"
FLORENCE_URL = "http://localhost:8092"
ENRICHMENT_URL = "http://localhost:8094"
NEMOTRON_URL = "http://localhost:8091"
BACKEND_URL = "http://localhost:8000"

# Synthetic data directory
SYNTHETIC_DATA_DIR = PROJECT_ROOT / "data" / "synthetic"

# Timeouts
AI_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)


@dataclass
class ServiceHealth:
    """Health status of an AI service."""
    name: str
    healthy: bool
    url: str
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result from processing a single sample through the pipeline."""
    sample_id: str
    scenario: str
    category: str
    media_file: str

    # Raw results from each service
    yolo_result: dict[str, Any] | None = None
    florence_result: dict[str, Any] | None = None
    enrichment_result: dict[str, Any] | None = None
    nemotron_result: dict[str, Any] | None = None

    # Timing
    yolo_time_ms: float = 0.0
    florence_time_ms: float = 0.0
    enrichment_time_ms: float = 0.0
    nemotron_time_ms: float = 0.0
    total_time_ms: float = 0.0

    # Comparison result
    comparison: ComparisonResult | None = None

    # Errors
    errors: list[str] = field(default_factory=list)


@dataclass
class TestReport:
    """Aggregate test report for all samples."""
    run_id: str
    started_at: str
    completed_at: str

    # Summary
    total_samples: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0

    # By category
    by_category: dict[str, dict[str, int]] = field(default_factory=dict)

    # By scenario
    by_scenario: dict[str, dict[str, int]] = field(default_factory=dict)

    # Detailed results
    results: list[PipelineResult] = field(default_factory=list)

    # Field-level analysis
    field_failures: dict[str, int] = field(default_factory=dict)

    # Timing stats
    avg_total_time_ms: float = 0.0
    avg_yolo_time_ms: float = 0.0
    avg_florence_time_ms: float = 0.0
    avg_enrichment_time_ms: float = 0.0
    avg_nemotron_time_ms: float = 0.0


class AIPipelineTester:
    """Tests AI pipeline with synthetic data."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.comparison_engine = ComparisonEngine()
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=AI_TIMEOUT)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def check_service_health(self, name: str, url: str) -> ServiceHealth:
        """Check if an AI service is healthy."""
        try:
            # Nemotron (llama.cpp) uses /v1/models instead of /health
            if "8091" in url:  # Nemotron
                response = await self.client.get(f"{url}/v1/models")
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", data.get("data", []))
                    return ServiceHealth(
                        name=name,
                        healthy=len(models) > 0,
                        url=url,
                        details={"models": [m.get("id", m.get("name", "unknown")) for m in models]},
                    )
            else:
                response = await self.client.get(f"{url}/health")
                if response.status_code == 200:
                    data = response.json()
                    return ServiceHealth(
                        name=name,
                        healthy=data.get("status") == "healthy" or data.get("model_loaded", False),
                        url=url,
                        details=data,
                    )
            return ServiceHealth(
                name=name,
                healthy=False,
                url=url,
                error=f"HTTP {response.status_code}",
            )
        except Exception as e:
            return ServiceHealth(
                name=name,
                healthy=False,
                url=url,
                error=str(e),
            )

    async def check_all_services(self) -> list[ServiceHealth]:
        """Check health of all AI services."""
        services = [
            ("YOLO26", YOLO26_URL),
            ("Florence-2", FLORENCE_URL),
            ("Enrichment", ENRICHMENT_URL),
            ("Nemotron LLM", NEMOTRON_URL),
        ]

        tasks = [self.check_service_health(name, url) for name, url in services]
        return await asyncio.gather(*tasks)

    async def detect_objects(self, image_path: Path) -> tuple[dict[str, Any] | None, float]:
        """Send image to YOLO26 for object detection."""
        start = time.perf_counter()
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()

            # Send as multipart file upload (YOLO26 prefers this)
            files = {"file": (image_path.name, image_data, "image/png")}
            response = await self.client.post(
                f"{YOLO26_URL}/detect",
                files=files,
            )

            elapsed_ms = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                return response.json(), elapsed_ms
            # Try to get error detail from response
            try:
                error_detail = response.json().get("detail", f"HTTP {response.status_code}")
            except Exception:
                error_detail = f"HTTP {response.status_code}"
            return {"error": error_detail}, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {"error": str(e)}, elapsed_ms

    async def get_florence_caption(
        self, image_path: Path, prompt: str = "<DETAILED_CAPTION>"
    ) -> tuple[dict[str, Any] | None, float]:
        """Get caption from Florence-2."""
        start = time.perf_counter()
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()

            b64_data = base64.b64encode(image_data).decode("utf-8")
            # Florence uses /extract endpoint with "image" field (not image_base64)
            response = await self.client.post(
                f"{FLORENCE_URL}/extract",
                json={"image": b64_data, "prompt": prompt},
            )

            elapsed_ms = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                return response.json(), elapsed_ms
            try:
                error_detail = response.json().get("detail", f"HTTP {response.status_code}")
            except Exception:
                error_detail = f"HTTP {response.status_code}"
            return {"error": error_detail}, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {"error": str(e)}, elapsed_ms

    async def run_enrichment(
        self, image_path: Path, detections: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, float]:
        """Run enrichment pipeline on detections.

        The enrichment API expects one detection at a time with:
        - image: base64 encoded image
        - detection_type: "person", "vehicle", "animal", or "object"
        - bbox: {"x1": ..., "y1": ..., "x2": ..., "y2": ...}
        """
        start = time.perf_counter()
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()

            b64_data = base64.b64encode(image_data).decode("utf-8")

            # Process each detection through enrichment API
            all_results = {"results": {}}

            for det in detections:
                # Map YOLO class to enrichment detection_type
                yolo_class = det.get("class", "person")
                if yolo_class in ("person", "man", "woman", "child"):
                    detection_type = "person"
                elif yolo_class in ("car", "truck", "bus", "motorcycle", "bicycle"):
                    detection_type = "vehicle"
                elif yolo_class in ("dog", "cat", "bird", "horse", "cow", "sheep"):
                    detection_type = "animal"
                else:
                    detection_type = "object"

                # Convert bbox from {x, y, width, height} to {x1, y1, x2, y2}
                bbox = det.get("bbox", {"x": 0, "y": 0, "width": 100, "height": 100})
                enrichment_bbox = {
                    "x1": float(bbox.get("x", 0)),
                    "y1": float(bbox.get("y", 0)),
                    "x2": float(bbox.get("x", 0) + bbox.get("width", 100)),
                    "y2": float(bbox.get("y", 0) + bbox.get("height", 100)),
                }

                response = await self.client.post(
                    f"{ENRICHMENT_URL}/enrich",
                    json={
                        "image": b64_data,
                        "detection_type": detection_type,
                        "bbox": enrichment_bbox,
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    # Merge results into combined output
                    for key, value in result.items():
                        if key not in all_results["results"]:
                            all_results["results"][key] = value
                        elif isinstance(value, dict) and isinstance(all_results["results"][key], dict):
                            all_results["results"][key].update(value)
                else:
                    all_results["results"][f"error_{detection_type}"] = {
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }

            elapsed_ms = (time.perf_counter() - start) * 1000
            return all_results, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {"error": str(e)}, elapsed_ms

    async def analyze_risk(
        self,
        detections: list[dict[str, Any]],
        enrichment: dict[str, Any] | None,
        florence_caption: str | None,
    ) -> tuple[dict[str, Any] | None, float]:
        """Analyze risk using Nemotron LLM."""
        start = time.perf_counter()
        try:
            # Build context for LLM
            context_parts = []

            # Add detection summary
            if detections:
                det_summary = ", ".join(
                    f"{d.get('class', 'unknown')} ({d.get('confidence', 0):.0%})"
                    for d in detections
                )
                context_parts.append(f"Detections: {det_summary}")

            # Add enrichment context (handle both nested and top-level formats)
            if enrichment:
                results = enrichment.get("results", enrichment)
                for model, result in results.items():
                    # Skip metadata fields
                    if model in ("models_used", "inference_time_ms", "error"):
                        continue
                    if result and isinstance(result, dict) and not result.get("error"):
                        context_parts.append(f"{model}: {json.dumps(result)}")

            # Add Florence caption
            if florence_caption:
                context_parts.append(f"Scene description: {florence_caption}")

            # Build prompt
            prompt = f"""Analyze this security camera observation and provide a risk assessment.

Context:
{chr(10).join(context_parts)}

Provide a JSON response with:
- risk_score: 0-100 integer
- risk_level: "low", "medium", "high", or "critical"
- risk_factors: list of contributing factors
- summary: brief description

Response (JSON only):"""

            response = await self.client.post(
                f"{NEMOTRON_URL}/v1/completions",
                json={
                    "prompt": prompt,
                    "max_tokens": 500,
                    "temperature": 0.1,
                },
            )

            elapsed_ms = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                result = response.json()
                # Try to parse the completion as JSON
                completion = result.get("choices", [{}])[0].get("text", "")
                try:
                    # Extract JSON from response
                    import re
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', completion)
                    if json_match:
                        risk_data = json.loads(json_match.group())
                        return risk_data, elapsed_ms
                except (json.JSONDecodeError, AttributeError):
                    pass
                return {"raw_response": completion, "error": "Failed to parse JSON"}, elapsed_ms
            return {"error": f"HTTP {response.status_code}"}, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {"error": str(e)}, elapsed_ms

    def build_actual_results(
        self,
        yolo_result: dict[str, Any] | None,
        florence_result: dict[str, Any] | None,
        enrichment_result: dict[str, Any] | None,
        nemotron_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build a unified result dict for comparison against expected labels."""
        actual = {}

        # Map YOLO detections
        if yolo_result and "detections" in yolo_result:
            actual["detections"] = yolo_result["detections"]

        # Map Florence caption
        if florence_result and "result" in florence_result:
            actual["florence_caption"] = florence_result.get("result", "")

        # Map enrichment results (top-level fields from enrichment API)
        if enrichment_result:
            # Handle nested "results" format (from load test) or top-level format (from API)
            results = enrichment_result.get("results", enrichment_result)

            # Pose
            pose = results.get("pose")
            if pose and isinstance(pose, dict) and not pose.get("error"):
                actual["pose"] = {
                    "posture": pose.get("posture"),
                    "is_suspicious": pose.get("is_suspicious", False),
                    "keypoints_visible": pose.get("keypoints_visible", []),
                }

            # Threats
            threat = results.get("threat")
            if threat and isinstance(threat, dict) and not threat.get("error"):
                actual["threats"] = {
                    "has_threat": threat.get("has_threat", False),
                    "types": threat.get("threat_types", []),
                    "max_severity": threat.get("max_severity", "none"),
                }

            # Clothing
            clothing = results.get("clothing")
            if clothing and isinstance(clothing, dict) and not clothing.get("error"):
                actual["clothing"] = {
                    "type": clothing.get("clothing_type") or clothing.get("type"),
                    "color": clothing.get("color"),
                    "is_suspicious": clothing.get("is_suspicious", False),
                }

            # Demographics
            demo = results.get("demographics")
            if demo and isinstance(demo, dict) and not demo.get("error"):
                actual["demographics"] = {
                    "age_range": demo.get("age_range"),
                    "gender": demo.get("gender"),
                }

            # Pet
            pet = results.get("pet")
            if pet and isinstance(pet, dict) and not pet.get("error"):
                actual["pet"] = {
                    "type": pet.get("species") or pet.get("type"),
                    "is_known_pet": pet.get("is_known", False),
                }

            # Vehicle
            vehicle = results.get("vehicle")
            if vehicle and isinstance(vehicle, dict) and not vehicle.get("error"):
                actual["vehicle"] = {
                    "type": vehicle.get("vehicle_type") or vehicle.get("type"),
                    "color": vehicle.get("color"),
                }

        # Map Nemotron risk assessment
        if nemotron_result and not nemotron_result.get("error"):
            actual["risk_score"] = nemotron_result.get("risk_score")
            actual["risk_level"] = nemotron_result.get("risk_level")
            actual["risk_factors"] = nemotron_result.get("risk_factors", [])

        return actual

    async def process_sample(
        self, sample_dir: Path, category: str, scenario: str
    ) -> PipelineResult:
        """Process a single synthetic sample through the pipeline."""
        sample_id = sample_dir.name
        result = PipelineResult(
            sample_id=sample_id,
            scenario=scenario,
            category=category,
            media_file="",
        )

        # Find media file
        media_dir = sample_dir / "media"
        if not media_dir.exists():
            result.errors.append("No media directory found")
            return result

        media_files = list(media_dir.glob("*.png")) + list(media_dir.glob("*.jpg"))
        if not media_files:
            result.errors.append("No image files found in media directory")
            return result

        # Use first image
        image_path = media_files[0]
        result.media_file = str(image_path.relative_to(PROJECT_ROOT))

        # Load expected labels
        expected_path = sample_dir / "expected_labels.json"
        if not expected_path.exists():
            result.errors.append("No expected_labels.json found")
            return result

        with open(expected_path) as f:
            expected = json.load(f)

        total_start = time.perf_counter()

        # Step 1: Object detection
        result.yolo_result, result.yolo_time_ms = await self.detect_objects(image_path)
        if result.yolo_result and result.yolo_result.get("error"):
            result.errors.append(f"YOLO error: {result.yolo_result['error']}")

        # Step 2: Florence caption
        result.florence_result, result.florence_time_ms = await self.get_florence_caption(image_path)
        if result.florence_result and result.florence_result.get("error"):
            result.errors.append(f"Florence error: {result.florence_result['error']}")

        # Step 3: Enrichment (if we have detections)
        detections = []
        if result.yolo_result and "detections" in result.yolo_result:
            detections = result.yolo_result["detections"]

        if detections:
            result.enrichment_result, result.enrichment_time_ms = await self.run_enrichment(
                image_path, detections
            )
            if result.enrichment_result and result.enrichment_result.get("error"):
                result.errors.append(f"Enrichment error: {result.enrichment_result['error']}")

        # Step 4: Risk analysis
        florence_caption = None
        if result.florence_result and "result" in result.florence_result:
            florence_caption = result.florence_result["result"]

        result.nemotron_result, result.nemotron_time_ms = await self.analyze_risk(
            detections, result.enrichment_result, florence_caption
        )
        if result.nemotron_result and result.nemotron_result.get("error"):
            result.errors.append(f"Nemotron error: {result.nemotron_result['error']}")

        result.total_time_ms = (time.perf_counter() - total_start) * 1000

        # Build actual results and compare
        actual = self.build_actual_results(
            result.yolo_result,
            result.florence_result,
            result.enrichment_result,
            result.nemotron_result,
        )

        result.comparison = self.comparison_engine.compare(expected, actual)

        return result


def discover_samples(
    category: str | None = None,
    scenario: str | None = None,
    quick: bool = False,
) -> list[tuple[Path, str, str]]:
    """Discover synthetic samples to test.

    Returns:
        List of (sample_dir, category, scenario) tuples
    """
    samples = []

    categories = [category] if category else ["normal", "suspicious", "threats"]

    for cat in categories:
        cat_dir = SYNTHETIC_DATA_DIR / cat
        if not cat_dir.exists():
            continue

        # Group by scenario
        seen_scenarios = set()

        for sample_dir in sorted(cat_dir.iterdir()):
            if not sample_dir.is_dir():
                continue

            # Check for media
            media_dir = sample_dir / "media"
            if not media_dir.exists():
                continue

            # Extract scenario name
            # Format: scenario_YYYYMMDD_HHMMSS
            parts = sample_dir.name.rsplit("_", 2)
            if len(parts) >= 3:
                scen_name = parts[0]
            else:
                scen_name = sample_dir.name

            # Filter by scenario
            if scenario and scen_name != scenario:
                continue

            # Quick mode: only first sample per scenario
            if quick:
                if scen_name in seen_scenarios:
                    continue
                seen_scenarios.add(scen_name)

            samples.append((sample_dir, cat, scen_name))

    return samples


def print_service_status(services: list[ServiceHealth]) -> bool:
    """Print service health status. Returns True if all healthy."""
    table = Table(title="AI Service Health Check")
    table.add_column("Service", style="cyan")
    table.add_column("URL", style="dim")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    all_healthy = True
    for svc in services:
        status = "[green]✓ Healthy[/green]" if svc.healthy else "[red]✗ Unhealthy[/red]"
        details = svc.error or ""
        if svc.healthy and svc.details:
            if "model_loaded" in svc.details:
                details = f"Model: {svc.details.get('model_name', 'loaded')}"

        table.add_row(svc.name, svc.url, status, details)
        if not svc.healthy:
            all_healthy = False

    console.print(table)
    return all_healthy


def print_result_summary(result: PipelineResult, verbose: bool = False):
    """Print summary of a single result."""
    status_icon = "✓" if result.comparison and result.comparison.passed else "✗"
    status_color = "green" if result.comparison and result.comparison.passed else "red"

    # Build summary line
    summary = f"[{status_color}]{status_icon}[/{status_color}] {result.category}/{result.scenario}"

    if result.comparison:
        summary += f" ({result.comparison.summary.get('passed', 0)}/{result.comparison.summary.get('total_fields', 0)} fields)"

    summary += f" [{result.total_time_ms:.0f}ms]"

    if result.errors:
        summary += f" [yellow]({len(result.errors)} errors)[/yellow]"

    console.print(summary)

    # Print failures if verbose or if failed
    if verbose or (result.comparison and not result.comparison.passed):
        for fr in result.comparison.field_results if result.comparison else []:
            if not fr.passed:
                console.print(f"  [red]FAIL[/red] {fr.field_name}: expected {fr.expected}, got {fr.actual}")

        for err in result.errors[:3]:  # Limit to first 3 errors
            console.print(f"  [yellow]ERROR[/yellow] {err[:100]}")


def generate_report(results: list[PipelineResult]) -> TestReport:
    """Generate aggregate test report."""
    now = datetime.now(UTC).isoformat()
    report = TestReport(
        run_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
        started_at=now,
        completed_at=now,
        total_samples=len(results),
    )

    timing_totals = {"total": 0.0, "yolo": 0.0, "florence": 0.0, "enrichment": 0.0, "nemotron": 0.0}

    for result in results:
        report.results.append(result)

        # Update timing
        timing_totals["total"] += result.total_time_ms
        timing_totals["yolo"] += result.yolo_time_ms
        timing_totals["florence"] += result.florence_time_ms
        timing_totals["enrichment"] += result.enrichment_time_ms
        timing_totals["nemotron"] += result.nemotron_time_ms

        # Update pass/fail counts
        if result.errors:
            report.errors += 1
        elif result.comparison and result.comparison.passed:
            report.passed += 1
        else:
            report.failed += 1

        # Update category stats
        if result.category not in report.by_category:
            report.by_category[result.category] = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
        report.by_category[result.category]["total"] += 1
        if result.errors:
            report.by_category[result.category]["errors"] += 1
        elif result.comparison and result.comparison.passed:
            report.by_category[result.category]["passed"] += 1
        else:
            report.by_category[result.category]["failed"] += 1

        # Update scenario stats
        if result.scenario not in report.by_scenario:
            report.by_scenario[result.scenario] = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
        report.by_scenario[result.scenario]["total"] += 1
        if result.errors:
            report.by_scenario[result.scenario]["errors"] += 1
        elif result.comparison and result.comparison.passed:
            report.by_scenario[result.scenario]["passed"] += 1
        else:
            report.by_scenario[result.scenario]["failed"] += 1

        # Track field-level failures
        if result.comparison:
            for fr in result.comparison.field_results:
                if not fr.passed:
                    report.field_failures[fr.field_name] = report.field_failures.get(fr.field_name, 0) + 1

    # Calculate averages
    n = len(results) or 1
    report.avg_total_time_ms = timing_totals["total"] / n
    report.avg_yolo_time_ms = timing_totals["yolo"] / n
    report.avg_florence_time_ms = timing_totals["florence"] / n
    report.avg_enrichment_time_ms = timing_totals["enrichment"] / n
    report.avg_nemotron_time_ms = timing_totals["nemotron"] / n

    return report


def print_report(report: TestReport):
    """Print formatted test report."""
    console.print()

    # Overall summary
    pass_rate = (report.passed / report.total_samples * 100) if report.total_samples else 0
    summary_color = "green" if pass_rate >= 80 else "yellow" if pass_rate >= 50 else "red"

    console.print(Panel(
        f"[bold]Total: {report.total_samples}[/bold] | "
        f"[green]Passed: {report.passed}[/green] | "
        f"[red]Failed: {report.failed}[/red] | "
        f"[yellow]Errors: {report.errors}[/yellow] | "
        f"[{summary_color}]Pass Rate: {pass_rate:.1f}%[/{summary_color}]",
        title="Test Summary",
    ))

    # Category breakdown
    if report.by_category:
        table = Table(title="Results by Category")
        table.add_column("Category")
        table.add_column("Total", justify="right")
        table.add_column("Passed", justify="right", style="green")
        table.add_column("Failed", justify="right", style="red")
        table.add_column("Errors", justify="right", style="yellow")
        table.add_column("Pass Rate", justify="right")

        for cat, stats in sorted(report.by_category.items()):
            rate = (stats["passed"] / stats["total"] * 100) if stats["total"] else 0
            rate_style = "green" if rate >= 80 else "yellow" if rate >= 50 else "red"
            table.add_row(
                cat,
                str(stats["total"]),
                str(stats["passed"]),
                str(stats["failed"]),
                str(stats["errors"]),
                f"[{rate_style}]{rate:.0f}%[/{rate_style}]",
            )

        console.print(table)

    # Top field failures
    if report.field_failures:
        console.print()
        table = Table(title="Most Common Field Failures (Top 10)")
        table.add_column("Field")
        table.add_column("Failures", justify="right", style="red")

        sorted_failures = sorted(report.field_failures.items(), key=lambda x: x[1], reverse=True)
        for field_name, count in sorted_failures[:10]:
            table.add_row(field_name, str(count))

        console.print(table)

    # Timing
    console.print()
    console.print(Panel(
        f"[bold]Avg Total:[/bold] {report.avg_total_time_ms:.0f}ms | "
        f"YOLO: {report.avg_yolo_time_ms:.0f}ms | "
        f"Florence: {report.avg_florence_time_ms:.0f}ms | "
        f"Enrichment: {report.avg_enrichment_time_ms:.0f}ms | "
        f"Nemotron: {report.avg_nemotron_time_ms:.0f}ms",
        title="Timing",
    ))


def save_report(report: TestReport, output_path: Path):
    """Save detailed report to JSON."""
    def serialize(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: serialize(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, list):
            return [serialize(v) for v in obj]
        elif isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        elif isinstance(obj, Path):
            return str(obj)
        return obj

    with open(output_path, "w") as f:
        json.dump(serialize(report), f, indent=2, default=str)

    console.print(f"\nDetailed report saved to: {output_path}")


async def main():
    parser = argparse.ArgumentParser(
        description="Load test AI pipeline with synthetic data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--all", action="store_true", help="Test all synthetic data")
    parser.add_argument("--category", "-c", choices=["normal", "suspicious", "threats"],
                        help="Test specific category")
    parser.add_argument("--scenario", "-s", help="Test specific scenario (e.g., break_in_attempt)")
    parser.add_argument("--quick", "-q", action="store_true",
                        help="Quick mode: test first sample of each scenario")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", "-o", type=Path, help="Save detailed report to JSON file")
    parser.add_argument("--skip-health", action="store_true", help="Skip service health check")

    args = parser.parse_args()

    # Default to quick mode if no specific filter
    if not args.all and not args.category and not args.scenario:
        args.quick = True

    console.print(Panel("[bold]AI Pipeline Load Testing[/bold]", subtitle="Using Synthetic Data"))

    async with AIPipelineTester(verbose=args.verbose) as tester:
        # Check service health
        if not args.skip_health:
            console.print("\n[bold]Checking AI services...[/bold]")
            services = await tester.check_all_services()
            all_healthy = print_service_status(services)

            if not all_healthy:
                console.print("\n[yellow]Warning: Some services are unhealthy. Proceeding anyway...[/yellow]")

        # Discover samples
        console.print("\n[bold]Discovering samples...[/bold]")
        samples = discover_samples(
            category=args.category,
            scenario=args.scenario,
            quick=args.quick,
        )

        if not samples:
            console.print("[red]No samples found matching criteria[/red]")
            return 1

        console.print(f"Found {len(samples)} samples to test")

        # Process samples
        results = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=len(samples))

            for sample_dir, category, scenario in samples:
                progress.update(task, description=f"Testing {category}/{scenario}...")

                result = await tester.process_sample(sample_dir, category, scenario)
                results.append(result)

                # Print result immediately if verbose
                if args.verbose:
                    print_result_summary(result, verbose=True)

                progress.advance(task)

        # Generate and print report
        report = generate_report(results)
        print_report(report)

        # Print detailed failures (non-verbose mode)
        if not args.verbose:
            console.print("\n[bold]Failed Tests:[/bold]")
            for result in results:
                if result.comparison and not result.comparison.passed:
                    print_result_summary(result, verbose=True)

        # Save report if requested
        if args.output:
            save_report(report, args.output)

        # Return exit code
        return 0 if report.failed == 0 and report.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
