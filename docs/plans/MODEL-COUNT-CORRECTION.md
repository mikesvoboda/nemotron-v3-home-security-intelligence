# Model Count Correction

**Date:** 2026-01-28
**Issue:** Videos showed "9+ AI models" but project actually has 24 models
**Status:** ✅ Corrected in specs, current batch finishing with wrong count

---

## Actual Model Count

**Total: 24 AI Models**

### Model Zoo (23 on-demand models)
1. **Always loaded:**
   - yolo26-general (650 MB)
   - Nemotron LLM (21,700 MB)

2. **On-demand detection models:**
   - yolo11-face
   - yolo11-license-plate
   - yolov8n-pose
   - yolo-world-s
   - threat-detection-yolov8n
   - violence-detection
   - pet-classifier

3. **Vision-language models:**
   - florence-2-large
   - clip-vit-l
   - xclip-base
   - fashion-clip

4. **Computer vision models:**
   - depth-anything-v2-small
   - segformer-b2-clothes
   - vitpose-small
   - osnet-x0-25 (re-ID)

5. **Classification models:**
   - vit-age-classifier
   - vit-gender-classifier
   - weather-classification
   - brisque-quality (image quality)

6. **Vehicle models:**
   - vehicle-damage-detection
   - vehicle-segment-classification

7. **OCR:**
   - paddleocr

**Total VRAM requirement:** ~24GB when all loaded

---

## Videos Affected

### Current Generation (Wrong Count)
**Batch 1-4:** 10 variants with "9 MODELS RUNNING" text
- variant01-detection-alert ✅ (3.3M)
- variant02-gpu-power ✅ (8.2M) - **has wrong "9 MODELS" text**
- variant03-privacy-shield ✅ (5.4M)
- variant04-model-selection 🔄 (batch 2)
- variant05-alert-delivery 🔄 (batch 2)
- variant06-camera-monitor 🔄 (batch 2)
- variant07-risk-assessment ⏳ (batch 3)
- variant08-batch-ready ⏳ (batch 3)
- variant09-system-health ⏳ (batch 3)
- variant10-always-on ⏳ (batch 4)

### Specs Updated
✅ `veo3-video-specs-variants.json` - Changed to "24 MODELS RUNNING"
✅ `veo3-video-specs.json` - Updated with corrected count

---

## What to Regenerate

After current batch completes, regenerate only **variant02-gpu-power** with corrected text:

```bash
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --id variant02-gpu-power
```

This will create:
- `docs/media/veo3-mascot-variants/variant02-gpu-power.mp4` (corrected version)

---

## Original V3 Scenes

The original 6 mascot-branded v3 videos need checking:

| Scene | Model Count Mention? | Action Needed |
|-------|---------------------|---------------|
| scene04-what-if-moment | ❌ No | None |
| scene06-ai-pipeline-presenter | ❌ No | None |
| scene07-model-zoo-conductor | ⚠️ "9+ AI models, 24GB VRAM, 100% local" | Regenerate |
| scene08-nemotron-hero | ❌ No | None |
| scene28-full-architecture | ❌ No | None |
| scene30-nvidia-ecosystem | ❌ No | None |

**Note:** scene07-model-zoo-conductor was in original plan but may not have been generated yet.

---

## Updated Prompts

### Variant 02: GPU Processing Power (Corrected)
```
"24 MODELS RUNNING" text appears above
```

### Scene 07: Model Zoo Conductor (If regenerating)
Should say: **"24 AI models, 24GB VRAM, 100% local"**

---

## Cost Impact

- Current batch (10 videos with wrong count): ~$5-10
- Regenerate variant02 only: ~$0.50-1
- Total wasted: ~$0.50-1 for one video

**Recommendation:** Wait for current batch to complete, keep all except variant02, regenerate only variant02.

---

## Action Plan

1. ✅ Updated spec files with "24 MODELS"
2. ⏳ Let current batch complete (ETA 5-10 minutes)
3. ⏳ Verify variant02 shows "9 MODELS" (wrong)
4. ⏳ Regenerate variant02 with corrected spec
5. ✅ All other videos don't mention model count - can use as-is

---

## Files Updated

| File | Status |
|------|--------|
| `veo3-video-specs-variants.json` | ✅ Updated to 24 models |
| `veo3-video-specs.json` | ✅ Copy of variants (corrected) |
| `veo3-video-specs-backup.json` | ❌ Still has 9 models (old backup) |

---

## Verification Checklist

After regeneration:
- [ ] variant02 shows "24 MODELS RUNNING" text
- [ ] Green NVIDIA robot (not blue)
- [ ] Complete 8-second action (no cut-offs)
- [ ] GPU visualization prominent
- [ ] Models orbiting around Nano

---

**Status:** Waiting for current batch to complete, then regenerate variant02 only
