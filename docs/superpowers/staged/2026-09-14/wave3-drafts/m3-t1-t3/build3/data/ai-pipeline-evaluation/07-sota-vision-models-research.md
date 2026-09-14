# SOTA Vision Models Research for Home Security AI Pipeline

**Date:** 2026-02-08
**Target Hardware:** NVIDIA A400 (4GB) via Triton Inference Server + NVIDIA A5500 (24GB) for LLM
**Constraint:** Models must be under 1GB VRAM (ideally under 500MB), ONNX-exportable, production-ready
**Current Total VRAM Budget for Model Zoo:** ~1,650 MB (shared with sequential loading)

---

## Table of Contents

1. [Person Re-Identification](#1-person-re-identification)
2. [Action Recognition](#2-action-recognition)
3. [Anomaly Detection](#3-anomaly-detection)
4. [Smoke/Fire Detection](#4-smokefire-detection)
5. [Low-Light Enhancement](#5-low-light-enhancement)
6. [License Plate Recognition](#6-license-plate-recognition)
7. [Better Embeddings](#7-better-embeddings)
8. [Scene Classification](#8-scene-classification)
9. [Implementation Priority Matrix](#9-implementation-priority-matrix)
10. [Triton Deployment Architecture](#10-triton-deployment-architecture)

---

## 1. Person Re-Identification

**Current model:** OSNet x0.25 (~2.5MB, 0.56M params) -- extremely lightweight but dated (2019), low accuracy on modern benchmarks.

| Model                         | Architecture                                      | Params                 | Size (est.)             | ONNX                                      | Pretrained                     | License    | Market1501 R1/mAP          | Security Value                                   |
| ----------------------------- | ------------------------------------------------- | ---------------------- | ----------------------- | ----------------------------------------- | ------------------------------ | ---------- | -------------------------- | ------------------------------------------------ |
| **OSNet x1.0**                | Omni-Scale CNN                                    | 2.2M                   | ~9MB                    | Yes (torchreid export)                    | Yes (Market1501, MSMT17)       | MIT        | 94.8% / 84.9%              | 4x better than x0.25, minimal VRAM increase      |
| **OSNet-AIN x1.0**            | OSNet + Instance Norm                             | 2.2M                   | ~9MB ONNX               | Yes (verified osnet_ain_x1_0_msmt17.onnx) | Yes (MSMT17)                   | MIT        | ~95% / ~86%                | Cross-domain robustness for outdoor cameras      |
| **FastReID (OSNet backbone)** | OSNet via FastReID toolbox                        | 2.2M                   | ~9MB                    | Yes (built-in Caffe/ONNX/TRT export)      | Yes (multiple datasets)        | Apache 2.0 | Competitive                | Distillation support for even lighter models     |
| **SOLIDER-ReID**              | Transformer (ViT-S/B) + human-centric pretraining | 22M (ViT-S)            | ~85MB                   | Possible (PyTorch-based)                  | Yes (SOLIDER pretrained)       | Apache 2.0 | 96.9% / 90.4%              | SOTA accuracy, human-centric features            |
| **TransReID-SSL**             | ViT-S + self-supervised                           | 22M                    | ~85MB                   | Requires manual export                    | Yes (DukeMTMC, Market1501)     | MIT        | 95.2% / 88.2%              | Self-supervised pretraining, no labels needed    |
| **ReIDMamba**                 | Pure Mamba (SSM-based)                            | ~7M (1/3 of TransReID) | ~28MB                   | Untested (PyTorch)                        | Research only (arxiv Nov 2025) | Unknown    | Competitive with TransReID | Mamba arch = efficient long-sequence modeling    |
| **Pose2ID** (CVPR 2025)       | Training-free, pose features                      | 0 (uses pose model)    | 0 (reuses YOLOv8n-Pose) | N/A                                       | N/A                            | Unknown    | Competitive                | Zero additional VRAM, reuses existing pose model |

### Top Recommendation: OSNet-AIN x1.0

**Why:** Drop-in upgrade from OSNet x0.25 with verified ONNX weights, same architecture family (easy integration), 4x accuracy improvement, only ~9MB. The `osnet_ain_x1_0_msmt17.onnx` model is confirmed available. MSMT17 pretraining provides better cross-domain generalization for real-world surveillance.

**Runner-up:** SOLIDER-ReID (ViT-S) if willing to invest ~85MB for SOTA accuracy. The human-centric pretraining specifically learns body structure features ideal for security cameras.

**Dark horse:** Pose2ID (CVPR 2025) -- training-free ReID using pose keypoints from the existing YOLOv8n-Pose model. Zero additional VRAM cost. Worth prototyping.

**Sources:**

- [deep-person-reid (torchreid)](https://github.com/KaiyangZhou/deep-person-reid)
- [FastReID](https://github.com/JDAI-CV/fast-reid)
- [SOLIDER-REID](https://github.com/tinyvision/SOLIDER-REID)
- [TransReID-SSL](https://github.com/damo-cv/TransReID-SSL)
- [ReIDMamba (arxiv)](https://arxiv.org/html/2511.07948)
- [Pose2ID (CVPR 2025)](https://github.com/yuanc3/Pose2ID)

---

## 2. Action Recognition

**Current model:** X-CLIP Base (~2GB VRAM) -- far too heavy, needs 16 video frames, slow inference.

| Model                      | Architecture                     | Params  | Size (est.) | ONNX                                | Pretrained                | License    | Accuracy                   | Security Value                               |
| -------------------------- | -------------------------------- | ------- | ----------- | ----------------------------------- | ------------------------- | ---------- | -------------------------- | -------------------------------------------- |
| **ST-GCN**                 | Spatial-Temporal GCN             | 3.1M    | ~12MB       | Yes (opset 12+, requires 5D tensor) | Yes (Kinetics, NTU-RGB+D) | MIT        | 81.5% NTU X-Sub            | Reuses pose keypoints, very lightweight      |
| **ST-GCN++** (PYSKL)       | Improved ST-GCN                  | ~3.5M   | ~14MB       | Possible (opset 12+)                | Yes (NTU-RGB+D)           | Apache 2.0 | ~86% NTU X-Sub             | Stronger baseline, no attention overhead     |
| **MSA-STGCN**              | Multi-scale attention GCN        | 1.21M   | ~5MB        | Untested                            | Research only             | Unknown    | 95.3% Filtered NTU         | Extremely lightweight, high accuracy         |
| **ESTS-GCN**               | Ensemble ST skeleton GCN         | ~3M     | ~12MB       | Untested                            | Research (2024)           | Unknown    | High on violence detection | Specifically designed for violence detection |
| **MSAR**                   | Multi-Skeleton Action Recognizer | ~5M     | ~20MB       | Untested                            | Research (2025)           | Unknown    | SOTA multi-person violence | Multi-person violence recognition            |
| **EZ-CLIP** (if available) | Efficient zero-shot CLIP         | Unknown | Unknown     | Unknown                             | Unknown                   | Unknown    | Unknown                    | Would need verification                      |

### Top Recommendation: ST-GCN++ via PYSKL

**Why:** The skeleton-based approach is the key insight here. The pipeline already runs YOLOv8n-Pose which extracts 17 COCO keypoints. ST-GCN++ takes these keypoints as input (no image processing needed), uses only ~14MB, and can recognize security-relevant actions like fighting, falling, running, and loitering. This replaces the 2GB X-CLIP with a ~14MB model.

**Implementation strategy:**

1. YOLOv8n-Pose extracts keypoints (already in pipeline, ~200MB)
2. Buffer 30-60 frames of keypoints per tracked person (~minimal memory)
3. ST-GCN++ classifies the keypoint sequence into actions (~14MB)
4. Total: 200MB (shared) + 14MB = 214MB vs X-CLIP's 2GB

**For violence detection specifically:** Fine-tune ST-GCN++ on NTU-RGB+D mutual actions subset + UCF-Crime skeleton data. The ESTS-GCN paper shows skeleton GCNs achieve strong violence detection results.

**Sources:**

- [PYSKL (ST-GCN++)](https://github.com/kennymckormick/pyskl)
- [ST-GCN original](https://github.com/yysijie/st-gcn)
- [MMAction2 skeleton models](https://mmaction2.readthedocs.io/en/latest/model_zoo/skeleton.html)
- [ESTS-GCN for violence](https://onlinelibrary.wiley.com/doi/10.1155/2024/2323337)
- [Skeleton multi-person violence (2025)](https://www.sciencedirect.com/science/article/abs/pii/S0952197625019955)

---

## 3. Anomaly Detection

**Current model:** None dedicated. The pipeline relies on the LLM (Nemotron) to assess risk from object/action context.

| Model                         | Architecture                        | Params                         | Size (est.) | ONNX                                | Pretrained           | License    | Dataset                      | Security Value                             |
| ----------------------------- | ----------------------------------- | ------------------------------ | ----------- | ----------------------------------- | -------------------- | ---------- | ---------------------------- | ------------------------------------------ |
| **GiCiSAD**                   | Graph-Jigsaw + Diffusion (skeleton) | Very low (40% fewer than SOTA) | ~10-20MB    | Untested                            | Research (WACV 2025) | Unknown    | ShanghaiTech, CUHK, UBnormal | Skeleton-based anomaly = reuses pose model |
| **Anomalib PatchCore**        | Memory bank + pretrained CNN        | Depends on backbone            | ~50-200MB   | Yes (built-in ONNX/OpenVINO export) | Yes (MVTec, custom)  | Apache 2.0 | MVTec AD                     | Industrial-grade anomaly library           |
| **Anomalib PaDiM**            | Patch Distribution Modeling         | Depends on backbone            | ~50-150MB   | Yes (built-in export)               | Yes (MVTec)          | Apache 2.0 | MVTec AD                     | Gaussian distribution anomaly detection    |
| **UCF-Crime MIL models**      | C3D/I3D + MIL ranking               | ~12M (C3D)                     | ~100MB      | Possible                            | Yes (UCF-Crime)      | Academic   | UCF-Crime (13 anomaly types) | Directly trained on surveillance anomalies |
| **Skeleton anomaly (Barata)** | Regularity in trajectories          | Small                          | ~10MB       | Untested                            | Yes (CVPR 2019)      | Unknown    | ShanghaiTech                 | Skeleton trajectory regularity scoring     |

### Top Recommendation: Two-pronged approach

**Approach A (skeleton-based, zero additional VRAM):** Use ST-GCN++ (from Action Recognition above) to classify actions, then feed classification confidence scores to the LLM for anomaly reasoning. Abnormal actions (fighting, falling, running at night) get flagged automatically.

**Approach B (Anomalib PatchCore, ~100MB):** For scene-level anomaly detection (unusual objects, tampered cameras, structural changes). Anomalib has built-in ONNX export and has been specifically designed for edge deployment. Train PatchCore on "normal" camera views to detect scene deviations.

**Why not a single model:** Surveillance anomaly detection is fundamentally different from industrial anomaly detection. The combination of skeleton-based action classification + scene-level PatchCore + LLM reasoning is more robust than any single model.

**Sources:**

- [GiCiSAD (WACV 2025)](https://arxiv.org/abs/2403.12172)
- [Anomalib](https://github.com/open-edge-platform/anomalib)
- [UCF-Crime dataset](https://www.crcv.ucf.edu/projects/real-world/)
- [Skeleton anomaly detection (CVPR 2019)](https://github.com/RomeroBarata/skeleton_based_anomaly_detection)

---

## 4. Smoke/Fire Detection

**Current model:** Loader exists (`smoke_fire_loader.py`) and ModelConfig registered (`smoke-fire-yolov8n`), but NO model weights on disk.

| Model                                 | Architecture                 | Params       | Size (est.)            | ONNX                                | Pretrained          | License             | mAP                 | Security Value                   |
| ------------------------------------- | ---------------------------- | ------------ | ---------------------- | ----------------------------------- | ------------------- | ------------------- | ------------------- | -------------------------------- |
| **YOLOv8n fire-smoke** (luminous0219) | YOLOv8n fine-tuned           | 3.2M         | ~6MB (.pt), ~12MB ONNX | Yes (`model.export(format="onnx")`) | Yes (150 epochs)    | Unknown             | ~0.85               | Direct fire+smoke detection      |
| **DSS-YOLO**                          | YOLOv8n + DynamicConv + SEAM | ~3M          | ~10MB                  | Exportable                          | Research (2025)     | Unknown             | Better than YOLOv8n | Better on obscured/small targets |
| **YOLOv8n-SMMP**                      | YOLOv8n + SlimNeck + MCA     | <3M (pruned) | ~8MB                   | Exportable                          | Research (May 2025) | Unknown             | High (forest fire)  | Pruned = faster inference        |
| **YOLO11n fire-smoke** (Roboflow)     | YOLO11n fine-tuned           | ~2.6M        | ~5MB                   | Yes (Ultralytics export)            | Yes (4359 images)   | CC-BY-4.0 (dataset) | 0.94 mAP            | Latest YOLO arch, smallest model |
| **YOLOv9-c fire**                     | YOLOv9-c                     | ~25M         | ~100MB                 | Exportable                          | Yes (50 epochs)     | GPL-3.0             | Higher accuracy     | Much larger, not lightweight     |

### Top Recommendation: YOLOv8n fire-smoke (luminous0219) OR YOLO11n variant

**Why:** The pipeline already has the loader code and ModelConfig for `smoke-fire-yolov8n`. Just need to download the weights. YOLOv8n is the most proven architecture with native Ultralytics ONNX export. At ~6-12MB, it fits easily in the VRAM budget. The model_zoo.py already allocates 350MB for this slot (generous headroom).

**Action items:**

1. Download pretrained weights from `luminous0219/fire-and-smoke-detection-yolov8` GitHub repo
2. Place in `/models/model-zoo/smoke-fire-yolov8n/`
3. Export to ONNX: `model.export(format="onnx")`
4. Test with the existing `smoke_fire_loader.py`
5. Classes: `fire`, `smoke` (2-class detection)

**For Triton deployment:** Export to TensorRT via Ultralytics for best inference speed on the A400 GPU.

**Sources:**

- [luminous0219/fire-and-smoke-detection-yolov8](https://github.com/luminous0219/fire-and-smoke-detection-yolov8)
- [DSS-YOLO (2025)](https://www.nature.com/articles/s41598-025-93278-w)
- [YOLOv8n-SMMP (2025)](https://www.mdpi.com/2571-6255/8/5/183)
- [Fire-Smoke-Detection-Yolov11 on Roboflow](https://universe.roboflow.com/sayed-gamall/fire-smoke-detection-yolov11)
- [Abonia1/YOLOv8-Fire-and-Smoke-Detection](https://github.com/Abonia1/YOLOv8-Fire-and-Smoke-Detection)

---

## 5. Low-Light Enhancement

**Current model:** None. The pipeline has no preprocessing for night-time or low-light conditions.

| Model                | Architecture                | Params                  | Size (est.)     | ONNX                    | Pretrained         | License      | Performance                         | Security Value                               |
| -------------------- | --------------------------- | ----------------------- | --------------- | ----------------------- | ------------------ | ------------ | ----------------------------------- | -------------------------------------------- |
| **Zero-DCE**         | Plain CNN (7 conv layers)   | 79K                     | ~0.3MB          | Exportable (simple CNN) | Yes                | BSD-3-Clause | Good quality                        | Extremely lightweight, no reference needed   |
| **Zero-DCE++**       | Depthwise separable CNN     | 10K                     | ~0.04MB (40KB!) | Exportable              | Yes                | BSD-3-Clause | 1000 FPS GPU, 11 FPS CPU (1200x900) | Near-zero overhead preprocessing             |
| **LYT-Net**          | YUV Transformer             | ~1.3M                   | ~5MB            | Exportable              | Yes                | Unknown      | NTIRE 2024 competitor               | Color-space aware enhancement                |
| **UltraFast-LieNET** | Dynamic Shifted Conv        | 12 learnable params (!) | <0.01MB         | Exportable              | Research (2025)    | Unknown      | NTIRE 2025                          | Practically zero-cost enhancement            |
| **LiteIE**           | Unsupervised, 2 conv layers | Minimal                 | <0.1MB          | Exportable              | Yes (unsupervised) | Unknown      | Good generalization                 | No training data needed, works on any camera |
| **Retinexformer**    | Retinex-based Transformer   | ~1.6M                   | ~6MB            | Possible                | Yes (ICCV 2023)    | MIT          | NTIRE 2024 Runner-Up                | High quality, reasonable size                |

### Top Recommendation: Zero-DCE++

**Why:** At 10K parameters and ~40KB model size, Zero-DCE++ adds essentially zero overhead to the pipeline. It runs at 1000 FPS on GPU, meaning it can preprocess every frame before YOLO detection with negligible latency. The model requires no reference images and works via curve estimation -- it learns to adjust brightness curves without needing paired training data.

**Implementation strategy:**

1. Export Zero-DCE++ to ONNX (~40KB model)
2. Deploy as Triton preprocessing step (CPU or GPU)
3. Apply to all frames during night hours (or when BRISQUE detects low quality)
4. Feed enhanced frames to YOLO26 for detection
5. Expected improvement: 5-15% better detection accuracy in low-light conditions

**Alternative:** If Zero-DCE++ quality is insufficient, Retinexformer at ~6MB provides SOTA quality with reasonable size.

**Sources:**

- [Zero-DCE](https://github.com/Li-Chongyi/Zero-DCE)
- [Retinexformer](https://github.com/caiyuanhao1998/Retinexformer)
- [NTIRE 2025 Low-Light Challenge](https://arxiv.org/abs/2510.13670)
- [Lightweight Automotive Low-Light Enhancement](https://arxiv.org/abs/2512.02965)
- [LYT-Net](https://www.sciencedirect.com/science/article/abs/pii/S0097849325000093)

---

## 6. License Plate Recognition (ALPR)

**Current model:** yolo11-license-plate on disk (detection only), PaddleOCR for text. Integrated in model_zoo.py.

| Model                                         | Architecture                   | Params                | Size (est.)     | ONNX                            | Pretrained         | License | Accuracy                 | Security Value                         |
| --------------------------------------------- | ------------------------------ | --------------------- | --------------- | ------------------------------- | ------------------ | ------- | ------------------------ | -------------------------------------- |
| **FastALPR**                                  | YOLO-v9-t + fast-plate-ocr     | ~5M (det) + ~2M (OCR) | ~20MB + ~8MB    | Yes (ONNX by default!)          | Yes                | MIT     | 98.15% (EU), 95.61% (BR) | End-to-end ONNX pipeline, minimal size |
| **fast-plate-ocr**                            | CCT (Compact Conv Transformer) | ~2M                   | ~8MB            | Yes (native ONNX/CoreML/TFLite) | Yes (global model) | MIT     | High                     | Dedicated OCR for plates, tiny model   |
| **Current: yolo11-license-plate + PaddleOCR** | YOLO11n + PaddleOCR            | ~3M + ~15M            | ~300MB + ~100MB | Partial                         | Yes                | Mixed   | Good                     | Already integrated but heavy           |
| **ort-alpr**                                  | ONNX Runtime optimized         | Small                 | ~30MB total     | Yes (ONNX-native)               | Yes                | MIT     | Good                     | CPU-optimized, no GPU needed           |
| **YOLO11 CodeProject.AI**                     | YOLO11 + char recognition      | ~5M                   | ~20MB           | Yes                             | Yes                | Unknown | Good                     | Detection + state classification       |

### Top Recommendation: FastALPR (for future upgrade)

**Why:** FastALPR provides the best end-to-end ALPR solution with native ONNX support. The `yolo-v9-t-384-license-plate-end2end` detector + `cct-xs-v1-global-model` OCR combination is only ~28MB total, compared to the current ~400MB (yolo11 + PaddleOCR). However, the current pipeline already works, so this is a lower priority upgrade.

**Immediate action:** Verify the existing `yolo11-license-plate` integration works end-to-end with PaddleOCR. If it does, keep it. If not, swap to FastALPR.

**For fast-plate-ocr specifically:** The `cct-xs-v1-global-model` ONNX model is a drop-in replacement for PaddleOCR at 1/12th the size. Worth evaluating as a PaddleOCR alternative.

**Sources:**

- [FastALPR](https://github.com/ankandrew/fast-alpr)
- [fast-plate-ocr](https://github.com/ankandrew/fast-plate-ocr)
- [ort-alpr (ONNX Runtime)](https://github.com/tharakarehan/ort-alpr)

---

## 7. Better Embeddings

**Current model:** CLIP ViT-L (~1.2GB VRAM) -- the heaviest model in the pipeline by far.

| Model                            | Architecture             | Params                    | Size (est.)              | ONNX                                                 | Pretrained     | License                   | ImageNet ZS            | Security Value                             |
| -------------------------------- | ------------------------ | ------------------------- | ------------------------ | ---------------------------------------------------- | -------------- | ------------------------- | ---------------------- | ------------------------------------------ |
| **SigLIP 2 Base** (ViT-B/16-224) | ViT-B Sigmoid loss       | 86M                       | ~330MB FP32, ~165MB FP16 | Yes (`onnx-community/siglip2-base-patch16-224-ONNX`) | Yes (Google)   | Apache 2.0                | Better than SigLIP v1  | Multilingual, improved localization        |
| **SigLIP 2 So400m**              | ViT-So400m               | 400M                      | ~1.5GB FP32, ~800MB FP16 | Possible                                             | Yes            | Apache 2.0                | Very high              | Near-CLIP ViT-L quality, same size         |
| **MobileCLIP-S0**                | Hybrid CNN-Transformer   | 11.4M (img) + 42.4M (txt) | ~200MB total             | Possible (CoreML proven)                             | Yes (Apple)    | Apple sample code license | 67.8%                  | 4.8x faster than ViT-B/16, 2.8x smaller    |
| **MobileCLIP-S2**                | Hybrid MCi2 + Base text  | ~100M total               | ~400MB                   | Possible                                             | Yes (Apple HF) | Apple sample code license | ~72%                   | Better than SigLIP ViT-B/16, 2.3x faster   |
| **MobileCLIP2-S4** (Aug 2025)    | Improved hybrid          | ~150M total               | ~600MB                   | Untested                                             | Yes (Apple HF) | Apple sample code license | Matches SigLIP-SO400M  | 2x fewer params than SO400M                |
| **DINOv2-Small**                 | ViT-S/14 self-supervised | 22M                       | ~85MB FP32, ~42MB FP16   | Yes (`sefaburak/dinov2-small-onnx`)                  | Yes (Meta)     | Apache 2.0                | N/A (features, not ZS) | Best visual features at this size, no text |
| **EVA-02 Base**                  | ViT-B + MIM pretrained   | 86M                       | ~330MB                   | Possible (via timm)                                  | Yes (BAAI)     | MIT                       | High                   | Strong visual representations              |
| **OpenCLIP ViT-B/32**            | ViT-B/32 standard        | 87M                       | ~340MB                   | Yes (community ONNX)                                 | Yes (LAION)    | MIT                       | ~68%                   | Well-tested, broad community support       |

### Top Recommendation: SigLIP 2 Base (ViT-B/16-224)

**Why:** Pre-converted ONNX weights already exist on HuggingFace (`onnx-community/siglip2-base-patch16-224-ONNX`). At ~165MB in FP16, it is 7x smaller than the current CLIP ViT-L (1.2GB). SigLIP 2 outperforms original SigLIP at all scales with improved semantic understanding, localization, and dense features. Apache 2.0 license. Drop-in replacement for zero-shot classification tasks.

**VRAM savings:** 1,200MB (current CLIP ViT-L) -> 165MB (SigLIP 2 Base FP16) = **1,035MB saved**

**Runner-up for embeddings only (no text matching):** DINOv2-Small at ~42MB FP16. ONNX already available. Best pure visual features at this size, but cannot do zero-shot text-image matching. Use for pure visual similarity (person re-appearance, scene matching).

**Runner-up for mobile-optimized:** MobileCLIP-S2 at ~400MB if latency is critical. 2.3x faster inference than ViT-B/16.

**Sources:**

- [SigLIP 2 blog](https://huggingface.co/blog/siglip2)
- [SigLIP 2 ONNX model](https://huggingface.co/onnx-community/siglip2-base-patch16-224-ONNX)
- [google/siglip2-base-patch16-224](https://huggingface.co/google/siglip2-base-patch16-224)
- [MobileCLIP (Apple)](https://github.com/apple/ml-mobileclip)
- [MobileCLIP2 paper](https://arxiv.org/html/2508.20691v1)
- [DINOv2-Small ONNX](https://huggingface.co/sefaburak/dinov2-small-onnx)
- [DINOv2-Small (Meta)](https://huggingface.co/facebook/dinov2-small)
- [EVA-02 (BAAI)](https://github.com/baaivision/EVA)

---

## 8. Scene Classification

**Current model:** None. The pipeline has weather classification (SigLIP-based) but no general scene understanding.

| Model                      | Architecture                | Params                     | Size (est.)  | ONNX                                 | Pretrained                         | License    | Accuracy                   | Security Value                           |
| -------------------------- | --------------------------- | -------------------------- | ------------ | ------------------------------------ | ---------------------------------- | ---------- | -------------------------- | ---------------------------------------- |
| **Places365-ResNet18**     | ResNet-18                   | 11.7M                      | ~45MB        | Exportable (PyTorch -> ONNX trivial) | Yes (Places365, 365 scene classes) | MIT/BSD    | ~54% Top-1                 | Indoor/outdoor, scene context for LLM    |
| **Places365-ResNet50**     | ResNet-50                   | 25.6M                      | ~100MB       | Exportable                           | Yes (Places365)                    | MIT/BSD    | ~55% Top-1                 | Better accuracy, still lightweight       |
| **Places365-MobileNetV2**  | MobileNetV2                 | 3.5M                       | ~14MB        | Exportable                           | Community fine-tuned               | Apache 2.0 | ~52% Top-1                 | Ultra-lightweight for CPU                |
| **GFNet-distilled** (2025) | Distilled Global Filter Net | <10M                       | ~40MB        | Exportable                           | Research (2025)                    | Unknown    | Competitive                | Dynamic early-exit for edge              |
| **CLIP zero-shot scene**   | Uses SigLIP 2 Base          | 0 (reuses embedding model) | 0 additional | Yes                                  | Yes                                | Apache 2.0 | ~55-60% (prompt-dependent) | Zero additional cost if SigLIP 2 adopted |

### Top Recommendation: Zero-shot via SigLIP 2 (if adopted from Embeddings section)

**Why:** If SigLIP 2 Base is adopted as the new embedding model, scene classification comes free via zero-shot prompting. Prompt with scene labels like "front yard", "driveway", "porch", "street", "backyard", "garage", "indoor room" and classify at zero additional VRAM cost. This was impossible with pure visual encoders like DINOv2 but trivial with vision-language models.

**Fallback:** If SigLIP 2 is not adopted or if higher accuracy is needed, Places365-ResNet18 at ~45MB provides 365 scene classes with a well-tested model. The official PyTorch checkpoint is available from MIT CSAIL and can be trivially exported to ONNX. CPU inference is fast enough for per-frame classification.

**Security context gained:**

- Time-of-day estimation (from scene lighting patterns)
- Indoor vs outdoor (helps calibrate expected objects)
- Scene type (parking lot, street, yard) for context-aware alerts
- Weather conditions (complementing existing weather classifier)

**Sources:**

- [Places365 official](https://github.com/CSAILVision/places365)
- [Places365 PyTorch weights](http://places2.csail.mit.edu/models_places365/)
- [IBM MAX-Scene-Classifier](https://github.com/IBM/MAX-Scene-Classifier)
- [Lightweight Scene Classification (2025)](https://arxiv.org/abs/2507.20623v1)

---

## 9. Implementation Priority Matrix

Ranked by (security value \* ease of implementation) / VRAM cost:

| Priority | Model Upgrade                        | VRAM Change                         | Effort                       | Security Impact                      | ROI Score |
| -------- | ------------------------------------ | ----------------------------------- | ---------------------------- | ------------------------------------ | --------- |
| **P0**   | Smoke/Fire YOLOv8n weights           | +6MB (already allocated 350MB slot) | Low (download + test)        | CRITICAL (life safety)               | 10/10     |
| **P1**   | SigLIP 2 Base replaces CLIP ViT-L    | -1,035MB                            | Medium (new loader)          | High (better embeddings, 7x smaller) | 9/10      |
| **P2**   | Zero-DCE++ low-light preprocess      | +0.04MB                             | Medium (new preprocess step) | High (night detection improvement)   | 9/10      |
| **P3**   | OSNet-AIN x1.0 replaces OSNet x0.25  | +7MB                                | Low (same architecture)      | High (4x better ReID)                | 8/10      |
| **P4**   | ST-GCN++ replaces X-CLIP             | -1,986MB                            | High (new architecture)      | High (action recognition, violence)  | 8/10      |
| **P5**   | Scene classification via SigLIP 2    | +0MB (reuses P1)                    | Low (prompt engineering)     | Medium (context for LLM)             | 7/10      |
| **P6**   | FastALPR replaces PaddleOCR          | -72MB                               | Medium (new OCR module)      | Medium (lighter, faster plates)      | 6/10      |
| **P7**   | Anomalib PatchCore for scene anomaly | +100MB                              | High (training required)     | Medium (scene tamper detection)      | 5/10      |
| **P8**   | DINOv2-Small for visual features     | +42MB                               | Medium (new loader)          | Medium (better visual similarity)    | 5/10      |

### Total VRAM Impact if All Implemented

| Model                                  | Current VRAM | New VRAM | Delta               |
| -------------------------------------- | ------------ | -------- | ------------------- |
| CLIP ViT-L -> SigLIP 2 Base FP16       | 1,200 MB     | 165 MB   | **-1,035 MB**       |
| X-CLIP -> ST-GCN++                     | 2,000 MB     | 14 MB    | **-1,986 MB**       |
| OSNet x0.25 -> OSNet-AIN x1.0          | 100 MB       | 100 MB   | 0 MB                |
| Smoke/Fire (empty -> YOLOv8n)          | 0 MB         | 12 MB    | +12 MB              |
| Zero-DCE++ (new)                       | 0 MB         | 0.04 MB  | +0.04 MB            |
| FastALPR (optional, replace PaddleOCR) | 100 MB       | 28 MB    | -72 MB              |
| PatchCore (optional, new)              | 0 MB         | 100 MB   | +100 MB             |
| **Total Change**                       |              |          | **-2,981 MB freed** |

This frees up nearly 3GB of VRAM budget, enabling either:

- Running more models concurrently (batch efficiency)
- Adding new capabilities without VRAM pressure
- Moving some models from sequential to concurrent loading

---

## 10. Triton Deployment Architecture

### Recommended Triton Model Repository Structure

```
model_repository/
  # GPU models (A400 4GB)
  yolo26m/              # Object detection (always loaded)
  siglip2_base/         # Embeddings (replaces CLIP ViT-L)
    1/model.onnx        # From onnx-community/siglip2-base-patch16-224-ONNX
    config.pbtxt
  stgcn_plus/           # Action recognition (replaces X-CLIP)
    1/model.onnx        # Skeleton input, action output
    config.pbtxt
  smoke_fire_yolov8n/   # Fire/smoke detection
    1/model.onnx        # Ultralytics ONNX export
    config.pbtxt

  # CPU models (host CPU, minimal latency impact)
  zero_dce_plus/        # Low-light enhancement (40KB!)
    1/model.onnx
    config.pbtxt
  osnet_ain_x1_0/       # Person ReID (~9MB)
    1/model.onnx
    config.pbtxt
  places365_resnet18/   # Scene classification (~45MB)
    1/model.onnx
    config.pbtxt
  fast_plate_ocr/       # License plate OCR (~8MB)
    1/model.onnx
    config.pbtxt

  # Ensemble pipelines
  security_enrichment/  # Orchestrates the full pipeline
    config.pbtxt        # DAG: detect -> classify -> embed -> action
```

### Ensemble Pipeline Design

```
Frame Input
    |
    v
[Zero-DCE++ preprocess] (CPU, if low-light detected)
    |
    v
[YOLO26m detect] (GPU)
    |
    +---> Person detections ---> [OSNet-AIN x1.0 ReID] (CPU)
    |                      \---> [ST-GCN++ action] (GPU, buffered keypoints)
    |                       \--> [YOLOv8n-Pose keypoints] (GPU)
    |
    +---> Vehicle detections --> [License Plate YOLO] (GPU)
    |                       \--> [fast-plate-ocr] (CPU)
    |
    +---> Full frame ---------> [SigLIP 2 embeddings] (GPU)
    |                       \--> [Smoke/Fire YOLOv8n] (GPU)
    |                        \-> [Scene classification] (zero-shot via SigLIP 2)
    |
    v
[Nemotron LLM risk scoring] (GPU 0, A5500)
```

### Key Deployment Notes

1. **ONNX Opset Requirements:**

   - ST-GCN++ requires opset 12+ (5D tensor + einsum support)
   - SigLIP 2 ONNX uses standard opset 17
   - Zero-DCE++ is simple CNN, any opset works

2. **Dynamic Batching:**

   - SigLIP 2: Enable dynamic batching for embedding multiple crops
   - YOLO models: Fixed batch (frame-level)
   - ST-GCN++: Batch across tracked persons

3. **Model Format Preference:**

   - GPU models: TensorRT > ONNX (2-3x faster on A400)
   - CPU models: ONNX Runtime with OpenVINO EP (Intel optimized)

4. **Instance Groups:**
   - A400 GPU: 1 instance each for YOLO26, SigLIP 2, smoke/fire
   - CPU: 2-4 instances for OSNet, OCR, scene (parallel per-detection)

---

## Appendix A: Models NOT Recommended

| Model                     | Reason for Exclusion                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------ |
| ReIDMamba                 | Research-only (Nov 2025 arxiv), no pretrained weights available, no ONNX support     |
| EZ-CLIP                   | Cannot find verified implementation or pretrained weights                            |
| VideoMAE-v2 Small         | Still requires video frames (not skeleton), 200MB+, marginal improvement over X-CLIP |
| X-CLIP (keeping current)  | 2GB is too heavy, skeleton-based approach is fundamentally better for security       |
| EVA-CLIP-18B              | 18 billion parameters, absurdly large                                                |
| SegFormer-b2 for clothing | Keep current model, no clear lightweight replacement found                           |
| Vehicle ResNet-50         | Keep current model, already integrated                                               |

## Appendix B: Future Research Areas (Post-Implementation)

1. **MobileCLIP2-S4** (Apple, Aug 2025) -- matches SigLIP-SO400M at 2x fewer params. Monitor for ONNX export support.
2. **DINOv3** (Meta, 2025) -- next generation visual features, ConvNeXt-Small variant available on HF.
3. **RTMO** -- one-stage multi-person pose estimation (no detector needed), ONNX support confirmed. Could replace YOLOv8n-Pose + separate detector.
4. **EfficientViT-SAM** (MIT) -- if segmentation needs arise, 48.9x faster than SAM on A100.
5. **GiCiSAD** (WACV 2025) -- skeleton-based anomaly detection with diffusion models, watch for code release.
6. **LITE tracker** -- extracts ReID features within YOLO detection pipeline itself, eliminating need for separate OSNet.
7. **Compact VLMs for surveillance** (2025 benchmark) -- Qwen2.5-VL-3B and InternVL3-2B evaluated on UCF-Crime for clip-level anomaly detection.
