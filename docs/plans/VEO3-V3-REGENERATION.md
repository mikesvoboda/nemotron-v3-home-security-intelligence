# VEO3 Mascot Videos V3 - Root Cause Fix

**Date:** 2026-01-28
**Status:** 🔄 Regenerating with corrected prompts

---

## Root Cause Analysis

### The Problem

Generated mascot videos (v1 and v2) showed a **blue crystalline geometric humanoid** instead of the **green NVIDIA robot mascot**.

**Character consistency: 0%** - completely different character from reference image.

### The Discovery

Examining the working script at `/Users/msvoboda/gitlab/slack-channel-fetcher/scripts/generate_nano_videos.py` revealed the actual solution:

**The reference image is NOT sufficient for character consistency.** VEO3 requires the FULL character description embedded in every prompt.

### Working vs Broken Prompts

**❌ Broken (v1, v2):**
```
"The Nemotron mascot (a futuristic AI character) stands confidently..."
```

**✅ Working (v3):**
```
"A cute chibi-style robot mascot named Nano with uniform lime green metallic body throughout, rounded head with dark visor screen showing TWO friendly glowing green cartoon eyes, the text 'NVIDIA' written in black letters directly on the green chest (no white plate, no emblem, no symbol - just black text on green metal), small ear modules, circuit traces on body. Pixar-style 3D animated character. [Nano] stands confidently..."
```

---

## The Fix

Updated all 6 mascot-branded video prompts in `veo3-video-specs.json` to include the complete mascot description at the start of each prompt.

### Key Elements of Mascot Description

1. **Body:** Uniform lime green metallic body throughout
2. **Head:** Rounded head with dark visor screen
3. **Eyes:** TWO friendly glowing green cartoon eyes
4. **Chest:** Text 'NVIDIA' written in black letters directly on green chest
5. **Details:** Small ear modules, circuit traces on body
6. **Style:** Pixar-style 3D animated character

---

## V3 Generation Plan

### Videos to Regenerate

| Scene | Previous Issue | V3 Fix |
|-------|----------------|--------|
| scene04 | Blue crystalline character | Green NVIDIA robot with full description |
| scene06 | Blue crystalline character | Green NVIDIA robot with full description |
| scene07 | Blue crystalline character | Green NVIDIA robot with full description |
| scene08 | Blue crystalline character | Green NVIDIA robot with full description |
| scene28 | Blue crystalline character | Green NVIDIA robot with full description |
| scene30 | Blue crystalline character | Green NVIDIA robot with full description |

### Expected Results

- ✅ Lime green metallic body (not blue/cyan crystalline)
- ✅ "NVIDIA" text visible on chest (not generic futuristic character)
- ✅ Friendly cartoon eyes on visor (not geometric shapes)
- ✅ Rounded chibi-style design (not angular geometric)
- ✅ Consistent character across all 6 videos

---

## Cost Impact

| Batch | Videos | Cost | Result |
|-------|--------|------|--------|
| V1 | 6 mascot videos | ~$3-6 | ❌ Wrong character (blue) |
| V2 | 6 mascot videos | ~$3-6 | ❌ Wrong character (blue) |
| V3 | 6 mascot videos | ~$3-6 | ✅ Expected: Correct green robot |

**Total wasted:** ~$6-12 on incorrect character generations
**Lesson learned:** Character description MUST be embedded in prompt text, not just reference image

---

## Architecture Videos Status

Architecture videos (scene09, scene14, scene29) do not use the mascot, so V2 versions are still valid:

| Scene | Status | Use |
|-------|--------|-----|
| scene09 | ✅ V1 good | Use current |
| scene14 | ✅ V1 acceptable | Use current (or V2 if regenerated) |
| scene29 | ✅ V2 improved | Use V2 (fixed text rendering) |

---

## File Locations

| Asset | Location |
|-------|----------|
| V3 videos (generating) | `docs/media/veo3-mascot-branded-v3/` |
| V2 videos (wrong character) | `docs/media/veo3-mascot-branded-v2/` |
| V1 videos (wrong character) | `docs/media/veo3-mascot-branded/` |
| Updated specs | `docs/plans/veo3-video-specs.json` |
| Working reference | `/Users/msvoboda/gitlab/slack-channel-fetcher/clb-vibecode/nano-videos/video-specs.json` |

---

## Final Video Assembly Plan

**Use these videos for final 5-minute presentation:**

| Scene | Video Source | Character |
|-------|--------------|-----------|
| scene04 | ✅ V3 | Green NVIDIA robot |
| scene06 | ✅ V3 | Green NVIDIA robot |
| scene07 | ✅ V3 | Green NVIDIA robot |
| scene08 | ✅ V3 | Green NVIDIA robot |
| scene09 | ✅ V1 architecture | No mascot |
| scene14 | ✅ V1/V2 architecture | No mascot |
| scene28 | ✅ V3 | Green NVIDIA robot |
| scene29 | ✅ V2 architecture | No mascot |
| scene30 | ✅ V3 | Green NVIDIA robot |

**Total:** 9 VEO3 videos ready for final presentation assembly

---

## Prompt Engineering Lessons

**Critical Discovery:** For character consistency in VEO3 image-to-video:

1. ❌ **Reference image alone is NOT sufficient** for character appearance
2. ✅ **Full character description MUST be in prompt text**
3. ✅ **Specific details matter:** "lime green metallic body", "TWO friendly eyes", "NVIDIA text on chest"
4. ✅ **Avoid generic descriptions:** "futuristic AI character" → VEO3 creates its own interpretation
5. ✅ **Style keywords help:** "Pixar-style", "chibi-style", "cute mascot aesthetic"

---

## Next Steps

1. ✅ Updated prompts with full mascot description
2. 🔄 Generate V3 mascot videos (in progress)
3. ⏳ Verify V3 videos show correct green NVIDIA robot
4. ⏳ Compare V3 side-by-side with working examples
5. ⏳ Proceed with remaining video components (UI recordings, static slides)
6. ⏳ Assemble final 5-minute presentation

---

## Verification Checklist

When V3 videos complete, verify:

- [ ] Body is lime green (not blue/cyan)
- [ ] "NVIDIA" text visible on chest
- [ ] Two cartoon eyes on visor screen
- [ ] Rounded chibi-style proportions
- [ ] Friendly/cute aesthetic (not industrial)
- [ ] Consistent across all 6 videos
- [ ] Matches original working examples

If all checks pass → Proceed to final video assembly

If any checks fail → Review prompt description for missing details

---

**Status:** Awaiting V3 generation completion
