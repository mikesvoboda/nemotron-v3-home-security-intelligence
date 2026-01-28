# Cosmos Synthetic Video Quality Report - Batch 2

**Analysis Date:** 2026-01-28
**Video Series:** E-series (E01-E22), F-series (F01-F16), R-series (R01-R18)
**Total Videos Analyzed:** 163 files across 56 unique video IDs

---

## Executive Summary

| Metric                          | Count | Percentage |
| ------------------------------- | ----- | ---------- |
| **Total Files**                 | 163   | 100%       |
| **Unique Video IDs**            | 56    | -          |
| **Playable (Valid Streams)**    | 163   | 100%       |
| **Corrupt/Unplayable**          | 0     | 0%         |
| **Correct Duration**            | 0     | 0%         |
| **Wrong Duration**              | 163   | 100%       |
| **Duplicate Duration Variants** | 163   | 100%       |

### Critical Issues Identified

1. **ALL videos have wrong duration** - Every video is 5.8125s regardless of filename (5s/10s/30s)
2. **ALL duration variants are duplicates** - 5s, 10s, and 30s variants are byte-for-byte identical
3. **Generation parameters were ignored** - The `num_output_frames` settings in prompts were not applied

---

## Video Series Overview

### E-Series: Everyday/Expected Activity (22 videos)

Expected routine activities that should be classified as LOW risk:

- E01-E06: Delivery drivers (Amazon, FedEx, UPS, USPS, DoorDash, Instacart)
- E07-E11: Service professionals (landscaping, pool cleaning, pest control, mail carrier, newspaper)
- E12-E17: Utility workers (meter reading, cable tech, window washing, tree trimmer, irrigation, roofer)
- E18-E22: Routine visits (real estate showing, house sitter, babysitter, pet sitter, house cleaner)

### F-Series: False Alarms / Wildlife (16 videos)

Natural activities that should NOT trigger alerts:

- F01-F06: Wildlife (deer, rabbit, squirrel, raccoon, stray cat, bird)
- F07-F12: Weather/environmental (wind-blown debris, rain/sprinkler, shadow movement, car headlights, sun glare, cloud shadow)
- F13-F16: Innocent human activity (child retrieving toy, dog walker, jogger, lost neighbor looking for pet)

### R-Series: Risk/Threat Scenarios (18 videos)

Security threats requiring HIGH risk classification:

- R01-R06: Package theft patterns (grab-and-run, distraction theft, follow delivery)
- R07-R12: Break-in attempts (window check, door handle test, lock picking, forced entry)
- R13-R18: Suspicious activity (casing behavior, vandalism, prowling, confrontation, trespassing, unauthorized camping)

---

## Detailed Analysis

### Duration Analysis

| Expected Duration | Expected Frames (24fps) | Actual Duration | Actual Frames |
| ----------------- | ----------------------- | --------------- | ------------- |
| 5 seconds         | 120 frames              | 5.8125s         | ~140 frames   |
| 10 seconds        | 240 frames              | 5.8125s         | ~140 frames   |
| 30 seconds        | 720 frames              | 5.8125s         | ~140 frames   |

**Root Cause:** The Cosmos generation process appears to have used default parameters (140 frames) instead of respecting the `num_output_frames` specification in each prompt JSON file.

### Duplicate Detection Results

All 56 video IDs have identical content across their 5s/10s/30s variants:

#### E-Series Duplicates (22 IDs x 3 variants = 66 files)

| Video ID | Files | Unique Hashes | Status    |
| -------- | ----- | ------------- | --------- |
| E01      | 3     | 1             | DUPLICATE |
| E02      | 3     | 1             | DUPLICATE |
| E03      | 3     | 1             | DUPLICATE |
| E04      | 3     | 1             | DUPLICATE |
| E05      | 3     | 1             | DUPLICATE |
| E06      | 3     | 1             | DUPLICATE |
| E07      | 3     | 1             | DUPLICATE |
| E08      | 3     | 1             | DUPLICATE |
| E09      | 3     | 1             | DUPLICATE |
| E10      | 3     | 1             | DUPLICATE |
| E11      | 3     | 1             | DUPLICATE |
| E12      | 3     | 1             | DUPLICATE |
| E13      | 3     | 1             | DUPLICATE |
| E14      | 3     | 1             | DUPLICATE |
| E15      | 3     | 1             | DUPLICATE |
| E16      | 3     | 1             | DUPLICATE |
| E17      | 3     | 1             | DUPLICATE |
| E18      | 3     | 1             | DUPLICATE |
| E19      | 3     | 1             | DUPLICATE |
| E20      | 3     | 1             | DUPLICATE |
| E21      | 3     | 1             | DUPLICATE |
| E22      | 3     | 1             | DUPLICATE |

#### F-Series Duplicates (16 IDs x 3 variants = 48 files)

| Video ID | Files | Unique Hashes | Status    |
| -------- | ----- | ------------- | --------- |
| F01      | 3     | 1             | DUPLICATE |
| F02      | 3     | 1             | DUPLICATE |
| F03      | 3     | 1             | DUPLICATE |
| F04      | 3     | 1             | DUPLICATE |
| F05      | 3     | 1             | DUPLICATE |
| F06      | 3     | 1             | DUPLICATE |
| F07      | 3     | 1             | DUPLICATE |
| F08      | 3     | 1             | DUPLICATE |
| F09      | 3     | 1             | DUPLICATE |
| F10      | 3     | 1             | DUPLICATE |
| F11      | 3     | 1             | DUPLICATE |
| F12      | 3     | 1             | DUPLICATE |
| F13      | 3     | 1             | DUPLICATE |
| F14      | 3     | 1             | DUPLICATE |
| F15      | 3     | 1             | DUPLICATE |
| F16      | 3     | 1             | DUPLICATE |

#### R-Series Duplicates (18 IDs, mixed variants = 49 files)

| Video ID | Files | Unique Hashes | Status                  |
| -------- | ----- | ------------- | ----------------------- |
| R01      | 3     | 1             | DUPLICATE               |
| R02      | 3     | 1             | DUPLICATE               |
| R03      | 3     | 1             | DUPLICATE               |
| R04      | 3     | 1             | DUPLICATE               |
| R05      | 3     | 1             | DUPLICATE               |
| R06      | 3     | 1             | DUPLICATE               |
| R07      | 3     | 1             | DUPLICATE               |
| R08      | 3     | 1             | DUPLICATE               |
| R09      | 3     | 1             | DUPLICATE               |
| R10      | 3     | 1             | DUPLICATE               |
| R11      | 3     | 1             | DUPLICATE               |
| R12      | 3     | 1             | DUPLICATE               |
| R13      | 3     | 1             | DUPLICATE               |
| R14      | 2     | 1             | DUPLICATE (missing 30s) |
| R15      | 2     | 1             | DUPLICATE (missing 30s) |
| R16      | 2     | 1             | DUPLICATE (missing 30s) |
| R17      | 2     | 1             | DUPLICATE (missing 30s) |
| R18      | 2     | 1             | DUPLICATE (missing 30s) |

**Note:** R14-R18 are missing 30s variants entirely.

### Video Technical Specifications

All videos share these characteristics:

- **Codec:** H.264 (AVC)
- **Resolution:** 1280x704
- **Pixel Format:** yuv420p
- **Duration:** 5.812500 seconds
- **Frame Rate:** 16 fps (93 frames)
- **Playability:** All videos play without errors

---

## Videos Requiring Regeneration

### Priority 1: All Duration Variants (163 files)

All 5s/10s/30s variant files need regeneration with correct frame counts.

#### E-Series (66 files to regenerate)

| Video ID | Files                                         | Issue                      |
| -------- | --------------------------------------------- | -------------------------- |
| E01-E22  | E{ID}\_5s.mp4, E{ID}\_10s.mp4, E{ID}\_30s.mp4 | Duplicates, wrong duration |

#### F-Series (48 files to regenerate)

| Video ID | Files                                         | Issue                      |
| -------- | --------------------------------------------- | -------------------------- |
| F01-F16  | F{ID}\_5s.mp4, F{ID}\_10s.mp4, F{ID}\_30s.mp4 | Duplicates, wrong duration |

#### R-Series (49 files to regenerate + 5 missing)

| Video ID | Files                                         | Issue                                   |
| -------- | --------------------------------------------- | --------------------------------------- |
| R01-R13  | R{ID}\_5s.mp4, R{ID}\_10s.mp4, R{ID}\_30s.mp4 | Duplicates, wrong duration              |
| R14-R18  | R{ID}\_5s.mp4, R{ID}\_10s.mp4                 | Duplicates, wrong duration, missing 30s |

### Priority 2: Missing 30s Variants (5 files)

| Video ID | Missing File |
| -------- | ------------ |
| R14      | R14_30s.mp4  |
| R15      | R15_30s.mp4  |
| R16      | R16_30s.mp4  |
| R17      | R17_30s.mp4  |
| R18      | R18_30s.mp4  |

---

## Prompt Adjustment Suggestions

### Issue 1: Generation Script Not Respecting Parameters

The prompts correctly specify different frame counts:

- `{ID}_5s.json`: `"num_output_frames": 120`
- `{ID}_10s.json`: `"num_output_frames": 240`
- `{ID}_30s.json`: `"num_output_frames": 720`

**Suggested Fix:** Update the generation script (`batch_generate.sh` or `parallel_generate.py`) to:

1. Read the `num_output_frames` parameter from each JSON file
2. Pass it explicitly to the Cosmos model via `--num_frames` or equivalent CLI argument
3. Verify output duration after generation

### Issue 2: Autoregressive Generation for 30s Videos

The 30-second videos (720 frames) exceed Cosmos's native single-pass capability. Per `generation_manifest.yaml`:

```yaml
training:
  duration_total: 30 # seconds
  num_iterations: 6 # 6 x 5s = 30s using sliding window
  autoregressive_mode: 'sliding_window'
```

**Suggested Fix:** Implement autoregressive generation for 30s videos:

1. Generate initial 5s clip (120 frames)
2. Use last frame(s) as conditioning for next 5s
3. Repeat 6 times for 30s total
4. Concatenate segments with frame interpolation if needed

### Issue 3: Separate Generations Required

Each duration variant must be generated as a separate inference run.

**Suggested Fix:**

```bash
# For each video ID, run THREE separate generations:
cosmos generate --input E01_5s.json --num_frames 120 --output E01_5s.mp4
cosmos generate --input E01_10s.json --num_frames 240 --output E01_10s.mp4
cosmos generate --input E01_30s.json --num_frames 720 --output E01_30s.mp4
```

---

## Sample Prompts for Reference

### E01 (Amazon Delivery - Expected Activity)

```
Suburban home front porch at midday, viewed from an elevated vantage point near
the door. An Amazon delivery driver in blue Amazon vest walks up carrying a
package, places it at the door, takes a photo with phone, and walks back to blue
Amazon van. Standard delivery. Static elevated viewpoint, clear daytime footage.
Real-time speed, natural fluid motion at 1x playback rate.
```

### E12 (Utility Worker - Expected Activity)

```
Suburban home side yard at midday, viewed from a corner vantage point at the
house edge. A utility worker in safety vest approaches the electric meter on
the side of the house, takes a reading with a handheld device, and walks to
the next property. Monthly meter reading. Static viewpoint, clear daytime footage.
Real-time speed, natural fluid motion at 1x playback rate.
```

### F01 (Wildlife - False Alarm)

```
Suburban home backyard at dawn, viewed from an elevated position under the
roofline. A deer walks calmly across the lawn, pausing to sniff the grass, then
continues walking out of frame. Natural animal movement, peaceful scene. Static
elevated viewpoint, warm dawn lighting. Real-time speed, natural fluid motion
at 1x playback rate.
```

### F16 (Innocent Child - False Alarm)

```
Suburban home backyard at midday, viewed from an elevated position under the
roofline. A child quickly runs into the yard, grabs a soccer ball, waves
apologetically toward neighboring house, and runs back out. Innocent brief
intrusion. Static elevated viewpoint, clear daytime footage. Real-time speed,
natural fluid motion at 1x playback rate.
```

### R01 (Package Theft - Threat)

```
Suburban home front porch at midday, viewed from an elevated vantage point near
the door. A person runs up to the porch, quickly grabs a package sitting by the
door, turns and sprints away. Fast theft in progress. Static elevated viewpoint,
clear daytime footage. Real-time speed, natural fluid motion at 1x playback rate.
```

### R18 (Unauthorized Camping - Threat)

```
Suburban home backyard at night, viewed from an elevated position under the
roofline. A person with a bag enters the yard, finds a hidden corner near the
shed, and begins setting up a sleeping area with a blanket. Unauthorized camping.
Static elevated viewpoint, IR-tinted footage quality. Real-time speed, natural
fluid motion at 1x playback rate.
```

---

## Content vs Prompt Alignment

Since all videos are only 5.8s long, actions described in prompts may be truncated:

| Video | Prompt Action                                             | Likely Issue                   |
| ----- | --------------------------------------------------------- | ------------------------------ |
| E01   | "places package, takes photo, walks back to van"          | May only show arrival          |
| E12   | "approaches meter, takes reading, walks to next property" | May only show approach         |
| F01   | "walks across lawn, pauses, continues out of frame"       | May only show initial movement |
| R01   | "runs up, grabs package, sprints away"                    | May capture full action (fast) |
| R18   | "enters yard, finds corner, sets up sleeping area"        | May only show entry            |

**Recommendation:** After regeneration with correct durations:

- 5s videos: Verify core action is visible
- 10s videos: Verify action completes within frame
- 30s videos: Verify full scenario plays out naturally

---

## Regeneration Checklist

After regeneration, verify:

- [ ] Each `_5s.mp4` file is approximately 5 seconds (4.9-5.1s)
- [ ] Each `_10s.mp4` file is approximately 10 seconds (9.9-10.1s)
- [ ] Each `_30s.mp4` file is approximately 30 seconds (29.5-30.5s)
- [ ] MD5 hashes differ between duration variants of same ID
- [ ] Videos play without artifacts or corruption
- [ ] Content matches prompt description (action completes within duration)
- [ ] Scene consistency maintained throughout video
- [ ] No Cosmos hallucination artifacts (morphing objects, disappearing subjects)
- [ ] R14-R18 30s variants are generated

---

## Technical Notes

### File Size Observations

Videos with similar prompts have varying file sizes, suggesting actual generation occurred:

| Video ID | File Size | Content Type             |
| -------- | --------- | ------------------------ |
| E01      | 3.1 MB    | Delivery driver, vehicle |
| E08      | 6.3 MB    | Complex outdoor scene    |
| E13      | 7.3 MB    | Multi-person scene       |
| F01      | 2.1 MB    | Simple wildlife          |
| R01      | 2.5 MB    | Fast action scene        |

### Batch Coverage Summary

| Batch       | Series      | Video IDs                     | Total Files |
| ----------- | ----------- | ----------------------------- | ----------- |
| Batch 1     | C           | C01-C23                       | 69          |
| **Batch 2** | **E, F, R** | **E01-E22, F01-F16, R01-R18** | **163**     |
| Batch 3     | P, T        | P01-P48, T01-T40              | 264         |

---

## Conclusion

All 163 videos in Batch 2 (E01-E22, F01-F16, R01-R18) require regeneration due to:

1. **Incorrect duration** - All videos are 5.8s instead of 5s/10s/30s
2. **Duplicate content** - Duration variants are byte-identical copies
3. **Generation parameter ignored** - `num_output_frames` not respected
4. **Missing files** - R14-R18 are missing 30s variants

The prompts themselves are well-formed and ready for use. The issue lies in the generation pipeline not respecting per-prompt parameters.

**Estimated regeneration workload:**

- 56 unique video IDs x 3 durations = 168 generations required
- Plus 5 missing R-series 30s files
- Total: ~168 separate Cosmos inference runs

**Recommended priority:**

1. Fix generation script to read `num_output_frames` from JSON
2. Implement autoregressive mode for 30s videos
3. Generate missing R14-R18 30s variants
4. Regenerate all Batch 2 videos with corrected pipeline
5. Validate output durations before committing

---

_Report generated by automated quality analysis pipeline_
