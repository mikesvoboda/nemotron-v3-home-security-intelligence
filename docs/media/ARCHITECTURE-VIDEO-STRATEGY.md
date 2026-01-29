# Architecture Video Strategy - Using Reference Images

**Goal:** Generate architecture videos that match your actual system diagrams

---

## Current vs Reference-Based Approach

### Current (Text-Only)
- ❌ VEO3 imagines architecture from text
- ❌ May not match your actual architecture
- ❌ Inconsistent style

### Reference-Based (Recommended)
- ✅ Uses your actual architecture diagrams as reference
- ✅ VEO3 animates your existing visuals
- ✅ Consistent with documentation
- ✅ Accurate to your system

---

## Reference Images Available

| Diagram | Path | Best For |
|---------|------|----------|
| **Architecture Overview** | `docs/images/architecture-overview.png` | scene28 (full system) |
| **Batch Aggregation** | `docs/images/flow-batch-aggregator.png` | scene14 (batch processing) |
| **Security Architecture** | `docs/images/admin/security-architecture.png` | scene09 (privacy design) |

---

## Implementation Approach

### Option 1: Per-Video Reference Images (Recommended)

Add `reference_image` field to each video in specs:

```json
{
  "id": "scene09-privacy-design",
  "title": "Privacy by Design Architecture",
  "reference_image": "docs/images/admin/security-architecture.png",
  "prompt": "Animated version of the security architecture diagram showing..."
}
```

### Option 2: Category-Level Reference

```json
{
  "architecture-tech": {
    "output_dir": "docs/media/veo3-architecture-tech",
    "reference_image": "docs/media/architecture-reference.png",
    "videos": [...]
  }
}
```

### Option 3: Multiple Reference Images

Some videos might benefit from multiple references:
- Main architecture diagram
- Specific component diagram
- Color/style reference

---

## Updated Prompts Strategy

Instead of describing the architecture from scratch, reference the diagram:

**Current prompt (text-only):**
```
"Docker containers materialize as glowing 3D boxes..."
```

**Reference-based prompt:**
```
"Animated version of the architecture diagram. Docker containers from the
diagram come to life with glowing edges. GPU passthrough shown as animated
yellow lightning connecting to AI services. Camera pans across the complete
system as components pulse and connect."
```

**Key changes:**
- Start with "Animated version of the diagram"
- Reference elements that exist in the diagram
- Add animation/effects to the static elements
- Maintain the diagram's color scheme and layout

---

## Recommended Videos to Regenerate

| Scene | Current Status | Regenerate With | Priority |
|-------|----------------|-----------------|----------|
| scene28 | Generic architecture | architecture-overview.png | HIGH |
| scene14 | Abstract visualization | flow-batch-aggregator.png | MEDIUM |
| scene09 | Good quality | security-architecture.png | LOW |
| scene29 | Text errors (fixed in v2) | Docker diagram (need to create) | MEDIUM |

---

## Generator Modifications Needed

The current generator (`generate_veo3_videos.py`) needs:

1. **Support per-video reference images:**
```python
# In video spec:
{
  "reference_image": "path/to/diagram.png",  # Optional field
  "prompt": "..."
}

# In generator:
reference_img = video.get("reference_image", MASCOT_IMAGE)
```

2. **Load multiple reference images:**
```python
def load_reference_image(path: str) -> str:
    """Load and encode any reference image as base64."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
```

3. **Pass to VEO3 API:**
```python
reference_images = [{
    "image": {
        "inlineData": {
            "mimeType": "image/png",  # or image/jpeg
            "data": reference_image_b64
        }
    },
    "referenceType": "asset"
}]
```

---

## Example: scene28 with Reference

### Video Spec:
```json
{
  "id": "scene28-full-architecture",
  "title": "Full System Architecture",
  "reference_image": "docs/images/architecture-overview.png",
  "prompt": "Animated version of the full system architecture diagram. The diagram comes to life with glowing connections between components. Camera starts at the top (Frontend/Dashboards) and pushes down through the layers: Backend API layer pulses with activity, AI Services container shows models activating, Data layer at bottom glows. Green boundary box labeled 'YOUR HOME NETWORK' pulses around everything. Connection lines between components animate with flowing data. NVIDIA branding visible. Smooth camera movement revealing the complete stack. Tech aesthetic matching the diagram's neon style."
}
```

### Result:
- VEO3 uses your actual architecture diagram as the base
- Adds animation: glowing, pulsing, flowing data
- Camera movement shows the complete system
- Visual style matches your documentation

---

## Quick Test

Generate one architecture video with reference to see the difference:

```bash
# 1. Update scene28 in veo3-video-specs.json with reference_image field
# 2. Modify generator to support reference_image field
# 3. Generate:
./docs/media/generate_veo3_videos.sh generate --id scene28-full-architecture

# Compare:
# - Old: Generic architecture visualization
# - New: Your actual diagram, animated
```

---

## Recommendation

**Immediate:**
1. ✅ Copy architecture diagrams to `docs/media/`
2. ⏳ Modify generator to support per-video `reference_image` field
3. ⏳ Update scene28, scene14, scene29 specs with reference images
4. ⏳ Regenerate architecture videos with references

**Later:**
1. Create docker-compose visualization diagram for scene29
2. Extract specific component diagrams for more focused videos
3. Consider creating animated SVGs as intermediate step

---

## Files Referenced

- Generator: `docs/media/generate_veo3_videos.py` (needs modification)
- Specs: `docs/media/veo3-video-specs.json` (add reference_image fields)
- Diagrams: `docs/images/architecture-overview.png` (already exists)
- Output: `docs/media/veo3-architecture-tech/` (regenerated videos)

---

**Next Step:** Modify the generator to support per-video reference images, then regenerate architecture videos.
