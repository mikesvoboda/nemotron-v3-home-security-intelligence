# Model Zoo Benchmark Results

> Performance benchmarks for all on-demand AI models in the Model Zoo.

**Source:** `backend/services/model_zoo.py`

---

## Summary

The Model Zoo provides on-demand loading of AI models during batch processing to extract additional context. Models are loaded sequentially (never concurrently) to stay within VRAM budget.

### VRAM Budget

| Component     | VRAM Allocation |
| ------------- | --------------- |
| Nemotron LLM  | 21,700 MB       |
| YOLO26v2      | 650 MB          |
| **Model Zoo** | ~1,650 MB       |

---

## Model Registry

### Detection Models

| Model                      | VRAM    | Category  | Description                             | Status   |
| -------------------------- | ------- | --------- | --------------------------------------- | -------- |
| `yolo11-license-plate`     | 300 MB  | detection | License plate detection on vehicles     | Enabled  |
| `yolo11-face`              | 200 MB  | detection | Face detection on persons               | Enabled  |
| `yolo26-general`           | 400 MB  | detection | Future YOLO26 general detection         | Disabled |
| `yolo-world-s`             | 1500 MB | detection | Open-vocabulary zero-shot detection     | Enabled  |
| `threat-detection-yolov8n` | 300 MB  | detection | Weapon/threat detection                 | Enabled  |
| `vehicle-damage-detection` | 2000 MB | detection | Vehicle damage segmentation (6 classes) | Enabled  |

### Classification Models

| Model                            | VRAM    | Category       | Description                            | Status  |
| -------------------------------- | ------- | -------------- | -------------------------------------- | ------- |
| `violence-detection`             | 500 MB  | classification | Binary violence classification         | Enabled |
| `weather-classification`         | 200 MB  | classification | Weather condition (5 classes)          | Enabled |
| `fashion-clip`                   | 500 MB  | classification | Zero-shot clothing classification      | Enabled |
| `vehicle-segment-classification` | 1500 MB | classification | Vehicle type (11 categories)           | Enabled |
| `pet-classifier`                 | 200 MB  | classification | Dog/cat classification                 | Enabled |
| `vit-age-classifier`             | 200 MB  | classification | Age estimation from face/person crops  | Enabled |
| `vit-gender-classifier`          | 200 MB  | classification | Gender classification from face/person | Enabled |

### Embedding Models

| Model         | VRAM   | Category  | Description                           | Status  |
| ------------- | ------ | --------- | ------------------------------------- | ------- |
| `clip-vit-l`  | 800 MB | embedding | CLIP embeddings for re-identification | Enabled |
| `osnet-x0-25` | 100 MB | embedding | Person re-identification embeddings   | Enabled |

### Pose Estimation Models

| Model           | VRAM    | Category | Description                 | Status  |
| --------------- | ------- | -------- | --------------------------- | ------- |
| `vitpose-small` | 1500 MB | pose     | 17 COCO keypoint detection  | Enabled |
| `yolov8n-pose`  | 200 MB  | pose     | Alternative pose estimation | Enabled |

### Vision-Language Models

| Model              | VRAM    | Category        | Description             | Status   |
| ------------------ | ------- | --------------- | ----------------------- | -------- |
| `florence-2-large` | 1200 MB | vision-language | Vision-language queries | Disabled |

**Note:** Florence-2 now runs as a dedicated HTTP service at `http://ai-florence:8092`.

### Segmentation Models

| Model                  | VRAM    | Category     | Description                           | Status  |
| ---------------------- | ------- | ------------ | ------------------------------------- | ------- |
| `segformer-b2-clothes` | 1500 MB | segmentation | Clothing segmentation (18 categories) | Enabled |

### Depth Estimation Models

| Model                     | VRAM   | Category         | Description                | Status  |
| ------------------------- | ------ | ---------------- | -------------------------- | ------- |
| `depth-anything-v2-small` | 150 MB | depth-estimation | Monocular depth estimation | Enabled |

### Action Recognition Models

| Model        | VRAM    | Category           | Description                          | Status  |
| ------------ | ------- | ------------------ | ------------------------------------ | ------- |
| `xclip-base` | 2000 MB | action-recognition | Temporal action recognition in video | Enabled |

### OCR Models

| Model       | VRAM   | Category | Description                     | Status  |
| ----------- | ------ | -------- | ------------------------------- | ------- |
| `paddleocr` | 100 MB | ocr      | OCR text extraction from plates | Enabled |

### Quality Assessment Models

| Model             | VRAM | Category           | Description                          | Status  |
| ----------------- | ---- | ------------------ | ------------------------------------ | ------- |
| `brisque-quality` | 0 MB | quality-assessment | Image quality assessment (CPU-based) | Enabled |

---

## Model Details

### yolo11-license-plate

**Purpose:** Detect license plates on vehicles detected by YOLO26v2.

| Specification | Value                                                                 |
| ------------- | --------------------------------------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/yolo11-license-plate/license-plate-finetune-v1n.pt` |
| VRAM          | ~300 MB                                                               |
| Trigger       | Vehicle detection (car, truck, bus, motorcycle, bicycle)              |
| Output        | License plate bounding boxes                                          |

### yolo11-face

**Purpose:** Detect faces on persons detected by YOLO26v2.

| Specification | Value                                             |
| ------------- | ------------------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/yolo11-face-detection/model.pt` |
| VRAM          | ~200 MB                                           |
| Trigger       | Person detection                                  |
| Output        | Face bounding boxes                               |

### paddleocr

**Purpose:** Extract text from detected license plates.

| Specification | Value                                   |
| ------------- | --------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/paddleocr`            |
| VRAM          | ~100 MB                                 |
| Trigger       | License plate detection                 |
| Output        | Extracted plate text                    |
| Optional Dep  | Requires `paddleocr` and `paddlepaddle` |

### clip-vit-l

**Purpose:** Generate embeddings for person re-identification.

| Specification | Value                         |
| ------------- | ----------------------------- |
| Path          | `{MODEL_ZOO_PATH}/clip-vit-l` |
| VRAM          | ~800 MB                       |
| Output        | 512-dimensional embeddings    |

### yolo-world-s

**Purpose:** Open-vocabulary zero-shot detection for security-relevant objects.

| Specification | Value                              |
| ------------- | ---------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/yolo-world-s`    |
| VRAM          | ~1500 MB                           |
| Output        | Detected objects from text prompts |

### vitpose-small

**Purpose:** Human pose keypoint detection for behavior analysis.

| Specification | Value                                   |
| ------------- | --------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/vitpose-small`        |
| VRAM          | ~1500 MB                                |
| Output        | 17 COCO keypoints per person            |
| Pose Classes  | standing, crouching, bending_over, etc. |

### depth-anything-v2-small

**Purpose:** Monocular depth estimation for distance context.

| Specification | Value                                       |
| ------------- | ------------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/depth-anything-v2-small`  |
| VRAM          | ~150 MB (very lightweight)                  |
| Output        | Depth map (lower values = closer to camera) |

### violence-detection

**Purpose:** Binary classification for violent content detection.

| Specification | Value                                 |
| ------------- | ------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/violence-detection` |
| VRAM          | ~500 MB                               |
| Trigger       | 2+ persons detected (optimization)    |
| Accuracy      | 98.80%                                |
| Output        | violent / non-violent                 |

### weather-classification

**Purpose:** Environmental context for risk calibration.

| Specification | Value                                                           |
| ------------- | --------------------------------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/weather-classification`                       |
| VRAM          | ~200 MB                                                         |
| Classes       | cloudy/overcast, foggy/hazy, rain/storm, snow/frosty, sun/clear |
| Trigger       | Once per batch on full frame                                    |

### segformer-b2-clothes

**Purpose:** Clothing segmentation for person identification.

| Specification | Value                                   |
| ------------- | --------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/segformer-b2-clothes` |
| VRAM          | ~1500 MB                                |
| Categories    | 18 clothing/body part categories        |
| Trigger       | Person detection                        |

### xclip-base

**Purpose:** Temporal action recognition in video sequences.

| Specification | Value                                                          |
| ------------- | -------------------------------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/xclip-base`                                  |
| VRAM          | ~2000 MB                                                       |
| Base Model    | microsoft/xclip-base-patch32                                   |
| Actions       | loitering, approaching door, running away, suspicious behavior |

### fashion-clip

**Purpose:** Zero-shot clothing classification for security context.

| Specification | Value                                                           |
| ------------- | --------------------------------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/fashion-siglip`                               |
| VRAM          | ~500 MB                                                         |
| Model         | Marqo-FashionSigLIP (57% accuracy improvement over FashionCLIP) |
| Attributes    | Dark hoodie, face mask, gloves, uniforms (Amazon, FedEx, UPS)   |

### brisque-quality

**Purpose:** No-reference image quality assessment.

| Specification | Value                                                |
| ------------- | ---------------------------------------------------- |
| Library       | piq (Photosynthesis Image Quality)                   |
| VRAM          | 0 MB (CPU-based)                                     |
| Use Cases     | Camera obstruction, motion blur, quality degradation |

### vehicle-segment-classification

**Purpose:** Detailed vehicle type classification beyond YOLO26v2.

| Specification | Value                                                                                                                                      |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Path          | `{MODEL_ZOO_PATH}/vehicle-segment-classification`                                                                                          |
| VRAM          | ~1500 MB                                                                                                                                   |
| Architecture  | ResNet-50                                                                                                                                  |
| Classes (11)  | car, pickup_truck, single_unit_truck, articulated_truck, bus, motorcycle, bicycle, work_van, non_motorized_vehicle, pedestrian, background |
| Training Data | MIO-TCD Traffic Dataset (50K images)                                                                                                       |

### vehicle-damage-detection

**Purpose:** Vehicle damage segmentation for security context.

| Specification | Value                                                           |
| ------------- | --------------------------------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/vehicle-damage-detection`                     |
| VRAM          | ~2000 MB                                                        |
| Architecture  | YOLOv11x-seg                                                    |
| Classes (6)   | cracks, dents, glass_shatter, lamp_broken, scratches, tire_flat |
| Security Note | glass_shatter + lamp_broken at night = suspicious (break-in)    |

### pet-classifier

**Purpose:** Dog/cat classification for false positive reduction.

| Specification | Value                                |
| ------------- | ------------------------------------ |
| Path          | `{MODEL_ZOO_PATH}/pet-classifier`    |
| VRAM          | ~200 MB (very lightweight ResNet-18) |
| Trigger       | Animal detection (cat, dog)          |
| Output        | dog / cat classification             |

### osnet-x0-25

**Purpose:** Person re-identification embeddings across cameras.

| Specification | Value                          |
| ------------- | ------------------------------ |
| Path          | `{MODEL_ZOO_PATH}/osnet-x0-25` |
| VRAM          | ~100 MB (very lightweight)     |
| Output        | 512-dimensional embeddings     |

### threat-detection-yolov8n

**Purpose:** Weapon and threatening object detection.

| Specification | Value                                        |
| ------------- | -------------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/threat-detection-yolov8n`  |
| VRAM          | ~300 MB                                      |
| Trigger       | Suspicious activity detected                 |
| Output        | Weapon detections (knives, guns, bats, etc.) |

### vit-age-classifier

**Purpose:** Age estimation from face/person crops.

| Specification | Value                                                    |
| ------------- | -------------------------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/vit-age-classifier`                    |
| VRAM          | ~200 MB                                                  |
| Classes       | child, teenager, young_adult, adult, middle_aged, senior |

### vit-gender-classifier

**Purpose:** Gender classification from face/person crops.

| Specification | Value                                    |
| ------------- | ---------------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/vit-gender-classifier` |
| VRAM          | ~200 MB                                  |
| Classes       | male / female                            |

### yolov8n-pose

**Purpose:** Alternative pose estimation model.

| Specification | Value                           |
| ------------- | ------------------------------- |
| Path          | `{MODEL_ZOO_PATH}/yolov8n-pose` |
| VRAM          | ~200 MB (lightweight)           |
| Use Case      | Backup when ViTPose unavailable |

---

## Benchmark Methodology

### Running Benchmarks

```bash
# Run full model zoo benchmark
uv run python scripts/benchmark_model_zoo.py

# Test specific model
uv run python scripts/benchmark_model_zoo.py --model weather-classification
```

### Success Criteria

| Criteria           | Target   | Description                       |
| ------------------ | -------- | --------------------------------- |
| Max VRAM per model | <1500 MB | Must fit in Model Zoo VRAM budget |
| Max load time      | <5s      | Quick loading for on-demand use   |
| VRAM recovered     | Yes      | Clean unload without memory leaks |

---

## Related Documentation

- [Model Zoo Service](../../ai/model-zoo.md) - Service architecture
- [AI Orchestration](../../architecture/ai-orchestration/model-zoo.md) - Orchestration patterns
- [YOLO26 Performance](../reference/benchmarks/yolo26-performance.md) - Primary detection model
- [Multi-GPU Configuration](../development/multi-gpu.md) - GPU assignment strategies
