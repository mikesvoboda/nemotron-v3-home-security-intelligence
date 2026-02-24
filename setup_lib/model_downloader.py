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
    download_method: str = ""  # empty → snapshot_download; see models.yml for special values
    local_path: str = ""  # path relative to AI_MODELS_PATH (from models.yml)


def build_model_specs() -> list[ModelSpec]:
    """Build the model download list from models.yml — single source of truth.

    Replaces the hardcoded REQUIRED_MODELS / PHASE*_MODELS lists.
    Models with download_method='skip' are excluded (no download needed).
    """
    try:
        from setup_lib.models_config import get_downloadable_models
    except ImportError:
        # Fallback when called outside the package (e.g. direct script execution)
        from pathlib import Path as _Path
        import yaml as _yaml
        _yml = _Path(__file__).parent.parent / "models.yml"
        _all = _yaml.safe_load(_yml.read_text())["models"]
        _downloadable = [
            m for m in _all
            if m.get("download_method") != "skip"
            and (m.get("hf_repo") or m.get("download_method"))
        ]
        return [
            ModelSpec(
                name=m["name"],
                hf_repo=m.get("hf_repo") or "",
                phase=m.get("download_phase", 3),
                size_mb=int(m.get("size_mb", 0)),
                description=m.get("description", ""),
                required=bool(m.get("required", False)),
                download_method=m.get("download_method") or "",
                local_path=m.get("local_path") or "",
            )
            for m in _downloadable
        ]

    entries = get_downloadable_models()
    return [
        ModelSpec(
            name=m["name"],
            hf_repo=m.get("hf_repo") or "",
            phase=m.get("download_phase", 3),
            size_mb=int(m.get("size_mb", 0)),
            description=m.get("description", ""),
            required=bool(m.get("required", False)),
            download_method=m.get("download_method") or "",
            local_path=m.get("local_path") or "",
        )
        for m in entries
    ]


# ---------------------------------------------------------------------------
# Legacy hardcoded lists — DEPRECATED.  Kept only so external callers that
# still reference them continue to work.  New code should call build_model_specs().
# ---------------------------------------------------------------------------

# Core models required for the system to function
REQUIRED_MODELS: list[ModelSpec] = [
    # Nemotron LLM - risk reasoning (CRITICAL)
    ModelSpec(
        name="nemotron-3-nano-30b-a3b-q4km",
        hf_repo="unsloth/Nemotron-3-Nano-30B-A3B-GGUF",
        phase=0,
        size_mb=15073,  # ~14.7GB
        description="Nemotron-3-Nano-30B LLM for risk reasoning (Q4_K_M quantization)",
        required=True,
    ),
    # YOLO26 - primary object detection
    ModelSpec(
        name="yolo26",
        hf_repo="",  # Downloaded via ultralytics GitHub releases
        phase=0,
        size_mb=67,  # n/s/m combined
        description="YOLO26 object detection (n/s/m variants)",
        required=True,
    ),
    # Florence-2-Base - vision-language model (used by ai-gateway)
    ModelSpec(
        name="florence-2-base",
        hf_repo="microsoft/Florence-2-base",
        phase=0,
        size_mb=1024,  # ~1GB (base variant saves ~1.2GB VRAM vs large)
        description="Florence-2-base vision-language model (ai-gateway)",
        required=True,
    ),
    # SigLIP 2 Base - embeddings for re-identification (replaces CLIP ViT-L)
    ModelSpec(
        name="siglip2-base-patch16-224",
        hf_repo="onnx-community/siglip2-base-patch16-224-ONNX",  # pragma: allowlist secret
        phase=0,
        size_mb=400,  # ~400MB (replaces CLIP ViT-L, saves ~1035MB VRAM)
        description="SigLIP 2 Base embeddings for entity re-identification (ai-gateway)",
        required=True,
    ),
]

# Phase 1 - Core enrichment models (used by ai-gateway)
PHASE1_MODELS: list[ModelSpec] = [
    # Fashion-CLIP - clothing classification (ai-gateway: fashion_clip)
    ModelSpec(
        name="fashion-clip",
        hf_repo="patrickjohncyh/fashion-clip",
        phase=1,
        size_mb=3584,  # ~3.5GB
        description="Zero-shot clothing attribute detection (ai-gateway)",
        required=False,
    ),
    # Vehicle classification (ai-gateway: vehicle)
    ModelSpec(
        name="vehicle-segment-classification",
        hf_repo="AventIQ-AI/ResNet-50-Vehicle-Segment-classification",
        phase=1,
        size_mb=358,  # ~350MB
        description="Vehicle type classification - 11 classes (ai-gateway)",
        required=False,
    ),
    # Pet classifier (ai-gateway: pet)
    ModelSpec(
        name="pet-classifier",
        hf_repo="microsoft/resnet-18",
        phase=1,
        size_mb=46,  # ~45MB
        description="Dog/cat classification for false positive reduction (ai-gateway)",
        required=False,
    ),
    # Depth estimation (ai-gateway: depth)
    ModelSpec(
        name="depth-anything-v2-tiny",
        hf_repo="depth-anything/Depth-Anything-V2-Small-hf",
        phase=1,
        size_mb=98,  # ~98MB (small variant, smallest available)
        description="Monocular depth estimation (ai-gateway)",
        required=False,
    ),
    # Person re-identification (ai-gateway: reid)
    ModelSpec(
        name="osnet-ain-x1-0",
        hf_repo="kaiyangzhou/osnet",
        phase=1,
        size_mb=10,  # ~10MB per model file
        description="Person re-identification embeddings - OSNet-AIN x1.0 (ai-gateway)",
        required=False,
    ),
    # Pose estimation (ai-gateway: pose)
    ModelSpec(
        name="yolov8n-pose",
        hf_repo="ultralytics/yolov8n-pose",  # ultralytics GitHub releases
        phase=1,
        size_mb=6,
        description="Human pose estimation - 17 COCO keypoints (ai-gateway)",
        required=False,
    ),
    # Threat detection (ai-gateway: threat)
    ModelSpec(
        name="threat-detection-yolov8n",
        hf_repo="Subh775/Threat-Detection-YOLOv8n",
        phase=1,
        size_mb=25,
        description="Threat/weapon detection - CRITICAL security model (ai-gateway)",
        required=False,
    ),
]

# Phase 2 - Demographics and action recognition
PHASE2_MODELS: list[ModelSpec] = [
    # Age estimation (ai-gateway: demographics_age)
    ModelSpec(
        name="vit-age-classifier",
        hf_repo="nateraw/vit-age-classifier",
        phase=2,
        size_mb=358,  # ~350MB
        description="Age estimation from face crops (ai-gateway)",
        required=False,
    ),
    # Gender classification (ai-gateway: demographics_gender)
    ModelSpec(
        name="vit-gender-classifier",
        hf_repo="rizvandwiki/gender-classification",
        phase=2,
        size_mb=358,  # ~350MB
        description="Gender classification from face crops (ai-gateway)",
        required=False,
    ),
    # ST-GCN++ action recognition (ai-gateway: stgcn_action)
    ModelSpec(
        name="stgcn-plus-plus",
        hf_repo="",  # Downloaded via direct URL from OpenMMLab
        phase=2,
        size_mb=20,
        description="ST-GCN++ skeleton-based action recognition (ai-gateway)",
        required=False,
    ),
    # X-CLIP action recognition (ai-gateway: xclip_action)
    ModelSpec(
        name="xclip-base-patch32",
        hf_repo="microsoft/xclip-base-patch32",
        phase=2,
        size_mb=600,
        description="X-CLIP zero-shot video action recognition (ai-gateway)",
        required=False,
    ),
]

# Phase 3 - Optional specialized models (not used by ai-gateway default)
PHASE3_MODELS: list[ModelSpec] = [
    # Weather classification (backend enrichment pipeline)
    ModelSpec(
        name="weather-classification",
        hf_repo="prithivMLmods/Weather-Image-Classification",
        phase=3,
        size_mb=200,  # ~200MB (SigLIP-based)
        description="Weather condition classification for security camera context (backend)",
        required=False,
    ),
    # Violence detection (backend enrichment pipeline)
    ModelSpec(
        name="violence-detection",
        hf_repo="jaranohaal/vit-base-violence-detection",
        phase=3,
        size_mb=350,  # ~350MB (ViT-base)
        description="ViT-base binary violence/non-violence classifier for backend pipeline",
        required=False,
    ),
    # Marqo FashionSigLIP — clothing zero-shot classifier used by ai-gateway enrichment
    # Stored in the HuggingFace hub cache (not model-zoo) because open_clip loads it
    # via hf-hub: format which requires the standard HF cache directory structure.
    ModelSpec(
        name="marqo-fashionSigLIP",
        hf_repo="Marqo/marqo-fashionSigLIP",
        phase=3,
        size_mb=4400,  # ~4.4GB (full vision + text encoder)
        description="FashionSigLIP clothing classifier for ai-gateway (stored in HF hub cache)",
        required=False,
    ),
    # Face detection
    ModelSpec(
        name="yolo11-face-detection",
        hf_repo="AdamCodd/YOLOv11n-face-detection",
        phase=3,
        size_mb=11,
        description="YOLO11 face detection on person crops",
        required=False,
    ),
    # License plate detection
    ModelSpec(
        name="yolo11-license-plate",
        hf_repo="morsetechlab/yolov11-license-plate-detection",
        phase=3,
        size_mb=650,
        description="YOLO11 license plate detection (multiple variants)",
        required=False,
    ),
    # Smoke/fire detection
    ModelSpec(
        name="smoke-fire-yolov8n",
        hf_repo="SHOU-ISD/fire-and-smoke",
        phase=3,
        size_mb=25,
        description="Smoke/fire detection (CRITICAL safety model)",
        required=False,
    ),
    # YOLO-World open-vocabulary detection
    ModelSpec(
        name="yolo-world-s",
        hf_repo="",  # ultralytics YOLOWorld
        phase=3,
        size_mb=1500,
        description="Open-vocabulary detection (packages, weapons, tools)",
        required=False,
    ),
    # Low-light enhancement
    ModelSpec(
        name="zero-dce-plus-plus",
        hf_repo="keras-io/low-light-image-enhancement",
        phase=3,
        size_mb=5,
        description="Zero-DCE++ low-light enhancement preprocessing",
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
    # Special handling for Nemotron (stored in different location)
    if model_name == "nemotron-3-nano-30b-a3b-q4km":
        nemotron_file = model_path / "nemotron" / model_name / "Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"
        return nemotron_file.exists()

    # Special handling for OSNet (specific .pth file required)
    if model_name == "osnet-ain-x1-0":
        osnet_file = model_path / "model-zoo" / model_name / "osnet_ain_x1_0_msmt17.pth"
        return osnet_file.exists()

    # Special handling for YOLO-World-S (specific .pt file)
    if model_name == "yolo-world-s":
        yolo_world_file = model_path / "model-zoo" / model_name / "yolov8s-worldv2.pt"
        return yolo_world_file.exists()

    # Special handling for ST-GCN++ (specific .pth file)
    if model_name == "stgcn-plus-plus":
        stgcn_file = model_path / "model-zoo" / model_name / "stgcnpp_ntu60_xsub_hrnet_j.pth"
        return stgcn_file.exists()

    # Special handling for YOLOv8n-pose (specific .pt file)
    if model_name == "yolov8n-pose":
        pose_file = model_path / "model-zoo" / model_name / "yolov8n-pose.pt"
        return pose_file.exists()

    # fashion-clip uses Marqo FashionSigLIP stored in HF hub cache (open_clip hf-hub format)
    if model_name in ("fashion-clip", "marqo-fashionSigLIP"):
        hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
        marqo_snapshots = hf_cache / "models--Marqo--marqo-fashionSigLIP" / "snapshots"
        return marqo_snapshots.exists() and any(marqo_snapshots.iterdir())

    model_dir = model_path / "model-zoo" / model_name
    if not model_dir.exists():
        return False

    # Check for common model file extensions
    model_extensions = (".pt", ".pth", ".safetensors", ".bin", ".onnx", ".engine", ".gguf", ".pb", ".h5", ".keras")
    return any(list(model_dir.rglob(f"*{ext}")) for ext in model_extensions)


def download_nemotron_gguf(model_path: Path) -> bool:
    """Download Nemotron LLM GGUF file.

    Args:
        model_path: Base path for AI models.

    Returns:
        True if download successful, False otherwise.
    """
    nemotron_dir = model_path / "nemotron" / "nemotron-3-nano-30b-a3b-q4km"
    nemotron_dir.mkdir(parents=True, exist_ok=True)

    gguf_file = nemotron_dir / "Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"

    if gguf_file.exists():
        print(f"    Already exists: {gguf_file.name}")
        return True

    # Check for existing file in common locations
    search_paths = [
        Path.home()
        / ".cache/huggingface/hub"
        / "models--unsloth--Nemotron-3-Nano-30B-A3B-GGUF/snapshots",
    ]

    for search_path in search_paths:
        if search_path.exists():
            for gguf in search_path.rglob("Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"):
                print(f"    Found existing: {gguf}")
                print(f"    Creating symlink to: {gguf_file}")
                try:
                    gguf_file.symlink_to(gguf)
                    return True
                except OSError as e:
                    print(f"    ! Failed to create symlink: {e}")
                    break

    # Download using huggingface_hub
    if not HF_HUB_AVAILABLE:
        print("    ! huggingface_hub not installed, cannot download")
        print("    Install with: pip install huggingface_hub")
        return False

    print("    Downloading Nemotron GGUF (~14.7GB, may take 10-30 minutes)...")
    try:
        from huggingface_hub import hf_hub_download

        downloaded = hf_hub_download(
            repo_id="unsloth/Nemotron-3-Nano-30B-A3B-GGUF",
            filename="Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf",
            local_dir=nemotron_dir,
            local_dir_use_symlinks=False,
        )
        print(f"    Downloaded to: {downloaded}")
        return True
    except Exception as e:
        print(f"    ! Download failed: {e}")
        return False


def download_yolo26_models(model_path: Path) -> bool:
    """Download YOLO26 models from ultralytics GitHub releases.

    Args:
        model_path: Base path for AI models.

    Returns:
        True if at least one model downloaded successfully.
    """
    yolo26_dir = model_path / "model-zoo" / "yolo26"
    yolo26_dir.mkdir(parents=True, exist_ok=True)

    release_url = "https://github.com/ultralytics/assets/releases/download/v8.4.0"

    models = [
        ("yolo26n.pt", 5.3, "Nano - fastest"),
        ("yolo26s.pt", 19.5, "Small - balanced"),
        ("yolo26m.pt", 42.2, "Medium - highest accuracy"),
    ]

    success_count = 0
    for filename, size_mb, desc in models:
        target = yolo26_dir / filename
        if target.exists():
            print(f"    Already exists: {filename}")
            success_count += 1
            continue

        url = f"{release_url}/{filename}"
        print(f"    Downloading {filename} (~{size_mb}MB - {desc})...")

        try:
            import urllib.request

            urllib.request.urlretrieve(url, target)  # noqa: S310
            print(f"    Downloaded: {filename}")
            success_count += 1
        except Exception as e:
            print(f"    ! Failed to download {filename}: {e}")

    return success_count > 0


def download_brisque_weights(model_path: Path) -> bool:
    """Download piq BRISQUE SVR weights to the persistent torch hub cache.

    piq.brisque() fetches these weights via torch.hub.load_state_dict_from_url
    on first use.  By pre-downloading them into the persistent TORCH_HOME path
    (model-zoo/.torch_cache/hub/checkpoints/) they survive container restarts
    and work with TORCH_HOME=/models/model-zoo/.torch_cache in the container.

    Args:
        model_path: Base path for AI models (AI_MODELS_PATH).

    Returns:
        True if the weights are present (already existed or freshly downloaded).
    """
    import urllib.request

    cache_dir = model_path / "model-zoo" / ".torch_cache" / "hub" / "checkpoints"
    cache_dir.mkdir(parents=True, exist_ok=True)

    target = cache_dir / "brisque_svm_weights.pt"
    if target.exists():
        print("    Already exists: brisque_svm_weights.pt")
        return True

    url = (
        "https://github.com/photosynthesis-team/piq/"
        "releases/download/v0.4.0/brisque_svm_weights.pt"
    )
    print("    Downloading brisque_svm_weights.pt (~1MB)...")
    try:
        urllib.request.urlretrieve(url, target)  # noqa: S310
        print("    Downloaded: brisque_svm_weights.pt")
        return True
    except Exception as e:
        print(f"    ! Failed to download brisque_svm_weights.pt: {e}")
        return False


def download_yolov8n_pose(model_path: Path) -> bool:
    """Download YOLOv8n-pose from ultralytics GitHub releases.

    Args:
        model_path: Base path for AI models.

    Returns:
        True if download successful.
    """
    pose_dir = model_path / "model-zoo" / "yolov8n-pose"
    pose_dir.mkdir(parents=True, exist_ok=True)

    target = pose_dir / "yolov8n-pose.pt"

    if target.exists():
        print("    Already exists: yolov8n-pose.pt")
        return True

    # YOLOv8 pose models from ultralytics releases
    release_url = "https://github.com/ultralytics/assets/releases/download/v8.2.0"
    url = f"{release_url}/yolov8n-pose.pt"

    print("    Downloading yolov8n-pose.pt (~6MB)...")

    try:
        import urllib.request

        urllib.request.urlretrieve(url, target)  # noqa: S310
        print("    Downloaded: yolov8n-pose.pt")
        return True
    except Exception as e:
        print(f"    ! Failed to download: {e}")
        return False


def download_osnet_reid(model_path: Path) -> bool:
    """Download OSNet-AIN x1.0 Re-ID model from HuggingFace.

    Args:
        model_path: Base path for AI models.

    Returns:
        True if download successful.
    """
    if not HF_HUB_AVAILABLE:
        print("    ! huggingface_hub not installed")
        return False

    osnet_dir = model_path / "model-zoo" / "osnet-ain-x1-0"
    osnet_dir.mkdir(parents=True, exist_ok=True)

    target = osnet_dir / "osnet_ain_x1_0_msmt17.pth"

    if target.exists():
        print("    Already exists: osnet_ain_x1_0_msmt17.pth")
        return True

    print("    Downloading from kaiyangzhou/osnet (~10MB)...")

    try:
        from huggingface_hub import hf_hub_download

        # The full filename in the repo
        full_filename = "osnet_ain_x1_0_msmt17_256x128_amsgrad_ep50_lr0.0015_coslr_b64_fb10_softmax_labsmth_flip_jitter.pth"

        # Download the specific MSMT17-trained weights
        downloaded = hf_hub_download(
            repo_id="kaiyangzhou/osnet",
            filename=full_filename,
            local_dir=osnet_dir,
            local_dir_use_symlinks=False,
        )

        # Create symlink with shorter name for easier referencing
        downloaded_path = Path(downloaded)
        if downloaded_path.exists() and not target.exists():
            target.symlink_to(downloaded_path.name)  # Relative symlink
            print("    Downloaded: osnet_ain_x1_0_msmt17.pth")

        return True
    except Exception as e:
        print(f"    ! Failed to download: {e}")
        return False


def download_stgcnpp(model_path: Path) -> bool:
    """Download ST-GCN++ checkpoint from OpenMMLab.

    Args:
        model_path: Base path for AI models.

    Returns:
        True if download successful.
    """
    stgcn_dir = model_path / "model-zoo" / "stgcn-plus-plus"
    stgcn_dir.mkdir(parents=True, exist_ok=True)

    # Joint checkpoint for NTU60 XSub with HRNet 2D keypoints
    target = stgcn_dir / "stgcnpp_ntu60_xsub_hrnet_j.pth"

    if target.exists():
        print("    Already exists: stgcnpp_ntu60_xsub_hrnet_j.pth")
        return True

    url = "http://download.openmmlab.com/mmaction/pyskl/ckpt/stgcnpp/stgcnpp_ntu60_xsub_hrnet/j.pth"
    print("    Downloading ST-GCN++ from OpenMMLab (~20MB)...")

    try:
        import urllib.request

        urllib.request.urlretrieve(url, target)  # noqa: S310
        print("    Downloaded: stgcnpp_ntu60_xsub_hrnet_j.pth")
        return True
    except Exception as e:
        print(f"    ! Failed to download: {e}")
        return False


def download_yolo_world(model_path: Path) -> bool:
    """Download YOLO-World-S from ultralytics GitHub releases.

    Args:
        model_path: Base path for AI models.

    Returns:
        True if download successful.
    """
    yolo_world_dir = model_path / "model-zoo" / "yolo-world-s"
    yolo_world_dir.mkdir(parents=True, exist_ok=True)

    target = yolo_world_dir / "yolov8s-worldv2.pt"

    if target.exists():
        print("    Already exists: yolov8s-worldv2.pt")
        return True

    release_url = "https://github.com/ultralytics/assets/releases/download/v8.2.0"
    url = f"{release_url}/yolov8s-worldv2.pt"

    print("    Downloading yolov8s-worldv2.pt (~46MB)...")

    try:
        import urllib.request

        urllib.request.urlretrieve(url, target)  # noqa: S310
        print("    Downloaded: yolov8s-worldv2.pt")
        return True
    except Exception as e:
        print(f"    ! Failed to download: {e}")
        return False


def download_marqo_fashionsiglip() -> bool:
    """Download Marqo FashionSigLIP into the standard HuggingFace hub cache.

    open_clip loads this model via ``hf-hub:Marqo/marqo-fashionSigLIP`` which
    requires the model to exist in the HF hub cache directory structure at
    ``~/.cache/huggingface/hub/``.  Unlike other models, it is NOT stored under
    model-zoo because open_clip does not support arbitrary local directory paths
    for this model (meta-tensor loading issue).

    Args:
        None — always downloads to ``~/.cache/huggingface/hub/``.

    Returns:
        True if download successful or model already cached.
    """
    if not HF_HUB_AVAILABLE:
        print("    ! huggingface_hub not installed, cannot download")
        return False

    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    snapshots_dir = hf_cache / "models--Marqo--marqo-fashionSigLIP" / "snapshots"
    if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
        print(f"    Already cached: {snapshots_dir}")
        return True

    print("    Downloading Marqo/marqo-fashionSigLIP to HF hub cache (~4.4GB)...")
    try:
        path = snapshot_download(repo_id="Marqo/marqo-fashionSigLIP")
        print(f"    Cached at: {path}")
        return True
    except Exception as e:
        print(f"    ! Download failed: {e}")
        return False


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
        print(
            f"    ! {model.name} uses alternative download method (will auto-download on first run)"
        )
        return True  # Not an error - just skipped

    # Special handling for Nemotron (different directory structure)
    if model.name == "nemotron-3-nano-30b-a3b-q4km":
        model_dir = model_path / "nemotron" / model.name
    else:
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


def _bootstrap_venv_and_import_hf() -> bool:
    """Create a virtualenv and install huggingface_hub if needed.

    On Ubuntu 24.04+ (PEP 668), pip install into the system Python is blocked.
    This creates a .venv in the project root, installs huggingface_hub there,
    and adds it to sys.path so the current process can import it.

    Returns:
        True if huggingface_hub is now importable, False otherwise.
    """
    global HF_HUB_AVAILABLE  # noqa: PLW0603

    print("! huggingface_hub not installed")

    # Find project root (directory containing setup.py)
    project_root = Path(__file__).resolve().parent.parent
    venv_dir = project_root / ".venv"
    venv_python = venv_dir / "bin" / "python"

    # Step 1: Create venv if it doesn't exist
    if not venv_python.exists():
        print("  Creating virtual environment (.venv/)...")
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True,
                capture_output=True,
            )
            print("  + Virtual environment created")
        except subprocess.CalledProcessError as e:
            print(f"  ! Failed to create venv: {e}")
            return False

    # Step 2: Install huggingface_hub into the venv
    print("  Installing huggingface_hub into .venv/...")
    venv_pip = venv_dir / "bin" / "pip"
    try:
        subprocess.run(
            [str(venv_pip), "install", "huggingface_hub"],
            check=True,
            capture_output=True,
        )
        print("  + huggingface_hub installed")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
        print(f"  ! Failed to install huggingface_hub: {stderr[:200]}")
        return False

    # Step 3: Add venv site-packages to sys.path so we can import
    import glob as glob_mod

    site_pattern = str(venv_dir / "lib" / "python*" / "site-packages")
    site_dirs = glob_mod.glob(site_pattern)
    for site_dir in site_dirs:
        if site_dir not in sys.path:
            sys.path.insert(0, site_dir)

    # Step 4: Try importing again
    try:
        from huggingface_hub import snapshot_download  # noqa: F811

        HF_HUB_AVAILABLE = True
        # Update module-level reference so download_hf_model can use it
        globals()["snapshot_download"] = snapshot_download
        return True
    except ImportError as e:
        print(f"  ! Failed to import huggingface_hub after install: {e}")
        return False


def prompt_and_download_models(config: dict) -> None:
    """Prompt user and download AI models.

    Args:
        config: Configuration dictionary with 'ai_models_path', optional 'skip_download',
                and optional 'auto_download' to select option 2 automatically.
    """
    skip_download = config.get("skip_download", False)
    auto_download = config.get("auto_download", False)

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
        print("  Creating directory...")
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
    all_models = build_model_specs()
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
    if skip_download:
        print("Skipping model downloads (can be downloaded later).")
        print("  To download later: ./ai/download_models.sh")
        print()
        return

    # Download all models
    models_to_download: list[ModelSpec] = list(build_model_specs())

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
        hf_available = _bootstrap_venv_and_import_hf()
        if not hf_available:
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

        # Dispatch based on download_method from models.yml (falls back to name for legacy compat)
        method = model.download_method or model.name
        if method == "nemotron_gguf" or model.name == "nemotron-3-nano-30b-a3b-q4km":
            if download_nemotron_gguf(ai_models_path):
                success_count += 1
            else:
                fail_count += 1
        elif method == "yolo26" or model.name == "yolo26":
            if download_yolo26_models(ai_models_path):
                success_count += 1
            else:
                fail_count += 1
        elif model.name == "yolov8n-pose":
            if download_yolov8n_pose(ai_models_path):
                success_count += 1
            else:
                fail_count += 1
        elif method == "osnet" or model.name == "osnet-ain-x1-0":
            if download_osnet_reid(ai_models_path):
                success_count += 1
            else:
                fail_count += 1
        elif method == "stgcn" or model.name == "stgcn-plus-plus":
            if download_stgcnpp(ai_models_path):
                success_count += 1
            else:
                fail_count += 1
        elif method == "yolo_world" or model.name == "yolo-world-s":
            if download_yolo_world(ai_models_path):
                success_count += 1
            else:
                fail_count += 1
        elif method == "hf_cache" or model.name in ("fashion-clip", "marqo-fashionSigLIP"):
            if download_marqo_fashionsiglip():
                success_count += 1
            else:
                fail_count += 1
        elif download_hf_model(model, ai_models_path):
            success_count += 1
        else:
            fail_count += 1

    # Download auxiliary weights that aren't HuggingFace models.
    # These are small files fetched from other hosting (e.g. GitHub releases).
    print("  [aux] brisque-quality (SVR weights)")
    download_brisque_weights(ai_models_path)

    # Summary
    print()
    print("=" * 60)
    print(f"Download Summary: {success_count} succeeded, {fail_count} failed")
    print("=" * 60)

    if success_count > 0:
        print()
        print("+ Models downloaded successfully!")
        print()
        print("Next steps:")
        print("  1. Ensure docker-compose.prod.yml has correct AI_MODELS_PATH")
        print("  2. Start services: podman compose -f docker-compose.prod.yml up -d")
        print("  3. Wait for AI models to load (~2-3 minutes)")
        print("  4. Check health: curl http://localhost:8000/api/system/health/ready")

    if fail_count > 0:
        print()
        print("! Some models failed to download.")
        print("  Check your internet connection and try again.")
        print()
        print("  Models are also auto-downloaded on first container start.")
