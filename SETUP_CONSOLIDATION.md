# Setup Consolidation Summary

## Changes Made

### 1. Python 3.10 Compatibility Fix
**File:** `setup_lib/ssl_certs.py`
- Added compatibility shim for `datetime.UTC` (only available in Python 3.11+)
- Now uses `timezone.utc` for Python 3.10

### 2. Automated Installation (No Prompts)
**Modified Files:** `setup.py`, `setup_lib/podman_install.py`, `setup_lib/rootful_services.py`, `setup_lib/storage_config.py`, `setup_lib/ssl_certs.py`, `setup_lib/model_downloader.py`, `setup_lib/image_pull.py`, `setup_lib/linux_optimizer.py`

All components now support auto-installation:
- **Podman**: Auto-installs without prompting
- **DCGM Exporter**: Auto-installs GPU metrics service
- **Storage directories**: Auto-creates `/export/foscam` and `/export/ai_models`
- **SSL certificates**: Auto-generates self-signed certs
- **Firewall rules**: Auto-configures (if firewall detected)
- **Linux optimizations**: Skipped by default (can be run separately)
- **Container images**: Skipped by default (pulled during `docker compose up`)

### 3. Consolidated Model Downloads

**File:** `setup_lib/model_downloader.py`

Migrated all model download logic from `ai/download_models.sh` into Python:

#### Models Now Downloaded by setup.py:

**REQUIRED (Phase 0) - ai-gateway + ai-llm:**
- ✅ Nemotron-3-Nano-30B (Q4_K_M GGUF) - ~14.7GB
- ✅ YOLO26 (n/s/m variants) - ~67MB
- ✅ Florence-2-Large - ~3GB
- ✅ CLIP ViT-L - ~1.7GB

**PHASE 1 - Core enrichment (ai-gateway):**
- Fashion-CLIP (clothing) - ~3.5GB
- Vehicle classifier - ~350MB
- Pet classifier - ~45MB
- Depth-Anything-V2-Tiny - ~25MB
- OSNet-AIN x1.0 Re-ID - ~10MB ✅ **Now downloaded by setup.py**
- YOLOv8n-Pose - ~6MB ✅ **Now downloaded by setup.py**
- Threat detection - ~25MB

**PHASE 2 - Demographics:**
- ViT Age classifier - ~350MB
- ViT Gender classifier - ~350MB
- ST-GCN++ action recognition - ~20MB

**PHASE 3 - Optional:**
- Face detection, license plates, smoke/fire, etc.

## Model Alignment with docker-compose.prod.yml

### ai-gateway expects these 13 models (ALL NOW COVERED):

| Gateway Model | setup.py Model | Status |
|---|---|---|
| yolo26 | ✅ yolo26 (REQUIRED) | Downloaded |
| clip | ✅ clip-vit-l (REQUIRED) | Downloaded |
| florence2 | ✅ florence-2-large (REQUIRED) | Downloaded |
| vehicle | ✅ vehicle-segment-classification (PHASE1) | Downloaded |
| fashion_clip | ✅ fashion-clip (PHASE1) | Downloaded |
| demographics_age | ✅ vit-age-classifier (PHASE2) | Downloaded |
| demographics_gender | ✅ vit-gender-classifier (PHASE2) | Downloaded |
| pet | ✅ pet-classifier (PHASE1) | Downloaded |
| depth | ✅ depth-anything-v2-tiny (PHASE1) | Downloaded |
| reid | ✅ osnet-ain-x1-0 (PHASE1) | ✅ Downloaded |
| pose | ✅ yolov8n-pose (PHASE1) | ✅ Downloaded |
| threat | ✅ threat-detection-yolov8n (PHASE1) | Downloaded |
| xclip_action | ✅ stgcn-plus-plus (PHASE2) | Downloaded |

### ai-llm expects:

| Model | setup.py | Status |
|---|---|---|
| Nemotron GGUF | ✅ nemotron-3-nano-30b-a3b-q4km (REQUIRED) | Downloaded |

## Download Options

When running `python3 setup.py`, users will be prompted:

```
Download options:
  1. Download required models only (~20GB)
     - Nemotron LLM, YOLO26, Florence-2, CLIP
  2. Download required + Phase 1 (~25GB)
     - + Fashion-CLIP, Vehicle, Pet, Depth, Pose, Threat models
  3. Download all models (~26GB)
     - + Demographics (age/gender), Action recognition
  4. Skip (download later manually)
```

**Recommendation for single-GPU setup:** Choose option 2 or 3 for full functionality.

## Benefits of Consolidation

1. **Single entry point**: `python3 setup.py` handles everything
2. **Better UX**: Interactive prompts with clear choices
3. **Cross-platform**: Python works on Windows/Linux/macOS
4. **Progress tracking**: HuggingFace Hub shows download progress
5. **Smart detection**: Checks for existing models before downloading
6. **Auto-symlinks**: Reuses models from HuggingFace cache if found

## Next Steps

### Option 1: Run setup.py interactively (with model downloads)
```bash
cd /home/ubuntu/nemotron-v3-home-security-intelligence
python3 setup.py
# Select option 2 (required + Phase 1) for full ai-gateway support
```

### Option 2: Delete old download script (after testing)
```bash
# Once confirmed working:
rm ai/download_models.sh
git add -u
git commit -m "Consolidate model downloads into setup.py"
```

## Directory Structure After Setup

```
/export/ai_models/
├── nemotron/
│   └── nemotron-3-nano-30b-a3b-q4km/
│       └── Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf  (~14.7GB)
└── model-zoo/
    ├── yolo26/
    │   ├── yolo26n.pt  (~5.3MB)
    │   ├── yolo26s.pt  (~19.5MB)
    │   └── yolo26m.pt  (~42.2MB)
    ├── florence-2-large/                (~3GB)
    ├── clip-vit-l/                      (~1.7GB)
    ├── fashion-clip/                    (~3.5GB)
    ├── vehicle-segment-classification/  (~350MB)
    ├── pet-classifier/                  (~45MB)
    ├── depth-anything-v2-tiny/          (~25MB)
    ├── threat-detection-yolov8n/        (~25MB)
    ├── vit-age-classifier/              (~350MB)
    ├── vit-gender-classifier/           (~350MB)
    ├── stgcn-plus-plus/                 (~20MB)
    ├── osnet-ain-x1-0/
    │   └── osnet_ain_x1_0_msmt17.pth    (~10MB)
    └── yolov8n-pose/
        └── yolov8n-pose.pt              (~6MB)
```

All models are now downloaded during setup - no auto-download on first container start!
