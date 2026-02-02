#!/usr/bin/env python3
"""Download open-licensed datasets for AI pipeline evaluation.

This script downloads and extracts datasets with permissive licenses:
- Kinetics-700 (CC BY 4.0) - Action recognition
- COCO (CC BY 4.0) - Object detection baseline
- ShanghaiTech (BSD) - Anomaly detection
- CCPD (MIT) - License plates
- FLIR ADAS (dev use) - Thermal/night

Usage:
    uv run scripts/download_open_datasets.py --dataset ccpd --limit 100
    uv run scripts/download_open_datasets.py --dataset all --dry-run
    uv run scripts/download_open_datasets.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_EXTERNAL = PROJECT_ROOT / "data" / "external"


@dataclass
class DatasetInfo:
    """Information about an external dataset."""

    name: str
    description: str
    license: str
    license_url: str
    commercial_use: bool
    attribution_required: bool
    download_urls: list[str]
    size_estimate: str
    categories: list[str]


# Dataset registry with metadata and download information
DATASETS: dict[str, DatasetInfo] = {
    "ccpd": DatasetInfo(
        name="CCPD - Chinese City Parking Dataset",
        description="License plate detection and OCR with 250k+ images",
        license="MIT",
        license_url="https://github.com/detectRecog/CCPD/blob/master/LICENSE",
        commercial_use=True,
        attribution_required=True,
        download_urls=[
            # CCPD2019 base dataset
            "https://github.com/detectRecog/CCPD/releases/download/v1.0/CCPD2019.tar.gz",
        ],
        size_estimate="12GB",
        categories=["license_plates", "vehicles"],
    ),
    "coco": DatasetInfo(
        name="COCO - Common Objects in Context",
        description="Object detection with 80 categories, 330K+ images",
        license="CC BY 4.0",
        license_url="https://cocodataset.org/#termsofuse",
        commercial_use=True,
        attribution_required=True,
        download_urls=[
            # 2017 validation set (smaller, good for evaluation)
            "http://images.cocodataset.org/zips/val2017.zip",
            "http://images.cocodataset.org/annotations/annotations_trainval2017.zip",
        ],
        size_estimate="1GB (val only)",
        categories=["objects", "animals", "vehicles", "people"],
    ),
    "kinetics": DatasetInfo(
        name="Kinetics-700",
        description="Action recognition with 700 human action classes",
        license="CC BY 4.0",
        license_url="https://github.com/cvdfoundation/kinetics-dataset",
        commercial_use=True,
        attribution_required=True,
        download_urls=[
            # Kinetics dataset requires youtube-dl to download videos
            # We store the annotation files and download tool
            "https://storage.googleapis.com/deepmind-media/Datasets/kinetics700_2020.tar.gz",
        ],
        size_estimate="650GB (full), annotations only ~50MB",
        categories=["actions", "fighting", "breaking", "running", "walking"],
    ),
    "shanghaitech": DatasetInfo(
        name="ShanghaiTech Anomaly Detection",
        description="Surveillance anomaly detection with 130 abnormal events",
        license="BSD 2-Clause",
        license_url="https://svip-lab.github.io/dataset/campus_dataset.html",
        commercial_use=True,
        attribution_required=True,
        download_urls=[
            # ShanghaiTech Campus dataset
            "https://drive.google.com/uc?id=1rB1deKlNpdB0Je-9xANNKr1B6OgHNJfU",
        ],
        size_estimate="15GB",
        categories=["anomaly", "surveillance", "suspicious"],
    ),
    "flir": DatasetInfo(
        name="FLIR ADAS Thermal Dataset",
        description="Thermal/night imagery with 14k+ annotated images",
        license="FLIR Free Dataset License Agreement",
        license_url="https://www.flir.com/oem/adas/adas-dataset-form/",
        commercial_use=False,  # Research/development only
        attribution_required=True,
        download_urls=[
            # Requires registration at FLIR website
            "https://www.flir.com/oem/adas/adas-dataset-form/",
        ],
        size_estimate="1.5GB",
        categories=["thermal", "night", "vehicles", "pedestrians"],
    ),
}

# Security-relevant Kinetics-700 action classes for selective download
KINETICS_SECURITY_CLASSES = [
    # Threatening actions
    "punching_person_(boxing)",
    "wrestling",
    "slapping",
    "kicking_person",
    "headbutting",
    "throwing_axe",
    "throwing_ball",
    "shooting_goal_(soccer)",
    # Suspicious actions
    "climbing_a_rope",
    "climbing_ladder",
    "climbing_tree",
    "crawling_baby",
    "opening_door",
    "opening_present",
    "opening_bottle",
    "picking_fruit",
    "picking_up",
    # Normal activities
    "walking_the_dog",
    "walking_through_snow",
    "jogging",
    "running_on_treadmill",
    "riding_a_bike",
    "riding_scooter",
    "getting_out_of_car",
    "parking_car",
    "delivering_mail",
    "mowing_lawn",
    "gardening",
    "watering_plants",
]


def get_cache_path(url: str) -> Path:
    """Get cache file path for a URL."""
    # MD5 is used only for cache file naming, not security purposes
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]  # noqa: S324  # nosemgrep
    filename = Path(urlparse(url).path).name or f"download_{url_hash}"
    return DATA_EXTERNAL / ".cache" / filename


def download_file(
    url: str,
    output_path: Path,
    resume: bool = True,
    chunk_size: int = 8192,
) -> bool:
    """Download a file with progress bar and resume support.

    Args:
        url: URL to download from
        output_path: Path to save the file
        resume: Whether to resume partial downloads
        chunk_size: Download chunk size in bytes

    Returns:
        True if download successful, False otherwise
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Check for existing partial download
    headers: dict[str, str] = {}
    initial_size = 0
    if resume and output_path.exists():
        initial_size = output_path.stat().st_size
        headers["Range"] = f"bytes={initial_size}-"
        logger.info("Resuming download from byte %d", initial_size)

    try:
        # URLs are hardcoded from DATASETS registry - no user input
        response = requests.get(url, headers=headers, stream=True, timeout=30)  # nosemgrep

        # Handle resume response
        if response.status_code == 416:  # Range not satisfiable (file complete)
            logger.info("File already complete: %s", output_path)
            return True
        elif response.status_code == 206:  # Partial content
            mode = "ab"
        elif response.status_code == 200:
            mode = "wb"
            initial_size = 0
        else:
            logger.error("Download failed: HTTP %d", response.status_code)
            return False

        # Get total size
        total_size = int(response.headers.get("content-length", 0))
        if total_size:
            total_size += initial_size

        # Download with progress bar - output_path is constructed by get_cache_path()
        with (
            open(output_path, mode) as f,  # nosemgrep
            tqdm(
                total=total_size,
                initial=initial_size,
                unit="B",
                unit_scale=True,
                desc=output_path.name,
            ) as pbar,
        ):
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

        return True

    except requests.RequestException as e:
        logger.error("Download error: %s", e)
        return False


def verify_checksum(file_path: Path, expected_hash: str, algorithm: str = "sha256") -> bool:
    """Verify file checksum.

    Args:
        file_path: Path to file to verify
        expected_hash: Expected hash value
        algorithm: Hash algorithm (md5, sha256, etc.)

    Returns:
        True if checksum matches, False otherwise
    """
    hash_func = hashlib.new(algorithm)
    # file_path is from trusted cache directory
    with open(file_path, "rb") as f:  # nosemgrep
        for chunk in iter(lambda: f.read(8192), b""):
            hash_func.update(chunk)

    actual_hash = hash_func.hexdigest()
    if actual_hash != expected_hash:
        logger.error(
            "Checksum mismatch for %s: expected %s, got %s",
            file_path,
            expected_hash,
            actual_hash,
        )
        return False
    return True


def extract_archive(
    archive_path: Path,
    output_dir: Path,
    remove_archive: bool = False,
) -> bool:
    """Extract tar.gz or zip archive.

    Args:
        archive_path: Path to archive file
        output_dir: Directory to extract to
        remove_archive: Whether to remove archive after extraction

    Returns:
        True if extraction successful, False otherwise
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Archives are from trusted sources (official dataset downloads)
        if archive_path.suffix == ".zip" or archive_path.name.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(output_dir)  # noqa: S202
        elif archive_path.name.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive_path, "r:gz") as tf:
                tf.extractall(output_dir)  # noqa: S202
        elif archive_path.name.endswith(".tar"):
            with tarfile.open(archive_path, "r") as tf:
                tf.extractall(output_dir)  # noqa: S202
        else:
            logger.error("Unknown archive format: %s", archive_path)
            return False

        logger.info("Extracted to %s", output_dir)

        if remove_archive:
            archive_path.unlink()
            logger.info("Removed archive: %s", archive_path)

        return True

    except (zipfile.BadZipFile, tarfile.TarError) as e:
        logger.error("Extraction failed: %s", e)
        return False


def write_license_file(dataset_name: str, output_dir: Path) -> None:
    """Write license information file for a dataset.

    Args:
        dataset_name: Name of the dataset
        output_dir: Directory to write LICENSE.txt to
    """
    info = DATASETS.get(dataset_name)
    if not info:
        return

    license_content = f"""Dataset: {info.name}
License: {info.license}
License URL: {info.license_url}

Commercial Use: {"Yes" if info.commercial_use else "No (Research/Development only)"}
Attribution Required: {"Yes" if info.attribution_required else "No"}

Description:
{info.description}

Downloaded: {datetime.now().isoformat()}

Categories: {", ".join(info.categories)}

---

Please refer to the license URL above for full terms and conditions.
"""

    license_path = output_dir / "LICENSE.txt"
    license_path.write_text(license_content)
    logger.info("Wrote license file: %s", license_path)


def write_manifest(
    dataset_name: str,
    output_dir: Path,
    file_count: int,
    total_size: int,
) -> None:
    """Write manifest.json for downloaded dataset.

    Args:
        dataset_name: Name of the dataset
        output_dir: Dataset output directory
        file_count: Number of files downloaded
        total_size: Total size in bytes
    """
    info = DATASETS.get(dataset_name)
    if not info:
        return

    manifest = {
        "dataset": dataset_name,
        "name": info.name,
        "license": info.license,
        "download_date": datetime.now().isoformat(),
        "file_count": file_count,
        "total_size_bytes": total_size,
        "categories": info.categories,
        "converted": False,
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info("Wrote manifest: %s", manifest_path)


def download_ccpd(output_dir: Path, limit: int | None = None, dry_run: bool = False) -> bool:
    """Download CCPD license plate dataset.

    Args:
        output_dir: Output directory
        limit: Maximum number of images to keep (None for all)
        dry_run: If True, only show what would be downloaded

    Returns:
        True if successful
    """
    info = DATASETS["ccpd"]
    logger.info("Downloading %s", info.name)

    if dry_run:
        logger.info("[DRY RUN] Would download CCPD dataset (~12GB)")
        return True

    # Download archive
    url = info.download_urls[0]
    cache_path = get_cache_path(url)

    if not cache_path.exists():
        logger.info("Downloading from %s", url)
        if not download_file(url, cache_path):
            return False
    else:
        logger.info("Using cached file: %s", cache_path)

    # Extract
    raw_dir = output_dir / "raw"
    if not extract_archive(cache_path, raw_dir):
        return False

    # Apply limit if specified
    if limit:
        logger.info("Limiting to %d images", limit)
        images = list(raw_dir.rglob("*.jpg"))
        for img in images[limit:]:
            img.unlink()

    # Write metadata
    write_license_file("ccpd", output_dir)

    file_count = len(list(raw_dir.rglob("*.jpg")))
    total_size = sum(f.stat().st_size for f in raw_dir.rglob("*") if f.is_file())
    write_manifest("ccpd", output_dir, file_count, total_size)

    logger.info("CCPD download complete: %d images", file_count)
    return True


def download_coco(output_dir: Path, limit: int | None = None, dry_run: bool = False) -> bool:
    """Download COCO validation dataset.

    Args:
        output_dir: Output directory
        limit: Maximum number of images to keep (None for all)
        dry_run: If True, only show what would be downloaded

    Returns:
        True if successful
    """
    info = DATASETS["coco"]
    logger.info("Downloading %s", info.name)

    if dry_run:
        logger.info("[DRY RUN] Would download COCO val2017 (~1GB)")
        return True

    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Download images and annotations
    for url in info.download_urls:
        cache_path = get_cache_path(url)
        if not cache_path.exists():
            logger.info("Downloading from %s", url)
            if not download_file(url, cache_path):
                return False
        else:
            logger.info("Using cached file: %s", cache_path)

        # Extract
        if not extract_archive(cache_path, raw_dir):
            return False

    # Apply limit if specified
    if limit:
        logger.info("Limiting to %d images", limit)
        images = list(raw_dir.rglob("*.jpg"))
        for img in images[limit:]:
            img.unlink()

    # Write metadata
    write_license_file("coco", output_dir)

    file_count = len(list(raw_dir.rglob("*.jpg")))
    total_size = sum(f.stat().st_size for f in raw_dir.rglob("*") if f.is_file())
    write_manifest("coco", output_dir, file_count, total_size)

    logger.info("COCO download complete: %d images", file_count)
    return True


def download_kinetics(
    output_dir: Path,
    limit: int | None = None,
    dry_run: bool = False,
) -> bool:
    """Download Kinetics annotation files.

    Note: Full video download requires youtube-dl and is handled separately.

    Args:
        output_dir: Output directory
        limit: Not used for annotations
        dry_run: If True, only show what would be downloaded

    Returns:
        True if successful
    """
    info = DATASETS["kinetics"]
    logger.info("Downloading %s (annotations only)", info.name)

    if dry_run:
        logger.info("[DRY RUN] Would download Kinetics annotations (~50MB)")
        logger.info("Note: Full videos require youtube-dl")
        return True

    # Download annotations
    url = info.download_urls[0]
    cache_path = get_cache_path(url)

    if not cache_path.exists():
        logger.info("Downloading from %s", url)
        if not download_file(url, cache_path):
            return False
    else:
        logger.info("Using cached file: %s", cache_path)

    # Extract
    raw_dir = output_dir / "raw"
    if not extract_archive(cache_path, raw_dir):
        return False

    # Write security-relevant classes file
    classes_file = output_dir / "security_classes.json"
    classes_file.write_text(json.dumps(KINETICS_SECURITY_CLASSES, indent=2))
    logger.info("Wrote security classes: %s", classes_file)

    # Write metadata
    write_license_file("kinetics", output_dir)
    write_manifest("kinetics", output_dir, 0, 0)

    logger.info("Kinetics annotations downloaded")
    logger.info("To download videos, use: scripts/download_kinetics_videos.py")
    return True


def download_shanghaitech(
    output_dir: Path,
    limit: int | None = None,
    dry_run: bool = False,
) -> bool:
    """Download ShanghaiTech Campus dataset.

    Note: Dataset hosted on Google Drive requires manual download or gdown.

    Args:
        output_dir: Output directory
        limit: Maximum number of videos to keep
        dry_run: If True, only show what would be downloaded

    Returns:
        True if successful
    """
    info = DATASETS["shanghaitech"]
    logger.info("Downloading %s", info.name)

    if dry_run:
        logger.info("[DRY RUN] Would download ShanghaiTech (~15GB)")
        logger.info("Note: Hosted on Google Drive, may require manual download")
        return True

    # Check for gdown
    try:
        import gdown
    except ImportError:
        logger.error("gdown required: pip install gdown")
        logger.info("Or download manually from: %s", info.download_urls[0])
        return False

    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Download from Google Drive
    archive_path = raw_dir / "shanghaitech.zip"
    if not archive_path.exists():
        gdown.download(info.download_urls[0], str(archive_path), quiet=False)

    # Extract
    if not extract_archive(archive_path, raw_dir):
        return False

    # Write metadata
    write_license_file("shanghaitech", output_dir)

    file_count = len(list(raw_dir.rglob("*.avi")))
    total_size = sum(f.stat().st_size for f in raw_dir.rglob("*") if f.is_file())
    write_manifest("shanghaitech", output_dir, file_count, total_size)

    logger.info("ShanghaiTech download complete: %d videos", file_count)
    return True


def download_flir(
    output_dir: Path,
    limit: int | None = None,
    dry_run: bool = False,
) -> bool:
    """Provide instructions for FLIR ADAS dataset download.

    Note: FLIR requires registration, cannot be automated.

    Args:
        output_dir: Output directory
        limit: Not applicable
        dry_run: If True, only show instructions

    Returns:
        True (always, since this is informational)
    """
    info = DATASETS["flir"]
    logger.info("FLIR ADAS Dataset")
    logger.info("=" * 50)
    logger.info("License: %s", info.license)
    logger.info(
        "Commercial Use: %s", "No (Research/Development only)" if not info.commercial_use else "Yes"
    )
    logger.info("")
    logger.info("FLIR requires manual registration:")
    logger.info("1. Visit: %s", info.download_urls[0])
    logger.info("2. Fill out the registration form")
    logger.info("3. Download the dataset")
    logger.info("4. Extract to: %s/raw/", output_dir)
    logger.info("")
    logger.info("After extraction, run the converter:")
    logger.info("  uv run scripts/dataset_converters/flir_converter.py")

    # Write metadata
    write_license_file("flir", output_dir)

    return True


# Dataset download handlers
DOWNLOAD_HANDLERS: dict[str, Any] = {
    "ccpd": download_ccpd,
    "coco": download_coco,
    "kinetics": download_kinetics,
    "shanghaitech": download_shanghaitech,
    "flir": download_flir,
}


def list_datasets() -> None:
    """Print information about available datasets."""
    print("\nAvailable Datasets:")
    print("=" * 80)

    for name, info in DATASETS.items():
        print(f"\n{name}:")
        print(f"  Name: {info.name}")
        print(f"  License: {info.license}")
        print(f"  Commercial Use: {'Yes' if info.commercial_use else 'No'}")
        print(f"  Size: {info.size_estimate}")
        print(f"  Categories: {', '.join(info.categories)}")
        print(f"  Description: {info.description}")

    print("\n" + "=" * 80)
    print("Usage: uv run scripts/download_open_datasets.py --dataset <name>")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download open-licensed datasets for AI evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run scripts/download_open_datasets.py --list
  uv run scripts/download_open_datasets.py --dataset ccpd --limit 100
  uv run scripts/download_open_datasets.py --dataset coco --dry-run
  uv run scripts/download_open_datasets.py --dataset all
        """,
    )

    parser.add_argument(
        "--dataset",
        choices=[*DATASETS.keys(), "all"],
        help="Dataset to download",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of samples to keep",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without downloading",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available datasets",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATA_EXTERNAL,
        help="Output directory (default: data/external)",
    )

    args = parser.parse_args()

    if args.list:
        list_datasets()
        return 0

    if not args.dataset:
        parser.print_help()
        return 1

    # Create cache directory
    cache_dir = args.output_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Download requested datasets
    datasets = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]

    success = True
    for dataset_name in datasets:
        output_dir = args.output_dir / dataset_name
        handler = DOWNLOAD_HANDLERS.get(dataset_name)

        if handler:
            try:
                if not handler(output_dir, args.limit, args.dry_run):
                    success = False
                    logger.error("Failed to download %s", dataset_name)
            except Exception as e:
                logger.exception("Error downloading %s: %s", dataset_name, e)
                success = False
        else:
            logger.error("No handler for dataset: %s", dataset_name)
            success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
