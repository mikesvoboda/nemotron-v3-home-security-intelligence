# Cosmos Synthetic Video Quality Report - Batch 1 (C01-C23)

**Analysis Date:** 2026-01-28
**Videos Analyzed:** 69 files across 23 video IDs
**Video ID Range:** C01-C23 (Note: C24-C60 do not exist in the dataset)

## Summary Statistics

| Metric               | Count | Percentage |
| -------------------- | ----- | ---------- |
| **Video IDs Passed** | 0     | 0.0%       |
| **Video IDs Failed** | 23    | 100.0%     |
| **Total Files**      | 69    | -          |

## Critical Issues Detected

### 1. Duration Mismatch (ALL VIDEOS AFFECTED)

**Problem:** All videos have the same actual duration (~5.81s / 93 frames at 16fps) regardless of whether the filename indicates 5s, 10s, or 30s.

**Expected Behavior:**

- `*_5s.mp4` should be ~5 seconds (120 frames at 24fps, or 80 frames at 16fps)
- `*_10s.mp4` should be ~10 seconds (240 frames at 24fps, or 160 frames at 16fps)
- `*_30s.mp4` should be ~30 seconds (720 frames at 24fps, or 480 frames at 16fps)

**Actual Behavior:**

- ALL videos are 5.8125 seconds (93 frames at 16fps)

**Root Cause:** The Cosmos generation pipeline appears to ignore the `num_output_frames` parameter in the prompt JSON files.

### 2. Duplicate Content (ALL VIDEOS AFFECTED)

**Problem:** For every video ID (C01-C23), the 5s, 10s, and 30s variants are byte-for-byte identical (same MD5 hash).

| Video ID | 5s Hash     | 10s Hash    | 30s Hash    | Status    |
| -------- | ----------- | ----------- | ----------- | --------- |
| C01      | 76e0a163... | 76e0a163... | 76e0a163... | DUPLICATE |
| C02      | 388b7f32... | 388b7f32... | 388b7f32... | DUPLICATE |
| C03      | b9cec1d9... | b9cec1d9... | b9cec1d9... | DUPLICATE |
| C04      | de6f87a4... | de6f87a4... | de6f87a4... | DUPLICATE |
| C05      | 10a01501... | 10a01501... | 10a01501... | DUPLICATE |
| C06      | a64a66e6... | a64a66e6... | a64a66e6... | DUPLICATE |
| C07      | 6bbbe7e6... | 6bbbe7e6... | 6bbbe7e6... | DUPLICATE |
| C08      | 825ad227... | 825ad227... | 825ad227... | DUPLICATE |
| C09      | dd52f701... | dd52f701... | dd52f701... | DUPLICATE |
| C10      | 51ae6568... | 51ae6568... | 51ae6568... | DUPLICATE |
| C11      | 39b642ed... | 39b642ed... | 39b642ed... | DUPLICATE |
| C12      | 9c882109... | 9c882109... | 9c882109... | DUPLICATE |
| C13      | 401d17df... | 401d17df... | 401d17df... | DUPLICATE |
| C14      | 21167caf... | 21167caf... | 21167caf... | DUPLICATE |
| C15      | bf2b06b3... | bf2b06b3... | bf2b06b3... | DUPLICATE |
| C16      | 6e8d3e32... | 6e8d3e32... | 6e8d3e32... | DUPLICATE |
| C17      | 53b722df... | 53b722df... | 53b722df... | DUPLICATE |
| C18      | dc5553cc... | dc5553cc... | dc5553cc... | DUPLICATE |
| C19      | 8a2870eb... | 8a2870eb... | 8a2870eb... | DUPLICATE |
| C20      | 8985f6c5... | 8985f6c5... | 8985f6c5... | DUPLICATE |
| C21      | e1d08759... | e1d08759... | e1d08759... | DUPLICATE |
| C22      | 0f0d173e... | 0f0d173e... | 0f0d173e... | DUPLICATE |
| C23      | e9c5f7f4... | e9c5f7f4... | e9c5f7f4... | DUPLICATE |

### 3. Playability Status

**All videos are technically playable.** No corruption or encoding errors detected.

| Property        | Value              |
| --------------- | ------------------ |
| Codec           | H.264              |
| Resolution      | 1280x704           |
| Frame Rate      | 16 fps             |
| Pixel Format    | yuv420p            |
| Duration        | ~5.81s (93 frames) |
| Decoding Errors | None               |

## Videos Requiring Regeneration

**ALL 69 videos need regeneration** due to the duration/duplicate issues.

### Regeneration Priority

| Priority      | Video IDs                  | Reason                                     |
| ------------- | -------------------------- | ------------------------------------------ |
| P1 - Critical | C01-C23 (all 10s variants) | Wrong duration (should be 10s, is 5.8s)    |
| P1 - Critical | C01-C23 (all 30s variants) | Wrong duration (should be 30s, is 5.8s)    |
| P2 - Moderate | C01-C23 (all 5s variants)  | Slightly longer than expected (5.8s vs 5s) |

### Detailed Issue List

| Video ID | Issues                                                                                                                                                                         |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| C01      | C01_5s.mp4: Expected ~5.0s, got 5.81s; C01_10s.mp4: Expected ~10.0s, got 5.81s; C01_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C02      | C02_5s.mp4: Expected ~5.0s, got 5.81s; C02_10s.mp4: Expected ~10.0s, got 5.81s; C02_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C03      | C03_5s.mp4: Expected ~5.0s, got 5.81s; C03_10s.mp4: Expected ~10.0s, got 5.81s; C03_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C04      | C04_5s.mp4: Expected ~5.0s, got 5.81s; C04_10s.mp4: Expected ~10.0s, got 5.81s; C04_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C05      | C05_5s.mp4: Expected ~5.0s, got 5.81s; C05_10s.mp4: Expected ~10.0s, got 5.81s; C05_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C06      | C06_5s.mp4: Expected ~5.0s, got 5.81s; C06_10s.mp4: Expected ~10.0s, got 5.81s; C06_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C07      | C07_5s.mp4: Expected ~5.0s, got 5.81s; C07_10s.mp4: Expected ~10.0s, got 5.81s; C07_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C08      | C08_5s.mp4: Expected ~5.0s, got 5.81s; C08_10s.mp4: Expected ~10.0s, got 5.81s; C08_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C09      | C09_5s.mp4: Expected ~5.0s, got 5.81s; C09_10s.mp4: Expected ~10.0s, got 5.81s; C09_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C10      | C10_5s.mp4: Expected ~5.0s, got 5.81s; C10_10s.mp4: Expected ~10.0s, got 5.81s; C10_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C11      | C11_5s.mp4: Expected ~5.0s, got 5.81s; C11_10s.mp4: Expected ~10.0s, got 5.81s; C11_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C12      | C12_5s.mp4: Expected ~5.0s, got 5.81s; C12_10s.mp4: Expected ~10.0s, got 5.81s; C12_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C13      | C13_5s.mp4: Expected ~5.0s, got 5.81s; C13_10s.mp4: Expected ~10.0s, got 5.81s; C13_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C14      | C14_5s.mp4: Expected ~5.0s, got 5.81s; C14_10s.mp4: Expected ~10.0s, got 5.81s; C14_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C15      | C15_5s.mp4: Expected ~5.0s, got 5.81s; C15_10s.mp4: Expected ~10.0s, got 5.81s; C15_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C16      | C16_5s.mp4: Expected ~5.0s, got 5.81s; C16_10s.mp4: Expected ~10.0s, got 5.81s; C16_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C17      | C17_5s.mp4: Expected ~5.0s, got 5.81s; C17_10s.mp4: Expected ~10.0s, got 5.81s; C17_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C18      | C18_5s.mp4: Expected ~5.0s, got 5.81s; C18_10s.mp4: Expected ~10.0s, got 5.81s; C18_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C19      | C19_5s.mp4: Expected ~5.0s, got 5.81s; C19_10s.mp4: Expected ~10.0s, got 5.81s; C19_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C20      | C20_5s.mp4: Expected ~5.0s, got 5.81s; C20_10s.mp4: Expected ~10.0s, got 5.81s; C20_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C21      | C21_5s.mp4: Expected ~5.0s, got 5.81s; C21_10s.mp4: Expected ~10.0s, got 5.81s; C21_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C22      | C22_5s.mp4: Expected ~5.0s, got 5.81s; C22_10s.mp4: Expected ~10.0s, got 5.81s; C22_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |
| C23      | C23_5s.mp4: Expected ~5.0s, got 5.81s; C23_10s.mp4: Expected ~10.0s, got 5.81s; C23_30s.mp4: Expected ~30.0s, got 5.81s; All 3 duration variants are IDENTICAL (same MD5 hash) |

## Prompt Content Summary

The prompts describe challenging security camera scenarios for AI training:

| Video ID | Scenario                    | Challenge Type       |
| -------- | --------------------------- | -------------------- |
| C01      | Night + heavy rain          | Weather + Visibility |
| C02      | Snowfall                    | Weather + Visibility |
| C03      | Dense fog                   | Weather + Visibility |
| C04      | Hail storm                  | Weather              |
| C05      | Strong wind                 | Weather              |
| C06      | Harsh backlight/silhouette  | Lighting             |
| C07      | Car headlights at night     | Dynamic Lighting     |
| C08      | Flashlight illumination     | Dynamic Lighting     |
| C09      | Thunderstorm lightning      | Dynamic Lighting     |
| C10      | Sunrise auto-exposure       | Lighting Transition  |
| C11      | Umbrella occlusion          | Occlusion            |
| C12      | Large package occlusion     | Occlusion            |
| C13      | Crowd occlusion             | Occlusion            |
| C14      | Stroller occlusion          | Occlusion            |
| C15      | Person sprinting            | Fast Motion          |
| C16      | Cyclist fast motion         | Fast Motion          |
| C17      | Rain gear face concealment  | Face Obscured        |
| C18      | Winter clothing concealment | Face Obscured        |
| C19      | Halloween costume/mask      | Face Obscured        |
| C20      | Motorcycle helmet           | Face Obscured        |
| C21      | Far to near scale change    | Scale Variation      |
| C22      | Extreme overhead angle      | Camera Angle         |
| C23      | Split attention (2 events)  | Multi-Subject        |

## Root Cause Analysis

### Why Are Duration Variants Identical?

Analysis of `batch_generate.sh` reveals the generation pipeline passes **all prompt files** to the Cosmos inference script in a single batch:

```bash
docker run ... cosmos-b300 \
    python examples/inference.py \
    -i ${INPUT_FILES[*]} \  # All 501 prompt files at once
    -o /workspace/outputs/security_videos \
    --inference-type=text2world \
    --model=14B/post-trained \
    --disable-guardrails
```

**Problem 1: Output Filename Handling**
The Cosmos script likely uses the `name` field from each JSON file to determine the output filename. When processing `C01_5s.json`, `C01_10s.json`, and `C01_30s.json` sequentially:

- All three have the same prompt text (only `num_output_frames` differs)
- If Cosmos caches results by prompt text, it may output the same video three times
- OR the script may be copying a single output to all three filenames

**Problem 2: `num_output_frames` Not Passed as CLI Argument**
The inference script is called with fixed parameters. The `num_output_frames` value in the JSON file may not be read by the inference script, or Cosmos may use a default value regardless.

**Likely Fix Required:**
The generation must either:

1. Pass `--num-output-frames` as a CLI argument for each video
2. Run separate inference calls for each duration variant
3. Modify the JSON parsing to actually use the `num_output_frames` field

### Why 93 Frames at 16fps?

Cosmos Predict 2.5 has a **default output of 93 frames at 16fps** (~5.8 seconds). This appears to be the model's native inference length when no explicit duration is specified.

For longer videos (10s, 30s), Cosmos requires:

- **Autoregressive generation** - generating in chunks and continuing from the last frame
- This may need explicit CLI flags or API parameters not currently being passed

## Prompt Adjustment Recommendations

The prompts are well-structured for their intended scenarios. However, the following adjustments are recommended for regeneration:

### 1. Frame Count Clarification

**Current prompt format:**

```json
{
  "num_output_frames": 240 // for 10s @ 24fps
}
```

**Problem:** Cosmos is generating at 16fps, not 24fps. Also, `num_output_frames` appears to be ignored.

**Recommendation:**

- Investigate why Cosmos ignores the frame count parameter
- Add explicit duration in the prompt text: "Duration: exactly 10 seconds of video"
- Consider using a different Cosmos API parameter for duration control

### 2. Frame Rate Alignment

**Current:** Prompts assume 24fps (e.g., 120 frames for 5s)
**Actual:** Cosmos generates at 16fps

**Recommendation:** Update `num_output_frames` calculations for 16fps:

- 5s video: 80 frames (not 120)
- 10s video: 160 frames (not 240)
- 30s video: 480 frames (not 720)

### 3. Batch Generation Pipeline Fix

The root cause is likely in the generation pipeline (`batch_generate.sh` or `parallel_generate.py`) not correctly passing duration parameters to Cosmos.

**Files to investigate:**

- `data/synthetic/cosmos/batch_generate.sh`
- `data/synthetic/cosmos/parallel_generate.py`
- Cosmos API call parameters

## Regeneration Commands

After fixing the pipeline issues, regenerate using:

```bash
# Regenerate all C-series videos with correct durations
cd data/synthetic/cosmos
./batch_generate.sh --ids C01-C23 --durations 5s,10s,30s --force

# Or individual regeneration
./batch_generate.sh --id C01 --duration 10s --force
./batch_generate.sh --id C01 --duration 30s --force
```

## Action Items

1. **[CRITICAL]** Fix Cosmos generation pipeline to respect `num_output_frames` parameter
2. **[CRITICAL]** Ensure each duration variant (5s/10s/30s) is generated separately with unique content
3. **[HIGH]** Update frame count calculations for 16fps output
4. **[MEDIUM]** Add duration validation in the generation pipeline to catch this issue early
5. **[LOW]** Consider adding explicit duration text to prompts as fallback

---

_Report generated by automated quality analysis script_
