# AI Pipeline Validation Report

**Date:** 2026-01-31
**Epic:** NEM-4522 - AI Pipeline Validation
**Analyst:** Claude Code
**Database:** PostgreSQL (fine8_188fe20254c51e93)

---

## Executive Summary

This report analyzes YOLO26 object detection performance against expected labels from synthetic security footage. The validation covered 10 scenarios with 59 detections.

### Key Findings

- **Precision:** 54.55% (below target of >85%)
- **Recall:** 100.00% (excellent - no false negatives)
- **F1 Score:** 70.59% (degraded by poor precision)
- **Primary Issue:** False positive car detections in background (10 out of 22 detections)
- **Secondary Issue:** 2 person detections below confidence thresholds

### Recommendation Priority

1. **Critical:** Fix false positive car detections (NEM-4523)
2. **High:** Improve validation coverage to 100+ scenarios (NEM-4527)
3. **Medium:** Address low confidence person detections (NEM-4524)
4. **Medium:** Add class-specific metrics (NEM-4529)
5. **Medium:** Investigate missing object classes (NEM-4531)

---

## Metrics Breakdown

### Aggregate Performance

| Metric          | Value   | Target | Status  |
| --------------- | ------- | ------ | ------- |
| **Precision**   | 54.55%  | >85%   | ❌ FAIL |
| **Recall**      | 100.00% | >85%   | ✅ PASS |
| **F1 Score**    | 70.59%  | >85%   | ❌ FAIL |
| True Positives  | 12      | -      | -       |
| False Positives | 10      | -      | -       |
| False Negatives | 0       | -      | -       |

### Scenario Coverage

| Category   | Scenarios Validated | Total Available | Coverage |
| ---------- | ------------------: | --------------: | -------: |
| Normal     |                   4 |             ~50 |       8% |
| Suspicious |                   1 |             ~15 |       7% |
| Threats    |                   5 |             ~20 |      25% |
| **Total**  |              **10** |       **~100+** | **~10%** |

---

## Issue Analysis

### 1. False Positive Car Detections (Critical)

**Issue ID:** NEM-4523
**Impact:** Precision 54.55% (should be >85%)

#### Details

YOLO26 is detecting small background vehicles that are not relevant to the security event. These are technically true positives (they are cars) but contextually false positives (not the focus of the scene).

#### Examples

**Scenario: delivery_driver_20260125_180409**

- 8 unexpected car detections
- Confidence range: 0.606 - 0.756
- Bbox sizes: 33-39 pixels (very small - distant vehicles)
- Expected: person only

**Scenario: loitering_20260125_181405**

- 2 unexpected car detections
- Confidence: 0.613, 0.826
- Bbox sizes: 46x20, 79x25 pixels
- Expected: person only

#### Root Cause

Small distant vehicles in background are detected when they are not the primary subject. The model is working correctly from a technical standpoint, but lacks contextual awareness.

#### Remediation Options

1. **Minimum bbox size filter:** Filter detections <50x50 pixels (distant objects)
2. **Update expected labels:** Add car expectations where appropriate
3. **Confidence threshold tuning:** Raise car detection threshold from 0.60 to 0.75
4. **Scene context filtering:** Implement salience/importance scoring
5. **Spatial attention:** Focus on detections in center/foreground of frame

---

### 2. Low Confidence Person Detections (Medium)

**Issue ID:** NEM-4524
**Impact:** Risk of false negatives in single-person scenarios

#### Details

Two person detections fell below minimum confidence thresholds, indicating model uncertainty.

#### Examples

| Scenario                        | Detection ID | Confidence | Min Required | Gap   | Scenario Type |
| ------------------------------- | ------------ | ---------- | ------------ | ----- | ------------- |
| vandalism_20260125_191245       | 47           | 0.662      | 0.700        | -5.4% | Threat        |
| delivery_driver_20260125_180409 | 8            | 0.723      | 0.800        | -9.6% | Normal        |

#### Analysis

These low-confidence detections may indicate:

- Partial occlusion of person
- Poor lighting conditions
- Unusual pose or angle
- Small person size in frame

**Note:** These scenarios still met requirements due to multiple high-confidence detections, but in single-person scenarios these would be false negatives.

#### Remediation Options

1. **Investigate frames:** Examine detection IDs 47 and 8 to understand root cause
2. **Training data augmentation:** Add similar edge cases to training set
3. **Model fine-tuning:** Fine-tune on security camera footage
4. **Multi-frame fusion:** Use temporal information to boost confidence
5. **Confidence policy:** Document acceptable ranges by object class

---

### 3. Limited Validation Coverage (High Priority)

**Issue ID:** NEM-4527
**Impact:** Unknown model performance on 90+ scenarios

#### Current Coverage

Only 10 out of 100+ scenarios have been validated:

**Validated:**

- delivery_driver_20260125_180409
- loitering_20260125_181405
- package_theft_20260125_181949
- pet_activity_20260125_180555
- resident_arrival_20260125_180812
- vandalism_20260125_184659
- vandalism_20260125_185117
- vandalism_20260125_190821
- vandalism_20260125_191245
- vehicle_parking_20260125_180954

**Not Validated:**

- Cosmos scenarios (E01-F16, P01-P47, C01+): ~80 scenarios
- Additional threat scenarios: weapon_visible, break_in_attempt
- Additional suspicious: casing, prowling, tailgating
- Additional normal: yard_maintenance

#### Impact

- Limited confidence in overall model performance
- Unknown accuracy on diverse scenarios (weather, wildlife, edge cases)
- Cannot identify class-specific weaknesses

#### Action Items

1. Process all synthetic videos through YOLO26
2. Import detections to database
3. Re-run validation on full dataset
4. Calculate class-specific and scenario-type metrics

---

### 4. Missing Object Classes (Research Required)

**Issue ID:** NEM-4531
**Impact:** Unknown model capabilities for specialized objects

#### Missing Classes

Based on expected_labels.json files, these classes are expected but not yet seen:

**Weapons/Threats:**

- firearm (weapon_visible scenarios)
- knife
- other threat objects

**Wildlife:**

- deer, rabbit, squirrel, raccoon, cat, bird

**Specialized Objects:**

- package/box (delivery scenarios)
- bicycle (cyclist scenarios)
- motorcycle, truck

#### Investigation Required

1. **Check processing status:** Have these scenarios been processed?
2. **Review YOLO26 capabilities:** Does it support these classes?
3. **Analyze failures:** Are expected objects not being detected?

#### Possible Outcomes

- **Scenario A:** Videos not yet processed → Process them
- **Scenario B:** Model limitations → Document or enhance model
- **Scenario C:** Detection failures → Investigate and fix

---

## Detailed Results by Scenario

### Scenarios with Issues

#### delivery_driver_20260125_180409 (Normal)

| Metric   | Value                                          |
| -------- | ---------------------------------------------- |
| Expected | 1 person (min_conf: 0.80)                      |
| Detected | 6 person, 8 car                                |
| Issues   | 8 false positive cars, 1 low confidence person |

**Analysis:**

- Person detection: 5 high-conf (0.932-0.950), 1 low-conf (0.723)
- Car detections: All small background objects (33-39px)
- Impact: Precision significantly reduced

#### loitering_20260125_181405 (Suspicious)

| Metric   | Value                     |
| -------- | ------------------------- |
| Expected | 1 person (min_conf: 0.75) |
| Detected | 2 person, 2 car           |
| Issues   | 2 false positive cars     |

**Analysis:**

- Person detection: 2 high-conf (0.954, 0.954)
- Car detections: Small background objects (46x20, 79x25px)
- Impact: Precision reduced

#### vandalism_20260125_191245 (Threat)

| Metric   | Value                     |
| -------- | ------------------------- |
| Expected | 3 person (min_conf: 0.70) |
| Detected | 16 person                 |
| Issues   | 1 low confidence person   |

**Analysis:**

- Person detection: 15 high-conf (0.887-0.961), 1 low-conf (0.662)
- Over-detection: 16 detections vs 3 expected (possible tracking across frames)
- Impact: Minor - still meets requirements

### Scenarios Performing Well

#### pet_activity_20260125_180555 (Normal)

| Metric   | Value                  |
| -------- | ---------------------- |
| Expected | 1 dog (min_conf: 0.70) |
| Detected | 3 dog                  |
| Issues   | None                   |

**Analysis:**

- Dog detection: 3 high-conf (0.896-0.958)
- Clean result: No false positives, all above threshold

#### vehicle_parking_20260125_180954 (Normal)

| Metric   | Value                  |
| -------- | ---------------------- |
| Expected | 1 car (min_conf: 0.80) |
| Detected | 3 car                  |
| Issues   | None                   |

**Analysis:**

- Car detection: 3 high-conf (0.950-0.964)
- Clean result: No false positives, all above threshold

#### vandalism scenarios (Threats)

Multiple vandalism scenarios performed well:

- vandalism_20260125_184659: 4 person detected, all >0.934
- vandalism_20260125_185117: 5 person detected, all >0.929
- vandalism_20260125_190821: 4 person detected, all >0.937

---

## Recommendations

### Immediate Actions (Week 1)

1. **Implement bbox size filter** (NEM-4523)

   - Filter out detections with bbox area <2500px² (50x50)
   - Test on validation set to ensure no false negatives
   - Measure precision improvement

2. **Investigate low-confidence detections** (NEM-4524)

   - Review frames for detection IDs 47 and 8
   - Document visual characteristics
   - Determine if training data needs augmentation

3. **Process remaining scenarios** (NEM-4527)
   - Run YOLO26 inference on all 100+ synthetic videos
   - Import to database
   - Re-run validation

### Short-term Improvements (Weeks 2-4)

4. **Enhance validation script** (NEM-4529)

   - Add per-class metrics (precision/recall/F1 per object type)
   - Add scenario-type metrics (normal/suspicious/threats)
   - Generate confidence distribution analysis
   - Export detailed CSV/JSON reports

5. **Research missing classes** (NEM-4531)

   - Document YOLO26 supported classes
   - Identify gaps (weapons, wildlife, specialized objects)
   - Plan for additional models or fine-tuning

6. **Implement confidence policies**
   - Define minimum confidence thresholds per class
   - Document acceptable ranges
   - Add threshold validation to CI/CD

### Long-term Enhancements (Month 2+)

7. **Scene context filtering**

   - Implement salience scoring
   - Focus on foreground/center objects
   - De-prioritize background detections

8. **Model fine-tuning**

   - Collect security camera training data
   - Fine-tune YOLO26 on domain-specific footage
   - Target edge cases (occlusion, lighting, poses)

9. **Multi-frame temporal fusion**

   - Use adjacent frames to boost confidence
   - Implement tracking-aware confidence aggregation
   - Reduce single-frame detection errors

10. **Automated validation pipeline**
    - Integrate validation into CI/CD
    - Set quality gates (precision >85%, recall >90%)
    - Alert on regression

---

## Appendix A: Validation Methodology

### Data Collection

1. **Database Query:**

   ```sql
   SELECT d.id, d.camera_id, d.file_path, d.object_type, d.confidence,
          d.bbox_x, d.bbox_y, d.bbox_width, d.bbox_height, d.detected_at
   FROM detections d
   ORDER BY d.detected_at DESC;
   ```

2. **Expected Labels:**

   - Source: `data/synthetic/*/expected_labels.json`
   - Format: JSON with detection expectations per scenario

3. **Mapping:**
   - Extracted scenario name from file path
   - Matched to expected_labels.json file
   - Grouped detections by scenario

### Comparison Logic

For each scenario:

1. **Match:** Detection class and confidence meet expectations
2. **Missing:** Expected class not detected or below confidence
3. **Extra:** Detected class not in expected list
4. **Low Confidence:** Detected but below min_confidence threshold

### Metrics Calculation

- **Precision:** TP / (TP + FP)
- **Recall:** TP / (TP + FN)
- **F1 Score:** 2 × (Precision × Recall) / (Precision + Recall)

Where:

- TP = Matched expected detections
- FP = Extra unexpected detections
- FN = Missing expected detections

---

## Appendix B: Linear Tasks Created

| Issue ID | Title                                                      | Priority | URL                                                                 |
| -------- | ---------------------------------------------------------- | -------- | ------------------------------------------------------------------- |
| NEM-4523 | Fix: False positive car detections in background           | High     | [Link](https://linear.app/nemotron-v3-home-security/issue/NEM-4523) |
| NEM-4524 | Fix: Low confidence person detections below threshold      | Medium   | [Link](https://linear.app/nemotron-v3-home-security/issue/NEM-4524) |
| NEM-4527 | Enhancement: Improve detection validation coverage         | Medium   | [Link](https://linear.app/nemotron-v3-home-security/issue/NEM-4527) |
| NEM-4529 | Feature: Add class-specific and scenario-type metrics      | Medium   | [Link](https://linear.app/nemotron-v3-home-security/issue/NEM-4529) |
| NEM-4531 | Research: Investigate missing object classes in detections | Medium   | [Link](https://linear.app/nemotron-v3-home-security/issue/NEM-4531) |

All tasks are linked to parent epic: **NEM-4522** (AI Pipeline Validation)

---

## Appendix C: Raw Data

Full validation results available at:

- `/tmp/detection_validation_results.json`

Validation script:

- `/home/msvoboda/.claude-squad/worktrees/msvoboda/fine8_188fe20254c51e93/scripts/validate_detections.py`

---

**End of Report**
