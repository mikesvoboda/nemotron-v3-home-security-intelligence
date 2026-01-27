# Model Zoo Prompt Improvements Design

**Date:** 2026-01-19
**Status:** Draft
**Author:** maui + Mike Svoboda

## Executive Summary

This design improves the context provided to Nemotron for risk assessment by:

1. Optimizing prompts for existing models (Florence-2, CLIP, FashionCLIP)
2. Adding new high-value models with on-demand loading
3. Implementing intelligent model orchestration based on detection context

**Constraints:**

- 24GB GPU total
- Nemotron is CPU-offloaded
- Latency for model loading is acceptable if it adds value

**Key Architecture Decision:** Option A — Internal on-demand loading within the existing `ai-enrichment` container. This preserves the current container structure while gaining VRAM efficiency.

---

## Current Architecture

### Container Structure (docker-compose.prod.yml)

The system runs 5 GPU-enabled AI containers:

| Service           | Port | Models                           | VRAM          | Loading                                   |
| ----------------- | ---- | -------------------------------- | ------------- | ----------------------------------------- |
| **ai-yolo26**     | 8090 | YOLO26                           | ~650MB        | Always                                    |
| **ai-llm**        | 8091 | Nemotron 30B                     | CPU-offloaded | Always                                    |
| **ai-florence**   | 8092 | Florence-2-large                 | ~1.2GB        | Always                                    |
| **ai-clip**       | 8093 | CLIP ViT-L/14                    | ~800MB        | Always                                    |
| **ai-enrichment** | 8094 | Vehicle, Pet, FashionCLIP, Depth | ~2.65GB       | **Currently always, moving to on-demand** |

### Current ai-enrichment Models (all load at startup)

```yaml
# docker-compose.prod.yml:207-210
- VEHICLE_MODEL_PATH=/models/vehicle-segment-classification # ~1.5GB
- PET_MODEL_PATH=/models/pet-classifier # ~200MB
- CLOTHING_MODEL_PATH=/models/fashion-clip # ~800MB
- DEPTH_MODEL_PATH=/models/depth-anything-v2-small # ~150MB
```

**Problem:** All 4 models load at startup (~2.65GB), but each only runs when specific detection types occur.

---

## Proposed Architecture

### VRAM Allocation

```
┌─────────────────────────────────────────────────────────────┐
│                    Always Loaded (~2.65GB)                  │
├─────────────────────────────────────────────────────────────┤
│     YOLO26     │     Florence-2     │       CLIP        │
│      ~650MB       │       ~1.2GB       │      ~800MB       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│          On-Demand Pool in ai-enrichment (~6.8GB)           │
├──────────┬────────┬───────┬───────┬────────┬────────┬──────┤
│FashionCLIP│Vehicle│ Depth │  Pet  │  Pose  │ Threat │Age-Gen│
│  ~800MB  │ ~1.5GB │~150MB │~200MB │ ~300MB │ ~400MB │~500MB │
│ (person) │  (car) │(prox.)│(animal)│(person)│(person)│(face) │
├──────────┴────────┴───────┴───────┴────────┴────────┴──────┤
│           ReID (~100MB)  │  X-CLIP (~1.5GB, suspicious)     │
└──────────────────────────┴──────────────────────────────────┘
```

### Model Loading Triggers

| Model           | VRAM   | Trigger                         | Load Time |
| --------------- | ------ | ------------------------------- | --------- |
| **FashionCLIP** | ~800MB | Person detected                 | ~3s       |
| **Vehicle**     | ~1.5GB | Car/truck/vehicle detected      | ~4s       |
| **Depth**       | ~150MB | Any detection needing proximity | ~2s       |
| **Pet**         | ~200MB | Animal detected                 | ~2s       |
| **Pose**        | ~300MB | Person detected                 | ~2s       |
| **Threat**      | ~400MB | Person detected                 | ~3s       |
| **Age-Gender**  | ~500MB | Face visible in detection       | ~3s       |
| **ReID**        | ~100MB | Person detected                 | ~1s       |
| **X-CLIP**      | ~1.5GB | Suspicious activity flagged     | ~5s       |

### Typical Loading Scenarios

| Detection Type        | Models Loaded                              | Total VRAM |
| --------------------- | ------------------------------------------ | ---------- |
| Person (no face)      | FashionCLIP + Pose + Threat + ReID + Depth | ~1.75GB    |
| Person (face visible) | Above + Age-Gender                         | ~2.25GB    |
| Person (suspicious)   | Above + X-CLIP                             | ~3.75GB    |
| Vehicle               | Vehicle + Depth                            | ~1.65GB    |
| Animal                | Pet + Depth                                | ~350MB     |

With ~6.8GB headroom, all scenarios fit comfortably with room to spare.

---

## Part 1: Prompt Improvements for Existing Models

### 1.1 Florence-2 Task Selection Improvements

**Current State:**

- Using `<CAPTION>` as default
- `<DENSE_REGION_CAPTION>` for regions
- `<OCR>` for text extraction

**Proposed Changes:**

| Task              | Current                  | Proposed                      | Rationale                                  |
| ----------------- | ------------------------ | ----------------------------- | ------------------------------------------ |
| Scene description | `<CAPTION>`              | `<MORE_DETAILED_CAPTION>`     | 2-3x more detail, identifies brands/models |
| Object detection  | `<OD>`                   | `<OPEN_VOCABULARY_DETECTION>` | Custom security-relevant objects           |
| Region analysis   | `<DENSE_REGION_CAPTION>` | Keep                          | Already optimal                            |
| Text extraction   | `<OCR>`                  | `<OCR_WITH_REGION>`           | Adds spatial context                       |

**New Security-Focused Object Detection:**

```python
SECURITY_OBJECTS = "person. face. vehicle. car. truck. van. package. box. bag. backpack. weapon. knife. tool. crowbar. flashlight. animal. dog. cat."
```

**Implementation:**

```python
# In florence_client.py or vision_extractor.py
async def extract_security_context(self, image: bytes) -> dict:
    results = {}

    # 1. Rich scene description
    results["scene"] = await self.extract(image, "<MORE_DETAILED_CAPTION>")

    # 2. Security-relevant object detection
    results["security_objects"] = await self.extract(
        image,
        "<OPEN_VOCABULARY_DETECTION>",
        text_input=SECURITY_OBJECTS
    )

    # 3. Text with locations (plates, signs)
    results["text_regions"] = await self.extract(image, "<OCR_WITH_REGION>")

    return results
```

**Expected Impact:**

- Scene descriptions: 2-3x more detail
- Object detection: Catches packages, bags, tools not in YOLO26 classes
- OCR: Spatial context for license plate locations

---

### 1.2 CLIP/FashionCLIP Prompt Engineering

**Current State (ai/enrichment/model.py:494-519):**

```python
SECURITY_CLOTHING_PROMPTS = [
    "person wearing dark hoodie",
    "person wearing face mask",
    "delivery uniform",
    # ... 19 total prompts
]
```

**Problems:**

1. No camera context (trained on product images, not surveillance)
2. No prompt ensembling (single prompt per category)
3. Coarse categories (no granular colors, no carrying items)

**Proposed Prompt Templates:**

```python
# Surveillance-context templates for ensembling
SURVEILLANCE_TEMPLATES = [
    "a surveillance camera photo of {}",
    "CCTV footage showing {}",
    "a security camera image of {}",
    "a low resolution photo of {}",
    "a distant shot of {}",
]

# Expanded clothing categories with granular attributes
ENHANCED_CLOTHING_PROMPTS = {
    # Suspicious attire - expanded with colors
    "suspicious": [
        "person wearing black hoodie with hood up",
        "person wearing dark hoodie covering face",
        "person in ski mask or balaclava",
        "person wearing face covering at night",
        "person in all black clothing",
        "person with face obscured by hat and sunglasses",
        "person wearing gloves in warm weather",
    ],

    # Service uniforms - more specific
    "delivery": [
        "Amazon delivery driver in blue vest",
        "FedEx courier in purple uniform",
        "UPS driver in brown uniform",
        "USPS mail carrier in blue uniform",
        "DoorDash delivery person with red bag",
        "food delivery courier with insulated bag",
    ],

    # Utility workers
    "utility": [
        "utility worker in orange high-visibility vest",
        "construction worker in yellow safety vest",
        "electrician in work clothes with tool belt",
        "cable technician in company uniform",
        "landscaper in work clothes",
    ],

    # Carrying items - NEW CATEGORY
    "carrying": [
        "person carrying a large box or package",
        "person with a backpack",
        "person carrying a duffel bag",
        "person holding tools",
        "person carrying nothing",
        "person with hands in pockets",
    ],

    # Normal attire - for contrast
    "casual": [
        "person in casual everyday clothes",
        "person in business casual attire",
        "person in athletic or exercise clothing",
        "person dressed for outdoor activities",
    ],
}
```

**Prompt Ensembling Implementation:**

```python
class EnhancedClothingClassifier:
    """FashionCLIP with prompt ensembling for improved accuracy."""

    def __init__(self, ...):
        self.surveillance_templates = SURVEILLANCE_TEMPLATES
        self.clothing_prompts = ENHANCED_CLOTHING_PROMPTS
        self._precomputed_embeddings: dict[str, torch.Tensor] = {}

    def precompute_embeddings(self) -> None:
        """Precompute averaged embeddings for all prompt categories."""
        for category, prompts in self.clothing_prompts.items():
            category_embeddings = []
            for prompt in prompts:
                # Ensemble across surveillance templates
                template_embeddings = []
                for template in self.surveillance_templates:
                    full_prompt = template.format(prompt)
                    embedding = self.model.encode_text(self.tokenizer([full_prompt]))
                    template_embeddings.append(embedding)

                # Average across templates
                avg_template = torch.stack(template_embeddings).mean(dim=0)
                category_embeddings.append(avg_template)

            # Store averaged embeddings per category
            self._precomputed_embeddings[category] = torch.stack(category_embeddings)

    def classify(self, image: Image.Image) -> dict[str, Any]:
        """Classify using precomputed ensembled embeddings."""
        image_features = self.model.encode_image(self.preprocess(image))
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        results = {}
        for category, embeddings in self._precomputed_embeddings.items():
            # Normalize embeddings
            embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)

            # Compute similarities
            similarities = (image_features @ embeddings.T).softmax(dim=-1)
            top_idx = similarities.argmax().item()

            results[category] = {
                "top_match": self.clothing_prompts[category][top_idx],
                "confidence": float(similarities[0, top_idx]),
                "all_scores": {
                    p: float(s) for p, s in
                    zip(self.clothing_prompts[category], similarities[0].tolist())
                }
            }

        return results
```

**Expected Impact:**

- Classification accuracy: +5-10% from surveillance context
- +3-5% from prompt ensembling
- New "carrying" category provides critical context
- Granular colors enable better re-identification

---

### 1.3 Nemotron Prompt Formatting Improvements

**Current State (backend/services/prompts.py):**
Enrichment data is formatted into sections, but some context is lost or under-utilized.

**Proposed Enhancements:**

```python
def format_enhanced_clothing_context(clothing_result: dict) -> str:
    """Format enhanced clothing analysis for Nemotron."""
    lines = ["### Person Appearance Analysis"]

    # Primary classification
    if clothing_result.get("suspicious"):
        susp = clothing_result["suspicious"]
        if susp["confidence"] > 0.6:
            lines.append(f"- **ALERT**: {susp['top_match']} (confidence: {susp['confidence']:.0%})")

    # Service uniform detection
    if clothing_result.get("delivery"):
        deliv = clothing_result["delivery"]
        if deliv["confidence"] > 0.5:
            lines.append(f"- Service worker identified: {deliv['top_match']} ({deliv['confidence']:.0%})")

    # Carrying items - critical for risk assessment
    if clothing_result.get("carrying"):
        carry = clothing_result["carrying"]
        lines.append(f"- Carrying: {carry['top_match']} ({carry['confidence']:.0%})")

    # General attire
    if clothing_result.get("casual"):
        casual = clothing_result["casual"]
        lines.append(f"- General attire: {casual['top_match']}")

    return "\n".join(lines)


def format_florence_scene_context(florence_result: dict) -> str:
    """Format Florence-2 enhanced extraction for Nemotron."""
    lines = ["### Scene Analysis (Florence-2)"]

    # Detailed scene description
    if florence_result.get("scene"):
        lines.append(f"\n**Scene Description:**\n{florence_result['scene']}")

    # Security-relevant objects detected
    if florence_result.get("security_objects"):
        objects = florence_result["security_objects"]
        if objects.get("labels"):
            lines.append(f"\n**Objects Detected:** {', '.join(objects['labels'])}")

            # Flag high-risk objects
            high_risk = {"weapon", "knife", "crowbar", "tool"}
            detected_risks = [o for o in objects["labels"] if any(r in o.lower() for r in high_risk)]
            if detected_risks:
                lines.append(f"- **HIGH RISK OBJECTS**: {', '.join(detected_risks)}")

    # Text/plates found
    if florence_result.get("text_regions"):
        texts = florence_result["text_regions"]
        if texts.get("labels"):
            lines.append(f"\n**Visible Text:** {', '.join(texts['labels'])}")

    return "\n".join(lines)
```

---

## Part 2: On-Demand Model Loading Architecture

### 2.1 Architecture Decision: Option A

**Chosen Approach:** Modify the existing `ai-enrichment` service (`ai/enrichment/model.py`) to load/unload models on-demand internally.

**Why Option A:**

- Preserves existing container structure (no docker-compose changes for model loading)
- Single code change location (`ai/enrichment/model.py`)
- Least disruptive to current deployment
- Backend continues to call same HTTP endpoints

**Alternatives Considered:**

- Option B (Split Containers): More complex orchestration, requires Docker API calls
- Option C (Unified Model Manager): Bigger refactor, new container needed

### 2.2 VRAM Budget

| Category           | Models                      | VRAM          | Loading       |
| ------------------ | --------------------------- | ------------- | ------------- |
| **Always Loaded**  | YOLO26, Florence-2, CLIP    | ~2.65GB       | Startup       |
| **On-Demand Pool** | All enrichment + new models | ~6.8GB budget | Per-detection |

### 2.3 Models in On-Demand Pool

**Existing Models (moved from always-loaded):**

| Model              | VRAM   | Trigger          | Currently In  |
| ------------------ | ------ | ---------------- | ------------- |
| FashionCLIP        | ~800MB | Person detected  | ai-enrichment |
| Vehicle Classifier | ~1.5GB | Vehicle detected | ai-enrichment |
| Pet Classifier     | ~200MB | Animal detected  | ai-enrichment |
| Depth Anything V2  | ~150MB | Any detection    | ai-enrichment |

**New Models (to add):**

| Model                    | VRAM   | Trigger         | Context Provided                               |
| ------------------------ | ------ | --------------- | ---------------------------------------------- |
| YOLOv8n-pose             | ~300MB | Person detected | Body posture (crouching, bending, arms raised) |
| Threat-Detection-YOLOv8n | ~400MB | Person detected | Weapons (gun 96.7%, knife 86.5%)               |
| Age-Gender               | ~500MB | Face visible    | Demographics (age group, gender)               |
| OSNet-x0.25              | ~100MB | Person detected | 512-dim re-identification embedding            |
| X-CLIP                   | ~1.5GB | Suspicious flag | Zero-shot action classification                |

### 2.4 Changes to ai-enrichment Service

#### Current Startup (ai/enrichment/model.py:1220-1310)

```python
# CURRENT: All models load at startup
@asynccontextmanager
async def lifespan(_app: FastAPI):
    global vehicle_classifier, pet_classifier, clothing_classifier, depth_estimator

    # These all load immediately, using ~2.65GB VRAM
    vehicle_classifier = VehicleClassifier(...)
    vehicle_classifier.load_model()  # ~1.5GB

    pet_classifier = PetClassifier(...)
    pet_classifier.load_model()  # ~200MB

    clothing_classifier = ClothingClassifier(...)
    clothing_classifier.load_model()  # ~800MB

    depth_estimator = DepthEstimator(...)
    depth_estimator.load_model()  # ~150MB

    yield
```

#### Proposed Startup (on-demand)

```python
# PROPOSED: Only ModelManager initializes at startup
@asynccontextmanager
async def lifespan(_app: FastAPI):
    global model_manager

    # Initialize model manager with VRAM budget
    model_manager = OnDemandModelManager(
        vram_budget_mb=6800,  # 6.8GB budget
        device="cuda:0",
    )

    # Register all models (but don't load yet)
    model_manager.register_model(ModelSpec(
        name="clothing",
        vram_mb=800,
        priority=ModelPriority.HIGH,
        loader=lambda: ClothingClassifier("/models/fashion-clip").load_model(),
        unloader=lambda m: _unload_model(m),
        triggers=["person"],
    ))

    model_manager.register_model(ModelSpec(
        name="vehicle",
        vram_mb=1500,
        priority=ModelPriority.MEDIUM,
        loader=lambda: VehicleClassifier("/models/vehicle-segment-classification").load_model(),
        unloader=lambda m: _unload_model(m),
        triggers=["car", "truck", "vehicle", "motorcycle", "bus"],
    ))

    model_manager.register_model(ModelSpec(
        name="pet",
        vram_mb=200,
        priority=ModelPriority.MEDIUM,
        loader=lambda: PetClassifier("/models/pet-classifier").load_model(),
        unloader=lambda m: _unload_model(m),
        triggers=["dog", "cat", "animal"],
    ))

    model_manager.register_model(ModelSpec(
        name="depth",
        vram_mb=150,
        priority=ModelPriority.LOW,
        loader=lambda: DepthEstimator("/models/depth-anything-v2-small").load_model(),
        unloader=lambda m: _unload_model(m),
        triggers=["person", "vehicle", "animal"],  # Any detection
    ))

    # NEW MODELS
    model_manager.register_model(ModelSpec(
        name="pose",
        vram_mb=300,
        priority=ModelPriority.HIGH,
        loader=lambda: PoseEstimator("/models/yolov8n-pose").load_model(),
        unloader=lambda m: _unload_model(m),
        triggers=["person"],
    ))

    model_manager.register_model(ModelSpec(
        name="threat",
        vram_mb=400,
        priority=ModelPriority.CRITICAL,  # Always load first
        loader=lambda: ThreatDetector("/models/threat-yolov8n").load_model(),
        unloader=lambda m: _unload_model(m),
        triggers=["person"],
    ))

    model_manager.register_model(ModelSpec(
        name="age_gender",
        vram_mb=500,
        priority=ModelPriority.HIGH,
        loader=lambda: AgeGenderPredictor("/models/age-gender").load_model(),
        unloader=lambda m: _unload_model(m),
        triggers=["face"],
    ))

    model_manager.register_model(ModelSpec(
        name="reid",
        vram_mb=100,
        priority=ModelPriority.MEDIUM,
        loader=lambda: PersonReidentifier("/models/osnet").load_model(),
        unloader=lambda m: _unload_model(m),
        triggers=["person"],
    ))

    model_manager.register_model(ModelSpec(
        name="action",
        vram_mb=1500,
        priority=ModelPriority.LOW,  # Only for suspicious
        loader=lambda: ActionRecognizer("microsoft/xclip-base-patch16-zero-shot").load_model(),
        unloader=lambda m: _unload_model(m),
        triggers=["suspicious"],
    ))

    # Start idle cleanup task
    asyncio.create_task(model_manager.periodic_cleanup(idle_seconds=300))

    yield

    # Cleanup all loaded models
    await model_manager.unload_all()
```

### 2.5 New API Endpoint: Unified Enrichment

```python
# New endpoint that handles all enrichment in one call
class EnrichRequest(BaseModel):
    """Request for unified enrichment endpoint."""
    image: str = Field(..., description="Base64 encoded image")
    detection_type: str = Field(..., description="Type: person, vehicle, animal")
    bbox: list[float] = Field(..., description="Bounding box [x1, y1, x2, y2]")
    face_visible: bool = Field(default=False)
    suspicious_score: float = Field(default=0.0)
    frames_buffer: list[str] | None = Field(default=None, description="For action recognition")


class EnrichResponse(BaseModel):
    """Response with all enrichment results."""
    clothing: dict | None = None
    vehicle: dict | None = None
    pet: dict | None = None
    depth: dict | None = None
    pose: dict | None = None
    threat: dict | None = None
    demographics: dict | None = None
    reid_embedding: list[float] | None = None
    action: dict | None = None
    models_loaded: list[str] = Field(default_factory=list)
    inference_time_ms: float


@app.post("/enrich", response_model=EnrichResponse)
async def enrich(request: EnrichRequest) -> EnrichResponse:
    """Unified enrichment endpoint with on-demand model loading."""
    start_time = time.perf_counter()

    # Determine which models to load based on detection context
    models = await model_manager.get_models_for_detection(
        detection_type=request.detection_type,
        face_visible=request.face_visible,
        suspicious=request.suspicious_score > 50,
    )

    # Decode and crop image
    image = decode_and_crop_image(request.image, request.bbox)

    result = EnrichResponse(models_loaded=list(models.keys()))

    # Run appropriate enrichments based on loaded models
    if "clothing" in models:
        result.clothing = models["clothing"].classify(image)

    if "vehicle" in models:
        result.vehicle = models["vehicle"].classify(image)

    if "pet" in models:
        result.pet = models["pet"].classify(image)

    if "depth" in models:
        full_image = decode_and_crop_image(request.image)  # Full image for depth
        result.depth = models["depth"].estimate_object_distance(full_image, request.bbox)

    if "pose" in models:
        result.pose = models["pose"].estimate(image)

    if "threat" in models:
        result.threat = models["threat"].detect(image)

    if "age_gender" in models:
        # Extract face region
        face_crop = extract_face_crop(image, request.bbox)
        result.demographics = models["age_gender"].predict(face_crop)

    if "reid" in models:
        result.reid_embedding = models["reid"].get_embedding(image)

    if "action" in models and request.frames_buffer:
        frames = [decode_image(f) for f in request.frames_buffer]
        result.action = models["action"].classify_action(frames)

    result.inference_time_ms = (time.perf_counter() - start_time) * 1000
    return result
```

### 2.6 Model Manager Implementation

```python
# backend/services/model_manager.py

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable
import torch
import asyncio
from collections import OrderedDict
import time


class ModelPriority(Enum):
    """Priority levels for model loading decisions."""
    CRITICAL = 1    # Weapons detection
    HIGH = 2        # Pose, demographics
    MEDIUM = 3      # Re-identification
    LOW = 4         # Action recognition (only if suspicious)


@dataclass
class ModelSpec:
    """Specification for an on-demand model."""
    name: str
    vram_mb: int
    priority: ModelPriority
    loader: Callable[[], Any]  # Function to load the model
    unloader: Callable[[Any], None]  # Function to unload
    triggers: list[str]  # Detection types that trigger loading


class OnDemandModelManager:
    """Manages on-demand model loading with VRAM constraints."""

    def __init__(
        self,
        vram_budget_mb: int = 3500,  # 3.5GB default
        device: str = "cuda:0",
    ):
        self.vram_budget_mb = vram_budget_mb
        self.device = device
        self.loaded_models: OrderedDict[str, tuple[Any, int, float]] = OrderedDict()  # name -> (model, vram, last_used)
        self.model_specs: dict[str, ModelSpec] = {}
        self._lock = asyncio.Lock()

    def register_model(self, spec: ModelSpec) -> None:
        """Register a model specification."""
        self.model_specs[spec.name] = spec

    def get_current_vram_usage(self) -> int:
        """Get current VRAM usage of loaded on-demand models."""
        return sum(vram for _, vram, _ in self.loaded_models.values())

    async def get_model(self, name: str) -> Any:
        """Get a model, loading it if necessary."""
        async with self._lock:
            # Already loaded - update last_used and return
            if name in self.loaded_models:
                model, vram, _ = self.loaded_models[name]
                self.loaded_models[name] = (model, vram, time.time())
                self.loaded_models.move_to_end(name)  # LRU update
                return model

            spec = self.model_specs.get(name)
            if not spec:
                raise ValueError(f"Unknown model: {name}")

            # Check if we need to evict models
            await self._ensure_vram_available(spec.vram_mb)

            # Load the model
            model = await asyncio.to_thread(spec.loader)
            self.loaded_models[name] = (model, spec.vram_mb, time.time())

            return model

    async def _ensure_vram_available(self, required_mb: int) -> None:
        """Evict models if necessary to free VRAM."""
        current = self.get_current_vram_usage()

        while current + required_mb > self.vram_budget_mb:
            if not self.loaded_models:
                raise RuntimeError(
                    f"Cannot load model requiring {required_mb}MB - "
                    f"budget is {self.vram_budget_mb}MB"
                )

            # Evict least recently used (first item in OrderedDict)
            oldest_name = next(iter(self.loaded_models))
            await self.unload_model(oldest_name)
            current = self.get_current_vram_usage()

    async def unload_model(self, name: str) -> None:
        """Explicitly unload a model."""
        if name not in self.loaded_models:
            return

        model, vram, _ = self.loaded_models.pop(name)
        spec = self.model_specs[name]

        # Run unloader
        await asyncio.to_thread(spec.unloader, model)

        # Clear CUDA cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    async def get_models_for_detection(
        self,
        detection_type: str,
        face_visible: bool = False,
        suspicious: bool = False,
    ) -> dict[str, Any]:
        """Load appropriate models based on detection context."""
        models_to_load = []

        for name, spec in self.model_specs.items():
            if detection_type in spec.triggers:
                # Skip age-gender if no face
                if name == "age-gender" and not face_visible:
                    continue
                # Skip X-CLIP unless suspicious
                if name == "x-clip" and not suspicious:
                    continue
                models_to_load.append((spec.priority.value, name))

        # Sort by priority
        models_to_load.sort()

        # Load models in priority order
        loaded = {}
        for _, name in models_to_load:
            try:
                loaded[name] = await self.get_model(name)
            except RuntimeError:
                # Out of VRAM - stop loading lower priority models
                break

        return loaded

    async def cleanup_idle_models(self, idle_seconds: float = 300) -> None:
        """Unload models that haven't been used recently."""
        now = time.time()
        to_unload = []

        for name, (_, _, last_used) in self.loaded_models.items():
            if now - last_used > idle_seconds:
                to_unload.append(name)

        for name in to_unload:
            await self.unload_model(name)
```

### 2.4 Model Loader Implementations

```python
# backend/services/model_loaders.py

import torch
from pathlib import Path


class PoseEstimator:
    """YOLOv8n-pose wrapper for body posture detection."""

    def __init__(self, model_path: str, device: str = "cuda:0"):
        self.model_path = model_path
        self.device = device
        self.model = None

    def load(self) -> "PoseEstimator":
        from ultralytics import YOLO
        self.model = YOLO(self.model_path)
        self.model.to(self.device)
        return self

    def unload(self) -> None:
        if self.model:
            del self.model
            self.model = None

    def estimate(self, image) -> dict:
        """Extract pose keypoints and classify posture."""
        results = self.model(image, verbose=False)[0]

        poses = []
        for i, keypoints in enumerate(results.keypoints.xy):
            pose_data = {
                "keypoints": keypoints.cpu().numpy().tolist(),
                "confidence": float(results.keypoints.conf[i].mean()) if results.keypoints.conf is not None else 1.0,
            }

            # Classify posture from keypoints
            pose_data["posture"] = self._classify_posture(keypoints)
            poses.append(pose_data)

        return {"poses": poses}

    def _classify_posture(self, keypoints) -> str:
        """Classify body posture from keypoints."""
        # Keypoint indices: 0=nose, 5=left_shoulder, 6=right_shoulder,
        # 11=left_hip, 12=right_hip, 15=left_ankle, 16=right_ankle

        if len(keypoints) < 17:
            return "unknown"

        # Get key points
        nose = keypoints[0]
        shoulders = (keypoints[5] + keypoints[6]) / 2
        hips = (keypoints[11] + keypoints[12]) / 2
        ankles = (keypoints[15] + keypoints[16]) / 2

        # Calculate angles and positions
        torso_angle = self._angle_from_vertical(shoulders, hips)

        # Crouching: hips close to ankles, torso bent
        hip_ankle_dist = torch.norm(hips - ankles)
        shoulder_hip_dist = torch.norm(shoulders - hips)

        if hip_ankle_dist < shoulder_hip_dist * 0.5:
            return "crouching"

        if torso_angle > 45:
            return "bending_over"

        # Arms raised: wrists above shoulders
        left_wrist = keypoints[9]
        right_wrist = keypoints[10]
        if left_wrist[1] < shoulders[1] or right_wrist[1] < shoulders[1]:
            return "arms_raised"

        return "standing"

    def _angle_from_vertical(self, top, bottom) -> float:
        """Calculate angle from vertical in degrees."""
        diff = bottom - top
        angle = torch.atan2(diff[0], diff[1]) * 180 / 3.14159
        return abs(float(angle))


class ThreatDetector:
    """YOLOv8n threat detection for weapons."""

    THREAT_CLASSES = ["gun", "knife", "grenade", "explosive"]

    def __init__(self, model_path: str, device: str = "cuda:0"):
        self.model_path = model_path
        self.device = device
        self.model = None

    def load(self) -> "ThreatDetector":
        from ultralytics import YOLO
        self.model = YOLO(self.model_path)
        self.model.to(self.device)
        return self

    def unload(self) -> None:
        if self.model:
            del self.model
            self.model = None

    def detect(self, image) -> dict:
        """Detect weapons in image."""
        results = self.model(image, verbose=False)[0]

        threats = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])

            if conf > 0.5:  # Confidence threshold
                threats.append({
                    "type": self.model.names[cls_id],
                    "confidence": conf,
                    "bbox": box.xyxy[0].cpu().numpy().tolist(),
                })

        return {
            "threats_detected": len(threats) > 0,
            "threats": threats,
            "highest_threat": max(threats, key=lambda x: x["confidence"]) if threats else None,
        }


class AgeGenderPredictor:
    """Age and gender prediction from face crops."""

    def __init__(self, model_path: str, device: str = "cuda:0"):
        self.model_path = model_path
        self.device = device
        self.model = None
        self.processor = None

    def load(self) -> "AgeGenderPredictor":
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        self.processor = AutoImageProcessor.from_pretrained(self.model_path)
        self.model = AutoModelForImageClassification.from_pretrained(self.model_path)
        self.model.to(self.device)
        self.model.eval()
        return self

    def unload(self) -> None:
        if self.model:
            del self.model
            del self.processor
            self.model = None
            self.processor = None

    def predict(self, face_image) -> dict:
        """Predict age and gender from face image."""
        inputs = self.processor(images=face_image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits

        # Parse model output (depends on specific model)
        # This is a placeholder - actual implementation depends on model
        predicted_class = logits.argmax(-1).item()

        return {
            "age_group": self._get_age_group(predicted_class),
            "gender": self._get_gender(predicted_class),
            "confidence": float(torch.softmax(logits, dim=-1).max()),
        }

    def _get_age_group(self, class_id: int) -> str:
        # Map class to age group - depends on model
        age_groups = ["child", "teenager", "young_adult", "adult", "middle_aged", "senior"]
        return age_groups[class_id % len(age_groups)]

    def _get_gender(self, class_id: int) -> str:
        return "male" if class_id % 2 == 0 else "female"


class PersonReidentifier:
    """OSNet for person re-identification embeddings."""

    def __init__(self, model_path: str, device: str = "cuda:0"):
        self.model_path = model_path
        self.device = device
        self.model = None

    def load(self) -> "PersonReidentifier":
        # OSNet loading - may need torchreid or custom loading
        from torchreid import models
        self.model = models.build_model(
            name="osnet_x0_25",
            num_classes=1000,  # Pretrained
            pretrained=True,
        )
        self.model.to(self.device)
        self.model.eval()
        return self

    def unload(self) -> None:
        if self.model:
            del self.model
            self.model = None

    def get_embedding(self, person_crop) -> list[float]:
        """Extract 512-dim re-identification embedding."""
        from torchvision import transforms

        transform = transforms.Compose([
            transforms.Resize((256, 128)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        tensor = transform(person_crop).unsqueeze(0).to(self.device)

        with torch.no_grad():
            embedding = self.model(tensor)

        return embedding[0].cpu().numpy().tolist()


class ActionRecognizer:
    """X-CLIP for zero-shot action recognition."""

    SECURITY_ACTIONS = [
        "person walking normally",
        "person running",
        "person sneaking or creeping",
        "person climbing over fence",
        "person breaking window",
        "person picking lock",
        "person looking through window",
        "person hiding",
        "person fighting",
        "person falling down",
        "person carrying heavy object",
        "person using tool on door",
    ]

    def __init__(self, model_path: str, device: str = "cuda:0"):
        self.model_path = model_path
        self.device = device
        self.model = None
        self.processor = None

    def load(self) -> "ActionRecognizer":
        from transformers import XCLIPProcessor, XCLIPModel

        self.processor = XCLIPProcessor.from_pretrained(self.model_path)
        self.model = XCLIPModel.from_pretrained(self.model_path)
        self.model.to(self.device)
        self.model.eval()
        return self

    def unload(self) -> None:
        if self.model:
            del self.model
            del self.processor
            self.model = None
            self.processor = None

    def classify_action(self, frames: list, custom_actions: list[str] | None = None) -> dict:
        """Classify action from video frames."""
        actions = custom_actions or self.SECURITY_ACTIONS

        inputs = self.processor(
            text=actions,
            videos=frames,
            return_tensors="pt",
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits_per_video
            probs = logits.softmax(dim=-1)[0]

        # Get top actions
        top_indices = probs.argsort(descending=True)[:3]

        return {
            "top_action": actions[top_indices[0]],
            "confidence": float(probs[top_indices[0]]),
            "all_scores": {
                actions[i]: float(probs[i]) for i in top_indices
            },
        }
```

### 2.5 Integration with Enrichment Pipeline

```python
# backend/services/enhanced_enrichment_pipeline.py

from backend.services.model_manager import OnDemandModelManager, ModelSpec, ModelPriority
from backend.services.model_loaders import (
    PoseEstimator, ThreatDetector, AgeGenderPredictor,
    PersonReidentifier, ActionRecognizer
)


class EnhancedEnrichmentPipeline:
    """Enrichment pipeline with on-demand model loading."""

    def __init__(self, model_manager: OnDemandModelManager):
        self.model_manager = model_manager
        self._register_models()

    def _register_models(self) -> None:
        """Register all on-demand models."""

        # Pose estimation
        pose = PoseEstimator("/models/yolov8n-pose")
        self.model_manager.register_model(ModelSpec(
            name="pose",
            vram_mb=300,
            priority=ModelPriority.HIGH,
            loader=pose.load,
            unloader=lambda m: m.unload(),
            triggers=["person"],
        ))

        # Threat detection
        threat = ThreatDetector("/models/threat-yolov8n")
        self.model_manager.register_model(ModelSpec(
            name="threat",
            vram_mb=400,
            priority=ModelPriority.CRITICAL,
            loader=threat.load,
            unloader=lambda m: m.unload(),
            triggers=["person"],
        ))

        # Age-gender
        age_gender = AgeGenderPredictor("/models/age-gender")
        self.model_manager.register_model(ModelSpec(
            name="age-gender",
            vram_mb=500,
            priority=ModelPriority.HIGH,
            loader=age_gender.load,
            unloader=lambda m: m.unload(),
            triggers=["person", "face"],
        ))

        # Re-identification
        reid = PersonReidentifier("/models/osnet")
        self.model_manager.register_model(ModelSpec(
            name="reid",
            vram_mb=100,
            priority=ModelPriority.MEDIUM,
            loader=reid.load,
            unloader=lambda m: m.unload(),
            triggers=["person"],
        ))

        # Action recognition (only for suspicious scenarios)
        action = ActionRecognizer("microsoft/xclip-base-patch16-zero-shot")
        self.model_manager.register_model(ModelSpec(
            name="action",
            vram_mb=1500,
            priority=ModelPriority.LOW,
            loader=action.load,
            unloader=lambda m: m.unload(),
            triggers=["suspicious"],
        ))

    async def enrich_detection(
        self,
        image: bytes,
        detection: dict,
        frames_buffer: list | None = None,
    ) -> dict:
        """Enrich a detection with on-demand models."""
        enrichment = {}

        detection_type = detection.get("label", "").lower()
        has_face = detection.get("face_visible", False)
        is_suspicious = detection.get("suspicious_score", 0) > 50

        # Get appropriate models for this detection
        models = await self.model_manager.get_models_for_detection(
            detection_type=detection_type,
            face_visible=has_face,
            suspicious=is_suspicious,
        )

        # Extract person crop
        if "person" in detection_type:
            crop = self._extract_crop(image, detection["bbox"])

            # Pose estimation
            if "pose" in models:
                enrichment["pose"] = models["pose"].estimate(crop)

            # Threat detection
            if "threat" in models:
                enrichment["threat"] = models["threat"].detect(crop)

            # Age-gender (if face visible)
            if "age-gender" in models and has_face:
                face_crop = self._extract_face_crop(image, detection)
                enrichment["demographics"] = models["age-gender"].predict(face_crop)

            # Re-identification embedding
            if "reid" in models:
                enrichment["reid_embedding"] = models["reid"].get_embedding(crop)

            # Action recognition (if suspicious and have frames)
            if "action" in models and frames_buffer:
                enrichment["action"] = models["action"].classify_action(frames_buffer)

        return enrichment

    def _extract_crop(self, image: bytes, bbox: list[float]):
        """Extract image crop from bounding box."""
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image))
        x1, y1, x2, y2 = bbox
        return img.crop((x1, y1, x2, y2))

    def _extract_face_crop(self, image: bytes, detection: dict):
        """Extract face crop from detection."""
        # Use face bbox if available, otherwise estimate from person bbox
        if "face_bbox" in detection:
            return self._extract_crop(image, detection["face_bbox"])

        # Estimate face region from top of person bbox
        bbox = detection["bbox"]
        x1, y1, x2, y2 = bbox
        face_height = (y2 - y1) * 0.25
        face_bbox = [x1, y1, x2, y1 + face_height]
        return self._extract_crop(image, face_bbox)
```

---

## Part 3: Enhanced Nemotron Context Format

### 3.1 New Prompt Section: On-Demand Enrichment

```python
def format_ondemand_enrichment_context(enrichment: dict) -> str:
    """Format on-demand model enrichment for Nemotron."""
    sections = []

    # Threat detection (CRITICAL - always first)
    if enrichment.get("threat", {}).get("threats_detected"):
        threat = enrichment["threat"]
        sections.append(
            f"### ⚠️ THREAT DETECTED\n"
            f"- **Type**: {threat['highest_threat']['type'].upper()}\n"
            f"- **Confidence**: {threat['highest_threat']['confidence']:.0%}\n"
            f"- **Location**: {threat['highest_threat']['bbox']}"
        )

    # Pose analysis
    if enrichment.get("pose", {}).get("poses"):
        poses = enrichment["pose"]["poses"]
        pose_descriptions = []
        for i, pose in enumerate(poses):
            posture = pose.get("posture", "unknown")
            conf = pose.get("confidence", 0)
            pose_descriptions.append(f"Person {i+1}: {posture} (confidence: {conf:.0%})")

        sections.append(
            f"### Body Posture Analysis\n" + "\n".join(f"- {p}" for p in pose_descriptions)
        )

    # Demographics
    if enrichment.get("demographics"):
        demo = enrichment["demographics"]
        sections.append(
            f"### Person Demographics\n"
            f"- **Estimated age group**: {demo['age_group']}\n"
            f"- **Gender**: {demo['gender']}\n"
            f"- **Confidence**: {demo['confidence']:.0%}"
        )

    # Action recognition
    if enrichment.get("action"):
        action = enrichment["action"]
        sections.append(
            f"### Detected Activity\n"
            f"- **Primary action**: {action['top_action']}\n"
            f"- **Confidence**: {action['confidence']:.0%}\n"
            f"- **Alternative interpretations**: {', '.join(action['all_scores'].keys())}"
        )

    # Re-identification context (if matched to known person)
    if enrichment.get("reid_match"):
        match = enrichment["reid_match"]
        sections.append(
            f"### Person Recognition\n"
            f"- **Match**: {match['identity']}\n"
            f"- **Similarity**: {match['similarity']:.0%}\n"
            f"- **Previous sightings**: {match['sighting_count']} times"
        )

    return "\n\n".join(sections) if sections else ""
```

### 3.2 Updated MODEL_ZOO_ENHANCED Prompt Template

Add a new section to the existing prompt:

```python
# In prompts.py, add to MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT

ONDEMAND_ENRICHMENT_SECTION = """
## On-Demand Analysis Results

{ondemand_context}

Use this additional context to refine your risk assessment:
- Threat detection results are HIGH PRIORITY - any weapon detection should significantly increase risk
- Body posture can indicate intent (crouching near door = suspicious, standing normally = neutral)
- Demographics help contextualize behavior (child vs adult, known vs unknown)
- Action recognition provides behavioral context beyond static appearance
- Person recognition helps identify returning visitors vs new individuals
"""
```

---

## Part 4: Implementation Plan

### Phase 1: Prompt Improvements (No New Models)

**Files to modify:**

- `ai/florence/model.py` — Add `<MORE_DETAILED_CAPTION>` and `<OPEN_VOCABULARY_DETECTION>`
- `ai/enrichment/model.py` — Update `SECURITY_CLOTHING_PROMPTS` with ensembling
- `backend/services/prompts.py` — Add new formatting functions
- `backend/services/florence_client.py` — Update to use new Florence tasks

**Tasks:**

1. Update Florence-2 default task to `<MORE_DETAILED_CAPTION>`
2. Add `<OPEN_VOCABULARY_DETECTION>` endpoint with security objects
3. Implement CLIP/FashionCLIP prompt ensembling in `ClothingClassifier`
4. Add new clothing categories (carrying items, granular colors)
5. Update Nemotron prompt formatting functions
6. Add tests for new prompt formats

### Phase 2: On-Demand Model Infrastructure in ai-enrichment

**Files to modify:**

- `ai/enrichment/model.py` — Major refactor for on-demand loading
- `ai/enrichment/model_manager.py` — New file for `OnDemandModelManager`
- `ai/enrichment/model_loaders.py` — New file for model wrapper classes
- `ai/enrichment/Dockerfile` — Add new model dependencies

**Tasks:**

1. Create `OnDemandModelManager` class in new file
2. Create model loader classes for existing models (Vehicle, Pet, Clothing, Depth)
3. Refactor `lifespan()` to register models instead of loading
4. Update existing endpoints to use model manager
5. Add `/enrich` unified endpoint
6. Add Prometheus metrics for model loading/unloading
7. Add health endpoint updates to show loaded models
8. Integration tests with mock models

### Phase 3: New Model Integration

**Files to modify:**

- `ai/enrichment/model_loaders.py` — Add new model classes
- `ai/enrichment/model.py` — Register new models
- `ai/enrichment/Dockerfile` — Add ultralytics, torchreid dependencies
- `scripts/download_ondemand_models.sh` — New script

**Tasks:**

1. Implement `PoseEstimator` (YOLOv8n-pose)
2. Implement `ThreatDetector` (Threat-Detection-YOLOv8n)
3. Implement `AgeGenderPredictor`
4. Implement `PersonReidentifier` (OSNet)
5. Implement `ActionRecognizer` (X-CLIP)
6. Register all new models in model manager
7. Update Dockerfile with new dependencies
8. Create model download script
9. End-to-end testing

### Phase 4: Backend Integration

**Files to modify:**

- `backend/services/enrichment_client.py` — Call new `/enrich` endpoint
- `backend/services/enrichment_pipeline.py` — Use unified enrichment
- `backend/services/prompts.py` — Add `format_ondemand_enrichment_context()`
- `backend/services/nemotron_analyzer.py` — Include new context in prompts

**Tasks:**

1. Update `EnrichmentClient` to call unified `/enrich` endpoint
2. Update `EnrichmentPipeline` to pass detection context
3. Add `format_ondemand_enrichment_context()` formatting function
4. Update Nemotron prompts to include new enrichment sections
5. Add re-identification matching logic against known persons database
6. Performance testing and optimization
7. Documentation updates

### Phase 5: Docker & Deployment

**Files to modify:**

- `docker-compose.prod.yml` — Add new model volume mounts
- `docker-compose.staging.yml` — Mirror prod changes
- `scripts/download_ondemand_models.sh` — Model download script

**Tasks:**

1. Add volume mounts for new models in docker-compose
2. Update ai-enrichment healthcheck for longer startup (model download)
3. Create model download script for new models
4. Update deployment documentation
5. Test full deployment cycle

---

## Part 5: Model Download Scripts

```bash
#!/bin/bash
# scripts/download_ondemand_models.sh
#
# Downloads all on-demand models for the ai-enrichment service.
# Run this before first deployment or when adding new models.

set -e

MODELS_DIR="${AI_MODELS_PATH:-/export/ai_models}/model-zoo"

echo "=== Downloading On-Demand Models to $MODELS_DIR ==="

# Ensure models directory exists
mkdir -p "$MODELS_DIR"

# ============================================================================
# EXISTING MODELS (already in model-zoo, verify they exist)
# ============================================================================

echo ""
echo "--- Verifying existing models ---"

for model in "vehicle-segment-classification" "pet-classifier" "fashion-clip" "depth-anything-v2-small"; do
    if [ -d "$MODELS_DIR/$model" ]; then
        echo "✓ $model exists"
    else
        echo "✗ $model MISSING - please download manually"
    fi
done

# ============================================================================
# NEW MODELS
# ============================================================================

echo ""
echo "--- Downloading new models ---"

# YOLOv8n-pose (Ultralytics format)
echo "Downloading YOLOv8n-pose..."
mkdir -p "$MODELS_DIR/yolov8n-pose"
python -c "
from ultralytics import YOLO
model = YOLO('yolov8n-pose.pt')
# Model auto-downloads to ~/.cache/ultralytics, copy to models dir
import shutil
from pathlib import Path
cache_path = Path.home() / '.cache' / 'ultralytics' / 'yolov8n-pose.pt'
if cache_path.exists():
    shutil.copy(cache_path, '$MODELS_DIR/yolov8n-pose/yolov8n-pose.pt')
    print('✓ YOLOv8n-pose downloaded')
"

# Threat Detection YOLOv8n
echo "Downloading Threat-Detection-YOLOv8n..."
huggingface-cli download Subh775/Threat-Detection-YOLOv8n \
    --local-dir "$MODELS_DIR/threat-detection-yolov8n" \
    --local-dir-use-symlinks False
echo "✓ Threat-Detection-YOLOv8n downloaded"

# Age-Gender Prediction
echo "Downloading Age-Gender model..."
huggingface-cli download abhilash88/age-gender-prediction \
    --local-dir "$MODELS_DIR/age-gender-prediction" \
    --local-dir-use-symlinks False
echo "✓ Age-Gender model downloaded"

# OSNet for Person Re-identification
echo "Downloading OSNet-x0.25..."
mkdir -p "$MODELS_DIR/osnet-reid"
python -c "
import torch
from torchreid import models
# Build and save model
model = models.build_model(name='osnet_x0_25', num_classes=1000, pretrained=True)
torch.save(model.state_dict(), '$MODELS_DIR/osnet-reid/osnet_x0_25.pth')
print('✓ OSNet-x0.25 downloaded')
"

# X-CLIP (downloads on first use, but we can pre-cache)
echo "Pre-caching X-CLIP model..."
python -c "
from transformers import XCLIPProcessor, XCLIPModel
processor = XCLIPProcessor.from_pretrained('microsoft/xclip-base-patch16-zero-shot')
model = XCLIPModel.from_pretrained('microsoft/xclip-base-patch16-zero-shot')
# Save to local dir
processor.save_pretrained('$MODELS_DIR/xclip-base-patch16-zero-shot')
model.save_pretrained('$MODELS_DIR/xclip-base-patch16-zero-shot')
print('✓ X-CLIP downloaded')
"

echo ""
echo "=== All models downloaded successfully ==="
echo ""
echo "Model locations:"
echo "  - YOLOv8n-pose:     $MODELS_DIR/yolov8n-pose/"
echo "  - Threat Detection: $MODELS_DIR/threat-detection-yolov8n/"
echo "  - Age-Gender:       $MODELS_DIR/age-gender-prediction/"
echo "  - OSNet ReID:       $MODELS_DIR/osnet-reid/"
echo "  - X-CLIP:           $MODELS_DIR/xclip-base-patch16-zero-shot/"
```

### Docker Compose Volume Mounts

Add these to `docker-compose.prod.yml` for the ai-enrichment service:

```yaml
ai-enrichment:
  volumes:
    # Existing models
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/vehicle-segment-classification:/models/vehicle-segment-classification:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/pet-classifier:/models/pet-classifier:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/fashion-clip:/models/fashion-clip:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/depth-anything-v2-small:/models/depth-anything-v2-small:ro
    # NEW: On-demand models
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/yolov8n-pose:/models/yolov8n-pose:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/threat-detection-yolov8n:/models/threat-detection-yolov8n:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/age-gender-prediction:/models/age-gender-prediction:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/osnet-reid:/models/osnet-reid:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/xclip-base-patch16-zero-shot:/models/xclip-base-patch16-zero-shot:ro
  environment:
    # Existing
    - VEHICLE_MODEL_PATH=/models/vehicle-segment-classification
    - PET_MODEL_PATH=/models/pet-classifier
    - CLOTHING_MODEL_PATH=/models/fashion-clip
    - DEPTH_MODEL_PATH=/models/depth-anything-v2-small
    # NEW: On-demand model paths
    - POSE_MODEL_PATH=/models/yolov8n-pose/yolov8n-pose.pt
    - THREAT_MODEL_PATH=/models/threat-detection-yolov8n
    - AGE_GENDER_MODEL_PATH=/models/age-gender-prediction
    - REID_MODEL_PATH=/models/osnet-reid/osnet_x0_25.pth
    - ACTION_MODEL_PATH=/models/xclip-base-patch16-zero-shot
    # VRAM budget for on-demand loading
    - ONDEMAND_VRAM_BUDGET_MB=6800
```

---

## Part 6: Success Metrics

| Metric                | Current                | Target             | Measurement             |
| --------------------- | ---------------------- | ------------------ | ----------------------- |
| False positive rate   | TBD                    | -30%               | Manual review of alerts |
| Context richness      | 5 attributes/detection | 12+ attributes     | Automated counting      |
| Threat detection      | None                   | 95%+ accuracy      | Test dataset            |
| Person re-id accuracy | None                   | 85%+               | Cross-camera matching   |
| Model load latency    | N/A                    | <5s                | p95 timing              |
| VRAM headroom         | 3-4GB                  | Stay within budget | Monitoring              |

---

## Appendix: Research Sources

### Florence-2

- [Microsoft Florence-2 HuggingFace](https://huggingface.co/microsoft/Florence-2-large)
- [Florence-2 Task Guide - Towards Data Science](https://medium.com/data-science/)
- [Florence-2 with SAHI - Roboflow](https://roboflow.com/how-to-use-sahi/florence-2)

### CLIP/FashionCLIP

- [OpenAI CLIP Prompt Engineering](https://github.com/openai/CLIP/blob/main/notebooks/Prompt_Engineering_for_ImageNet.ipynb)
- [Marqo-FashionCLIP](https://huggingface.co/Marqo/marqo-fashionCLIP)
- [Prompt Ensemble Techniques](https://medium.com/@satojkovic/prompt-ensemble-in-zero-shot-classification-using-clip)

### New Models

- [YOLOv8n-pose](https://huggingface.co/Xenova/yolov8n-pose)
- [Threat-Detection-YOLOv8n](https://huggingface.co/Subh775/Threat-Detection-YOLOv8n)
- [Age-Gender Prediction](https://huggingface.co/abhilash88/age-gender-prediction)
- [X-CLIP Zero-Shot](https://huggingface.co/microsoft/xclip-base-patch16-zero-shot)

### Action Recognition

- [MoViNet - TensorFlow](https://www.tensorflow.org/hub/tutorials/movinet)
- [UCF-Crime Dataset](https://www.crcv.ucf.edu/projects/real-world/)
- [Pose-Based Anomaly Detection](https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/ipr2.12664)

---

## Appendix B: File Change Summary

### New Files to Create

| File                                  | Purpose                                                       |
| ------------------------------------- | ------------------------------------------------------------- |
| `ai/enrichment/model_manager.py`      | `OnDemandModelManager` class                                  |
| `ai/enrichment/model_loaders.py`      | Model wrapper classes (Pose, Threat, AgeGender, ReID, Action) |
| `scripts/download_ondemand_models.sh` | Download script for new models                                |

### Files to Modify

| File                                      | Changes                                                              |
| ----------------------------------------- | -------------------------------------------------------------------- |
| `ai/enrichment/model.py`                  | Refactor lifespan(), add `/enrich` endpoint, integrate model manager |
| `ai/enrichment/Dockerfile`                | Add ultralytics, torchreid, transformers[video] dependencies         |
| `ai/florence/model.py`                    | Add `<OPEN_VOCABULARY_DETECTION>` support                            |
| `backend/services/prompts.py`             | Add `format_ondemand_enrichment_context()`                           |
| `backend/services/enrichment_client.py`   | Add `enrich()` method for unified endpoint                           |
| `backend/services/enrichment_pipeline.py` | Use unified enrichment with detection context                        |
| `docker-compose.prod.yml`                 | Add new model volume mounts and environment variables                |
| `docker-compose.staging.yml`              | Mirror prod changes                                                  |

### Dependencies to Add (ai/enrichment/Dockerfile)

```dockerfile
# Add to requirements or pip install
ultralytics>=8.0.0        # YOLOv8 pose estimation
torchreid>=1.4.0          # Person re-identification (OSNet)
transformers[video]       # X-CLIP video support
```

---

## Appendix C: Quick Reference

### VRAM Summary

| State      | Always Loaded                               | On-Demand Budget | Total              |
| ---------- | ------------------------------------------- | ---------------- | ------------------ |
| **Before** | ~5.3GB (YOLO26, Florence, CLIP, Enrichment) | N/A              | ~5.3GB             |
| **After**  | ~2.65GB (YOLO26, Florence, CLIP)            | ~6.8GB           | Up to ~9.45GB peak |

### Model Priority Order

When VRAM is constrained, models load in this order:

1. **CRITICAL**: Threat Detection (weapons)
2. **HIGH**: Pose, FashionCLIP, Age-Gender
3. **MEDIUM**: Vehicle, Pet, ReID
4. **LOW**: Depth, X-CLIP (action)

### API Changes

| Endpoint                  | Change                                              |
| ------------------------- | --------------------------------------------------- |
| `POST /enrich`            | **NEW** - Unified enrichment with on-demand loading |
| `POST /clothing-classify` | Now loads model on-demand                           |
| `POST /vehicle-classify`  | Now loads model on-demand                           |
| `POST /pet-classify`      | Now loads model on-demand                           |
| `POST /depth-estimate`    | Now loads model on-demand                           |
| `GET /health`             | Updated to show loaded models                       |
