# Cosmos Synthetic Video Quality Report - Batch 3

**Generated:** 2026-01-28 11:35:15
**Analysis Scope:** P-series (P01-P48) and T-series (T01-T40)
**Note:** C-series only contains C01-C23, no C121+ videos exist in the repository.

---

## Executive Summary

**CRITICAL FINDING:** The Cosmos video generation pipeline has a systemic failure affecting 85% of analyzed videos. All P-series and T-series videos are generated with identical content regardless of requested duration (5s, 10s, or 30s).

### Key Issues Identified

1. **Duplicate Content Epidemic:** 88 video IDs have byte-identical files across all duration variants
2. **Frame Rate Mismatch:** Videos generated at 16 fps instead of manifest-specified 24 fps
3. **Fixed Duration Output:** All videos are exactly 93 frames / 5.81 seconds regardless of `num_output_frames` setting
4. **Autoregressive Mode Failure:** Sliding window generation for longer durations is not functioning

---

## Summary Statistics

| Metric                | Count |
| --------------------- | ----- |
| Total Videos Analyzed | 264   |
| Passed                | 40    |
| Failed                | 224   |
| Pass Rate             | 15.2% |

### By Series

| Series | Total | Passed | Failed | Description                                   |
| ------ | ----- | ------ | ------ | --------------------------------------------- |
| P      | 168   | 24     | 144    | Presentation videos (delivery, visitor, etc.) |
| T      | 96    | 16     | 80     | Threat/Training videos (security scenarios)   |

### Technical Analysis

All analyzed videos show identical technical characteristics:

| Parameter    | Expected   | Actual    | Status   |
| ------------ | ---------- | --------- | -------- |
| Frame Rate   | 24 fps     | 16 fps    | MISMATCH |
| 5s Duration  | 120 frames | 93 frames | MISMATCH |
| 10s Duration | 240 frames | 93 frames | CRITICAL |
| 30s Duration | 720 frames | 93 frames | CRITICAL |
| Resolution   | 1280x704   | 1280x704  | OK       |
| Codec        | H.264      | H.264     | OK       |

---

## Duplicate Detection

**Found 88 video IDs with duplicate content across duration variants.**

This is a critical issue - for each video ID (e.g., P01), the 5s, 10s, and 30s variants are byte-identical files. They are not just similar content but literally the same file with different names.

### P-Series Duplicates (48 video IDs)

| Video ID | 5s Hash  | 10s Hash | 30s Hash | Issue           |
| -------- | -------- | -------- | -------- | --------------- |
| P01      | 58323710 | 58323710 | 58323710 | Identical files |
| P02      | 0edee66d | 0edee66d | 0edee66d | Identical files |
| P03      | 5f100d64 | 5f100d64 | 5f100d64 | Identical files |
| P04      | bee43441 | bee43441 | bee43441 | Identical files |
| P05      | 55567c26 | 55567c26 | 55567c26 | Identical files |
| P06      | dd0d2e66 | dd0d2e66 | dd0d2e66 | Identical files |
| P07      | c5690be6 | c5690be6 | c5690be6 | Identical files |
| P08      | 91cfd794 | 91cfd794 | 91cfd794 | Identical files |
| P09      | c79e8af8 | c79e8af8 | c79e8af8 | Identical files |
| P10      | 145c9c2d | 145c9c2d | 145c9c2d | Identical files |
| P11      | 3a9c786c | 3a9c786c | 3a9c786c | Identical files |
| P12      | 03fcc9d5 | 03fcc9d5 | 03fcc9d5 | Identical files |
| P13      | 3749aafa | 3749aafa | 3749aafa | Identical files |
| P14      | 6ee51057 | 6ee51057 | 6ee51057 | Identical files |
| P15      | 33cc2111 | 33cc2111 | 33cc2111 | Identical files |
| P16      | 6152a371 | 6152a371 | 6152a371 | Identical files |
| P17      | 8136182e | 8136182e | 8136182e | Identical files |
| P18      | 7d16ec67 | 7d16ec67 | 7d16ec67 | Identical files |
| P19      | 745cc6fd | 745cc6fd | 745cc6fd | Identical files |
| P20      | d5fb2e16 | d5fb2e16 | d5fb2e16 | Identical files |
| P21      | 27ed4c3c | 27ed4c3c | 27ed4c3c | Identical files |
| P22      | 15517058 | 15517058 | 15517058 | Identical files |
| P23      | f09c213c | f09c213c | f09c213c | Identical files |
| P24      | ba8ee9c1 | ba8ee9c1 | ba8ee9c1 | Identical files |
| P25      | d1b77750 | d1b77750 | d1b77750 | Identical files |
| P26      | 03ef6f94 | 03ef6f94 | 03ef6f94 | Identical files |
| P27      | ff6edc55 | ff6edc55 | ff6edc55 | Identical files |
| P28      | 8601a447 | 8601a447 | 8601a447 | Identical files |
| P29      | 42ac07fa | 42ac07fa | 42ac07fa | Identical files |
| P30      | aa1585a7 | aa1585a7 | aa1585a7 | Identical files |
| P31      | 3a51867a | 3a51867a | 3a51867a | Identical files |
| P32      | fdea1749 | fdea1749 | fdea1749 | Identical files |
| P33      | c6cb54c3 | c6cb54c3 | c6cb54c3 | Identical files |
| P34      | e96966b4 | e96966b4 | e96966b4 | Identical files |
| P35      | 6deca764 | 6deca764 | 6deca764 | Identical files |
| P36      | 73a945e4 | 73a945e4 | 73a945e4 | Identical files |
| P37      | c2d29b37 | c2d29b37 | c2d29b37 | Identical files |
| P38      | 316fe252 | 316fe252 | 316fe252 | Identical files |
| P39      | 16cfcd50 | 16cfcd50 | 16cfcd50 | Identical files |
| P40      | b4a9e7b8 | b4a9e7b8 | b4a9e7b8 | Identical files |
| P41      | f3215b43 | f3215b43 | f3215b43 | Identical files |
| P42      | 28a327a9 | 28a327a9 | 28a327a9 | Identical files |
| P43      | d042f5da | d042f5da | d042f5da | Identical files |
| P44      | 22713207 | 22713207 | 22713207 | Identical files |
| P45      | 738d18aa | 738d18aa | 738d18aa | Identical files |
| P46      | 77c6e561 | 77c6e561 | 77c6e561 | Identical files |
| P47      | 09812db5 | 09812db5 | 09812db5 | Identical files |
| P48      | 0b4b3ecf | 0b4b3ecf | 0b4b3ecf | Identical files |

### T-Series Duplicates (40 video IDs)

| Video ID | 5s Hash  | 10s Hash | 30s Hash | Issue           |
| -------- | -------- | -------- | -------- | --------------- |
| T01      | 3ca4390a | 3ca4390a | N/A      | Identical files |
| T02      | e04e53f0 | e04e53f0 | N/A      | Identical files |
| T03      | a2435028 | a2435028 | N/A      | Identical files |
| T04      | 62c143db | 62c143db | N/A      | Identical files |
| T05      | 04ece07b | 04ece07b | N/A      | Identical files |
| T06      | 61a643cd | 61a643cd | N/A      | Identical files |
| T07      | 02cf5f92 | 02cf5f92 | N/A      | Identical files |
| T08      | 0e425b93 | 0e425b93 | N/A      | Identical files |
| T09      | bf88a1ea | bf88a1ea | N/A      | Identical files |
| T10      | 772d364b | 772d364b | N/A      | Identical files |
| T11      | 7618e7c6 | 7618e7c6 | N/A      | Identical files |
| T12      | da3caaca | da3caaca | N/A      | Identical files |
| T13      | 4235e9b8 | 4235e9b8 | N/A      | Identical files |
| T14      | cfefbe4d | cfefbe4d | N/A      | Identical files |
| T15      | dcaadaf1 | dcaadaf1 | N/A      | Identical files |
| T16      | 11cd8b91 | 11cd8b91 | N/A      | Identical files |
| T17      | 070ef017 | 070ef017 | N/A      | Identical files |
| T18      | 08d5d8ed | 08d5d8ed | N/A      | Identical files |
| T19      | f2d19d47 | f2d19d47 | N/A      | Identical files |
| T20      | 3db96eda | 3db96eda | N/A      | Identical files |
| T21      | 76525ccd | 76525ccd | N/A      | Identical files |
| T22      | 04c234d7 | 04c234d7 | N/A      | Identical files |
| T23      | e96af14b | e96af14b | N/A      | Identical files |
| T24      | 460c62e7 | 460c62e7 | N/A      | Identical files |
| T25      | 749c4870 | 749c4870 | N/A      | Identical files |
| T26      | b2d74cf5 | b2d74cf5 | N/A      | Identical files |
| T27      | f4f7ff55 | f4f7ff55 | N/A      | Identical files |
| T28      | 1f4f1637 | 1f4f1637 | N/A      | Identical files |
| T29      | a1a40175 | a1a40175 | N/A      | Identical files |
| T30      | b7402db6 | b7402db6 | N/A      | Identical files |
| T31      | 595f473e | 595f473e | N/A      | Identical files |
| T32      | ed196c9f | ed196c9f | N/A      | Identical files |
| T33      | 44d8886d | 44d8886d | N/A      | Identical files |
| T34      | 05da277b | 05da277b | N/A      | Identical files |
| T35      | 8d6d2bd4 | 8d6d2bd4 | N/A      | Identical files |
| T36      | d2f49be1 | d2f49be1 | N/A      | Identical files |
| T37      | 1b442134 | 1b442134 | N/A      | Identical files |
| T38      | 4202b1af | 4202b1af | N/A      | Identical files |
| T39      | fdec4e6c | fdec4e6c | N/A      | Identical files |
| T40      | 9c8a722c | 9c8a722c | N/A      | Identical files |

---

## Issues Found

**Found 224 issues across videos.**

### Duration Mismatch (224 occurrences)

All videos with duration suffixes (\_5s, \_10s, \_30s) have the wrong duration. Sample:

| Filename    | Expected | Actual | Delta   |
| ----------- | -------- | ------ | ------- |
| P01_5s.mp4  | 5.00s    | 5.81s  | +0.81s  |
| P01_10s.mp4 | 10.00s   | 5.81s  | -4.19s  |
| P01_30s.mp4 | 30.00s   | 5.81s  | -24.19s |
| T01_5s.mp4  | 5.00s    | 5.81s  | +0.81s  |
| T01_10s.mp4 | 10.00s   | 5.81s  | -4.19s  |

**Root Cause Analysis:**

- Prompt files specify `num_output_frames`: 120 (5s), 240 (10s), 720 (30s) at 24 fps
- Actual output: 93 frames at 16 fps = 5.8125s regardless of setting
- The `num_output_frames` parameter appears to be ignored by the generation pipeline
- Frame rate defaults to 16 fps instead of manifest-specified 24 fps

---

## Videos Needing Regeneration

**Total: 224 videos need regeneration**

### Regeneration Priority

#### Priority 1: Critical (Wrong Duration)

All 10s and 30s variants need complete regeneration with corrected pipeline:

- P01-P48: 96 videos (48 x 2 variants)
- T01-T40: 40 videos (40 x 1 variant each for 10s)

#### Priority 2: Duration Fix (5s variants)

5s variants are close (5.81s vs 5.00s) but still exceed tolerance:

- P01-P48: 48 videos
- T01-T40: 40 videos

### Complete Regeneration List

| Series    | Video IDs | Variants           | Count   |
| --------- | --------- | ------------------ | ------- |
| P         | P01-P48   | \_5s, \_10s, \_30s | 144     |
| T         | T01-T40   | \_5s, \_10s        | 80      |
| **Total** |           |                    | **224** |

---

## Prompt Adjustment Suggestions

Based on the analysis, the following pipeline fixes are required:

### 1. Frame Rate Configuration (CRITICAL)

**Problem:** Videos generated at 16 fps, not 24 fps as specified in manifest.

**Fix:**

```yaml
# generation_manifest.yaml
defaults:
  fps: 24 # Currently being ignored
```

Verify the generation script passes `--fps 24` or equivalent to the Cosmos model.

### 2. Duration/Frame Count Parameter (CRITICAL)

**Problem:** `num_output_frames` parameter is being ignored.

**Fix:**

- Verify `--num_output_frames` is passed correctly to inference
- Check if Cosmos-Predict2.5-14B supports variable frame counts
- Consider using native 5-second clips with concatenation for longer durations

### 3. Autoregressive Mode (CRITICAL)

**Problem:** Sliding window generation for longer durations is not functioning.

**Fix:**

```yaml
# generation_manifest.yaml
training:
  autoregressive_mode: 'sliding_window'
  num_iterations: 6 # 6 x 5s = 30s
```

- Verify sliding window implementation is correctly chaining clips
- Implement clip concatenation as fallback for 10s/30s variants

### 4. Unique Seeds for Variants

**Problem:** All variants use seed=0, potentially causing identical generation.

**Fix:**

```json
{
  "seed": 0, // 5s variant
  "seed": 1, // 10s variant
  "seed": 2 // 30s variant
}
```

Or use hash of filename as seed for reproducibility:

```python
seed = hash(f"{video_id}_{duration}") % (2**32)
```

### 5. File Deduplication in Pipeline

**Problem:** Pipeline may be copying base file for all variants instead of generating.

**Fix:**

- Add file hash verification after generation
- Fail if output matches any existing file hash
- Add size sanity checks (30s video should be ~6x size of 5s)

---

## Playability Status

**Good news:** All videos are technically playable.

| Metric                 | Status         |
| ---------------------- | -------------- |
| Files readable         | 264/264 (100%) |
| Valid MP4 container    | 264/264 (100%) |
| Video stream present   | 264/264 (100%) |
| Correct resolution     | 264/264 (100%) |
| No corruption detected | 264/264 (100%) |

---

## Passed Videos (Sample)

These videos have no duration suffix and match their expected characteristics:

| Filename | Duration | Resolution | Size    | Status |
| -------- | -------- | ---------- | ------- | ------ |
| P01.mp4  | 5.81s    | 1280x704   | 0.26 MB | OK     |
| P02.mp4  | 5.81s    | 1280x704   | 0.15 MB | OK     |
| P03.mp4  | 5.81s    | 1280x704   | 0.23 MB | OK     |
| P04.mp4  | 5.81s    | 1280x704   | 0.25 MB | OK     |
| P05.mp4  | 5.81s    | 1280x704   | 0.32 MB | OK     |
| T01.mp4  | 5.81s    | 1280x704   | 0.31 MB | OK     |
| T08.mp4  | 5.81s    | 1280x704   | 0.28 MB | OK     |
| T09.mp4  | 5.81s    | 1280x704   | 0.22 MB | OK     |

_Note: 40 videos passed because they don't have duration suffixes, so no duration expectation was set._

---

## Recommendations

### Immediate Actions

1. **Halt further video generation** until pipeline issues are fixed
2. **Audit generation script** for parameter passthrough issues
3. **Test with single video** to verify fixes before batch regeneration

### Pipeline Fixes Required

1. Fix `num_output_frames` parameter passthrough
2. Fix `fps` parameter (24 fps target)
3. Implement proper sliding window autoregressive generation
4. Add unique seeds per duration variant
5. Add output validation (hash check, size check, duration check)

### Regeneration Strategy

After fixes:

1. Regenerate all P-series (P01-P48) variants: 144 videos
2. Regenerate all T-series (T01-T40) variants: 80 videos
3. Verify each batch with automated quality checks before proceeding

---

## Appendix: Analysis Methodology

### Tools Used

- `ffprobe` for video metadata extraction
- MD5 hashing for duplicate detection
- Python script for batch analysis

### Tolerance Settings

- Duration tolerance: +/- 0.5 seconds
- Hash comparison: Exact match for duplicate detection

### Files Analyzed

- Location: `data/synthetic/cosmos/videos/`
- Prompts: `data/synthetic/cosmos/prompts/generated/`
- Manifest: `data/synthetic/cosmos/generation_manifest.yaml`

---

_Report generated by automated analysis script_
_Raw data available in: batch3_quality_report.json_
