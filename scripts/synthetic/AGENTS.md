# Synthetic Data Generation Scripts - Agent Guide

## Purpose

This directory contains the synthetic data generation system for testing the Home Security Intelligence AI pipeline. It provides tools for generating synthetic security camera footage with known ground truth labels, enabling A/B testing of detection models against controlled test scenarios.

## Directory Contents

```
scripts/synthetic/
  AGENTS.md                  # This file
  __init__.py                # Package exports and module documentation
  prompt_generator.py        # Converts scenario specs to natural language prompts
  media_generator.py         # NVIDIA API integration (Veo 3.1, Gemini)
  comparison_engine.py       # A/B testing and validation logic
  report_generator.py        # JSON test report generation
  stock_footage.py           # Pexels/Pixabay stock footage downloader
```

## Key Files

### prompt_generator.py

**Purpose:** Converts structured JSON scenario specifications into natural language prompts suitable for video/image generation APIs (Veo 3.1, Gemini).

**Key Classes:**
- `PromptGenerator`: Main class for generating prompts from scenario specs

**Key Constants:**
- `SECURITY_CAMERA_PROMPT`: Base template for all security camera prompts
- `CAMERA_EFFECT_DESCRIPTIONS`: Mappings for fisheye, IR night vision, motion blur, etc.
- `TIME_OF_DAY_DESCRIPTIONS`: Dawn, day, dusk, night, midnight with lighting styles
- `WEATHER_DESCRIPTIONS`: Clear, rain, snow, fog, wind, overcast conditions
- `ACTION_DESCRIPTIONS`: Loitering, prowling, approaching, running, etc.

**Usage:**
```python
from scripts.synthetic import PromptGenerator

generator = PromptGenerator()
spec = {
    "scene": {"location": "front_porch", "camera_type": "doorbell"},
    "environment": {"time_of_day": "night", "weather": "clear"},
    "subjects": [{"type": "person", "action": "loitering"}],
}
prompt = generator.generate_prompt(spec)
video_prompt = generator.generate_video_prompt(spec, duration_seconds=8)
```

### media_generator.py

**Purpose:** Handles media generation via NVIDIA's inference API (Veo 3.1 for video, Gemini for images) with async polling for long-running operations.

**Key Classes:**
- `MediaGenerator`: Main class for generating videos and images
- `MediaStatus`: Enum for job status (PENDING, PROCESSING, COMPLETED, FAILED)
- `GenerationResult`: Dataclass for generation operation results

**Exceptions:**
- `MediaGeneratorError`: Base exception
- `APIKeyNotFoundError`: Missing NVIDIA API key
- `GenerationTimeoutError`: Polling timeout exceeded

**Environment Variables:**
- `NVIDIA_API_KEY` or `NVAPIKEY`: Required for API authentication

**Usage:**
```python
from scripts.synthetic import MediaGenerator, generate_video_sync

# Async usage
generator = MediaGenerator()
success = await generator.generate_video(
    prompt="Security camera view of front porch at night",
    output_path=Path("output/video.mp4")
)

# Sync wrapper
success = generate_video_sync(
    prompt="Person walking up driveway",
    output_path=Path("output/video.mp4")
)
```

### comparison_engine.py

**Purpose:** Compares pipeline API results against expected_labels.json for automated A/B testing. Validates that actual AI pipeline outputs match expected outputs defined in synthetic scenario specifications.

**Key Classes:**
- `ComparisonEngine`: Main comparison class with field-type-specific comparisons
- `ComparisonResult`: Overall comparison result with pass/fail and field details
- `FieldResult`: Individual field comparison result

**Comparison Types:**
| Field Type | Comparison Method |
|------------|-------------------|
| `count` | Exact match or +/-1 tolerance |
| `min_confidence` | Actual >= expected |
| `class` | Exact string match |
| `is_suspicious` | Boolean exact match |
| `score_range` | min <= actual <= max |
| `text_pattern` | Regex match |
| `must_contain` | All keywords present (case-insensitive) |
| `must_not_contain` | No keywords present |
| `enum` | Value in allowed set |
| `distance_range` | Within [min, max] meters |

**Supported Domains:**
- Detections (class, count, confidence)
- License plate (detected, text pattern)
- Face detection (count, visible)
- Pose estimation (posture, keypoints)
- Clothing (type, color, suspicious)
- Threats (has_threat, types, severity)
- Weather classification
- Vehicle (type, color, damage)
- Pet detection (type, known_pet)
- Florence captions (with synonym expansion)
- Risk assessment (score range, level, factors)

**Usage:**
```python
from scripts.synthetic import ComparisonEngine

engine = ComparisonEngine()
expected = {
    "detections": [{"class": "person", "min_confidence": 0.75, "count": 1}],
    "risk": {"min_score": 40, "max_score": 70, "level": "medium"}
}
actual = {...}  # Results from AI pipeline
result = engine.compare(expected, actual)
if result.passed:
    print("All tests passed!")
```

### report_generator.py

**Purpose:** Generates structured JSON test reports for synthetic data A/B testing with summary statistics, per-model results, and failure details.

**Key Classes:**
- `ReportGenerator`: Main report generation class
- `TestReport`: Complete test report structure
- `ReportSummary`: Summary statistics (total, passed, failed, pass_rate)
- `ModelResult`: Aggregated per-model results
- `SampleModelResult`: Single sample/model comparison result
- `FailureDetail`: Detailed failure information

**Usage:**
```python
from scripts.synthetic import ReportGenerator, SampleModelResult

generator = ReportGenerator()
results = [
    SampleModelResult(
        sample_id="001.mp4",
        model_name="yolo26",
        passed=True,
        expected={"class": "person"},
        actual={"class": "person"},
    ),
    # ... more results
]
report = generator.create_report("20260125_143022", "loitering", results)
generator.save_report(report, Path("results/report.json"))
```

### stock_footage.py

**Purpose:** Downloads stock footage from Pexels and Pixabay APIs that matches scenario criteria. Supplements AI-generated content with real-world footage for comprehensive testing.

**Key Classes:**
- `StockFootageDownloader`: Main downloader class
- `StockResult`: Search result dataclass
- `StockSource`: Enum (PEXELS, PIXABAY, ALL)

**Key Constants:**
- `SCENARIO_SEARCH_TERMS`: Maps scenario IDs to optimized search queries
- `CATEGORY_SEARCH_TERMS`: Fallback category-level search terms

**Supported Scenarios:**
| Category | Scenarios |
|----------|-----------|
| Normal | resident_arrival, delivery_driver, pet_activity, vehicle_parking, yard_maintenance |
| Suspicious | loitering, prowling, casing, tailgating |
| Threats | break_in_attempt, package_theft, vandalism, weapon_visible |

**Environment Variables:**
- `PEXELS_API_KEY`: Pexels API key
- `PIXABAY_API_KEY`: Pixabay API key

**Usage:**
```python
from scripts.synthetic import StockFootageDownloader, search_stock_sync

# Async usage
downloader = StockFootageDownloader()
results = await downloader.search_for_scenario(
    scenario_id="loitering",
    media_type="video",
    count=10
)
for result in results:
    await downloader.download(result, Path(f"footage/{result.id}.mp4"))

# Sync wrapper
results = search_stock_sync("package_theft", media_type="video", count=5)
```

## Integration with AI Pipeline

The synthetic data system is designed to test the full AI pipeline:

1. **Generate Scenarios**: Create structured JSON specs defining expected detections
2. **Generate Media**: Use Veo 3.1/Gemini or stock footage to create test videos/images
3. **Run Pipeline**: Process generated media through YOLO26, Florence, Nemotron
4. **Compare Results**: Validate pipeline output against expected labels
5. **Generate Reports**: Create detailed JSON reports for CI/test tracking

## Dependencies

- `httpx`: Async HTTP client for API calls
- `pydantic`: Data validation (optional, for backend integration)

## Related Files

- `/ai/synthetic/`: Scenario templates and test fixtures
- `/data/synthetic/`: Generated media and test results
- `/backend/services/`: AI pipeline services being tested
