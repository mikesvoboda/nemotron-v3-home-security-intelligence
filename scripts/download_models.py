#!/usr/bin/env python3
"""Download all required AI models from HuggingFace."""

import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model configurations
# Maps local directory name -> download configuration
MODELS = {
    "fashion-clip": {"repo": "patrickjohncyh/fashion-clip", "type": "huggingface"},
    "depth-anything-v2-small": {
        "repo": "depth-anything/Depth-Anything-V2-Small",
        "type": "huggingface",
    },
    # X-CLIP 16-frame patch16 model for improved action recognition accuracy (NEM-3908)
    "xclip-base-patch16-16-frames": {
        "repo": "microsoft/xclip-base-patch16-16-frames",
        "type": "huggingface",
    },
    "vit-age-classifier": {"repo": "nateraw/vit-age-classifier", "type": "huggingface"},
    "yolov8n-pose": {"repo": "yolov8n-pose.pt", "type": "ultralytics"},
    "osnet-x0-25": {"repo": "osnet_x0_25", "type": "torchreid"},
    # Threat detection model for weapon/dangerous object detection
    # Reference: https://huggingface.co/Subh775/Threat-Detection-YOLOv8n
    "threat-detection-yolov8n": {
        "repo": "Subh775/Threat-Detection-YOLOv8n",
        "type": "huggingface",
    },
    # Gender classifier (reserved for future demographics enhancement)
    # Reference: https://huggingface.co/rizvandwiki/gender-classification
    "vit-gender-classifier": {
        "repo": "rizvandwiki/gender-classification",
        "type": "huggingface",
    },
}


def download_huggingface_model(repo: str, target_dir: Path) -> bool:
    """Download model from HuggingFace Hub."""
    try:
        from huggingface_hub import snapshot_download

        logger.info(f"Downloading {repo} to {target_dir}...")
        snapshot_download(repo_id=repo, local_dir=str(target_dir), local_dir_use_symlinks=False)
        return True
    except Exception as e:
        logger.error(f"Failed to download {repo}: {e}")
        return False


def download_ultralytics_model(model_name: str, target_dir: Path) -> bool:
    """Download model using Ultralytics."""
    try:
        from ultralytics import YOLO

        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloading {model_name}...")

        model = YOLO(model_name)
        # Model is downloaded to current dir, move it
        import shutil

        if Path(model_name).exists():
            shutil.move(model_name, target_dir / model_name)
        return True
    except Exception as e:
        logger.error(f"Failed to download {model_name}: {e}")
        return False


def download_torchreid_model(model_name: str, target_dir: Path) -> bool:
    """Download model using torchreid."""
    try:
        import torch
        import torchreid

        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloading {model_name}...")

        model = torchreid.models.build_model(name=model_name, num_classes=1, pretrained=True)
        torch.save(model.state_dict(), target_dir / f"{model_name}.pth")
        return True
    except Exception as e:
        logger.error(f"Failed to download {model_name}: {e}")
        return False


def model_exists(target_dir: Path, config: dict) -> bool:
    """Check if a model already exists at the target location."""
    if not target_dir.exists():
        return False

    # Check for model files based on type
    if config["type"] == "huggingface":
        # HuggingFace models have config.json or model files
        return (
            any(target_dir.glob("*.json"))
            or any(target_dir.glob("*.safetensors"))
            or any(target_dir.glob("*.bin"))
        )
    elif config["type"] == "ultralytics":
        # YOLO models are .pt files
        return any(target_dir.glob("*.pt"))
    elif config["type"] == "torchreid":
        # torchreid models are .pth files
        return any(target_dir.glob("*.pth"))
    return False


def download_all_models(models_dir: Path, force: bool = False):
    """Download all configured models.

    Args:
        models_dir: Directory to download models to
        force: If True, download even if model already exists
    """
    models_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for name, config in MODELS.items():
        target = models_dir / name

        # Skip if model already exists and not forcing re-download
        if not force and model_exists(target, config):
            logger.info(f"Skipping {name} - already exists at {target}")
            results[name] = True
            continue

        if config["type"] == "huggingface":
            results[name] = download_huggingface_model(config["repo"], target)
        elif config["type"] == "ultralytics":
            results[name] = download_ultralytics_model(config["repo"], target)
        elif config["type"] == "torchreid":
            results[name] = download_torchreid_model(config["repo"], target)

    # Print summary
    logger.info("\n" + "=" * 50)
    logger.info("Download Summary:")
    for name, success in results.items():
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"  [{status}] {name}")
    logger.info("=" * 50)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download AI models for enrichment service")
    parser.add_argument(
        "--force", action="store_true", help="Force re-download even if models exist"
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=Path(os.environ.get("MODELS_DIR", "./models")),
        help="Directory to download models to",
    )
    args = parser.parse_args()

    download_all_models(args.models_dir, force=args.force)
