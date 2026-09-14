# AI Enrichment Tests Directory

## Purpose

Unit tests for the AI Enrichment Service's Model Zoo architecture. Tests validate on-demand model loading, VRAM management, model registry, and individual model implementations (pose estimation, threat detection, demographics, person re-ID, action recognition) without requiring a GPU or actual model files.

## Directory Structure

```
ai/enrichment/tests/
├── AGENTS.md                    # This file
├── __init__.py                  # Package marker
├── conftest.py                  # pytest configuration (path setup)
├── test_action_recognizer.py    # X-CLIP action recognition tests
├── test_demographics.py         # Age/gender estimation tests
├── test_model_manager.py        # OnDemandModelManager VRAM tests
├── test_model_registry.py       # Model registry configuration tests
├── test_person_reid.py          # OSNet re-ID embedding tests
├── test_pose_estimator.py       # YOLOv8n-pose estimation tests
├── test_threat_detector.py      # Weapon detection tests
├── test_video_processing.py     # Video processing utilities tests (NEM-3719)
└── test_yolo26_detector.py      # YOLO26 detector tests
```

## Running Tests

```bash
# Run all enrichment tests
uv run pytest ai/enrichment/tests/ -v

# Run specific test file
uv run pytest ai/enrichment/tests/test_model_manager.py -v

# Run with coverage
uv run pytest ai/enrichment/tests/ -v --cov=ai.enrichment

# Parallel execution (unit tests)
uv run pytest ai/enrichment/tests/ -n auto --dist=worksteal
```

## Test Files

### `conftest.py`

Pytest configuration that adds the project root to `sys.path` for proper imports of `ai.enrichment` modules.

### `test_model_manager.py` (831 lines)

Tests for the `OnDemandModelManager` class that handles VRAM-aware model loading.

**Test Classes:**

| Class                   | Description                             | Tests |
| ----------------------- | --------------------------------------- | ----- |
| `TestModelPriority`     | Priority enum ordering (CRITICAL < LOW) | 3     |
| `TestModelInfo`         | ModelInfo dataclass storage             | 1     |
| `TestModelConfig`       | ModelConfig dataclass validation        | 1     |
| `TestModelManagerInit`  | Manager initialization and budget       | 3     |
| `TestModelRegistration` | Model register/unregister operations    | 4     |
| `TestModelLoading`      | On-demand model loading behavior        | 5     |
| `TestModelUnloading`    | Model unload and CUDA cache clearing    | 5     |
| `TestLRUEviction`       | LRU eviction with priority ordering     | 4     |
| `TestConcurrentAccess`  | Thread safety with concurrent loads     | 2     |
| `TestStatusReporting`   | Status and monitoring endpoints         | 3     |
| `TestIdleCleanup`       | Idle model cleanup functionality        | 3     |
| `TestCUDAIntegration`   | CUDA cache clearing on unload           | 2     |
| `TestPrometheusMetrics` | VRAM monitoring metrics (NEM-3149)      | 8     |

**Key Test Scenarios:**

- VRAM budget enforcement (models evicted when budget exceeded)
- LRU eviction ordering (least recently used evicted first)
- Priority-based eviction (LOW priority evicted before CRITICAL)
- Concurrent model loading (thread safety)
- Prometheus metrics for VRAM monitoring
- Model larger than budget raises RuntimeError

### `test_model_registry.py` (514 lines)

Tests for model registration and detection-type-to-model mapping.

**Test Classes:**

| Class                            | Description                         | Tests |
| -------------------------------- | ----------------------------------- | ----- |
| `TestCreateModelRegistry`        | Registry contains all 9 models      | 4     |
| `TestVRAMConfiguration`          | VRAM values per design spec         | 3     |
| `TestPriorityConfiguration`      | Priority levels per design spec     | 5     |
| `TestLoaderUnloaderFunctions`    | Loader/unloader function validation | 4     |
| `TestEnvironmentVariableSupport` | Environment variable configuration  | 7     |
| `TestGetModelsForDetectionType`  | Detection type to model mapping     | 12    |
| `TestLoaderFunctionErrors`       | Import error handling               | 4     |
| `TestDeviceConfiguration`        | CUDA/CPU device configuration       | 3     |

**Expected Model Registry:**

| Model              | VRAM   | Priority |
| ------------------ | ------ | -------- |
| fashion_clip       | 800 MB | MEDIUM   |
| vehicle_classifier | 1.5 GB | MEDIUM   |
| pet_classifier     | 200 MB | MEDIUM   |
| depth_estimator    | 150 MB | LOW      |
| pose_estimator     | 300 MB | HIGH     |
| threat_detector    | 400 MB | CRITICAL |
| demographics       | 500 MB | HIGH     |
| person_reid        | 100 MB | MEDIUM   |
| action_recognizer  | 1.5 GB | LOW      |

### `test_action_recognizer.py` (414 lines)

Tests for X-CLIP video action recognition.

**Test Classes:**

| Class                                | Description                       | Tests |
| ------------------------------------ | --------------------------------- | ----- |
| `TestActionResult`                   | ActionResult dataclass            | 2     |
| `TestSecurityActions`                | Security action class definitions | 5     |
| `TestActionRecognizerFrameSampling`  | Frame sampling logic              | 9     |
| `TestActionRecognizerModelLoading`   | Model load/unload behavior        | 4     |
| `TestActionRecognizerInference`      | Action recognition with mocks     | 3     |
| `TestActionRecognizerBatchInference` | Batch inference validation        | 3     |
| `TestLoadActionRecognizer`           | Factory function                  | 1     |
| `TestSuspiciousActionFlagging`       | Suspicious action identification  | 2     |

**Security Actions (15 total):**

```python
SECURITY_ACTIONS = ["walking normally", "running", "delivering package", ...]
SUSPICIOUS_ACTIONS = {"fighting", "climbing", "breaking window", "picking lock", "hiding", "loitering", "looking around suspiciously"}
```

### `test_demographics.py` (773 lines)

Tests for ViT-based age/gender estimation.

**Test Classes:**

| Class                              | Description                    | Tests |
| ---------------------------------- | ------------------------------ | ----- |
| `TestDemographicsConstants`        | AGE_RANGES and GENDER_LABELS   | 3     |
| `TestDemographicsResult`           | Result dataclass and to_dict() | 3     |
| `TestModelPathValidation`          | Path traversal security        | 3     |
| `TestDemographicsEstimatorInit`    | Initialization and validation  | 5     |
| `TestAgeLabelNormalization`        | Model label normalization      | 6     |
| `TestGenderLabelNormalization`     | Gender label normalization     | 3     |
| `TestImagePreprocessing`           | RGB conversion, numpy handling | 4     |
| `TestModelLoadingUnloading`        | Model lifecycle                | 5     |
| `TestLoadDemographicsFactory`      | Factory function               | 2     |
| `TestEstimationWithoutGenderModel` | Age-only estimation            | 1     |
| `TestDiverseFaceScenarios`         | Deterministic output tests     | 2     |
| `TestConfidenceThresholds`         | Confidence value validation    | 2     |

**Standard Age Ranges:**

```python
AGE_RANGES = ["0-10", "11-20", "21-35", "36-50", "51-65", "65+"]
```

### `test_person_reid.py` (749 lines)

Tests for OSNet person re-identification embeddings.

**Test Classes:**

| Class                            | Description                      | Tests |
| -------------------------------- | -------------------------------- | ----- |
| `TestReIDResult`                 | ReIDResult dataclass             | 3     |
| `TestPersonReIDInit`             | Initialization and device config | 4     |
| `TestPersonReIDPreprocessing`    | Image preprocessing transforms   | 3     |
| `TestPersonReIDExtractEmbedding` | Embedding extraction             | 5     |
| `TestPersonReIDSimilarity`       | Cosine similarity computation    | 6     |
| `TestPersonReIDIsSamePerson`     | Same person matching logic       | 5     |
| `TestPersonReIDModelLoading`     | Model loading with torchreid     | 4     |
| `TestPersonReIDUnload`           | Model unloading                  | 2     |
| `TestLoadPersonReID`             | Factory function                 | 2     |
| `TestConstants`                  | Module constants (512-dim, etc.) | 4     |
| `TestEmbeddingHash`              | SHA-256 hash generation          | 3     |

**Key Constants:**

```python
EMBEDDING_DIMENSION = 512
OSNET_INPUT_HEIGHT = 256
OSNET_INPUT_WIDTH = 128
DEFAULT_SIMILARITY_THRESHOLD = 0.7
```

### `test_pose_estimator.py` (580 lines)

Tests for YOLOv8n-pose human pose estimation.

**Test Classes:**

| Class                       | Description                    | Tests |
| --------------------------- | ------------------------------ | ----- |
| `TestKeypointConstants`     | 17 COCO keypoint names/indices | 3     |
| `TestSuspiciousPoses`       | Suspicious pose definitions    | 3     |
| `TestKeypointDataclass`     | Keypoint dataclass             | 2     |
| `TestPoseResultDataclass`   | PoseResult dataclass           | 3     |
| `TestModelPathValidation`   | Path traversal security        | 4     |
| `TestPoseEstimatorInit`     | Initialization                 | 3     |
| `TestPoseClassification`    | Pose classification logic      | 6     |
| `TestConfidenceCalculation` | Confidence calculation         | 3     |
| `TestEstimationPipeline`    | Full estimation pipeline       | 5     |
| `TestModelLifecycle`        | Load/unload behavior           | 2     |
| `TestEdgeCases`             | Edge cases and error handling  | 4     |

**Suspicious Poses:**

```python
SUSPICIOUS_POSES = {"crouching", "crawling", "hiding", "reaching_up"}
```

### `test_threat_detector.py` (786 lines)

Tests for YOLO-based weapon detection.

**Test Classes:**

| Class                             | Description                        | Tests |
| --------------------------------- | ---------------------------------- | ----- |
| `TestThreatDetection`             | ThreatDetection dataclass          | 3     |
| `TestThreatResult`                | ThreatResult and to_context_string | 9     |
| `TestSeverityConstants`           | Severity ordering                  | 2     |
| `TestThreatDetectorInit`          | Initialization                     | 3     |
| `TestThreatDetectorLoadModel`     | Model loading                      | 3     |
| `TestThreatDetectorDetection`     | Detection with mocked YOLO         | 6     |
| `TestThreatDetectorConfiguration` | Confidence threshold               | 6     |
| `TestThreatDetectorUnload`        | Model unloading                    | 3     |
| `TestLoadThreatDetector`          | Factory function                   | 2     |

**Threat Classes:**

| Class   | Severity |
| ------- | -------- |
| gun     | CRITICAL |
| rifle   | CRITICAL |
| pistol  | CRITICAL |
| knife   | HIGH     |
| bat     | MEDIUM   |
| crowbar | MEDIUM   |

## Testing Patterns

### Mocking YOLO Models

Tests use MagicMock to simulate YOLO model behavior:

```python
@pytest.fixture
def mock_yolo_model():
    mock = MagicMock()
    mock.names = {0: "knife", 1: "gun"}
    mock_results = MagicMock()
    mock_results.boxes = [mock_box1, mock_box2]
    mock.return_value = [mock_results]
    return mock
```

### Testing VRAM Budget Enforcement

```python
@pytest.mark.asyncio
async def test_eviction_when_over_budget(small_manager):
    # Budget is 500MB, two 300MB models should trigger eviction
    await small_manager.get_model("model1")  # 300MB loaded
    await small_manager.get_model("model2")  # Triggers eviction of model1
    assert not small_manager.is_loaded("model1")
    assert small_manager.is_loaded("model2")
```

### Testing Prometheus Metrics

```python
@pytest.mark.asyncio
async def test_vram_usage_metric_updated_on_load():
    manager = OnDemandModelManager(vram_budget_gb=1.0)
    config = create_model_config("test", 500)
    manager.register_model(config)

    initial = ENRICHMENT_VRAM_USAGE_BYTES._value.get()
    await manager.get_model("test")

    # 500 MB = 500 * 1024 * 1024 bytes
    assert ENRICHMENT_VRAM_USAGE_BYTES._value.get() == initial + (500 * 1024 * 1024)
```

## Fixtures Overview

### Common Fixtures

| Fixture                       | File                    | Description                     |
| ----------------------------- | ----------------------- | ------------------------------- |
| `manager`                     | test_model_manager.py   | ModelManager with 1GB budget    |
| `small_manager`               | test_model_manager.py   | ModelManager with 500MB budget  |
| `mock_yolo_model`             | test_pose_estimator.py  | Mocked YOLO model               |
| `mock_pose_estimator`         | test_pose_estimator.py  | PoseEstimator with mocked model |
| `sample_keypoints`            | test_pose_estimator.py  | Standing person keypoints       |
| `crouching_keypoints`         | test_pose_estimator.py  | Crouching person keypoints      |
| `sample_image`                | test_threat_detector.py | Safe test image (solid color)   |
| `detector_with_mock`          | test_threat_detector.py | ThreatDetector with mocked YOLO |
| `mock_demographics_estimator` | test_demographics.py    | Estimator with mocked models    |
| `valid_embedding`             | test_person_reid.py     | 512-dim normalized embedding    |
| `mock_torchreid_model`        | test_person_reid.py     | Mocked torchreid model          |

## Related Documentation

- `/ai/enrichment/AGENTS.md` - Enrichment service documentation
- `/ai/enrichment/model_manager.py` - OnDemandModelManager implementation
- `/ai/enrichment/model_registry.py` - Model registry configuration
- `/ai/enrichment/models/` - Model implementations
- `/ai/AGENTS.md` - AI pipeline overview
