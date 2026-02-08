"""AI model download integration for setup.py.

Provides model download functionality by invoking the existing download scripts
or downloading models directly via HuggingFace Hub.

Usage:
    from setup_lib.model_downloader import prompt_and_download_models
    prompt_and_download_models(config)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

# Try to import huggingface_hub for direct downloads
try:
    from huggingface_hub import snapshot_download

    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False


class ModelSpec(NamedTuple):
    """Specification for a model to download."""

    name: str
    hf_repo: str
    phase: int
    size_mb: int
    description: str
    required: bool  # True for essential models, False for optional


# Core models required for the system to function
REQUIRED_MODELS: list[ModelSpec] = [
    # YOLO26 - primary object detection
    ModelSpec(
        name="yolo26",
        hf_repo="",  # Downloaded via ultralytics
        phase=0,
        size_mb=50,
        description="YOLO26 object detection (downloaded via ultralytics on first run)",
        required=True,
    ),
    # Florence-2 - vision-language model
    ModelSpec(
        name="florence-2-base",
        hf_repo="microsoft/Florence-2-base",
        phase=1,
        size_mb=450,
        description="Florence-2-base vision-language model (smaller, saves ~1.2GB VRAM)",
        required=True,
    ),
    # CLIP - embeddings for re-identification
    ModelSpec(
        name="clip-vit-l",
        hf_repo="openai/clip-vit-large-patch14",
        phase=1,
        size_mb=800,
        description="CLIP embeddings for entity re-identification",
        required=True,
    ),
]

# Optional enrichment models (Phase 1 - Core)
PHASE1_MODELS: list[ModelSpec] = [
    ModelSpec(
        name="yolo11-face-detection",
        hf_repo="AdamCodd/YOLOv11n-face-detection",
        phase=1,
        size_mb=11,
        description="YOLO11 face detection on person crops",
        required=False,
    ),
    ModelSpec(
        name="yolo11-license-plate",
        hf_repo="morsetechlab/yolov11-license-plate-detection",
        phase=1,
        size_mb=650,
        description="YOLO11 license plate detection (multiple variants)",
        required=False,
    ),
    ModelSpec(
        name="smoke-fire-yolov8n",
        hf_repo="luminous0219/fire-and-smoke-detection-yolov8",
        phase=1,
        size_mb=25,
        description="Smoke/fire detection (CRITICAL safety model)",
        required=False,
    ),
    ModelSpec(
        name="depth-anything-v2-tiny",
        hf_repo="depth-anything/Depth-Anything-V2-Tiny-hf",
        phase=1,
        size_mb=100,
        description="Monocular depth estimation (3x faster than Small)",
        required=False,
    ),
    ModelSpec(
        name="osnet-x0-25",
        hf_repo="",  # torchreid model
        phase=1,
        size_mb=300,
        description="Person re-identification embeddings",
        required=False,
    ),
    ModelSpec(
        name="yolov8n-pose",
        hf_repo="",  # ultralytics
        phase=1,
        size_mb=50,
        description="Human pose estimation (17 COCO keypoints)",
        required=False,
    ),
]

# Optional enrichment models (Phase 2 - Context)
PHASE2_MODELS: list[ModelSpec] = [
    ModelSpec(
        name="fashion-clip",
        hf_repo="Marqo/marqo-fashionCLIP",
        phase=2,
        size_mb=500,
        description="Zero-shot clothing attribute detection",
        required=False,
    ),
    ModelSpec(
        name="xclip-base",
        hf_repo="microsoft/xclip-base-patch16-16-frames",
        phase=2,
        size_mb=2000,
        description="Video action recognition (16 frames)",
        required=False,
    ),
    ModelSpec(
        name="vit-age-classifier",
        hf_repo="nateraw/vit-age-classifier",
        phase=2,
        size_mb=350,
        description="Age estimation from face",
        required=False,
    ),
    ModelSpec(
        name="vit-gender-classifier",
        hf_repo="rizvandwiki/gender-classification",
        phase=2,
        size_mb=350,
        description="Gender classification from face",
        required=False,
    ),
]

# Optional enrichment models (Phase 3 - Specialized)
PHASE3_MODELS: list[ModelSpec] = [
    ModelSpec(
        name="vehicle-segment-classification",
        hf_repo="AventIQ-AI/ResNet-50-Vehicle-Segment-classification",
        phase=3,
        size_mb=1500,
        description="Vehicle type classification (11 classes)",
        required=False,
    ),
    ModelSpec(
        name="pet-classifier",
        hf_repo="hilmansw/resnet18-catdog-classifier",
        phase=3,
        size_mb=200,
        description="Dog/cat classification for false positive reduction",
        required=False,
    ),
    ModelSpec(
        name="threat-detection-yolov8n",
        hf_repo="Subh775/Threat-Detection-YOLOv8n",
        phase=3,
        size_mb=25,
        description="Threat/weapon detection",
        required=False,
    ),
]


def check_model_exists(model_path: Path, model_name: str) -> bool:
    """Check if a model is already downloaded.

    Args:
        model_path: Base path for AI models.
        model_name: Name of the model directory.

    Returns:
        True if model directory exists and has model files.
    """
    model_dir = model_path / "model-zoo" / model_name
    if not model_dir.exists():
        return False

    # Check for common model file extensions
    model_extensions = (".pt", ".pth", ".safetensors", ".bin", ".onnx", ".engine")
    return any(list(model_dir.rglob(f"*{ext}")) for ext in model_extensions)


def download_hf_model(model: ModelSpec, model_path: Path) -> bool:
    """Download a HuggingFace model.

    Args:
        model: Model specification.
        model_path: Base path for AI models.

    Returns:
        True if download successful, False otherwise.
    """
    if not HF_HUB_AVAILABLE:
        print("    ! huggingface_hub not installed")
        return False

    if not model.hf_repo:
        print(f"    ! {model.name} is not a HuggingFace model (uses alternative loader)")
        return False

    model_dir = model_path / "model-zoo" / model.name
    model_dir.mkdir(parents=True, exist_ok=True)

    try:
        print(f"    Downloading from {model.hf_repo}...")
        snapshot_download(
            repo_id=model.hf_repo,
            local_dir=str(model_dir),
            local_dir_use_symlinks=False,
        )
        print(f"    + Downloaded to {model_dir}")
        return True
    except Exception as e:
        print(f"    ! Download failed: {e}")
        return False


def run_download_script(script_name: str, args: list[str] | None = None) -> bool:
    """Run a download script from the scripts directory.

    Args:
        script_name: Name of the script (e.g., 'download-model-zoo.py').
        args: Additional arguments to pass to the script.

    Returns:
        True if script ran successfully, False otherwise.
    """
    script_path = Path("scripts") / script_name
    if not script_path.exists():
        print(f"    ! Script not found: {script_path}")
        return False

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=False,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"    ! Script failed with code {e.returncode}")
        return False
    except FileNotFoundError:
        print("    ! Python not found or script error")
        return False


def calculate_download_size(models: list[ModelSpec], model_path: Path) -> int:
    """Calculate total download size for models not yet downloaded.

    Args:
        models: List of models to check.
        model_path: Base path for AI models.

    Returns:
        Total size in MB of models that need downloading.
    """
    total_mb = 0
    for model in models:
        if not check_model_exists(model_path, model.name):
            total_mb += model.size_mb
    return total_mb


def prompt_and_download_models(config: dict) -> None:
    """Prompt user and download AI models.

    Args:
        config: Configuration dictionary with 'ai_models_path'.
    """
    print()
    print("=" * 60)
    print("AI Model Downloads")
    print("=" * 60)
    print()

    ai_models_path = Path(config.get("ai_models_path", "/export/ai_models"))

    # Check if model-zoo directory exists
    model_zoo_path = ai_models_path / "model-zoo"
    if not model_zoo_path.exists():
        print(f"Model directory: {model_zoo_path}")
        print("  This directory does not exist yet.")
        create = input("  Create it now? [y]: ").strip().lower()
        if not create or create in ("y", "yes"):
            try:
                model_zoo_path.mkdir(parents=True, exist_ok=True)
                print("  + Directory created")
            except PermissionError:
                print("  ! Permission denied. Create manually:")
                print(f"    sudo mkdir -p {model_zoo_path}")
                return
    else:
        print(f"Model directory: {model_zoo_path}")

    print()

    # Check which models are already downloaded
    all_models = REQUIRED_MODELS + PHASE1_MODELS + PHASE2_MODELS + PHASE3_MODELS
    downloaded = []
    missing = []

    for model in all_models:
        if check_model_exists(ai_models_path, model.name):
            downloaded.append(model)
        else:
            missing.append(model)

    print(f"Models found: {len(downloaded)}/{len(all_models)}")
    if downloaded:
        print("  Already downloaded:")
        for model in downloaded:
            print(f"    + {model.name}")

    if not missing:
        print()
        print("+ All models already downloaded!")
        return

    print()
    print(f"Models not yet downloaded: {len(missing)}")
    for model in missing:
        required_tag = " (REQUIRED)" if model.required else ""
        print(f"  - {model.name}: ~{model.size_mb}MB{required_tag}")
        print(f"    {model.description}")

    # Calculate total download size
    total_size_mb = sum(m.size_mb for m in missing)
    print()
    print(f"Total download size: ~{total_size_mb / 1024:.1f} GB")
    print()

    # Check for disk space
    try:
        usage = shutil.disk_usage(ai_models_path.parent if ai_models_path.exists() else Path.cwd())
        free_gb = usage.free / (1024**3)
        if free_gb < total_size_mb / 1024 * 1.2:  # 20% buffer
            print(
                f"! Warning: Only {free_gb:.1f} GB free, need ~{total_size_mb / 1024 * 1.2:.1f} GB"
            )
    except OSError:
        pass

    # Prompt for download options
    print("Download options:")
    print("  1. Download required models only (Florence-2, CLIP)")
    print("  2. Download required + Phase 1 (core enrichment)")
    print("  3. Download all models (full feature set)")
    print("  4. Skip (download later with scripts/download-model-zoo.py)")
    print()

    choice = input("Select option [1]: ").strip() or "1"

    if choice == "4":
        print()
        print("Skipping model downloads.")
        print("To download later, run:")
        print("  python scripts/download-model-zoo.py --all")
        return

    # Determine which models to download
    models_to_download: list[ModelSpec] = []

    if choice in ("1", "2", "3"):
        # Always include required models (skip yolo26 as it downloads on first run)
        models_to_download.extend([m for m in REQUIRED_MODELS if m.hf_repo])

    if choice in ("2", "3"):
        models_to_download.extend([m for m in PHASE1_MODELS if m.hf_repo])

    if choice == "3":
        models_to_download.extend([m for m in PHASE2_MODELS if m.hf_repo])
        models_to_download.extend([m for m in PHASE3_MODELS if m.hf_repo])

    # Filter out already downloaded models
    models_to_download = [
        m for m in models_to_download if not check_model_exists(ai_models_path, m.name)
    ]

    if not models_to_download:
        print()
        print("+ All selected models already downloaded!")
        return

    print()
    print(f"Downloading {len(models_to_download)} models...")
    print()

    # Check if we can use huggingface_hub directly
    hf_available = HF_HUB_AVAILABLE
    if not hf_available:
        print("! huggingface_hub not installed")
        print("  Installing: pip install huggingface_hub")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "huggingface_hub"],
                check=True,
                capture_output=True,
            )
            # Re-import after installation
            from huggingface_hub import snapshot_download  # noqa: F401

            hf_available = True
            print("  + huggingface_hub installed")
        except Exception as e:
            print(f"  ! Failed to install huggingface_hub: {e}")
            print("  Falling back to download script...")
            # Try using the download script
            if run_download_script("download-model-zoo.py", ["--all"]):
                print("+ Models downloaded via script")
            return

    # Download each model
    success_count = 0
    fail_count = 0

    for model in models_to_download:
        print(f"  [{model.phase}] {model.name}")
        if download_hf_model(model, ai_models_path):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    print()
    print("=" * 40)
    print(f"Download complete: {success_count} succeeded, {fail_count} failed")

    if fail_count > 0:
        print()
        print("! Some models failed to download.")
        print("  You can retry later with:")
        print("    python scripts/download-model-zoo.py --all")

    # Note about Nemotron LLM
    print()
    print("Note: The Nemotron LLM model (~22GB) is downloaded separately.")
    print("See docs/operator/nemotron-setup.md for instructions.")
