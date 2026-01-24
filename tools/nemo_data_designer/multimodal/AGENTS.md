# Multimodal Evaluation Pipeline

## Purpose

Evaluate the local RT-DETRv2 + Nemotron detection pipeline against NVIDIA's vision-capable models to generate ground truth and validate detection accuracy. This subpackage provides tools to analyze curated test images with NVIDIA vision APIs, generate structured ground truth datasets, and compare local pipeline outputs against this ground truth.

## Directory Contents

```
tools/nemo_data_designer/multimodal/
├── AGENTS.md                    # This file
├── __init__.py                  # Package exports
├── image_analyzer.py            # NVIDIA Vision API client
├── ground_truth_generator.py    # Ground truth from curated images
└── pipeline_comparator.py       # Local vs NVIDIA comparison
```

## Key Files

### `image_analyzer.py` (NVIDIA Vision API Client)

Wrapper for NVIDIA's vision-capable models (NVLM) to analyze security camera images.

**Classes:**

| Class                  | Purpose                              |
| ---------------------- | ------------------------------------ |
| `VisionAnalysisResult` | Pydantic model for analysis output   |
| `VisionAnalyzerConfig` | Configuration (API key, cache, etc.) |
| `NVIDIAVisionAnalyzer` | Async client for NVIDIA vision API   |

**VisionAnalysisResult Fields:**

```python
VisionAnalysisResult(
    description: str,           # Natural language scene description
    detected_objects: list,     # Objects with type, confidence, bbox
    risk_assessment: dict,      # risk_score (0-100), risk_level, reasoning
    scene_attributes: dict,     # lighting, weather, activity_level, location_type
    raw_response: str           # Raw API response for debugging
)
```

**Features:**

- Async image analysis with structured JSON output
- Response caching with SHA-256 content hashing
- Mock mode for testing without API calls
- Batch processing with concurrency control
- Automatic retry with exponential backoff
- Supports JPEG, PNG, WebP, GIF formats

**Usage:**

```python
from tools.nemo_data_designer.multimodal import NVIDIAVisionAnalyzer

async with NVIDIAVisionAnalyzer() as analyzer:
    result = await analyzer.analyze_image(Path("front_door.jpg"))
    print(f"Risk: {result.risk_assessment['risk_level']}")
    print(f"Objects: {len(result.detected_objects)}")

# Batch analysis
results = await analyzer.analyze_batch(
    [Path("img1.jpg"), Path("img2.jpg")],
    max_concurrency=5
)
```

**Configuration:**

```python
config = VisionAnalyzerConfig(
    api_key="nvapi-xxx",          # Or from NVIDIA_API_KEY env var  # pragma: allowlist secret
    model="nvidia/llama-3.2-nv-vision-90b-instruct",
    timeout=60.0,
    max_retries=3,
    cache_enabled=True,
    cache_dir=Path(".vision_cache"),
    mock_mode=False               # Set True for testing
)
analyzer = NVIDIAVisionAnalyzer(config=config)
```

### `ground_truth_generator.py` (Ground Truth Generation)

Generates ground truth datasets from curated test images using NVIDIA vision analysis.

**Expected Directory Structure:**

```
images/
├── normal/           # Expected activity scenarios
│   ├── delivery.jpg
│   └── family.jpg
├── suspicious/       # Unusual but not threatening
│   └── loitering.jpg
├── threat/           # Security concerns
│   └── break_in.jpg
└── edge_case/        # Ambiguous situations
    └── costume.jpg
```

**Usage:**

```python
from tools.nemo_data_designer.multimodal import (
    NVIDIAVisionAnalyzer,
    MultimodalGroundTruthGenerator,
)

async with NVIDIAVisionAnalyzer() as analyzer:
    generator = MultimodalGroundTruthGenerator(
        image_dir=Path("backend/tests/fixtures/synthetic/images"),
        analyzer=analyzer,
    )

    # Discover images by category
    images = generator.discover_images()
    print(f"Found: {sum(len(v) for v in images.values())} images")

    # Generate ground truth
    df = await generator.generate_ground_truth()

    # Export to parquet
    generator.export_ground_truth(Path("ground_truth.parquet"))

    # Get summary statistics
    summary = generator.get_summary()
    print(f"Risk score mean: {summary['risk_score_stats']['mean']:.1f}")
```

**Output DataFrame Columns:**

| Column                      | Type | Description                    |
| --------------------------- | ---- | ------------------------------ |
| `image_path`                | str  | Absolute path to image         |
| `image_name`                | str  | Filename                       |
| `category`                  | str  | Directory category             |
| `nvidia_vision_description` | str  | Scene description              |
| `nvidia_detected_objects`   | JSON | List of detected objects       |
| `nvidia_object_count`       | int  | Number of detections           |
| `nvidia_risk_score`         | int  | Risk score (0-100)             |
| `nvidia_risk_level`         | str  | low/medium/high/critical       |
| `nvidia_risk_reasoning`     | str  | Risk explanation               |
| `nvidia_concerning_factors` | JSON | List of concerns               |
| `nvidia_mitigating_factors` | JSON | List of mitigating factors     |
| `nvidia_lighting`           | str  | daylight/dusk/night/artificial |
| `nvidia_weather`            | str  | clear/cloudy/rainy/unknown     |
| `nvidia_activity_level`     | str  | none/low/moderate/high         |
| `nvidia_location_type`      | str  | front_door/backyard/etc.       |
| `generated_at`              | str  | ISO timestamp                  |

### `pipeline_comparator.py` (Local vs NVIDIA Comparison)

Compares local RT-DETRv2 + Nemotron pipeline outputs against NVIDIA vision ground truth.

**Comparison Metrics:**

| Metric Category | Metrics Included                                |
| --------------- | ----------------------------------------------- |
| Detection       | IoU, precision, recall, F1, matched count       |
| Risk Score      | Deviation, alignment rate, over/under estimate  |
| Risk Level      | Agreement rate (categorical matching)           |
| Per-Category    | Breakdown by normal/suspicious/threat/edge_case |

**Usage:**

```python
from tools.nemo_data_designer.multimodal import PipelineComparator

comparator = PipelineComparator(
    config=ComparisonConfig(
        iou_threshold=0.5,
        risk_deviation_threshold=15,
    )
)

# Compare DataFrames
report = comparator.generate_comparison_report(
    local_results,      # DataFrame with: image_path, detections, risk_score
    nvidia_ground_truth # DataFrame from ground truth generator
)

# Print summary
print(comparator.generate_summary(report))

# Access metrics
print(f"Detection IoU: {report.detection_metrics['average_iou']:.2%}")
print(f"Risk alignment: {report.risk_metrics['alignment_rate']:.2%}")
print(f"Failure cases: {len(report.failure_cases)}")
```

**ComparisonReport Structure:**

```python
ComparisonReport(
    total_images: int,
    detection_metrics: {
        "average_iou": float,
        "average_precision": float,
        "average_recall": float,
        "average_f1": float,
        "total_local_detections": int,
        "total_nvidia_detections": int,
        "total_matched": int,
        "iou_threshold_met_rate": float,
    },
    risk_metrics: {
        "average_deviation": float,
        "max_deviation": int,
        "min_deviation": int,
        "alignment_rate": float,
        "over_estimate_rate": float,
        "under_estimate_rate": float,
        "level_agreement_rate": float,
    },
    per_category_metrics: {
        "normal": {...},
        "suspicious": {...},
        "threat": {...},
        "edge_case": {...},
    },
    failure_cases: [...],
    generated_at: str,
)
```

## Alignment Thresholds

| Metric               | Threshold | Interpretation                    |
| -------------------- | --------- | --------------------------------- |
| Detection IoU        | >= 70%    | Bounding boxes sufficiently match |
| Risk Score Alignment | >= 90%    | Within 15 points of ground truth  |

## API Configuration

| Environment Variable | Default | Description           |
| -------------------- | ------- | --------------------- |
| `NVIDIA_API_KEY`     | None    | Required for real API |

**API Endpoint:** `https://integrate.api.nvidia.com/v1`

**Default Vision Model:** `nvidia/llama-3.2-nv-vision-90b-instruct`

## Cache Location

Default cache for API responses:

```
backend/tests/fixtures/synthetic/.vision_cache/
```

Cache files are named `{image_stem}_{content_hash}.json` where content_hash is the first 16 characters of the SHA-256 hash of the image content.

## Entry Points

1. **Vision analysis**: `image_analyzer.py:NVIDIAVisionAnalyzer` - NVIDIA API client
2. **Ground truth**: `ground_truth_generator.py:MultimodalGroundTruthGenerator` - Dataset generation
3. **Comparison**: `pipeline_comparator.py:PipelineComparator` - Pipeline evaluation
4. **CLI runner**: `../multimodal_evaluation.py` - Orchestration script

## Related Documentation

- [Parent AGENTS.md](../AGENTS.md) - NeMo Data Designer overview
- [NVIDIA Vision API](https://build.nvidia.com) - API documentation
- [Testing Guide](../../../docs/development/testing.md) - Test patterns
