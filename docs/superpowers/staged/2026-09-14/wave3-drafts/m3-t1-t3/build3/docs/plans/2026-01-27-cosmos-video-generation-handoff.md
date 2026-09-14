# Cosmos Video Generation Handoff Document

**Date:** 2026-01-27
**Purpose:** Guide for agent performing synthetic security camera video generation
**Total Videos:** 167

---

## Executive Summary

We are generating synthetic security camera footage using NVIDIA Cosmos for training a home security AI. The existing videos (26 generated so far) have critical issues and must be regenerated. This document provides everything needed to complete the video generation.

---

## Critical Issues with Existing Videos

### Problem: Camera Equipment Visible in Frame

Analysis of existing videos revealed that **~60% show security camera equipment IN the frame**. This is fundamentally broken - security camera footage should be FROM the camera's perspective, not showing the camera itself.

| Video              | Issue                                    |
| ------------------ | ---------------------------------------- |
| P01, P02, P12      | Dome camera visible in center of frame   |
| P13, P24           | Pole-mounted box camera in frame         |
| P14, P25, P34, P35 | Large bullet/dome camera dominates frame |
| P36, P45, P46, P47 | PTZ or bullet camera in corner           |
| T10                | Completely wrong scene (sci-fi vehicle)  |
| T21                | Person holding video camera in frame     |
| T30, T31           | Physical camera object in scene          |

### Root Cause

The original prompts used phrases like:

- "Security camera footage from elevated doorbell camera"
- "camera mounted on garage"

Cosmos interpreted these as instructions to SHOW a camera rather than simulate the camera's POV.

### Fixes Applied

1. **Prompt language changed** from device-centric to perspective-centric:

   - Before: `Security camera footage from elevated doorbell camera`
   - After: `Suburban home front porch, viewed from an elevated vantage point near the front door`

2. **Negative prompt expanded** to explicitly exclude camera equipment:

   ```
   visible camera, security camera device, doorbell camera, camera lens visible,
   camera equipment, camera housing, surveillance camera in frame, camera mount,
   camera on wall, camera on ceiling, CCTV camera visible, Ring doorbell visible
   ```

3. **FPS increased** from 16 to 24 for more natural real-time motion

4. **Real-time speed specification added** to all prompts:

   ```
   Real-time speed, natural fluid motion at 1x playback rate.
   ```

5. **Action sequences simplified** to fit 5-second clip duration

---

## Pre-Generation Setup

### Step 1: Archive Existing Videos

Before generating new videos, archive the existing broken ones:

```bash
cd /path/to/project/data/synthetic/cosmos

# Create archive directory
mkdir -p videos_deprecated

# Move existing videos to archive
mv videos/*.mp4 videos_deprecated/

# Verify videos directory is empty
ls videos/
```

### Step 2: Verify Prompt Templates

Confirm the updated templates are in place:

```bash
# Check base template has perspective-centric language
head -20 prompts/templates/base_prompt.jinja2

# Should show: "{{ scene.setting }}, viewed from {{ scene.viewing_angle }}"
# Should NOT show: "Security camera footage from"
```

### Step 3: Verify Generation Manifest

```bash
# Check total video count
grep "total_videos:" generation_manifest.yaml
# Should show: 167

# Check negative prompt includes camera exclusions
grep "negative_prompt:" generation_manifest.yaml | grep -o "visible camera"
# Should return match

# Check fps is 24
grep "fps:" generation_manifest.yaml
# Should show: 24
```

---

## Video Generation

### Generation Settings (from manifest)

| Setting       | Value                 |
| ------------- | --------------------- |
| Model         | Cosmos-Predict2.5-14B |
| Resolution    | 1280x704 (720p)       |
| FPS           | 24                    |
| Aspect Ratio  | 16:9                  |
| Guidance      | 7.0                   |
| Clip Duration | 5 seconds             |

### Video Categories to Generate

#### Presentation Videos (48)

| Range   | Category              | Description                              |
| ------- | --------------------- | ---------------------------------------- |
| P01-P12 | Threat Escalation     | Progressive suspicious behavior at night |
| P13-P24 | Cross-Camera Tracking | Zone movement at dusk                    |
| P25-P36 | Household Recognition | Known vs unknown during day              |
| P37-P48 | Vehicle + Person      | Vehicle arrivals/exits                   |

#### Training Videos (40)

| Range   | Category           | Description                 |
| ------- | ------------------ | --------------------------- |
| T01-T10 | Threat Patterns    | Weapons, aggression         |
| T11-T18 | Tracking Sequences | ReID exercises              |
| T19-T30 | Enrichment Stress  | Face/clothing/pet detection |
| T31-T40 | Edge Cases         | Weather/lighting challenges |

#### False Positive Training (16) - NEW

| Range   | Category            | Description                       |
| ------- | ------------------- | --------------------------------- |
| F01-F05 | Wildlife            | Deer, raccoon, coyote, cat, birds |
| F06-F08 | Wind Effects        | Trash, branches, flags            |
| F09-F11 | Shadows/Reflections | Headlights, clouds, glare         |
| F12-F14 | Passing Pedestrians | Joggers, dog walkers              |
| F15-F16 | Innocent Intrusions | Wrong delivery, ball retrieval    |

#### Real Threats (18) - NEW

| Range   | Category      | Description                              |
| ------- | ------------- | ---------------------------------------- |
| R01-R03 | Package Theft | Quick grab, casual, follow delivery      |
| R04-R07 | Vehicle Crime | Car break-in, theft, catalytic converter |
| R08-R10 | Vandalism     | Graffiti, mailbox, egging                |
| R11-R12 | Casing        | Photography, note-taking                 |
| R13-R16 | Break-ins     | Home invasion, garage, shed              |
| R17-R18 | Trespassing   | Shortcut, camping                        |

#### Everyday Recognition (22) - NEW

| Range   | Category      | Description                                      |
| ------- | ------------- | ------------------------------------------------ |
| E01-E07 | Deliveries    | Amazon, UPS, FedEx, USPS, food, grocery, drone   |
| E08-E11 | Home Services | Landscaper, pool, cleaner, pest control          |
| E12-E14 | Utilities     | Meter reader, electric, gas                      |
| E15-E17 | Solicitors    | Sales, religious, political                      |
| E18-E22 | Visitors      | Guests, rideshare, contractor, realtor, neighbor |

#### Challenging Conditions (23) - NEW

| Range   | Category  | Description                                       |
| ------- | --------- | ------------------------------------------------- |
| C01-C05 | Weather   | Rain, snow, fog, hail, wind                       |
| C06-C10 | Lighting  | Glare, headlights, flashlight, lightning, sunrise |
| C11-C14 | Occlusion | Umbrella, package, crowd, stroller                |
| C15-C16 | Speed     | Sprint, fast cyclist                              |
| C17-C20 | Clothing  | Rain gear, winter, costume, helmet                |
| C21-C23 | Other     | Distance, angle, multi-event                      |

### Prompt Files Location

All prompts are pre-generated at:

```
data/synthetic/cosmos/prompts/generated/
├── P01_delivery_baseline.txt
├── P01_delivery_baseline.json
├── ...
├── C23_multi_event_simultaneous.txt
└── C23_multi_event_simultaneous.json
```

Each `.txt` file contains the raw prompt. Each `.json` file contains metadata including the prompt.

### Generation Command (Example)

```bash
# Generate single video
cosmos-generate \
  --model checkpoints/Cosmos-Predict2.5-14B \
  --prompt "$(cat prompts/generated/P01_delivery_baseline.txt)" \
  --output videos/P01.mp4 \
  --resolution 720 \
  --fps 24 \
  --guidance 7.0 \
  --negative-prompt "$(grep negative_prompt generation_manifest.yaml | cut -d"'" -f2)"

# Or use batch generation if available
cosmos-generate-batch \
  --model checkpoints/Cosmos-Predict2.5-14B \
  --prompts prompts/generated/*.txt \
  --output-dir videos/ \
  --config generation_manifest.yaml
```

**Note:** Adjust the command syntax based on actual Cosmos CLI interface.

---

## Quality Assurance

### After Each Video is Generated

Perform these checks on each generated video:

#### 1. Camera Equipment Check (CRITICAL)

```bash
# Extract frame and visually inspect
ffmpeg -ss 2 -i videos/P01.mp4 -vframes 1 -q:v 2 /tmp/P01_check.jpg

# Look for:
# - NO dome cameras
# - NO bullet cameras
# - NO camera mounts or poles
# - NO doorbell camera devices
```

**If camera equipment is visible:** Flag the video for regeneration with modified prompt.

#### 2. Perspective Check

- View should be from ELEVATED position (looking down)
- NOT eye-level or ground-level
- NOT selfie-style close-up

#### 3. Motion Speed Check

```bash
# Check framerate
ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate videos/P01.mp4

# Should show: 24/1
```

- Motion should appear natural real-time speed
- NOT slow motion
- NOT time-lapse

#### 4. Content Check

- Scene matches prompt description
- Correct time of day (night/day/dusk)
- Correct weather conditions if specified
- Subject performs described action

### Quality Checklist Per Video

```
[ ] No camera equipment visible in frame
[ ] Elevated camera perspective (not eye-level)
[ ] 24fps confirmed
[ ] Real-time motion speed (not slow-mo)
[ ] Scene matches prompt description
[ ] Correct lighting/weather conditions
[ ] Subject action matches description
```

---

## Troubleshooting

### If Camera Equipment Still Appears

1. Check that the updated prompt templates are being used
2. Add to the specific prompt: "No security cameras or recording equipment visible"
3. Strengthen negative prompt with specific camera brand names seen

### If Motion Appears Slow

1. Verify fps is 24 in output
2. Check prompt includes "Real-time speed, natural fluid motion at 1x playback rate"
3. Simplify action description to fewer steps

### If Wrong Perspective

1. Ensure prompt includes "viewed from an elevated vantage point"
2. Add "looking down at" to scene description
3. Add "Static elevated viewpoint" to camera notes

### If Scene Doesn't Match

1. Simplify prompt - Cosmos works better with focused descriptions
2. Remove conflicting details
3. Ensure negative prompt isn't blocking desired elements

---

## File Naming Convention

| Prefix | Category               | Example                       |
| ------ | ---------------------- | ----------------------------- |
| P      | Presentation           | P01.mp4, P02.mp4, ... P48.mp4 |
| T      | Training               | T01.mp4, T02.mp4, ... T40.mp4 |
| F      | False Positives        | F01.mp4, F02.mp4, ... F16.mp4 |
| R      | Real Threats           | R01.mp4, R02.mp4, ... R18.mp4 |
| E      | Everyday Recognition   | E01.mp4, E02.mp4, ... E22.mp4 |
| C      | Challenging Conditions | C01.mp4, C02.mp4, ... C23.mp4 |

**Output location:** `data/synthetic/cosmos/videos/`

---

## Generation Progress Tracking

Use this checklist to track progress:

```
Presentation (48):
[ ] P01-P12 Threat Escalation (12)
[ ] P13-P24 Cross-Camera (12)
[ ] P25-P36 Household Recognition (12)
[ ] P37-P48 Vehicle + Person (12)

Training (40):
[ ] T01-T10 Threat Patterns (10)
[ ] T11-T18 Tracking Sequences (8)
[ ] T19-T30 Enrichment Stress (12)
[ ] T31-T40 Edge Cases (10)

False Positives (16):
[ ] F01-F16 All false positive scenarios

Real Threats (18):
[ ] R01-R18 All real threat scenarios

Everyday Recognition (22):
[ ] E01-E22 All everyday scenarios

Challenging Conditions (23):
[ ] C01-C23 All challenging condition scenarios

TOTAL: [ ] 167/167 complete
```

---

## Summary

1. **Archive existing videos** to `videos_deprecated/`
2. **Generate 167 videos** using the updated prompts in `prompts/generated/`
3. **Quality check each video** for camera visibility, perspective, and motion speed
4. **Save to** `videos/` with naming convention (P01.mp4, T01.mp4, F01.mp4, etc.)
5. **Flag and regenerate** any videos that fail quality checks

The prompts have been carefully crafted to avoid the camera-in-frame issue. If issues persist, refer to the troubleshooting section.
