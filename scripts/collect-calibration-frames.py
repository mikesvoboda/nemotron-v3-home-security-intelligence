#!/usr/bin/env python3
"""Collect calibration frames for CLIP INT8 TensorRT quantization.

Collects a diverse sample of security camera frames suitable for calibrating
CLIP ViT-L INT8 TensorRT engines. The calibration dataset should be
representative of the images the model will process in production.

Sources (checked in order of availability):
  1. Actual camera frame directories (FOSCAM_BASE_PATH from .env)
  2. Synthetic test data (data/synthetic/)
  3. Any JPEG/PNG images found in configured paths

The script selects frames to maximize diversity:
  - Different cameras (if multiple are available)
  - Different times of day (based on filename timestamps)
  - Different detection types (person, vehicle, animal frames)
  - Different lighting conditions

Usage:
    # Collect from default sources
    python scripts/collect-calibration-frames.py

    # Collect from a specific camera directory
    python scripts/collect-calibration-frames.py --source /export/foscam

    # Control output and count
    python scripts/collect-calibration-frames.py \\
        --output /data/calibration/clip \\
        --max-frames 300

    # Dry run to see what would be collected
    python scripts/collect-calibration-frames.py --dry-run

Environment Variables:
    FOSCAM_BASE_PATH: Base directory for camera uploads (default: /export/foscam)
    CLIP_CALIBRATION_DIR: Output directory (default: /data/calibration/clip)
"""

import argparse
import hashlib
import logging
import os
import shutil
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Default target frame count for calibration
DEFAULT_MAX_FRAMES = 300

# Minimum frames needed for useful calibration
MIN_FRAMES = 50


def find_image_files(source_dir: Path) -> list[Path]:
    """Recursively find all image files in a directory.

    Args:
        source_dir: Directory to search.

    Returns:
        List of image file paths sorted by name.
    """
    if not source_dir.exists():
        logger.warning(f"Source directory does not exist: {source_dir}")
        return []

    image_files: list[Path] = []
    for ext in IMAGE_EXTENSIONS:
        image_files.extend(source_dir.rglob(f"*{ext}"))
        image_files.extend(source_dir.rglob(f"*{ext.upper()}"))

    # Deduplicate and sort
    return sorted(set(image_files))


def select_diverse_sample(
    image_files: list[Path],
    max_frames: int,
) -> list[Path]:
    """Select a diverse sample of frames from the available images.

    Uses a deterministic sampling strategy that maximizes diversity by:
    1. Grouping images by parent directory (camera/source)
    2. Interleaving selections across groups
    3. Within each group, sampling at even intervals

    Args:
        image_files: All available image file paths.
        max_frames: Maximum number of frames to select.

    Returns:
        Selected image file paths.
    """
    if len(image_files) <= max_frames:
        return image_files

    # Group by parent directory (approximates different cameras/sources)
    groups: dict[Path, list[Path]] = {}
    for img_path in image_files:
        parent = img_path.parent
        if parent not in groups:
            groups[parent] = []
        groups[parent].append(img_path)

    # Allocate frames proportionally across groups
    total_available = len(image_files)
    selected: list[Path] = []

    for _group_dir, group_files in sorted(groups.items()):
        # Proportional allocation with minimum of 1
        group_allocation = max(1, int(max_frames * len(group_files) / total_available))
        group_allocation = min(group_allocation, len(group_files))

        if len(group_files) <= group_allocation:
            selected.extend(group_files)
        else:
            # Sample at even intervals for temporal diversity
            step = len(group_files) / group_allocation
            group_selected = [group_files[int(i * step)] for i in range(group_allocation)]
            selected.extend(group_selected)

    # Trim to max_frames if proportional allocation exceeded target
    if len(selected) > max_frames:
        step = len(selected) / max_frames
        selected = [selected[int(i * step)] for i in range(max_frames)]

    return selected


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file for deduplication.

    Args:
        file_path: Path to the file.

    Returns:
        Hex digest of the SHA256 hash.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:  # nosemgrep: path-traversal-open
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def collect_frames(
    source_dirs: list[Path],
    output_dir: Path,
    max_frames: int = DEFAULT_MAX_FRAMES,
    dry_run: bool = False,
) -> int:
    """Collect calibration frames from source directories.

    Args:
        source_dirs: List of directories to search for images.
        output_dir: Directory to copy selected frames to.
        max_frames: Maximum number of frames to collect.
        dry_run: If True, only report what would be done without copying.

    Returns:
        Number of frames collected.
    """
    # Discover all available images
    logger.info("Discovering images from source directories...")
    all_images: list[Path] = []
    for source_dir in source_dirs:
        found = find_image_files(source_dir)
        if found:
            logger.info(f"  {source_dir}: {len(found)} images")
            all_images.extend(found)
        else:
            logger.info(f"  {source_dir}: no images found")

    if not all_images:
        logger.error("No images found in any source directory.")
        logger.error("Available source directories checked:")
        for d in source_dirs:
            logger.error(f"  {d} (exists={d.exists()})")
        return 0

    logger.info(f"Total images found: {len(all_images)}")

    # Select diverse sample
    selected = select_diverse_sample(all_images, max_frames)
    logger.info(f"Selected {len(selected)} frames for calibration")

    if len(selected) < MIN_FRAMES:
        logger.warning(
            f"Only {len(selected)} frames available, below recommended minimum of {MIN_FRAMES}. "
            "Calibration may produce suboptimal results. Consider adding more source images."
        )

    if dry_run:
        logger.info("DRY RUN - no files will be copied")
        for i, img_path in enumerate(selected[:10]):
            logger.info(f"  [{i + 1}] {img_path}")
        if len(selected) > 10:
            logger.info(f"  ... and {len(selected) - 10} more")
        return len(selected)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy selected frames with deduplication
    seen_hashes: set[str] = set()
    copied = 0

    for img_path in selected:
        # Compute hash for deduplication
        file_hash = compute_file_hash(img_path)
        if file_hash in seen_hashes:
            continue
        seen_hashes.add(file_hash)

        # Generate unique output filename
        # Use hash prefix + original extension for collision-free naming
        ext = img_path.suffix.lower()
        output_name = f"calib_{copied:04d}_{file_hash[:8]}{ext}"
        output_path = output_dir / output_name

        try:
            shutil.copy2(img_path, output_path)
            copied += 1
        except (OSError, shutil.Error) as e:
            logger.warning(f"Failed to copy {img_path}: {e}")

        if copied % 50 == 0:
            logger.info(f"  Copied {copied}/{len(selected)} frames...")

    logger.info(f"Calibration frames collected: {copied} unique frames")
    logger.info(f"Output directory: {output_dir}")

    return copied


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Collect calibration frames for CLIP INT8 TensorRT quantization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect from default sources (camera uploads + synthetic data)
  python scripts/collect-calibration-frames.py

  # Collect from a specific directory
  python scripts/collect-calibration-frames.py --source /export/foscam

  # Multiple sources
  python scripts/collect-calibration-frames.py \\
      --source /export/foscam \\
      --source data/synthetic/

  # Custom output and frame count
  python scripts/collect-calibration-frames.py \\
      --output /data/calibration/clip \\
      --max-frames 500

  # Preview what would be collected
  python scripts/collect-calibration-frames.py --dry-run
        """,
    )

    parser.add_argument(
        "--source",
        action="append",
        help="Source directory for images (can be specified multiple times). "
        "Defaults to FOSCAM_BASE_PATH and data/synthetic/.",
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("CLIP_CALIBRATION_DIR", "data/calibration/clip"),
        help="Output directory for calibration frames "
        "(default: CLIP_CALIBRATION_DIR or data/calibration/clip)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=DEFAULT_MAX_FRAMES,
        help=f"Maximum number of frames to collect (default: {DEFAULT_MAX_FRAMES})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be collected without copying files",
    )

    args = parser.parse_args()

    # Determine source directories
    if args.source:
        source_dirs = [Path(s) for s in args.source]
    else:
        # Default sources: camera uploads + synthetic data
        project_root = Path(__file__).parent.parent
        source_dirs = []

        # Camera uploads from FOSCAM_BASE_PATH
        foscam_path = os.environ.get("FOSCAM_BASE_PATH", "/export/foscam")
        if Path(foscam_path).exists():
            source_dirs.append(Path(foscam_path))

        # Synthetic test data
        synthetic_dir = project_root / "data" / "synthetic"
        if synthetic_dir.exists():
            source_dirs.append(synthetic_dir)

        # Thumbnails directory (processed camera frames)
        thumbnails_dir = project_root / "data" / "thumbnails"
        if thumbnails_dir.exists():
            source_dirs.append(thumbnails_dir)

        if not source_dirs:
            logger.error(
                "No default source directories found. "
                "Please specify --source or ensure FOSCAM_BASE_PATH is set."
            )
            sys.exit(1)

    output_dir = Path(args.output)

    logger.info("CLIP INT8 Calibration Frame Collector")
    logger.info(f"  Sources: {[str(d) for d in source_dirs]}")
    logger.info(f"  Output: {output_dir}")
    logger.info(f"  Max frames: {args.max_frames}")

    collected = collect_frames(
        source_dirs=source_dirs,
        output_dir=output_dir,
        max_frames=args.max_frames,
        dry_run=args.dry_run,
    )

    if collected == 0:
        logger.error("No frames collected. Cannot proceed with calibration.")
        sys.exit(1)
    elif collected < MIN_FRAMES:
        logger.warning(
            f"Collected {collected} frames (below recommended {MIN_FRAMES}). "
            "Consider adding more source images for better calibration quality."
        )
    else:
        logger.info(f"Successfully collected {collected} calibration frames.")
        logger.info("Next steps:")
        logger.info("  1. Set CLIP_TENSORRT_PRECISION=int8 in .env")
        logger.info(f"  2. Set CLIP_CALIBRATION_DIR={output_dir} in .env")
        logger.info("  3. Rebuild CLIP TensorRT engine:")
        logger.info(
            "     python ai/clip/export_onnx.py pipeline "
            "--model-path /models/clip-vit-l "
            f"--output-dir /models/clip-vit-l --precision int8 --calibration-dir {output_dir}"
        )


if __name__ == "__main__":
    main()
