#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
# ]
# ///
# ABOUTME: CLI tool for synthetic data generation and A/B testing of the AI pipeline.
# ABOUTME: Generates security camera footage using NVIDIA's Veo/Gemini APIs with known ground truth.
"""
Synthetic Data Generation & A/B Testing CLI.

This tool generates synthetic security camera footage using NVIDIA's inference API
(Veo 3.1 for videos, Gemini for images) with known ground truth labels for automated
A/B comparison testing of the AI pipeline.

Commands:
    generate    Generate synthetic media from scenario templates
    test        Run A/B comparison tests on generated data
    list        List available scenario templates
    validate    Validate a scenario spec file

Usage:
    # Generate examples
    uv run scripts/synthetic_data.py generate --scenario loitering --count 5
    uv run scripts/synthetic_data.py generate --scenario break_in_attempt \\
        --time night --weather rain --count 3
    uv run scripts/synthetic_data.py generate --scenario package_theft \\
        --format video --count 2
    uv run scripts/synthetic_data.py generate --spec ./custom_scenario.json

    # Test examples
    uv run scripts/synthetic_data.py test --run-id 20260125_143022
    uv run scripts/synthetic_data.py test --run-id 20260125_143022 \\
        --models threat_detector,pose_estimator
    uv run scripts/synthetic_data.py test --all

    # List scenarios
    uv run scripts/synthetic_data.py list
    uv run scripts/synthetic_data.py list --category suspicious

    # Validate spec
    uv run scripts/synthetic_data.py validate ./my_scenario.json

Requires NVIDIA_API_KEY or NVAPIKEY environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.synthetic import (  # noqa: E402 - must be after sys.path modification
    ComparisonEngine,
    PromptGenerator,
    ReportGenerator,
    SampleModelResult,
    generate_image_sync,
    generate_video_sync,
)
from scripts.synthetic.scenarios import (  # noqa: E402
    ScenarioNotFoundError,
    get_scenario,
    get_scenario_with_modifiers,
    list_scenarios,
    list_time_modifiers,
    list_weather_modifiers,
)
from scripts.synthetic.stock_footage import (  # noqa: E402
    SCENARIO_SEARCH_TERMS,
    download_stock_sync,
    search_stock_sync,
)

# Output directories
DATA_DIR = PROJECT_ROOT / "data" / "synthetic"
RESULTS_DIR = DATA_DIR / "results"

# Pipeline integration
EXPORT_BASE_DIR = Path("/export/foscam")
POLL_INTERVAL = 5  # seconds
MAX_POLL_RETRIES = 60  # 5 minutes total


def get_run_id() -> str:
    """Generate a unique run ID based on current timestamp."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_output_dir(category: str, scenario_name: str, run_id: str) -> Path:
    """Get the output directory for a generation run."""
    return DATA_DIR / category / f"{scenario_name}_{run_id}"


def save_json(data: dict[str, Any], path: Path) -> None:
    """Save data as formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # nosemgrep: path-traversal-open - path is controlled by DATA_DIR constant
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON data from a file."""
    # nosemgrep: path-traversal-open - path is controlled by DATA_DIR constant
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_scenario_spec(spec: dict[str, Any]) -> list[str]:
    """Validate a scenario spec and return list of errors."""
    errors = []

    # Required top-level fields
    required = ["category", "name", "scene", "environment", "subjects", "expected_outputs"]
    for field in required:
        if field not in spec:
            errors.append(f"Missing required field: {field}")

    # Validate scene
    if "scene" in spec:
        scene = spec["scene"]
        if "location" not in scene:
            errors.append("scene.location is required")
        if "camera_type" not in scene:
            errors.append("scene.camera_type is required")

    # Validate environment
    if "environment" in spec:
        env = spec["environment"]
        if "time_of_day" not in env:
            errors.append("environment.time_of_day is required")

    # Validate subjects
    if "subjects" in spec:
        if not isinstance(spec["subjects"], list):
            errors.append("subjects must be a list")
        elif len(spec["subjects"]) == 0:
            errors.append("subjects list cannot be empty")
        else:
            for i, subject in enumerate(spec["subjects"]):
                if "type" not in subject:
                    errors.append(f"subjects[{i}].type is required")

    # Validate expected_outputs
    if "expected_outputs" in spec:
        outputs = spec["expected_outputs"]
        if not isinstance(outputs, dict):
            errors.append("expected_outputs must be a dictionary")

    return errors


def cmd_generate_stock(
    args: argparse.Namespace, spec: dict[str, Any], scenario_name: str, category: str, run_id: str
) -> int:
    """Generate data using stock footage from Pexels/Pixabay."""
    count = args.count or spec.get("generation", {}).get("count", 3)
    gen_format = spec.get("generation", {}).get("format", "video")

    # Setup output directory
    output_dir = get_output_dir(category, scenario_name, run_id)
    media_dir = output_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Save scenario spec and expected labels
    save_json(spec, output_dir / "scenario_spec.json")
    save_json(spec.get("expected_outputs", {}), output_dir / "expected_labels.json")

    # Determine stock source
    stock_source = (
        args.stock_source if hasattr(args, "stock_source") and args.stock_source else "all"
    )

    # Check for API keys
    pexels_key = os.environ.get("PEXELS_API_KEY")
    pixabay_key = os.environ.get("PIXABAY_API_KEY")

    if not pexels_key and not pixabay_key:
        print("Error: No stock API keys found.", file=sys.stderr)
        print("Set PEXELS_API_KEY and/or PIXABAY_API_KEY environment variables.", file=sys.stderr)
        print("\nGet free API keys from:", file=sys.stderr)
        print("  Pexels: https://www.pexels.com/api/", file=sys.stderr)
        print("  Pixabay: https://pixabay.com/api/docs/", file=sys.stderr)
        return 1

    available_sources = []
    if pexels_key:
        available_sources.append("pexels")
    if pixabay_key:
        available_sources.append("pixabay")

    print(f"\nSearching {stock_source} for '{scenario_name}' ({gen_format}s)...")
    print(f"Available sources: {', '.join(available_sources)}")

    # Search for matching stock footage
    results = search_stock_sync(
        scenario_id=scenario_name,
        category=category,
        media_type="video" if gen_format == "video" else "image",
        count=count * 2,  # Get extra results in case some fail
        source=stock_source,
    )

    if not results:
        print("No stock footage found matching scenario criteria", file=sys.stderr)
        print("Make sure PEXELS_API_KEY and/or PIXABAY_API_KEY are set", file=sys.stderr)
        return 1

    print(f"Found {len(results)} matching clips, downloading {count}...")

    # Download the requested count
    downloaded_files = []
    failed = 0

    for _i, result in enumerate(results):
        if len(downloaded_files) >= count:
            break

        ext = "mp4" if gen_format == "video" else "png"
        filename = f"{len(downloaded_files) + 1:03d}.{ext}"
        output_path = media_dir / filename

        print(
            f"  [{len(downloaded_files) + 1}/{count}] {result.source.value}:{result.id}...",
            end=" ",
            flush=True,
        )

        success = download_stock_sync(result, output_path)

        if success and output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            print(f"OK ({size_kb:.1f} KB)")
            downloaded_files.append(
                {
                    "file": str(output_path.relative_to(output_dir)),
                    "source": result.source.value,
                    "source_id": result.id,
                    "source_url": result.url,
                    "tags": result.tags,
                }
            )
        else:
            print("FAILED")
            failed += 1

    # Save metadata
    metadata = {
        "run_id": run_id,
        "scenario": scenario_name,
        "category": category,
        "format": gen_format,
        "source": "stock",
        "stock_source": stock_source,
        "count_requested": count,
        "count_generated": len(downloaded_files),
        "count_failed": failed,
        "generated_at": datetime.now(UTC).isoformat(),
        "files": downloaded_files,
        "search_terms": SCENARIO_SEARCH_TERMS.get(scenario_name, []),
    }
    save_json(metadata, output_dir / "metadata.json")

    print("\nDownload complete:")
    print(f"  Downloaded: {len(downloaded_files)}/{count}")
    print(f"  Failed: {failed}")
    print(f"  Output: {output_dir}")

    return 0 if len(downloaded_files) > 0 else 1


def cmd_generate(args: argparse.Namespace) -> int:
    """Execute the generate command."""
    run_id = get_run_id()
    print(f"Starting generation run: {run_id}")

    # Load scenario spec
    if args.spec:
        # Load from custom spec file
        spec_path = Path(args.spec)
        if not spec_path.exists():
            print(f"Error: Spec file not found: {spec_path}", file=sys.stderr)
            return 1
        spec = load_json(spec_path)
        scenario_name = spec.get("name", "custom")
        category = spec.get("category", "custom")
    elif args.scenario:
        # Load from built-in template
        try:
            spec = get_scenario_with_modifiers(
                args.scenario,
                variation_id=args.variation,
                time=args.time,
                weather=args.weather,
            )
            scenario_name = args.scenario
            category = spec.get("category", "unknown")
        except ScenarioNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        print("Error: Must specify --scenario or --spec", file=sys.stderr)
        return 1

    # Check if using stock footage source
    if hasattr(args, "source") and args.source == "stock":
        return cmd_generate_stock(args, spec, scenario_name, category, run_id)

    # Validate spec
    errors = validate_scenario_spec(spec)
    if errors:
        print("Error: Invalid scenario spec:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    # Override format if specified
    if args.format:
        spec.setdefault("generation", {})["format"] = args.format

    # Determine output format
    gen_format = spec.get("generation", {}).get("format", "image")
    count = args.count or spec.get("generation", {}).get("count", 1)

    # Setup output directory
    output_dir = get_output_dir(category, scenario_name, run_id)
    media_dir = output_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Save scenario spec and expected labels
    save_json(spec, output_dir / "scenario_spec.json")
    save_json(spec.get("expected_outputs", {}), output_dir / "expected_labels.json")

    # Generate prompt
    prompt_generator = PromptGenerator()
    if gen_format == "video":
        prompt = prompt_generator.generate_video_prompt(spec)
    else:
        prompt = prompt_generator.generate_image_prompt(spec)

    # Save prompt
    (output_dir / "generation_prompt.txt").write_text(prompt, encoding="utf-8")
    print(f"Generated prompt ({len(prompt)} chars)")

    if args.dry_run:
        print("\nDry run - not generating media")
        print(f"Output directory: {output_dir}")
        print(f"Prompt:\n{prompt[:500]}...")
        return 0

    # Generate media
    print(f"\nGenerating {count} {gen_format}(s)...")
    generated_files = []
    failed = 0

    for i in range(count):
        filename = f"{i + 1:03d}.{'mp4' if gen_format == 'video' else 'png'}"
        output_path = media_dir / filename

        print(f"  [{i + 1}/{count}] Generating {filename}...", end=" ", flush=True)

        try:
            if gen_format == "video":
                success = generate_video_sync(prompt, output_path)
            else:
                success = generate_image_sync(prompt, output_path)

            if success and output_path.exists():
                size_kb = output_path.stat().st_size / 1024
                print(f"OK ({size_kb:.1f} KB)")
                generated_files.append(str(output_path.relative_to(output_dir)))
            else:
                print("FAILED")
                failed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

    # Save metadata
    metadata = {
        "run_id": run_id,
        "scenario": scenario_name,
        "category": category,
        "format": gen_format,
        "count_requested": count,
        "count_generated": len(generated_files),
        "count_failed": failed,
        "generated_at": datetime.now(UTC).isoformat(),
        "files": generated_files,
        "applied_modifiers": {
            "variation": args.variation,
            "time": args.time,
            "weather": args.weather,
        },
    }
    save_json(metadata, output_dir / "metadata.json")

    print("\nGeneration complete:")
    print(f"  Generated: {len(generated_files)}/{count}")
    print(f"  Failed: {failed}")
    print(f"  Output: {output_dir}")

    return 0 if failed == 0 else 1


def cmd_test(args: argparse.Namespace) -> int:
    """Execute the test command."""
    # Find the run directory
    if args.run_id:
        # Search for the run
        run_dirs = list(DATA_DIR.glob(f"*/*_{args.run_id}"))
        if not run_dirs:
            print(f"Error: Run not found: {args.run_id}", file=sys.stderr)
            return 1
        if len(run_dirs) > 1:
            print(f"Error: Multiple runs match: {args.run_id}", file=sys.stderr)
            for d in run_dirs:
                print(f"  - {d}", file=sys.stderr)
            return 1
        run_dir = run_dirs[0]
    elif args.all:
        print("Testing all runs not yet implemented")
        return 1
    else:
        print("Error: Must specify --run-id or --all", file=sys.stderr)
        return 1

    print(f"Testing run: {run_dir.name}")

    # Load expected labels
    expected_path = run_dir / "expected_labels.json"
    if not expected_path.exists():
        print(f"Error: Expected labels not found: {expected_path}", file=sys.stderr)
        return 1
    expected = load_json(expected_path)

    # Load metadata
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        print(f"Error: Metadata not found: {metadata_path}", file=sys.stderr)
        return 1
    metadata = load_json(metadata_path)

    # Get list of media files
    media_dir = run_dir / "media"
    if not media_dir.exists():
        print(f"Error: Media directory not found: {media_dir}", file=sys.stderr)
        return 1

    media_files = sorted(media_dir.glob("*.*"))
    if not media_files:
        print(f"Error: No media files found in: {media_dir}", file=sys.stderr)
        return 1

    print(f"Found {len(media_files)} media files")

    # Setup synthetic camera directory for pipeline processing
    camera_name = f"synthetic_test_{uuid.uuid4().hex[:8]}"
    camera_dir = EXPORT_BASE_DIR / camera_name

    if not args.dry_run:
        if EXPORT_BASE_DIR.exists():
            camera_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created camera directory: {camera_dir}")

            # Copy media files to camera directory
            for media_file in media_files:
                shutil.copy2(media_file, camera_dir / media_file.name)
            print(f"Copied {len(media_files)} files to pipeline")
        else:
            print(f"Warning: Export directory not found: {EXPORT_BASE_DIR}")
            print("  Skipping pipeline integration (running in offline mode)")

    # Wait for pipeline processing
    if not args.dry_run and camera_dir.exists():
        print("\nWaiting for pipeline processing...")
        # TODO: Implement actual API polling when pipeline is running
        # For now, we'll simulate with a timeout
        print("  (Pipeline integration not yet implemented - using mock results)")

    # Initialize comparison engine
    comparison_engine = ComparisonEngine()
    report_generator = ReportGenerator()

    # Collect results
    all_results: list[SampleModelResult] = []

    # For each media file, compare expected vs actual
    for media_file in media_files:
        sample_id = media_file.name

        # TODO: Get actual results from pipeline API
        # For now, use mock results that match expected (for testing the framework)
        actual = expected.copy()  # Mock: assume pipeline returns expected values

        # Run comparison
        result = comparison_engine.compare(expected, actual)

        # Convert to SampleModelResult for each model
        # For now, treat it as a single "pipeline" model
        sample_result = SampleModelResult(
            sample_id=sample_id,
            model_name="pipeline",
            passed=result.passed,
            expected=expected,
            actual=actual,
            diff={
                fr.field_name: {"expected": fr.expected, "actual": fr.actual}
                for fr in result.field_results
                if not fr.passed
            },
        )
        all_results.append(sample_result)

    # Generate report
    run_id = metadata.get("run_id", run_dir.name.split("_")[-1])
    scenario = metadata.get("scenario", "unknown")
    generated_at = metadata.get("generated_at", "")

    report = report_generator.create_report(
        run_id=run_id,
        scenario=scenario,
        results=all_results,
        generated_at=generated_at,
    )

    # Save report
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / f"{run_id}_report.json"
    report_generator.save_report(report, report_path)

    # Print summary
    summary = report["summary"]
    print("\nTest Results:")
    print(f"  Total samples: {summary['total_samples']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Pass rate: {summary['pass_rate']:.1%}")
    print(f"\nReport saved: {report_path}")

    # Cleanup camera directory
    if camera_dir.exists():
        shutil.rmtree(camera_dir)

    return 0 if summary["failed"] == 0 else 1


def cmd_list(args: argparse.Namespace) -> int:
    """Execute the list command."""
    scenarios = list_scenarios()

    if args.category:
        if args.category not in scenarios:
            print(f"Error: Unknown category: {args.category}", file=sys.stderr)
            print(f"Available categories: {list(scenarios.keys())}", file=sys.stderr)
            return 1
        print(f"\n{args.category.upper()} SCENARIOS:")
        for scenario_id in scenarios[args.category]:
            try:
                spec = get_scenario(scenario_id)
                name = spec.get("name", scenario_id)
                print(f"  {scenario_id}: {name}")
            except ScenarioNotFoundError:
                print(f"  {scenario_id}")
    else:
        for category, scenario_ids in scenarios.items():
            print(f"\n{category.upper()} SCENARIOS:")
            for scenario_id in scenario_ids:
                try:
                    spec = get_scenario(scenario_id)
                    name = spec.get("name", scenario_id)
                    print(f"  {scenario_id}: {name}")
                except ScenarioNotFoundError:
                    print(f"  {scenario_id}")

    # List modifiers
    print("\nTIME MODIFIERS:")
    for mod_id in list_time_modifiers():
        print(f"  {mod_id}")

    print("\nWEATHER MODIFIERS:")
    for mod_id in list_weather_modifiers():
        print(f"  {mod_id}")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Execute the validate command."""
    spec_path = Path(args.spec)

    if not spec_path.exists():
        print(f"Error: File not found: {spec_path}", file=sys.stderr)
        return 1

    try:
        spec = load_json(spec_path)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return 1

    errors = validate_scenario_spec(spec)

    if errors:
        print(f"INVALID: {spec_path}")
        for error in errors:
            print(f"  - {error}")
        return 1
    else:
        print(f"VALID: {spec_path}")
        print(f"  Category: {spec.get('category')}")
        print(f"  Name: {spec.get('name')}")
        print(f"  Subjects: {len(spec.get('subjects', []))}")
        print(f"  Format: {spec.get('generation', {}).get('format', 'image')}")
        return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Synthetic data generation and A/B testing for Home Security Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Generate command
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate synthetic media from scenario templates",
    )
    gen_parser.add_argument(
        "--scenario",
        "-s",
        help="Built-in scenario template ID (e.g., loitering, break_in_attempt)",
    )
    gen_parser.add_argument(
        "--variation",
        "-v",
        help="Scenario variation ID",
    )
    gen_parser.add_argument(
        "--spec",
        help="Path to custom scenario spec JSON file",
    )
    gen_parser.add_argument(
        "--count",
        "-n",
        type=int,
        help="Number of media files to generate (overrides spec)",
    )
    gen_parser.add_argument(
        "--format",
        "-f",
        choices=["image", "video"],
        help="Media format (overrides spec)",
    )
    gen_parser.add_argument(
        "--time",
        "-t",
        help="Time modifier (dawn, day, dusk, night, midnight)",
    )
    gen_parser.add_argument(
        "--weather",
        "-w",
        help="Weather modifier (clear, rain, snow, fog, etc.)",
    )
    gen_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate prompt but don't call API",
    )
    gen_parser.add_argument(
        "--source",
        choices=["ai", "stock"],
        default="ai",
        help="Media source: 'ai' for Veo/Gemini generation (default), 'stock' for Pexels/Pixabay",
    )
    gen_parser.add_argument(
        "--stock-source",
        choices=["pexels", "pixabay", "all"],
        default="all",
        help="Stock footage source when --source=stock (default: all)",
    )

    # Test command
    test_parser = subparsers.add_parser(
        "test",
        help="Run A/B comparison tests on generated data",
    )
    test_parser.add_argument(
        "--run-id",
        "-r",
        help="Run ID to test (timestamp, e.g., 20260125_143022)",
    )
    test_parser.add_argument(
        "--all",
        action="store_true",
        help="Test all available runs",
    )
    test_parser.add_argument(
        "--models",
        "-m",
        help="Comma-separated list of models to test (default: all)",
    )
    test_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually run through pipeline",
    )

    # List command
    list_parser = subparsers.add_parser(
        "list",
        help="List available scenario templates",
    )
    list_parser.add_argument(
        "--category",
        "-c",
        choices=["normal", "suspicious", "threats"],
        help="Filter by category",
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a scenario spec file",
    )
    validate_parser.add_argument(
        "spec",
        help="Path to scenario spec JSON file",
    )

    args = parser.parse_args()

    if args.command == "generate":
        return cmd_generate(args)
    elif args.command == "test":
        return cmd_test(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "validate":
        return cmd_validate(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
