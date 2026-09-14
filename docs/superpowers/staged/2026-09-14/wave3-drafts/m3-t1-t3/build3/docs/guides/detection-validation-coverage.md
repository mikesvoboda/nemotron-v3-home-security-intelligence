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

Each scenario includes an `expected_labels.json` file that defines:

```json
{
  "detections": [
    {
      "class": "person",
      "min_confidence": 0.7,
      "count": 1
    }
  ],
  "risk": {
    "min_score": 35,
    "max_score": 60,
    "level": "medium",
    "expected_factors": ["prolonged_observation", "unknown_person"]
  },
  "florence_caption": {
    "must_contain": ["person"],
    "must_not_contain": ["delivery", "neighbor"]
  }
}
```

## Processing Scenarios Through the Pipeline

### Method 1: Camera Directory Processing (Recommended)

The AI pipeline automatically processes images placed in camera directories:

```bash
# 1. Copy synthetic scenario frames to a test camera directory
mkdir -p /cameras/test_validation_normal/2026/01/31/
cp data/synthetic/normal/delivery_driver_20260125_180255/*.jpg \
   /cameras/test_validation_normal/2026/01/31/

# 2. Wait for file watcher to detect and process images
# The file watcher scans camera directories every 30 seconds

# 3. Monitor processing via logs
podman logs -f fine8_188fe20254c51e93_backend_1 | grep "Processing batch"
```

### Method 2: Batch Upload via API

Use the bulk detection API to upload frames:

```bash
# Upload frames from a scenario
for frame in data/synthetic/normal/delivery_driver_20260125_180255/*.jpg; do
    curl -X POST http://localhost:8000/api/detections/bulk \
        -F "camera_id=test_validation_camera" \
        -F "file=@$frame"
done
```

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

            # Wait for processing (30 second file watcher interval)
            time.sleep(35)

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

Add validation to CI pipeline:

```yaml
# .github/workflows/validation.yml
name: Detection Validation
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Process synthetic scenarios
        run: ./scripts/process_scenarios.sh
      - name: Run validation tests
        run: |
          uv run pytest backend/tests/integration/test_risk_score_validation.py -v
          ./scripts/validate_detections.py
      - name: Check gap rate
        run: |
          # Fail if gap rate > 20%
          python -c "
          import json
          with open('/tmp/detection_validation_results.json') as f:
              results = json.load(f)
          # Extract gap rate from results and assert < 20%
          "
```

### Nightly Validation Runs

Schedule comprehensive validation runs:

```bash
# Cron job (runs nightly at 2 AM)
0 2 * * * cd /path/to/project && ./scripts/nightly_validation.sh
```

## Expanding Coverage

### Creating New Synthetic Scenarios

1. **Generate scenarios using VEO3 or COSMOS:**

   ```bash
   # Generate using VEO3 (Google)
   python scripts/generate_scenarios_veo3.py --category suspicious --count 10

   # Generate using COSMOS (NVIDIA)
   python scripts/generate_scenarios_cosmos.py --category threats --count 10
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
   podman logs fine8_188fe20254c51e93_backend_1 | grep "File watcher"
   ```

2. **Verify camera directory structure:**

   ```
   /cameras/<camera_id>/YYYY/MM/DD/*.jpg
   ```

3. **Check file permissions:**

   ```bash
   ls -la /cameras/test_validation_*/
   ```

4. **Manually trigger processing:**
   ```bash
   # Restart backend to trigger immediate scan
   podman-compose restart backend
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

- [Testing Guide](../development/testing.md) - Overall testing strategy
- [Video Analytics Guide](video-analytics.md) - AI pipeline architecture
- [Detection Validation Script](../../scripts/validate_detections.py) - Script source code
- [Risk Score Validation Tests](../../backend/tests/integration/test_risk_score_validation.py) - Test suite source
