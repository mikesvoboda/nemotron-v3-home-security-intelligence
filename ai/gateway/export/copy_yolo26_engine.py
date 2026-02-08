#!/usr/bin/env python3
"""Copy the pre-built YOLO26 TensorRT engine into the Triton model repository.

The YOLO26 TensorRT engine is already built during the ai-yolo26 container's
startup sequence (see ai/yolo26/model.py _prebuild_yolo26_engine).  This script
simply copies (or symlinks) the existing engine to the Triton-expected path.

Source: /models/zoo/yolo26/exports/yolo26m_fp16.engine
Destination: /models/cache/yolo26/1/model.plan

The engine is an FP16 TensorRT serialized plan built by Ultralytics from
the yolo26m.pt model.  It expects (1, 3, 640, 640) input and produces
COCO-format detections (bounding boxes, class IDs, confidence scores).

IMPORTANT: TensorRT engines are GPU-architecture-specific.  If the engine
was built on a different GPU than the Triton host, it will fail to load.
In that case, re-export from the .pt source using the YOLO26 container's
prebuild mechanism (YOLO26_PREBUILD_ENGINE=true).

Usage:
    python copy_yolo26_engine.py \\
        --model-path /models/zoo/yolo26/exports/yolo26m_fp16.engine \\
        --output-path /models/cache/yolo26/1/model.plan

    # Or with a .pt source (will look for adjacent exports/ directory):
    python copy_yolo26_engine.py \\
        --model-path /models/zoo/yolo26 \\
        --output-path /models/cache/yolo26/1/model.plan
"""

from __future__ import annotations

import argparse
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

# Default paths matching the YOLO26 service configuration
DEFAULT_MODEL_PATH = "/models/zoo/yolo26/exports/yolo26m_fp16.engine"
DEFAULT_OUTPUT_PATH = "/models/cache/yolo26/1/model.plan"

# Known engine filenames in order of preference
ENGINE_CANDIDATES = [
    "yolo26m_fp16.engine",
    "yolo26m.engine",
    "best_fp16.engine",
    "best.engine",
]


def find_engine(model_path: str) -> Path:
    """Locate the YOLO26 TensorRT engine file.

    Handles several input formats:
    - Direct path to .engine file
    - Path to the yolo26 model directory (searches exports/ subdirectory)
    - Path to the .pt model file (derives exports/ directory)

    Args:
        model_path: Path to engine file or model directory.

    Returns:
        Resolved path to the .engine file.

    Raises:
        FileNotFoundError: If no engine file can be located.
    """
    path = Path(model_path)

    # Case 1: Direct path to an .engine file
    if path.suffix == ".engine" and path.exists():
        logger.info(f"Found engine at explicit path: {path}")
        return path

    # Case 2: Path to a directory — search for engine files
    if path.is_dir():
        # Check exports/ subdirectory first
        exports_dir = path / "exports"
        search_dirs = [exports_dir, path] if exports_dir.is_dir() else [path]

        for search_dir in search_dirs:
            for candidate in ENGINE_CANDIDATES:
                engine_path = search_dir / candidate
                if engine_path.exists():
                    logger.info(f"Found engine: {engine_path}")
                    return engine_path

            # Fallback: any .engine file in the directory
            engine_files = sorted(search_dir.glob("*.engine"))
            if engine_files:
                logger.info(f"Found engine (glob fallback): {engine_files[0]}")
                return engine_files[0]

    # Case 3: Path to a .pt file — look in sibling exports/ directory
    if path.suffix == ".pt":
        exports_dir = path.parent / "exports"
        if exports_dir.is_dir():
            for candidate in ENGINE_CANDIDATES:
                engine_path = exports_dir / candidate
                if engine_path.exists():
                    logger.info(f"Found engine next to .pt model: {engine_path}")
                    return engine_path

    raise FileNotFoundError(
        f"No YOLO26 TensorRT engine found at or under: {model_path}\n"
        f"Searched for: {', '.join(ENGINE_CANDIDATES)}\n"
        "If the engine has not been built yet, start the ai-yolo26 container "
        "with YOLO26_PREBUILD_ENGINE=true to generate it."
    )


def validate_engine(engine_path: str) -> bool:
    """Validate that the TensorRT engine file is usable.

    Performs basic sanity checks:
    - File exists and is non-empty
    - File size is reasonable for a YOLO TensorRT engine (> 1 MB)
    - First bytes look like a serialized TensorRT engine

    Full load validation happens when Triton starts.

    Args:
        engine_path: Path to the engine file.

    Returns:
        True if basic checks pass, False otherwise.
    """
    path = Path(engine_path)

    if not path.exists():
        logger.error(f"Engine file does not exist: {engine_path}")
        return False

    file_size = path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)

    if file_size < 1024 * 1024:
        logger.error(
            f"Engine file too small ({file_size_mb:.2f} MB). "
            "Expected at least 1 MB for a YOLO TensorRT engine."
        )
        return False

    # Read first few bytes to check for TensorRT serialized format
    # TensorRT engines typically start with specific magic bytes, but
    # the exact format varies by version.  Just check it's not all zeros.
    with open(engine_path, "rb") as f:
        header = f.read(64)
        if header == b"\x00" * 64:
            logger.error("Engine file appears to be empty/zeroed")
            return False

    logger.info(f"Engine validation passed: {file_size_mb:.1f} MB")
    return True


def copy_engine(
    source: str,
    output_path: str,
    use_symlink: bool = False,
) -> None:
    """Copy or symlink the engine to the Triton model repository location.

    Args:
        source: Path to the source engine file.
        output_path: Destination path (e.g. /models/cache/yolo26/1/model.plan).
        use_symlink: If True, create a symlink instead of copying. Symlinks
                     save disk space but require the source to remain accessible.
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    if use_symlink:
        # Remove existing file/link if present
        dest = Path(output_path)
        if dest.exists() or dest.is_symlink():
            dest.unlink()

        os.symlink(os.path.abspath(source), output_path)
        logger.info(f"Created symlink: {output_path} -> {source}")
    else:
        shutil.copy2(source, output_path)
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"Copied engine: {source} -> {output_path} ({file_size_mb:.1f} MB)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy pre-built YOLO26 TensorRT engine to Triton model repository"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help=(
            "Path to the YOLO26 engine file, model directory, or .pt file. "
            "The script will search for the .engine file automatically."
        ),
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for the engine in Triton repository (model.plan)",
    )
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Create a symlink instead of copying (saves disk space)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip engine validation checks",
    )
    args = parser.parse_args()

    try:
        # Find the engine file
        engine_path = find_engine(args.model_path)

        # Validate before copying
        if not args.skip_validation:
            if not validate_engine(str(engine_path)):
                logger.error("Engine validation failed — aborting copy")
                return 1

        # Copy or symlink to output
        copy_engine(str(engine_path), args.output_path, use_symlink=args.symlink)

        # Validate the copy
        if not args.skip_validation:
            if not validate_engine(args.output_path):
                logger.error("Output validation failed — the copy may be corrupted")
                return 1

        logger.info("YOLO26 engine copy complete")
        return 0

    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"Failed to copy engine: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
