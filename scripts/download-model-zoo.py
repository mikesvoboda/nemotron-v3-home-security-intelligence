#!/usr/bin/env python3
"""
Model Zoo Download Script
Nemotron v3 Home Security Intelligence

Downloads all model zoo models for on-demand enrichment pipeline.
Models are stored in /export/ai_models/model-zoo/{model-name}/.

Usage:
    ./scripts/download-model-zoo.py                    # Download all Phase 1 models
    ./scripts/download-model-zoo.py --phase 2         # Download Phase 2 models
    ./scripts/download-model-zoo.py --all             # Download all phases
    ./scripts/download-model-zoo.py --model vitpose   # Download specific model
    ./scripts/download-model-zoo.py --list            # List available models

Requirements:
    pip install huggingface_hub transformers torch ultralytics
"""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

# Model zoo base path
MODEL_ZOO_PATH = Path("/export/ai_models/model-zoo")

# ANSI colors
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
NC = "\033[0m"  # No Color


class ModelSpec(NamedTuple):
    """Specification for a model to download."""

    name: str
    hf_repo: str
    phase: int
    vram_mb: int
    description: str
    model_type: str  # "transformers", "ultralytics", "paddleocr", "torchreid"


# Model Zoo registry - all models we want to pre-download
MODEL_ZOO: list[ModelSpec] = [
    # Phase 1 - Core Enhancements
    ModelSpec(
        name="yolo-world-s",
        hf_repo="yolov8s-worldv2.pt",  # ultralytics will download this
        phase=1,
        vram_mb=1500,
        description="Open-vocabulary detection (packages, weapons, tools)",
        model_type="ultralytics",
    ),
    ModelSpec(
        name="vitpose-small",
        hf_repo="usyd-community/vitpose-plus-small",
        phase=1,
        vram_mb=1500,
        description="Human pose estimation (17 COCO keypoints)",
        model_type="transformers",
    ),
    ModelSpec(
        name="depth-anything-v2-small",
        hf_repo="depth-anything/Depth-Anything-V2-Small-hf",
        phase=1,
        vram_mb=150,
        description="Monocular depth estimation",
        model_type="transformers",
    ),
    ModelSpec(
        name="osnet-x0-25",
        hf_repo="osnet_x0_25",  # torchreid model name
        phase=1,
        vram_mb=300,
        description="Person re-identification embeddings",
        model_type="torchreid",
    ),
    ModelSpec(
        name="paddleocr-v5",
        hf_repo="PP-OCRv5",  # PaddleOCR model
        phase=1,
        vram_mb=500,
        description="Text/label OCR extraction",
        model_type="paddleocr",
    ),
    # Phase 2 - Context Enrichment
    ModelSpec(
        name="segformer-b2-clothes",
        hf_repo="mattmdjaga/segformer_b2_clothes",
        phase=2,
        vram_mb=1500,
        description="Clothing segmentation (18 categories)",
        model_type="transformers",
    ),
    ModelSpec(
        name="weather-classification",
        hf_repo="prithivMLmods/Weather-Image-Classification",
        phase=2,
        vram_mb=200,
        description="Weather condition detection",
        model_type="transformers",
    ),
    ModelSpec(
        name="violence-detection",
        hf_repo="jaranohaal/vit-base-violence-detection",
        phase=2,
        vram_mb=500,
        description="Violence/aggression detection (98.8% accuracy)",
        model_type="transformers",
    ),
    # X-CLIP 16-frame patch16 model (NEM-3908: upgraded for +4% accuracy)
    ModelSpec(
        name="xclip-base",
        hf_repo="microsoft/xclip-base-patch16-16-frames",
        phase=2,
        vram_mb=2000,
        description="Zero-shot video action recognition (16 frames, +4% accuracy)",
        model_type="transformers",
    ),
    ModelSpec(
        name="fashion-clip",
        hf_repo="Marqo/marqo-fashionCLIP",
        phase=2,
        vram_mb=500,
        description="Zero-shot clothing attributes",
        model_type="transformers",
    ),
    ModelSpec(
        name="florence-2-large",
        hf_repo="microsoft/Florence-2-large",
        phase=2,
        vram_mb=1200,
        description="Vision-language queries (attributes, behavior, scene)",
        model_type="transformers",
    ),
    ModelSpec(
        name="clip-vit-l",
        hf_repo="openai/clip-vit-large-patch14",
        phase=2,
        vram_mb=800,
        description="CLIP embeddings for re-identification",
        model_type="transformers",
    ),
    # Phase 3 - Specialized
    ModelSpec(
        name="vehicle-segment-classification",
        hf_repo="AventIQ-AI/ResNet-50-Vehicle-Segment-classification",
        phase=3,
        vram_mb=1500,
        description="Vehicle type classification (11 classes)",
        model_type="transformers",
    ),
    ModelSpec(
        name="vehicle-damage-detection",
        hf_repo="harpreetsahota/car-dd-segmentation-yolov11",
        phase=3,
        vram_mb=2000,
        description="Vehicle damage segmentation (cracks, dents, glass_shatter)",
        model_type="ultralytics",
    ),
    ModelSpec(
        name="pet-classifier",
        hf_repo="hilmansw/resnet18-catdog-classifier",
        phase=3,
        vram_mb=200,
        description="Dog/cat classification for false positive reduction",
        model_type="transformers",
    ),
]


def print_header(msg: str) -> None:
    """Print a header message."""
    print(f"\n{BLUE}{'=' * 60}{NC}")
    print(f"{BLUE}  {msg}{NC}")
    print(f"{BLUE}{'=' * 60}{NC}\n")


def print_status(msg: str) -> None:
    """Print a status message."""
    print(f"{CYAN}[INFO]{NC} {msg}")


def print_success(msg: str) -> None:
    """Print a success message."""
    print(f"{GREEN}[OK]{NC} {msg}")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    print(f"{YELLOW}[WARN]{NC} {msg}")


def print_error(msg: str) -> None:
    """Print an error message."""
    print(f"{RED}[ERROR]{NC} {msg}")


def download_transformers_model(model: ModelSpec) -> bool:
    """Download a HuggingFace transformers model to model-zoo directory."""
    try:
        from huggingface_hub import snapshot_download

        # Create model directory
        model_dir = MODEL_ZOO_PATH / model.name
        model_dir.mkdir(parents=True, exist_ok=True)

        print_status(f"Downloading {model.name} from {model.hf_repo}...")
        print_status(f"  -> {model_dir}")
        snapshot_download(
            repo_id=model.hf_repo,
            local_dir=str(model_dir),
            local_dir_use_symlinks=False,  # Copy files, don't symlink
        )
        print_success(f"{model.name} downloaded to {model_dir}")
        return True
    except Exception as e:
        print_error(f"Failed to download {model.name}: {e}")
        return False


def download_ultralytics_model(model: ModelSpec) -> bool:
    """Download an ultralytics YOLO model to model-zoo directory."""
    try:
        import shutil

        from ultralytics import YOLO, YOLOWorld

        # Create model directory
        model_dir = MODEL_ZOO_PATH / model.name
        model_dir.mkdir(parents=True, exist_ok=True)
        target_path = model_dir / model.hf_repo

        print_status(f"Downloading {model.name} ({model.hf_repo})...")

        if "world" in model.name.lower():
            yolo_model = YOLOWorld(model.hf_repo)
        else:
            yolo_model = YOLO(model.hf_repo)

        # Access model to trigger download
        _ = yolo_model.model

        # Move downloaded model to model-zoo
        # Ultralytics downloads to current dir or cache
        source_path = Path(model.hf_repo)
        if source_path.exists() and not target_path.exists():
            shutil.move(str(source_path), str(target_path))
            print_status(f"  -> {target_path}")

        print_success(f"{model.name} downloaded to {model_dir}")
        return True
    except ImportError:
        print_error("ultralytics not installed. Run: pip install ultralytics")
        return False
    except Exception as e:
        print_error(f"Failed to download {model.name}: {e}")
        return False


def download_torchreid_model(model: ModelSpec) -> bool:
    """Download a torchreid model to model-zoo directory."""
    try:
        import shutil

        print_status(f"Downloading {model.name} ({model.hf_repo})...")

        # Create model directory
        model_dir = MODEL_ZOO_PATH / model.name
        model_dir.mkdir(parents=True, exist_ok=True)

        # Try torchreid first
        try:
            import torchreid

            torchreid.models.build_model(
                name=model.hf_repo,
                num_classes=1000,
                pretrained=True,
            )

            # Copy from torch cache to model-zoo
            cache_path = Path.home() / ".cache/torch/checkpoints" / f"{model.hf_repo}_imagenet.pth"
            if cache_path.exists():
                target_path = model_dir / f"{model.hf_repo}.pth"
                if not target_path.exists():
                    shutil.copy2(str(cache_path), str(target_path))
                print_status(f"  -> {target_path}")

            print_success(f"{model.name} downloaded to {model_dir}")
            return True
        except ImportError:
            print_warning("torchreid not installed, trying torch hub...")

        # Fallback to torch hub
        import torch

        torch.hub.load(
            "KaiyangZhou/deep-person-reid",
            model.hf_repo,
            pretrained=True,
        )
        print_success(f"{model.name} downloaded successfully via torch hub")
        return True
    except Exception as e:
        print_error(f"Failed to download {model.name}: {e}")
        print_warning("Install torchreid: pip install torchreid")
        return False


def download_paddleocr_model(model: ModelSpec) -> bool:
    """Download PaddleOCR models."""
    try:
        print_status(f"Downloading {model.name}...")

        # PaddleOCR downloads models on first use
        from paddleocr import PaddleOCR

        # Initialize to trigger download
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        _ = ocr  # Trigger initialization

        print_success(f"{model.name} downloaded successfully")
        return True
    except ImportError:
        print_error("paddleocr not installed. Run: pip install paddleocr")
        return False
    except Exception as e:
        print_error(f"Failed to download {model.name}: {e}")
        return False


def download_model(model: ModelSpec) -> bool:
    """Download a model based on its type."""
    downloaders = {
        "transformers": download_transformers_model,
        "ultralytics": download_ultralytics_model,
        "torchreid": download_torchreid_model,
        "paddleocr": download_paddleocr_model,
    }

    downloader = downloaders.get(model.model_type)
    if not downloader:
        print_error(f"Unknown model type: {model.model_type}")
        return False

    return downloader(model)


def list_models() -> None:
    """List all available models."""
    print_header("Available Model Zoo Models")

    for phase in [1, 2, 3]:
        print(f"\n{CYAN}Phase {phase}:{NC}")
        print("-" * 50)
        phase_models = [m for m in MODEL_ZOO if m.phase == phase]
        for model in phase_models:
            print(f"  {GREEN}{model.name:<30}{NC} {model.vram_mb:>5}MB  {model.description}")

    total_vram = sum(m.vram_mb for m in MODEL_ZOO)
    print(f"\n{YELLOW}Total VRAM (all models loaded): ~{total_vram}MB{NC}")
    print(f"{CYAN}Note: Models load on-demand, not all at once{NC}")


def check_existing_downloads() -> dict[str, bool]:
    """Check which models are already downloaded in model-zoo directory."""
    existing = {}

    for model in MODEL_ZOO:
        model_dir = MODEL_ZOO_PATH / model.name
        if model_dir.exists():
            # Check if directory has actual model files
            has_files = any(
                f.suffix in (".pt", ".pth", ".safetensors", ".bin", ".onnx")
                for f in model_dir.rglob("*")
                if f.is_file()
            )
            existing[model.name] = has_files
        else:
            existing[model.name] = False

    return existing


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download Model Zoo models for home security pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s                    # Download Phase 1 models
    %(prog)s --phase 2          # Download Phase 2 models
    %(prog)s --all              # Download all models
    %(prog)s --model vitpose    # Download specific model
    %(prog)s --list             # List available models
    %(prog)s --status           # Check download status
        """,
    )
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3],
        default=1,
        help="Download models from specific phase (default: 1)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all models from all phases",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Download a specific model by name",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available models",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check download status of all models",
    )

    args = parser.parse_args()

    if args.list:
        list_models()
        return 0

    if args.status:
        print_header("Model Download Status")
        existing = check_existing_downloads()
        for model in MODEL_ZOO:
            status = (
                f"{GREEN}Downloaded{NC}"
                if existing.get(model.name)
                else f"{YELLOW}Not downloaded{NC}"
            )
            print(f"  {model.name:<30} [{status}]")
        return 0

    # Determine which models to download
    if args.model:
        models_to_download = [m for m in MODEL_ZOO if args.model.lower() in m.name.lower()]
        if not models_to_download:
            print_error(f"No model found matching '{args.model}'")
            print("Use --list to see available models")
            return 1
    elif args.all:
        models_to_download = MODEL_ZOO
    else:
        models_to_download = [m for m in MODEL_ZOO if m.phase == args.phase]

    print_header(f"Model Zoo Download - {len(models_to_download)} models")

    # Check existing
    existing = check_existing_downloads()

    success_count = 0
    skip_count = 0
    fail_count = 0

    for model in models_to_download:
        print(f"\n{BLUE}[{model.phase}] {model.name}{NC} - {model.description}")

        if existing.get(model.name) and model.model_type == "transformers":
            print_success("Already downloaded, skipping")
            skip_count += 1
            continue

        if download_model(model):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    print_header("Download Summary")
    print(f"  {GREEN}Downloaded:{NC} {success_count}")
    print(f"  {CYAN}Skipped:{NC} {skip_count}")
    print(f"  {RED}Failed:{NC} {fail_count}")

    if fail_count > 0:
        print(f"\n{YELLOW}Some models failed to download. Check errors above.{NC}")
        return 1

    print(f"\n{GREEN}All models ready!{NC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
