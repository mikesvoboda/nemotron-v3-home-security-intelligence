#!/usr/bin/env python3
"""
Download and validate YOLO26 model weights.

This script downloads YOLO26 models from Ultralytics and validates they load correctly.
Models are saved to /export/ai_models/model-zoo/yolo26/

Usage:
    uv run python scripts/download_yolo26.py

Requirements:
    ultralytics>=8.4.0
"""

import shutil
import sys
from pathlib import Path

# Target directory for YOLO26 models
YOLO26_DIR = Path("/export/ai_models/model-zoo/yolo26")

# Models to download (detection variants only for Phase 1)
YOLO26_MODELS = [
    "yolo26n.pt",  # Nano - fastest, smallest
    "yolo26s.pt",  # Small - balance of speed/accuracy
    "yolo26m.pt",  # Medium - higher accuracy
]


def get_model_size(path: Path) -> str:
    """Get human-readable file size."""
    size_bytes = path.stat().st_size
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024**3):.2f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024**2):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} bytes"


def download_and_validate_models() -> dict:
    """Download YOLO26 models and validate they load correctly."""
    from ultralytics import YOLO

    # Create directory
    YOLO26_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Target directory: {YOLO26_DIR}")
    print()

    results = {}

    for model_name in YOLO26_MODELS:
        print(f"{'=' * 60}")
        print(f"Downloading {model_name}...")
        print(f"{'=' * 60}")

        target_path = YOLO26_DIR / model_name

        try:
            # Load model (triggers download if not present)
            model = YOLO(model_name)

            # Find where the model was downloaded
            # Ultralytics downloads to current directory or ~/.cache
            possible_locations = [
                Path(model_name),
                Path.home() / ".cache" / "ultralytics" / "models" / model_name,
                Path.cwd() / model_name,
            ]

            source_path = None
            for loc in possible_locations:
                if loc.exists():
                    source_path = loc
                    break

            # Copy to target directory if found elsewhere
            if source_path and source_path != target_path:
                if not target_path.exists():
                    shutil.copy(source_path, target_path)
                    print(f"Copied {source_path} to {target_path}")

            # Verify the model loads from target path
            if target_path.exists():
                model_from_path = YOLO(str(target_path))

                # Get model details
                file_size = get_model_size(target_path)

                # Count parameters directly from model
                model_obj = model_from_path.model
                if model_obj is not None and hasattr(model_obj, "parameters"):
                    total_params = sum(p.numel() for p in model_obj.parameters())
                    params_str = f"{total_params / 1e6:.2f}M"
                else:
                    params_str = "Unknown"

                # Get architecture scale
                arch_scale = "Unknown"
                if model_obj is not None and hasattr(model_obj, "yaml"):
                    yaml_dict = getattr(model_obj, "yaml", {})
                    if isinstance(yaml_dict, dict):
                        arch_scale = yaml_dict.get("scale", "Unknown")

                results[model_name] = {
                    "status": "SUCCESS",
                    "path": str(target_path),
                    "file_size": file_size,
                    "parameters": params_str,
                    "architecture": arch_scale,
                    "task": model_from_path.task,
                }

                print(f"[OK] {model_name} validated successfully")
                print(f"     Path: {target_path}")
                print(f"     Size: {file_size}")
                print(f"     Parameters: {params_str}")
                print(f"     Architecture: {arch_scale}")
                print(f"     Task: {model_from_path.task}")
            else:
                results[model_name] = {
                    "status": "ERROR",
                    "error": "Model file not found after download",
                }
                print(f"[ERROR] {model_name} - file not found after download")

        except Exception as e:
            results[model_name] = {
                "status": "ERROR",
                "error": str(e),
            }
            print(f"[ERROR] {model_name} - {e}")

        print()

    return results


def estimate_vram_requirements() -> dict:
    """
    Estimate VRAM requirements for YOLO26 models.

    These are estimates based on:
    - Model parameters
    - FP16 inference (2 bytes per parameter)
    - Additional overhead for activations and batch processing
    """
    # Estimates based on documentation and parameter counts
    # YOLO26 is optimized for edge devices, so VRAM requirements are relatively low
    vram_estimates = {
        "yolo26n.pt": {
            "parameters_m": 2.4,
            "vram_fp16_mb": 150,  # ~2.4M params * 2 bytes + activations + overhead
            "vram_fp32_mb": 250,
            "recommended_batch_1": 200,  # With some headroom
        },
        "yolo26s.pt": {
            "parameters_m": 9.5,
            "vram_fp16_mb": 350,  # ~9.5M params * 2 bytes + activations + overhead
            "vram_fp32_mb": 550,
            "recommended_batch_1": 500,
        },
        "yolo26m.pt": {
            "parameters_m": 20.4,
            "vram_fp16_mb": 650,  # ~20.4M params * 2 bytes + activations + overhead
            "vram_fp32_mb": 1000,
            "recommended_batch_1": 800,
        },
    }
    return vram_estimates


def generate_validation_report(results: dict, vram_estimates: dict) -> str:
    """Generate a validation report."""
    report_lines = [
        "# YOLO26 Model Validation Report",
        "",
        f"Generated: {__import__('datetime').datetime.now().isoformat()}",
        f"Ultralytics version: {__import__('ultralytics').__version__}",
        f"Model directory: {YOLO26_DIR}",
        "",
        "## Model Summary",
        "",
        "| Model | Status | File Size | Parameters | Architecture | Task |",
        "|-------|--------|-----------|------------|--------------|------|",
    ]

    for model_name, result in results.items():
        if result["status"] == "SUCCESS":
            report_lines.append(
                f"| {model_name} | OK | {result['file_size']} | "
                f"{result['parameters']} | {result['architecture']} | "
                f"{result['task']} |"
            )
        else:
            report_lines.append(f"| {model_name} | ERROR | - | - | - | - |")

    report_lines.extend(
        [
            "",
            "## VRAM Requirements (Estimated)",
            "",
            "These estimates are for single-image inference (batch size 1):",
            "",
            "| Model | Parameters | FP16 VRAM | FP32 VRAM | Recommended (w/ overhead) |",
            "|-------|------------|-----------|-----------|---------------------------|",
        ]
    )

    for model_name, vram in vram_estimates.items():
        report_lines.append(
            f"| {model_name} | {vram['parameters_m']}M | "
            f"{vram['vram_fp16_mb']} MB | {vram['vram_fp32_mb']} MB | "
            f"{vram['recommended_batch_1']} MB |"
        )

    report_lines.extend(
        [
            "",
            "## Notes",
            "",
            "- YOLO26 is optimized for edge devices and has lower VRAM requirements than "
            "previous versions",
            "- End-to-end NMS-free inference reduces post-processing overhead",
            "- Up to 43% faster CPU inference compared to YOLO11",
            "- All models support: detection, segmentation, pose estimation, OBB, and "
            "classification",
            "",
            "## Model Paths",
            "",
        ]
    )

    for model_name, result in results.items():
        if result["status"] == "SUCCESS":
            report_lines.append(f"- `{model_name}`: `{result['path']}`")

    report_lines.extend(
        [
            "",
            "## Usage Example",
            "",
            "```python",
            "from ultralytics import YOLO",
            "",
            "# Load a YOLO26 model",
            "model = YOLO('/export/ai_models/model-zoo/yolo26/yolo26n.pt')",
            "",
            "# Run inference",
            "results = model('path/to/image.jpg')",
            "",
            "# Process results",
            "for result in results:",
            "    boxes = result.boxes  # Detection boxes",
            "    for box in boxes:",
            "        cls = int(box.cls[0])",
            "        conf = float(box.conf[0])",
            "        xyxy = box.xyxy[0].tolist()",
            "        print(f'Class: {cls}, Confidence: {conf:.2f}, Box: {xyxy}')",
            "```",
            "",
        ]
    )

    return "\n".join(report_lines)


def main() -> None:
    """Main entry point."""
    print("=" * 60)
    print("YOLO26 Model Download and Validation")
    print("=" * 60)
    print()

    # Check ultralytics version
    import ultralytics

    print(f"Ultralytics version: {ultralytics.__version__}")
    if ultralytics.__version__ < "8.4.0":
        print("ERROR: ultralytics>=8.4.0 required for YOLO26 support")
        sys.exit(1)
    print()

    # Download and validate models
    results = download_and_validate_models()

    # Get VRAM estimates
    vram_estimates = estimate_vram_requirements()

    # Generate report
    report = generate_validation_report(results, vram_estimates)

    # Save report
    report_path = YOLO26_DIR / "VALIDATION_REPORT.md"
    report_path.write_text(report)
    print(f"Validation report saved to: {report_path}")

    # Print summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    success_count = sum(1 for r in results.values() if r["status"] == "SUCCESS")
    total_count = len(results)

    print(f"Models downloaded: {success_count}/{total_count}")
    print(f"Model directory: {YOLO26_DIR}")
    print(f"Validation report: {report_path}")

    if success_count < total_count:
        print()
        print("ERRORS:")
        for model_name, result in results.items():
            if result["status"] == "ERROR":
                print(f"  - {model_name}: {result.get('error', 'Unknown error')}")
        sys.exit(1)

    print()
    print("All models downloaded and validated successfully!")


if __name__ == "__main__":
    main()
