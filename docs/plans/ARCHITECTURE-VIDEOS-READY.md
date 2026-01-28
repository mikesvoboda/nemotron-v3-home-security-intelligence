# Architecture Videos Ready for Generation

**Date:** 2026-01-28
**Status:** ✅ Ready to generate (14 architecture videos)

---

## Overview

Created 14 architecture video variants based on the 5-minute video breakdown. These videos use actual project architecture diagrams as reference images, ensuring they match your real system design.

---

## Generator Updates

### What Changed

1. **Per-video reference image support:**
   - Added `load_reference_image_base64(path)` function
   - Generator checks for `reference_image` field in video specs
   - Falls back to mascot image if not specified

2. **Per-video duration support:**
   - Videos can now specify custom `duration_seconds`
   - Falls back to default 8 seconds if not specified

3. **Better list/preview commands:**
   - Shows reference image path when present
   - Optional `use_case` field (architecture videos don't need it)

### Files Modified

- `docs/media/generate_veo3_videos.py` - Added reference image support
- `docs/media/veo3-video-specs.json` - Added 14 architecture variants

---

## Architecture Videos Created

### Scene 4: "What If" Moment (8s each)
| ID | Focus | Reference |
|----|-------|-----------|
| arch04a-network-boundary | Green boundary box emphasis | arch-system-overview.png |
| arch04b-data-containment | Data flow staying within boundary | arch-system-overview.png |

### Scene 6: AI Pipeline (8s each)
| ID | Focus | Reference |
|----|-------|-----------|
| arch06a-pipeline-flow | Sequential stage lighting | ai-pipeline-hero.png |
| arch06b-performance-metrics | Speed metrics (30-50ms, 2-5s) | flow-batch-aggregator.png |

### Scene 7: Model Zoo (6s each)
| ID | Focus | Reference |
|----|-------|-----------|
| arch07a-model-loading | Models filling VRAM bars | arch-model-zoo.png |
| arch07b-concurrent-models | "24 AI models" running | arch-model-zoo.png |

### Scene 9: Privacy by Design (8s each)
| ID | Focus | Reference |
|----|-------|-----------|
| arch09a-privacy-shield | Boundary shield blocking cloud | arch-system-overview.png |
| arch09b-local-processing | Local processing emphasis | security-architecture.png |

### Scene 14: Batch Aggregation (8s each)
| ID | Focus | Reference |
|----|-------|-----------|
| arch14a-queue-filling | Queue filling with timer | flow-batch-aggregator.png |
| arch14b-batch-trigger | Batch window triggering | flow-batch-aggregator.png |

### Scene 28: Full Architecture (8s each)
| ID | Focus | Reference |
|----|-------|-----------|
| arch28a-layer-reveal | Top-to-bottom layer reveal | arch-system-overview.png |
| arch28b-complete-system | Pan across complete system | arch-system-overview.png |

### Scene 29: Container Architecture (6s each)
| ID | Focus | Reference |
|----|-------|-----------|
| arch29a-container-flow | GPU passthrough visualization | container-architecture.png |
| arch29b-docker-deployment | One-command deployment | container-architecture.png |

---

## Reference Images Used

All reference images copied to `docs/media/`:

| Image | Size | Source | Used By |
|-------|------|--------|---------|
| arch-system-overview.png | 4.8M | docs/images/ | 6 videos |
| ai-pipeline-hero.png | 1.5M | docs/images/ | 1 video |
| flow-batch-aggregator.png | 4.9M | docs/images/ | 4 videos |
| arch-model-zoo.png | 5.3M | docs/images/ | 2 videos |
| security-architecture.png | 33K | docs/images/admin/ | 1 video |
| container-architecture.png | 1.4M | docs/images/architecture/ | 2 videos |

---

## Generation Commands

### Preview Before Generating

```bash
# Preview a specific video
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh preview --id arch04a-network-boundary

# List all architecture videos
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh list | grep -A 30 "ARCHITECTURE TECH"
```

### Generate Architecture Videos

**Option 1: Generate entire category (recommended)**
```bash
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --category architecture-tech --parallel 3
```

**Option 2: Generate specific video**
```bash
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --id arch04a-network-boundary
```

**Option 3: Generate specific scene (multiple variants)**
```bash
# Scene 4 variants (What if moment)
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --id arch04a-network-boundary
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --id arch04b-data-containment

# Scene 6 variants (AI pipeline)
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --id arch06a-pipeline-flow
source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --id arch06b-performance-metrics

# etc.
```

---

## Cost Estimate

- **14 architecture videos** × **~$0.50-1.00 per video**
- **Total:** ~$7-14 for complete architecture set
- **Per scene:** ~$1-2 for 2 variants of one scene

---

## Output Location

All architecture videos will be saved to:
```
docs/media/veo3-architecture-tech/
├── arch04a-network-boundary.mp4
├── arch04b-data-containment.mp4
├── arch06a-pipeline-flow.mp4
├── arch06b-performance-metrics.mp4
├── arch07a-model-loading.mp4
├── arch07b-concurrent-models.mp4
├── arch09a-privacy-shield.mp4
├── arch09b-local-processing.mp4
├── arch14a-queue-filling.mp4
├── arch14b-batch-trigger.mp4
├── arch28a-layer-reveal.mp4
├── arch28b-complete-system.mp4
├── arch29a-container-flow.mp4
└── arch29b-docker-deployment.mp4
```

---

## Usage in 5-Minute Presentation

Based on `docs/plans/5-minute-video-breakdown.md`:

| Scene | Timestamp | Duration | Use Video |
|-------|-----------|----------|-----------|
| Scene 4: What if moment | 0:20-0:30 | 8s | arch04a or arch04b |
| Scene 6: AI pipeline | 0:38-0:46 | 8s | arch06a or arch06b |
| Scene 7: Model Zoo | 0:46-0:52 | 6s | arch07a or arch07b |
| Scene 9: Privacy by Design | 1:02-1:10 | 8s | arch09a or arch09b |
| Scene 14: Batch aggregation | 1:43-1:51 | 8s | arch14a or arch14b |
| Scene 28: Full architecture | 3:38-3:46 | 8s | arch28a or arch28b |
| Scene 29: Container architecture | 3:46-3:52 | 6s | arch29a or arch29b |

**Recommendation:** Generate all 14 variants, then review and select the best one for each scene during video editing.

---

## Validation Checklist

After generation, verify each video:
- [ ] Video uses correct reference architecture diagram
- [ ] All text/labels visible and readable
- [ ] Animations complete within time boundary (no cut-offs)
- [ ] Green network boundary prominent where applicable
- [ ] "24 AI models" text correct (not "9+")
- [ ] NVIDIA branding visible
- [ ] Tech aesthetic consistent with reference diagrams

---

## Next Steps

1. **Generate all 14 architecture videos:**
   ```bash
   source ~/.bashrc && ./docs/media/generate_veo3_videos.sh generate --category architecture-tech --parallel 3
   ```

2. **Monitor generation progress:**
   - Parallel generation with 3 concurrent jobs
   - ~2-3 minutes per batch
   - ~10-15 minutes total for all 14 videos

3. **Review generated videos:**
   - Extract frames to verify correct diagrams used
   - Check that animations match prompts
   - Verify timing (6s or 8s as specified)

4. **Select best variants for final presentation:**
   - Choose one variant per scene for the 5-minute video
   - Keep alternatives as backup footage

---

## Technical Notes

### How Reference Images Work

VEO 3.1 uses reference images as the base visual and animates from there:
- Reference image provides the style, colors, layout
- Prompt describes the animation and camera movement
- Result: Your actual architecture diagrams, animated

### Prompt Strategy

All architecture prompts follow this pattern:
1. "Animated version of the [diagram name]"
2. Describe what elements to highlight/animate
3. Describe camera movement
4. Specify tech aesthetic and style
5. Emphasize key messages (local processing, privacy, performance)

---

**Status:** Ready to generate! All specs defined, generator updated, reference images in place.
