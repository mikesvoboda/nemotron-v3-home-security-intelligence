# VEO3 Reference Image Issue - Critical Finding

**Date:** 2026-01-28
**Status:** 🔴 **CRITICAL - Reference images not working as expected**

---

## The Problem

**Expected:** VEO3 would use the NVIDIA green robot mascot image as a character reference
**Actual:** VEO3 creates its own interpretation, completely ignoring the reference image

### Visual Comparison

**Reference Image (nemotron-mascot.jpg):**
- NVIDIA green robot with rounded, friendly design
- Clear NVIDIA eye logo on chest
- Green and black color scheme
- Waving hand gesture
- Cute, approachable character

**Generated Video Character:**
- Blue/cyan geometric crystalline humanoid
- Abstract, fragmented body made of triangular shards
- No NVIDIA branding visible
- Different proportions, style, and design
- Technical/alien aesthetic vs friendly robot

**Gap:** 0% character consistency - completely different designs

---

## Root Cause Analysis

### Current Implementation

Looking at `generate_nano_videos.py`:

```python
reference_images = [
    {
        "image": {
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": reference_image_b64
            }
        },
        "referenceType": "asset"  # ← This might be wrong
    }
]
```

### Possible Issues

1. **referenceType: "asset" may not be for character consistency**
   - "asset" might be for props/objects, not characters
   - May need "subject", "character", or "style" instead

2. **Prompt doesn't explicitly reference the image**
   - Current: "The Nemotron mascot (a futuristic AI character)"
   - Should be: "The character shown in the reference image" or "This NVIDIA green robot mascot"

3. **VEO 3.1 image-to-video limitations**
   - Model: `gcp/google/veo-3.1-generate-001`
   - Google's VEO image-to-video might be style/motion transfer, not character copying
   - May prioritize motion/composition over exact appearance

4. **API endpoint mismatch**
   - Using `/v1/videos` endpoint
   - Might need image-specific endpoint or parameters

---

## Impact Assessment

### Videos Affected

| Category | Count | Status |
|----------|-------|--------|
| veo3-mascot-branded (v1) | 6 | ❌ Wrong mascot |
| veo3-mascot-branded-v2 (v2) | 6 | ❌ Wrong mascot |
| Total mascot videos | 12 | ❌ All unusable for branded content |

**Cost impact:** ~$6-12 in API costs for videos that don't meet requirements

### Architecture Videos

**Also affected:** Architecture videos (scene09, scene14, scene29) were generated with NO reference images at all.

We have architecture diagrams in `docs/images/`:
- `architecture-overview.png`
- `ai-pipeline-hero.png`
- `flow-batch-aggregator.png`
- `arch-model-zoo.png`
- `arch-system-overview.png`

**These should have been passed as references but weren't.**

---

## Solutions

### Option 1: Fix VEO3 Reference Image Usage ⭐

**Research needed:**
1. Find Google VEO 3.1 image-to-video documentation
2. Identify correct `referenceType` for character consistency
3. Update prompt language to explicitly reference the image
4. Test with single video before regenerating all

**Effort:** 2-3 hours research + testing
**Cost:** $1-2 for test generations
**Success probability:** Medium (depends on VEO capabilities)

**Prompt changes to try:**
```
Instead of: "The Nemotron mascot (a futuristic AI character)..."
Try: "The green NVIDIA robot mascot shown in the reference image..."
OR: "This character (reference image shows NVIDIA green robot)..."
```

### Option 2: Accept VEO's Interpretation ⚠️

**Pros:**
- No additional work or cost
- The blue crystalline character is consistent across videos
- Still looks futuristic and tech-forward
- Could rebrand as "Nemotron's digital AI form"

**Cons:**
- No NVIDIA branding visible
- Not the cute friendly robot you have
- Doesn't match existing mascot assets
- Less approachable for general audience

### Option 3: Use Static Mascot + Motion Graphics

**Approach:**
- Keep your NVIDIA green robot as static PNG
- Use After Effects or similar to animate:
  - Simple movements (wave, point, gesture)
  - Zoom in/out
  - Ken Burns effects
- Composite over backgrounds

**Effort:** 4-6 hours in After Effects
**Cost:** $0 (no API usage)
**Success probability:** High (full control)

### Option 4: Architecture Videos - Add Reference Images

**For architecture videos, we should:**
1. Pass actual architecture diagrams as reference images
2. Use `referenceType: "style"` or similar
3. Let VEO animate the existing diagrams

**This might work better than mascot since:**
- Style transfer is often more reliable than character copying
- Architecture is static structure, not character likeness
- Can verify quickly with one test generation

---

## Recommended Action Plan

### Immediate (Today):

1. **Stop current architecture-v2 generation** (if still running)
   - Task b668e92 is generating without reference images
   - Will have same issue as current architecture videos

2. **Research VEO 3.1 API properly**
   - Check NVIDIA API docs: https://docs.api.nvidia.com/
   - Look for image-to-video examples
   - Find correct referenceType values

3. **Test with single mascot video**
   - Try different referenceTypes: "character", "subject", "style"
   - Try explicit prompt: "The NVIDIA green robot in the reference image"
   - Verify if character likeness improves

### Short-term (This Week):

4. **If VEO reference works: Regenerate mascot videos**
   - Use corrected API parameters
   - Generate 1-2 test videos first
   - Verify mascot appearance before full batch

5. **If VEO reference doesn't work: Pivot strategy**
   - Option A: Accept blue crystalline character (rebrand)
   - Option B: Animate mascot in After Effects
   - Option C: Use mascot as static overlay

6. **Architecture videos: Add diagram references**
   - Pass architecture images as style references
   - Test with scene29 first (most critical)
   - Regenerate if improvement is significant

---

## Questions to Answer

1. **Does Google VEO 3.1 support character consistency from reference images?**
   - Or is it just style/motion transfer?

2. **What are the valid referenceType values?**
   - asset, style, character, subject, motion?

3. **Is there an example of successful character copying with VEO?**
   - Need to see working example

4. **Should we use a different model?**
   - Other models available through NVIDIA API?
   - Runway, Pika, Kling for better character consistency?

---

## Technical Details

### Current API Request Structure

```json
{
  "model": "gcp/google/veo-3.1-generate-001",
  "prompt": "The Nemotron mascot (a futuristic AI character)...",
  "referenceImages": [
    {
      "image": {
        "inlineData": {
          "mimeType": "image/jpeg",
          "data": "<base64>"
        }
      },
      "referenceType": "asset"
    }
  ],
  "duration_seconds": 8,
  "resolution": "720p",
  "aspect_ratio": "16:9"
}
```

### What Might Need to Change

```json
{
  "referenceImages": [
    {
      "image": {...},
      "referenceType": "character",  // or "subject"?
      "influence": 0.9  // if such parameter exists
    }
  ],
  "prompt": "The character in the reference image (NVIDIA green robot mascot)...",
  // Or maybe needs subject_image field instead?
}
```

---

## Cost Summary

**Spent so far:**
- 12 mascot videos (v1 + v2): $6-12
- 3 architecture videos (v1): $1.50-3
- **Total wasted:** ~$7.50-15 (reference images not working)

**Future testing:**
- 3-5 test videos: $1.50-2.50
- Full regeneration (if fix works): $4.50-7.50

---

## Next Steps

**User decision needed:**

1. **Spend time fixing VEO reference images?**
   - Research + testing: 2-3 hours
   - May or may not work

2. **Accept current blue crystalline character?**
   - Zero additional work
   - Rebrand as "digital form"

3. **Switch to manual animation?**
   - After Effects: 4-6 hours
   - Full control, guaranteed results

**I recommend:** Test with 1-2 videos first before deciding on full regeneration.
