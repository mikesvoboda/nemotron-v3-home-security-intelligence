# Cosmos Video Regeneration Handoff

**Date:** 2026-01-28
**Status:** ALL VIDEOS REQUIRE REGENERATION
**Priority:** Critical

---

## Executive Summary

Quality analysis of all 496 Cosmos synthetic videos reveals **systemic generation pipeline failures**. Every video has the same issues regardless of series (C/E/F/R/P/T).

| Metric | Value |
|--------|-------|
| Total videos analyzed | 496 |
| Screenshots extracted | 1,488 (3 per video) |
| Videos passing QA | 0 (0%) |
| Videos requiring regeneration | 496 (100%) |

---

## Critical Issues Found

### 1. All Duration Variants Are Identical (100% affected)

The 5s, 10s, and 30s variants for each video ID are **byte-for-byte identical copies**.

```
C01_5s.mp4:  MD5 76e0a163...  (643 KB)
C01_10s.mp4: MD5 76e0a163...  (643 KB)  <- SAME
C01_30s.mp4: MD5 76e0a163...  (643 KB)  <- SAME
```

**Impact:** Instead of 496 unique videos, there are only ~167 unique clips copied 3 times each.

### 2. Wrong Duration (100% affected)

All videos are **5.81 seconds (93 frames at 16fps)** regardless of filename:

| Filename | Expected | Actual | Status |
|----------|----------|--------|--------|
| `*_5s.mp4` | 5.0s | 5.81s | WRONG |
| `*_10s.mp4` | 10.0s | 5.81s | CRITICAL |
| `*_30s.mp4` | 30.0s | 5.81s | CRITICAL |

### 3. Frame Rate Mismatch

| Parameter | Manifest Config | Actual Output |
|-----------|-----------------|---------------|
| FPS | 24 | 16 |
| 5s frames | 120 | 93 |
| 10s frames | 240 | 93 |
| 30s frames | 720 | 93 |

### 4. Generation Parameters Ignored

The `num_output_frames` values in `prompts/generated/*.json` are not being passed to Cosmos inference:

```json
// C01_30s.json specifies:
"num_output_frames": 720

// But Cosmos outputs 93 frames (default)
```

### 5. Autoregressive Mode Not Functioning

30-second videos require sliding window autoregressive generation (6 × 5s clips). This is configured in the manifest but not implemented in the generation scripts.

---

## Root Cause Analysis

The `batch_generate.sh` script does **not** pass the `--num-output-frames` CLI argument to Cosmos inference. The model uses its default output (93 frames at 16fps = 5.81s).

**Fix required in generation script:**

```bash
# CURRENT (broken):
python examples/inference.py -i $prompt_file -o $output_dir

# REQUIRED (fixed):
num_frames=$(jq -r '.num_output_frames' $prompt_file)
python examples/inference.py \
  -i $prompt_file \
  -o $output_dir \
  --num-output-frames $num_frames
```

---

## Video Series Breakdown

### C-Series: Core Detection (23 IDs × 3 = 69 files)
Basic security scenarios for detection model training.

### E-Series: Everyday Activity (22 IDs × 3 = 66 files)
Routine activities: deliveries, service workers, utility workers.
Expected risk level: LOW

### F-Series: False Alarms (16 IDs × 3 = 48 files)
Wildlife, weather effects, innocent activity.
Expected risk level: NONE

### R-Series: Risk/Threat (18 IDs × 3 = 54 files)
Package theft, break-in attempts, suspicious activity.
Expected risk level: HIGH
**Note:** R14-R18 missing 30s variants (5 files)

### P-Series: Presentation (48 IDs × 3 = 144 files)
Demo scenarios for threat escalation, cross-camera tracking, household recognition, vehicle+person.

### T-Series: Training (40 IDs × varies = 96+ files)
Weapons, aggression, tracking sequences for model training.

---

## Required Pipeline Fixes

### Priority 1: Critical (Must Fix)

1. **Pass `num_output_frames` to Cosmos CLI**
   ```bash
   --num-output-frames $(jq -r '.num_output_frames' $prompt)
   ```

2. **Generate each duration variant separately**
   - Do NOT copy files between 5s/10s/30s
   - Each must be a unique Cosmos inference run

3. **Implement autoregressive mode for 30s videos**
   - Use sliding window: 6 × 5s clips with overlap
   - Concatenate with seamless transitions

### Priority 2: High

4. **Fix frame rate (24fps target)**
   - Either update Cosmos config or adjust frame calculations

5. **Add unique seeds per duration variant**
   - Currently all use `seed: 0`
   - Use deterministic seeds: `seed = hash(video_id + duration)`

### Priority 3: Medium

6. **Add post-generation validation**
   ```bash
   # Validate each output:
   actual_duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $output)
   expected_duration=${filename%s.mp4}  # Extract from filename
   if [ "$actual_duration" != "$expected_duration" ]; then
     echo "FAILED: $output"
   fi
   ```

7. **Generate missing R-series 30s variants**
   - R14_30s.mp4, R15_30s.mp4, R16_30s.mp4, R17_30s.mp4, R18_30s.mp4

---

## Regeneration Commands

### Full Regeneration (All 496 Videos)

```bash
# On Cosmos machine (B300/H200):
cd /path/to/cosmos-predict2.5

# Copy fixed prompts
cp -r /path/to/nemotron/data/synthetic/cosmos/prompts/generated/* inputs/

# Run with fixed script (after implementing fixes above)
./batch_generate_fixed.sh

# Or parallel (8 GPU)
python parallel_generate.py --gpus 8 --validate
```

### Validation After Generation

```bash
# Check durations
for f in outputs/*.mp4; do
  duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  echo "$f: ${duration}s"
done

# Check for duplicates
md5sum outputs/*_5s.mp4 outputs/*_10s.mp4 outputs/*_30s.mp4 | sort | uniq -d -w32

# Verify unique hashes per duration variant
for id in C01 C02 C03; do
  echo "=== $id ==="
  md5sum outputs/${id}_*.mp4
done
```

---

## Screenshots Available

1,488 screenshots extracted for visual QA review:

```
data/synthetic/cosmos/screenshots/
├── C01_5s_frame1.jpg   # 0.5s from start
├── C01_5s_frame2.jpg   # middle
├── C01_5s_frame3.jpg   # 0.5s from end
├── ...
```

Use these to verify:
- Subject visibility and clarity
- Action matches prompt description
- Scene consistency
- No Cosmos hallucination artifacts

---

## Detailed Reports

| Report | Location |
|--------|----------|
| Batch 1 (C-series) | `analysis/batch1_quality_report.md` |
| Batch 2 (E/F/R-series) | `analysis/batch2_quality_report.md` |
| Batch 3 (P/T-series) | `analysis/batch3_quality_report.md` |
| Screenshots | `screenshots/extraction_report.txt` |

---

## Post-Regeneration Checklist

After videos are regenerated:

- [ ] Verify each video plays correctly with ffprobe
- [ ] Confirm duration matches filename (5s/10s/30s within 0.5s tolerance)
- [ ] Check that duration variants have DIFFERENT MD5 hashes
- [ ] Spot-check screenshots for visual quality
- [ ] Push to Git LFS: `git lfs push --all origin`
- [ ] Update `generation_status.json` with completion status
- [ ] Run security model inference on sample videos to validate training utility

---

## Contact

For questions about:
- **Cosmos model issues:** Check NVIDIA Cosmos documentation
- **Prompt adjustments:** Edit `prompts/templates/` and regenerate with `generate_prompts.py`
- **This codebase:** See main `CLAUDE.md` and `AGENTS.md`
