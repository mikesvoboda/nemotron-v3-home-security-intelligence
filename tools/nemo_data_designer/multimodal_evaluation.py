#!/usr/bin/env python3
"""Multimodal evaluation script for comparing local pipeline against NVIDIA vision.

This script runs the full multimodal evaluation pipeline:
1. Load curated test images from backend/tests/fixtures/synthetic/images/
2. Generate NVIDIA ground truth (if not cached)
3. Run local RT-DETRv2 + Nemotron pipeline on same images
4. Compare outputs and generate report
5. Export results

Usage:
    # Preview mode (shows what would be done)
    uv run python tools/nemo_data_designer/multimodal_evaluation.py --preview

    # Run evaluation (requires NVIDIA_API_KEY for real mode)
    uv run python tools/nemo_data_designer/multimodal_evaluation.py --run

    # Run in mock mode (no API calls)
    uv run python tools/nemo_data_designer/multimodal_evaluation.py --run --mock

    # Export results to specific directory
    uv run python tools/nemo_data_designer/multimodal_evaluation.py --run --output ./reports/

Environment Variables:
    NVIDIA_API_KEY: Required for real NVIDIA vision API calls (not needed in mock mode)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.nemo_data_designer.multimodal.ground_truth_generator import (
    GroundTruthConfig,
    MultimodalGroundTruthGenerator,
)
from tools.nemo_data_designer.multimodal.image_analyzer import (
    NVIDIAVisionAnalyzer,
    VisionAnalyzerConfig,
)
from tools.nemo_data_designer.multimodal.pipeline_comparator import (
    ComparisonConfig,
    PipelineComparator,
)

# Default paths
DEFAULT_IMAGES_DIR = project_root / "backend" / "tests" / "fixtures" / "synthetic" / "images"
DEFAULT_OUTPUT_DIR = project_root / "backend" / "tests" / "fixtures" / "synthetic"
DEFAULT_GROUND_TRUTH_FILE = DEFAULT_OUTPUT_DIR / "multimodal_ground_truth.parquet"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run multimodal evaluation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview mode - show what would be done without executing",
    )

    parser.add_argument(
        "--run",
        action="store_true",
        help="Run the full evaluation pipeline",
    )

    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock mode (no real API calls)",
    )

    parser.add_argument(
        "--images",
        type=Path,
        default=DEFAULT_IMAGES_DIR,
        help=f"Path to test images directory (default: {DEFAULT_IMAGES_DIR})",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for results (default: {DEFAULT_OUTPUT_DIR})",
    )

    parser.add_argument(
        "--regenerate-ground-truth",
        action="store_true",
        help="Force regeneration of NVIDIA ground truth (ignore cache)",
    )

    parser.add_argument(
        "--skip-local-pipeline",
        action="store_true",
        help="Skip running local pipeline (use existing results)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    return parser.parse_args()


def preview_mode(args: argparse.Namespace) -> None:
    """Show what would be done in preview mode."""
    print("=" * 60)
    print("Multimodal Evaluation Pipeline - PREVIEW MODE")
    print("=" * 60)
    print()

    # Check images directory
    images_dir = args.images
    print(f"Images Directory: {images_dir}")
    if images_dir.exists():
        categories = ["normal", "suspicious", "threat", "edge_case"]
        total_images = 0
        for category in categories:
            cat_dir = images_dir / category
            if cat_dir.exists():
                images = list(cat_dir.glob("*.jpg")) + list(cat_dir.glob("*.png"))
                count = len(images)
                total_images += count
                print(f"  {category}/: {count} images")
            else:
                print(f"  {category}/: directory not found")
        print(f"  Total: {total_images} images")
    else:
        print("  WARNING: Directory does not exist")

    print()

    # Check NVIDIA API key
    api_key = os.environ.get("NVIDIA_API_KEY")
    if args.mock:
        print("API Mode: MOCK (no real API calls)")
    elif api_key:
        print(f"API Mode: REAL (NVIDIA_API_KEY set, {len(api_key)} chars)")
    else:
        print("API Mode: MOCK (NVIDIA_API_KEY not set)")

    print()

    # Check ground truth file
    gt_file = args.output / "multimodal_ground_truth.parquet"
    if gt_file.exists():
        print(f"Ground Truth: EXISTS at {gt_file}")
        if args.regenerate_ground_truth:
            print("  Will regenerate (--regenerate-ground-truth flag)")
        else:
            print("  Will use cached version")
    else:
        print(f"Ground Truth: WILL GENERATE at {gt_file}")

    print()

    # Output configuration
    print(f"Output Directory: {args.output}")
    print("Output Files:")
    print(f"  - {args.output / 'multimodal_ground_truth.parquet'}")
    print(f"  - {args.output / 'comparison_report.json'}")
    print(f"  - {args.output / 'comparison_summary.txt'}")

    print()
    print("=" * 60)
    print("To run the evaluation, use: --run flag")
    print("=" * 60)


async def generate_mock_local_results(
    images_dir: Path,
) -> pd.DataFrame:
    """Generate mock local pipeline results for testing.

    In production, this would run the actual RT-DETRv2 + Nemotron pipeline.
    For now, generates mock results based on image categories.
    """
    import pandas as pd

    records = []

    for category in ["normal", "suspicious", "threat", "edge_case"]:
        cat_dir = images_dir / category
        if not cat_dir.exists():
            continue

        images = list(cat_dir.glob("*.jpg")) + list(cat_dir.glob("*.png"))

        for image_path in images:
            # Generate category-appropriate mock data
            if category == "normal":
                risk_score = 20
                detections = [{"type": "person", "confidence": 0.90, "bbox": [30, 20, 15, 40]}]
            elif category == "suspicious":
                risk_score = 45
                detections = [{"type": "person", "confidence": 0.88, "bbox": [40, 25, 12, 38]}]
            elif category == "threat":
                risk_score = 80
                detections = [{"type": "person", "confidence": 0.95, "bbox": [35, 22, 18, 45]}]
            else:  # edge_case
                risk_score = 40
                detections = [{"type": "person", "confidence": 0.72, "bbox": [38, 28, 14, 36]}]

            records.append(
                {
                    "image_path": str(image_path),
                    "detections": json.dumps(detections),
                    "risk_score": risk_score,
                }
            )

    return pd.DataFrame(records)


async def _get_local_pipeline_results(
    args: argparse.Namespace,
    images_dir: Path,
) -> pd.DataFrame:
    """Get local pipeline results - either from cache or by generating mock results."""
    import pandas as pd

    if args.skip_local_pipeline:
        local_results_file = args.output / "local_pipeline_results.parquet"
        if local_results_file.exists():
            print(f"  Loading cached local results from {local_results_file}")
            return pd.read_parquet(local_results_file)
        raise FileNotFoundError("--skip-local-pipeline but no cached results found")

    # For now, generate mock local results
    # In production, this would call the actual RT-DETRv2 + Nemotron pipeline
    print("  Generating mock local pipeline results...")
    local_results = await generate_mock_local_results(images_dir)
    local_results.to_parquet(args.output / "local_pipeline_results.parquet", index=False)
    print(f"  Generated results for {len(local_results)} images")
    return local_results


def _check_alignment_thresholds(report: ComparisonReport) -> bool:  # noqa: F821
    """Check if alignment thresholds are met and print warnings."""
    if report.total_images == 0:
        return True

    iou_met = report.detection_metrics.get("iou_threshold_met_rate", 0) >= 0.70
    risk_aligned = report.risk_metrics.get("alignment_rate", 0) >= 0.90

    if not iou_met:
        print()
        print("WARNING: Detection IoU threshold (70%) not met")

    if not risk_aligned:
        print()
        print("WARNING: Risk alignment rate (90%) not met")

    return iou_met and risk_aligned


async def run_evaluation(args: argparse.Namespace) -> int:
    """Run the full multimodal evaluation pipeline."""
    import pandas as pd

    print("=" * 60)
    print("Multimodal Evaluation Pipeline")
    print("=" * 60)
    print(f"Started at: {datetime.now(UTC).isoformat()}")
    print()

    # Ensure output directory exists
    args.output.mkdir(parents=True, exist_ok=True)

    # Configure analyzer
    mock_mode = args.mock or not os.environ.get("NVIDIA_API_KEY")
    print(f"Running in {'MOCK' if mock_mode else 'REAL'} mode")

    config = VisionAnalyzerConfig(
        mock_mode=mock_mode,
        cache_enabled=not args.regenerate_ground_truth,
    )

    # Step 1: Discover images
    print()
    print("Step 1: Discovering test images...")
    images_dir = args.images

    if not images_dir.exists():
        print(f"ERROR: Images directory does not exist: {images_dir}")
        return 1

    async with NVIDIAVisionAnalyzer(config=config) as analyzer:
        generator = MultimodalGroundTruthGenerator(
            images_dir,
            analyzer,
            config=GroundTruthConfig(
                use_cache=not args.regenerate_ground_truth,
            ),
        )

        images_by_category = generator.discover_images()
        total_images = sum(len(imgs) for imgs in images_by_category.values())

        for category, images in images_by_category.items():
            print(f"  {category}: {len(images)} images")
        print(f"  Total: {total_images} images")

        if total_images == 0:
            print()
            print("WARNING: No images found. Add test images to:")
            print(f"  {images_dir}")
            print("See the README.md in that directory for guidelines.")
            print()
            print("Generating empty report...")

        # Step 2: Generate NVIDIA ground truth
        print()
        print("Step 2: Generating NVIDIA ground truth...")

        gt_file = args.output / "multimodal_ground_truth.parquet"

        if gt_file.exists() and not args.regenerate_ground_truth:
            print(f"  Loading cached ground truth from {gt_file}")
            nvidia_ground_truth = pd.read_parquet(gt_file)
        else:
            print("  Analyzing images with NVIDIA vision...")
            nvidia_ground_truth = await generator.generate_ground_truth()
            generator.export_ground_truth(gt_file)
            print(f"  Saved ground truth to {gt_file}")

        # Print summary
        if len(nvidia_ground_truth) > 0:
            summary = generator.get_summary()
            print(f"  Generated ground truth for {summary['total_images']} images")
            print(f"  Categories: {summary['category_counts']}")

        # Step 3: Run local pipeline
        print()
        print("Step 3: Running local pipeline...")

        try:
            local_results = await _get_local_pipeline_results(args, images_dir)
        except FileNotFoundError as e:
            print(f"  ERROR: {e}")
            return 1

        # Step 4: Compare results
        print()
        print("Step 4: Comparing pipelines...")

        comparator = PipelineComparator(
            config=ComparisonConfig(
                iou_threshold=0.5,
                risk_deviation_threshold=15,
            )
        )

        report = comparator.generate_comparison_report(local_results, nvidia_ground_truth)

        # Step 5: Generate and save report
        print()
        print("Step 5: Generating report...")

        # Save JSON report
        report_file = args.output / "comparison_report.json"
        with report_file.open("w") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"  Saved report to {report_file}")

        # Save text summary
        summary_text = comparator.generate_summary(report)
        summary_file = args.output / "comparison_summary.txt"
        summary_file.write_text(summary_text)
        print(f"  Saved summary to {summary_file}")

        # Print summary to console
        print()
        print(summary_text)

        # Step 6: Results
        print()
        print("=" * 60)
        print("Evaluation Complete")
        print("=" * 60)
        print(f"Finished at: {datetime.now(UTC).isoformat()}")
        print()
        print("Output files:")
        print(f"  - {gt_file}")
        print(f"  - {args.output / 'local_pipeline_results.parquet'}")
        print(f"  - {report_file}")
        print(f"  - {summary_file}")

        # Return non-zero if alignment thresholds not met
        if not _check_alignment_thresholds(report):
            return 1

    return 0


def main() -> int:
    """Main entry point."""
    args = parse_args()

    if args.preview:
        preview_mode(args)
        return 0

    if args.run:
        return asyncio.run(run_evaluation(args))

    # Default: show help
    print("Use --preview to see what would be done")
    print("Use --run to execute the evaluation pipeline")
    print("Use --help for full options")
    return 0


if __name__ == "__main__":
    sys.exit(main())
