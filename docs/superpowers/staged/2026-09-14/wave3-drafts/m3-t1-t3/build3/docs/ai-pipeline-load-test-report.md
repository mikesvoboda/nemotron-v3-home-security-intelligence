# AI Pipeline Load Testing Report

**Date:** 2026-01-27
**Test Type:** Synthetic Data Validation
**Status:** Partially resolved - YOLO26 fixed, calibration issues remain

## Executive Summary

Load testing of the AI pipeline using synthetic data revealed several issues. The critical YOLO26 failure was **resolved** by switching from TensorRT to PyTorch model. Remaining issues require calibration and model loading fixes.

| Issue                         | Severity     | Status       | Impact                                                 |
| ----------------------------- | ------------ | ------------ | ------------------------------------------------------ |
| YOLO26 TensorRT model failure | **Critical** | **RESOLVED** | Switched to PyTorch model                              |
| Enrichment models not loaded  | **High**     | Open         | Pose, demographics, threat detection unavailable       |
| Synthetic data quality        | **High**     | Open         | Generated images don't match expected threat scenarios |
| Risk score calibration        | **Medium**   | Open         | Scores don't match expected ranges                     |
| Caption keyword matching      | **Low**      | Open         | Too strict string matching                             |

## Test Configuration

- **Samples tested:** 28 (normal: 10, suspicious: 10, threats: 8)
- **Pass rate:** 0% (all samples have field mismatches)
- **Average timing (with PyTorch model):**
  - Total pipeline: ~8,000ms
  - YOLO26: ~100-200ms (working)
  - Florence-2: ~1,000ms (working)
  - Enrichment: ~300ms (partial - only clothing)
  - Nemotron LLM: ~6,000ms (working)

## Resolved Issues

### YOLO26 TensorRT Model Failure (FIXED)

**Original Error:** `'NoneType' object has no attribute 'create_execution_context'`

**Resolution:** Switched from TensorRT engine to PyTorch model in `docker-compose.prod.yml`:

```yaml
# Changed from:
- YOLO26_MODEL_PATH=/models/yolo26/exports/yolo26m_fp16.engine
# To:
- YOLO26_MODEL_PATH=/models/yolo26/yolo26m.pt
```

**Result:** YOLO26 now correctly detects objects with high confidence (95%+ for persons).

## Remaining Issues

### 1. Enrichment Models Not Loaded (GPU Memory)

**Problem:** Only the clothing classifier model is loaded. Other enrichment models show as not loaded due to GPU memory pressure (97.4% utilization).

**Models Status:**
| Model | Status | Impact |
|-------|--------|--------|
| `clothing` | Loaded | Working |
| `vehicle-segment-classification` | Loaded | Working |
| `fashion-clip` | Loaded | Working |
| `vitpose-plus-small` | **Not loaded** | No pose estimation |
| `pet-classifier` | **Not loaded** | No pet detection |
| `depth-anything-v2-small` | **Not loaded** | No depth estimation |

**Impact:**

- All pose-related fields (`pose.posture`, `pose.is_suspicious`) return null
- All face-related fields (`face.detected`, `face.count`) return null
- All action fields (`action.action`, `action.is_suspicious`) return null
- Demographics not available

**Recommended Actions:**

1. Reduce GPU memory usage by unloading unused models
2. Consider using smaller model variants
3. Implement lazy loading with model cycling based on detection types

### 2. Synthetic Data Quality

**Problem:** AI-generated images don't accurately represent the intended scenarios.

**Evidence:**
| Scenario | Expected | Actual Image Content |
|----------|----------|---------------------|
| `weapon_visible` | Person with handgun | Person in hoodie, no weapon |
| `package_theft` | Person stealing package | Person standing with box (looks like delivery) |
| `break_in_attempt` | Person forcing entry | Person with hammer near door |

**Impact:**

- Risk scores appear miscalibrated but may be correct for actual image content
- Cannot validate true threat detection capabilities

### 3. Risk Score Calibration

**Observations (with full pipeline working):**

| Scenario         | Category   | Expected Score | Actual Score | Delta     |
| ---------------- | ---------- | -------------- | ------------ | --------- |
| Delivery driver  | Normal     | 0-15           | 15           | OK        |
| Pet activity     | Normal     | 0-5            | 12           | +7        |
| Resident arrival | Normal     | 0-20           | 25           | +5        |
| Vehicle parking  | Normal     | 0-10           | 15           | +5        |
| Yard maintenance | Normal     | 0-15           | 12-15        | OK        |
| Casing           | Suspicious | 35-60          | 15           | **-20**   |
| Loitering        | Suspicious | 40-70          | 75           | +5        |
| Prowling         | Suspicious | 50-80          | 75           | OK        |
| Break-in attempt | Threat     | 85-100         | 75-78        | **-10**   |
| Package theft    | Threat     | 70-90          | 12-15        | **-60\*** |
| Weapon visible   | Threat     | 95-100         | 15-45        | **-50\*** |

\*These scenarios have synthetic data quality issues - the images don't show the expected threats.

**Analysis:**

- Normal activities are scored appropriately (within 5-10 points)
- Suspicious activities are scored inconsistently (casing too low, loitering appropriate)
- Threat scenarios are severely underscored, but this is primarily due to synthetic images not containing actual threats

### 4. Caption Keyword Matching

**Problem:** Strict string matching causes false failures.

**Examples:**
| Expected | Actual Caption | Issue |
|----------|---------------|-------|
| `['person', 'package']` | "man...holding cardboard box" | "man" ≠ "person", "box" ≠ "package" |
| `['car', 'driveway']` | "car parked...on the road" | "road" ≠ "driveway" |
| `['person', 'door']` | "man walking down a porch...door" | "man" ≠ "person" (passes for door) |

## Service Health Status

| Service      | Port | Status      | Notes                                  |
| ------------ | ---- | ----------- | -------------------------------------- |
| YOLO26       | 8095 | **Healthy** | Using PyTorch model, detecting objects |
| Florence-2   | 8092 | Healthy     | Generating accurate captions           |
| Enrichment   | 8094 | **Partial** | Only clothing classifier loaded        |
| Nemotron LLM | 8091 | Healthy     | Generating risk assessments            |
| Backend      | 8000 | Healthy     | API available                          |

## Clothing Classification Quality

The enrichment clothing classifier is working well:

| Scenario         | Detection | Actual Classification             |
| ---------------- | --------- | --------------------------------- |
| Delivery driver  | person    | `casual` (expected: uniform)      |
| Yard maintenance | person    | `casual` (expected: work_clothes) |
| Loitering        | person    | `casual, hoodie`                  |
| Prowling         | person    | `casual`                          |
| Break-in         | person    | `hoodie`                          |

Classification detects hoodie correctly for suspicious scenarios but misses uniform detection for service workers.

## Recommendations Priority

### P0 - Critical (Immediate)

1. ~~Fix YOLO26 TensorRT engine~~ **DONE** - Switched to PyTorch
2. Load additional enrichment models (pose, face detection)

### P1 - High (This Sprint)

3. Validate synthetic data generation - ensure images match prompts
4. Improve risk score calibration for suspicious activities
5. Update expected labels to match realistic synthetic data

### P2 - Medium (Next Sprint)

6. Implement semantic caption matching using embeddings
7. Add service uniform detection to clothing classifier
8. Rebuild TensorRT engine for better inference performance

### P3 - Low (Backlog)

9. Create curated real-world test dataset
10. Add confidence intervals to risk scores

## Test Command Reference

```bash
# Run quick sanity check (one sample per scenario)
uv run scripts/load_test_ai_pipeline.py --quick

# Run full test suite
uv run scripts/load_test_ai_pipeline.py --all

# Run with verbose output
uv run scripts/load_test_ai_pipeline.py --quick --verbose

# Test specific category
uv run scripts/load_test_ai_pipeline.py --category threats --verbose

# Test specific scenario
uv run scripts/load_test_ai_pipeline.py --scenario weapon_visible

# Save detailed JSON report
uv run scripts/load_test_ai_pipeline.py --all --output report.json
```

## Field Failure Analysis

Most common failures across all tests:

| Field                           | Failures | Cause                              | Resolution                  |
| ------------------------------- | -------- | ---------------------------------- | --------------------------- |
| `pose.*`                        | 28       | Pose model not loaded              | Load vitpose model          |
| `face.*`                        | 28       | Face detection not in enrichment   | Add face detection model    |
| `action.*`                      | 28       | Action recognition not implemented | Add action recognition      |
| `demographics.*`                | 28       | Demographics model not loaded      | Load model                  |
| `threats.*`                     | 28       | Threat detection model not loaded  | Load model                  |
| `florence_caption.must_contain` | 10       | Strict string matching             | Implement semantic matching |
| `risk.score`                    | 6        | Calibration + synthetic data       | Tune prompts, fix data      |

## Next Steps

1. ~~Fix YOLO26 TensorRT engine~~ **DONE**
2. Address GPU memory pressure to load more enrichment models
3. Review and regenerate synthetic threat images
4. Update expected labels to be achievable with current models
5. Fine-tune Nemotron risk prompts based on calibration data
6. Implement semantic caption matching

---

**Report Generated By:** AI Pipeline Load Testing Script
**Last Updated:** 2026-01-27 17:10 EST
**Detailed JSON Report:** `/tmp/full_test_report.json`
