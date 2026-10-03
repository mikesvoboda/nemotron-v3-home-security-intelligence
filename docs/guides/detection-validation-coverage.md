# Detection Validation Coverage Guide

This guide explains how to improve detection validation coverage by processing more synthetic scenarios through the AI pipeline.

**Related Issues:**

- NEM-4527: Improve detection validation coverage
- NEM-4533: Create automated risk score validation test suite
- NEM-4529: Add class-specific and scenario-type metrics

## Overview

The automated risk score validation test suite (`backend/tests/integration/test_risk_score_validation.py`) compares actual AI pipeline outputs against expected labels defined in synthetic scenarios. To maximize validation coverage, you need to process synthetic scenarios through the pipeline.

## Synthetic Scenario Structure

Synthetic scenarios are organized under `data/synthetic/` with the following structure:

```
data/synthetic/
├── normal/           # Low-risk scenarios (expected risk: 0-15)
│   ├── delivery_driver_20260125_180255/
│   │   ├── frame01.jpg
│   │   ├── frame02.jpg
│   │   └── expected_labels.json
│   └── ...
├── suspicious/       # Medium-risk scenarios (expected risk: 35-60)
│   ├── casing_20260125_180256/
│   │   ├── frame01.jpg
│   │   ├── frame02.jpg
│   │   └── expected_labels.json
│   └── ...
└── threats/          # High-risk scenarios (expected risk: 70-100)
    ├── intruder_20260125_180256/
    │   ├── frame01.jpg
    │   ├── frame02.jpg
    │   └── expected_labels.json
    └── ...
```

### Expected Labels Format

Every scenario file carries two blocks that the validation suite actually
asserts on — `detections` and `risk` (`backend/tests/integration/
test_risk_score_validation.py` reads `labels["risk"]["min_score"]`,
`["max_score"]`, `["level"]` and `labels.get("detections", [])`):

```json
{
  "detections": [
    {
      "class": "person",
      "min_confidence": 0.75,
      "count": 1
    }
  ],
  "risk": {
    "min_score": 55,
    "max_score": 85,
    "level": "medium",
    "expected_factors": ["loitering", "nighttime", "obscured_face"]
  }
}
```

That is the whole vocabulary a new scenario needs. Some scenario files also
carry per-attribute blocks (`pose`, `clothing`, `demographics`,
`florence_caption`, `pet`, `depth`); no stage in the shipped pipeline produces
those values, so they never gain a comparison and new scenarios should not
include them.

## Processing Scenarios Through the Pipeline

### Method 1: Camera Directory Processing (Recommended)

The AI pipeline automatically processes images placed in camera directories:

```bash
# 1. Copy synthetic scenario frames to a test camera directory
mkdir -p /cameras/test_validation_normal/2026/01/31/
cp data/synthetic/normal/delivery_driver_20260125_180255/*.jpg \
   /cameras/test_validation_normal/2026/01/31/

# 2. Watchdog picks the files up as filesystem events. On volume mounts where
#    inotify does not fire, set FILE_WATCHER_POLLING=true and the watcher
#    re-scans every FILE_WATCHER_POLLING_INTERVAL seconds (default 1.0, max 30).

# 3. Then wait for the batch to close: BATCH_WINDOW_SECONDS (default 90), with
#    BATCH_IDLE_TIMEOUT_SECONDS (default 30) closing it early once uploads stop.

# 4. Follow the pipeline in the backend logs. The strings that prove each stage:
#    "Queued image for detection" (watchdog) -> "Batch created" / "Batch closed"
#    (aggregator) -> "vlm batch analyzed" (VLM stage).
docker compose logs -f backend | grep -E "Queued .* for detection|Batch (created|closed)|vlm batch analyzed"
```

### Method 2: Batch Insert via API

`POST /api/detections/bulk` takes JSON (not multipart) and answers **207
Multi-Status** with per-item results. It writes detection rows directly — it
does not run the pipeline on your frames — so use it to seed detection records
and Method 1 when you want an end-to-end event. Up to 100 items per request, on
the `bulk` rate-limit tier (`RATE_LIMIT_BULK_REQUESTS_PER_MINUTE`):

```bash
curl -X POST http://localhost:8000/api/detections/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "detections": [
      {
        "camera_id": "test_validation_camera",
        "object_type": "person",
        "confidence": 0.91,
        "detected_at": "2026-01-31T18:02:55Z",
        "file_path": "/cameras/test_validation_camera/2026-01-31/frame01.jpg",
        "bbox_x": 412, "bbox_y": 88,
        "bbox_width": 190, "bbox_height": 402
      }
    ]
  }'
```

Every `camera_id` in the payload must already exist as a `Camera` row — the
route validates them up front and reports per-item failures in the 207 body.

### Method 3: Automated Bulk Processing Script

Create a script to process all synthetic scenarios:

```python
#!/usr/bin/env python3
"""Process all synthetic scenarios through the AI pipeline."""

import shutil
import time
from pathlib import Path

SYNTHETIC_DIR = Path("data/synthetic")
CAMERA_BASE = Path("/cameras")

def process_all_scenarios():
    """Process all synthetic scenarios by copying to camera directories."""
    for category in ["normal", "suspicious", "threats"]:
        category_path = SYNTHETIC_DIR / category
        if not category_path.exists():
            continue

        for scenario_dir in sorted(category_path.iterdir()):
            if not scenario_dir.is_dir():
                continue

            # Create unique camera directory
            camera_name = f"test_{category}_{scenario_dir.name}"
            camera_dir = CAMERA_BASE / camera_name / "2026" / "01" / "31"
            camera_dir.mkdir(parents=True, exist_ok=True)

            # Copy frames
            for frame in sorted(scenario_dir.glob("*.jpg")):
                dest = camera_dir / f"{scenario_dir.name}_{category}_{frame.name}"
                shutil.copy(frame, dest)
                print(f"Copied {frame} -> {dest}")

            # Wait for the batch to close: BATCH_WINDOW_SECONDS (default 90)
            # plus headroom, or the next scenario's frames land in this batch.
            time.sleep(100)

if __name__ == "__main__":
    process_all_scenarios()
```

## Running Validation Tests

### 1. Run Integration Tests

After processing scenarios through the pipeline:

```bash
# Run risk score validation tests
uv run pytest backend/tests/integration/test_risk_score_validation.py -v

# Run specific test
uv run pytest backend/tests/integration/test_risk_score_validation.py::TestRiskScoreValidation::test_gap_rate_below_threshold -v
```

### 2. Run Validation Script

The standalone validation script queries the database directly:

```bash
# Run detection validation with enhanced metrics
./scripts/validate_detections.py
```

Output includes:

- Overall precision, recall, F1 scores
- Per-class metrics (Person, Car, Dog, etc.)
- Per-scenario-type metrics (normal, suspicious, threats)
- Confidence distribution percentiles
- Detailed gap analysis
- JSON export with full results

## Validation Metrics

### Gap Rate (NEM-4533)

The **gap rate** measures the percentage of scenarios where the actual risk score falls outside the expected range:

- **Target:** < 20% gap rate
- **Calculation:** (Scenarios with gaps / Total scenarios) × 100%
- **Gap definition:** Distance from actual score to nearest boundary of expected range
  - 0 if within range
  - Positive distance otherwise

Example:

```
Expected range: [35, 60]
Actual score: 30
Gap: 5 (30 is 5 points below minimum)

Expected range: [35, 60]
Actual score: 45
Gap: 0 (within range)
```

### Per-Class Metrics (NEM-4529)

For each object class (Person, Car, Dog, etc.):

- **Precision:** TP / (TP + FP)
- **Recall:** TP / (TP + FN)
- **F1 Score:** Harmonic mean of precision and recall

### Per-Scenario-Type Metrics (NEM-4529)

Aggregated metrics by scenario category:

- **normal**: Low-risk scenarios (expected: 0-15)
- **suspicious**: Medium-risk scenarios (expected: 35-60)
- **threats**: High-risk scenarios (expected: 70-100)

### Confidence Distribution (NEM-4529)

Percentile analysis of detection confidence scores:

- **P50:** Median confidence
- **P90:** 90th percentile
- **P95:** 95th percentile
- **P99:** 99th percentile

## Interpreting Results

### High Gap Rate (>20%)

If gap rate exceeds 20%, investigate:

1. **Per-category gaps:** Which scenario types have highest gaps?
2. **Scenario patterns:** Are certain scenarios consistently misclassified?
3. **LLM prompt issues:** May need prompt tuning for specific scenario types
4. **Detection quality:** Check per-class metrics for detection accuracy

### Low Per-Class Precision/Recall

If a specific class has low metrics:

1. **Review detection confidence thresholds**
2. **Check YOLO26 model performance for that class**
3. **Verify expected labels are accurate**
4. **Consider retraining or fine-tuning detection model**

### Low Confidence Scores

If P90/P95 confidence is low:

1. **Review image quality in synthetic scenarios**
2. **Check lighting/resolution/occlusion in frames**
3. **Verify detection model is performing optimally**
4. **Consider generating higher-quality synthetic data**

## Continuous Validation

### CI/CD Integration

Nothing runs these checks in CI today — no workflow in `.github/workflows/`
calls `validate_detections.py` or `test_risk_score_validation.py`. Standing them
up needs the frames to reach a live pipeline first, which a `ubuntu-latest`
runner cannot do: the assertions compare against events written by a running
backend with the gateway and VLM reachable. Budget for a self-hosted GPU runner
plus a seeded `/cameras` tree before wiring a gate, and treat the per-category
gap numbers below as the thing to assert on.

### Nightly Validation Runs

Schedule the tiered runs that already exist in CI: `nightly.yml` (07:00 UTC
analysis), `nightly-full-gate.yml` (04:17 UTC full gate), and
`flaky-test-detection.yml` (02:00 UTC).

## Expanding Coverage

### Creating New Synthetic Scenarios

1. **Generate scenarios:**

   ```bash
   # Template-based synthetic media (local rendering, no external model needed)
   uv run scripts/synthetic_data.py list
   uv run scripts/synthetic_data.py generate --scenario loitering --count 10

   # Cosmos prompt packets (for off-line text-to-video generation)
   uv run scripts/cosmos_prompt_generator.py --all
   ```

2. **Define expected labels:**
   Create `expected_labels.json` for each scenario based on scenario content.

3. **Process through pipeline:**
   Use one of the methods above to process frames.

4. **Validate results:**
   Run validation tests to verify accuracy.

### Coverage Goals

Aim for comprehensive coverage across:

- **Object classes:** Person, Car, Dog, Cat, etc.
- **Scenario types:** Normal, Suspicious, Threats
- **Lighting conditions:** Day, Night, Dawn/Dusk
- **Weather conditions:** Clear, Rain, Fog
- **Camera angles:** Front door, Backyard, Driveway, Side yard
- **Activity types:** Delivery, Loitering, Intrusion, Wildlife

## Troubleshooting

### Scenarios Not Processing

If scenarios aren't being processed:

1. **Check file watcher logs:**

   ```bash
   docker compose logs -f backend | grep "FileWatcher"
   ```

2. **Verify camera directory structure.** The watcher roots at
   `FOSCAM_BASE_PATH` (inside the backend container that is `/cameras`, mapped
   from the host directory in `.env`) and watches it recursively, so the date
   subdirectories below the camera name are convention, not a requirement:

   ```
   {FOSCAM_BASE_PATH}/<camera_id>/[YYYY/MM/DD/] *.jpg
   ```

3. **Check file permissions:**

   ```bash
   ls -la /cameras/test_validation_*/
   ```

4. **Check the camera id the folder implies.** `_get_camera_id_from_path()`
   normalizes the _first_ directory component under the root with
   `normalize_camera_id()` (so `Front-Door` and `front_door` land on the same
   id) and auto-creates the `Camera` row if it is missing — which means a typo
   in a folder name silently makes a new camera rather than failing loudly:

   ```bash
   curl -s http://localhost:8000/api/cameras | jq '.[].id'
   ```

### Validation Tests Failing

If validation tests fail:

1. **Verify scenarios were processed:**

   ```sql
   SELECT COUNT(*) FROM detections WHERE file_path LIKE '%delivery_driver%';
   ```

2. **Check event creation:**

   ```sql
   SELECT COUNT(*) FROM events WHERE camera_id LIKE 'test_%';
   ```

3. **Review risk scores:**
   ```sql
   SELECT risk_score, risk_level FROM events WHERE camera_id LIKE 'test_%';
   ```

## Best Practices

1. **Incremental processing:** Process scenarios in batches to avoid overwhelming the pipeline
2. **Monitor resources:** Watch CPU/GPU usage during bulk processing
3. **Archive results:** Save validation results for trend analysis
4. **Regular updates:** Re-validate when LLM prompts or models change
5. **Document gaps:** Track scenarios with consistent gaps for improvement

## See Also

- [Testing Guide](../developer/testing.md) - Overall testing strategy
- [Video Analytics Guide](video-analytics.md) - AI pipeline architecture
- [Detection Validation Script](../../scripts/validate_detections.py) - Script source code
- [Risk Score Validation Tests](../../backend/tests/integration/test_risk_score_validation.py) - Test suite source
