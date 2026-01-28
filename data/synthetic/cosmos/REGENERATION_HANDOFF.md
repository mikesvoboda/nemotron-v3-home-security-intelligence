# Cosmos Video Regeneration Handoff

**Date:** 2026-01-28
**Status:** BLOCKED - Videos do not exist
**Priority:** Critical

---

## Executive Summary

Analysis of the `data/synthetic/cosmos/videos/` directory reveals that **no actual video content exists**. All 496 `.mp4` files are Git LFS pointer stubs (~131 bytes each) referencing content that was never uploaded to the LFS server.

---

## Critical Findings

### 1. Videos Do Not Exist

| Metric | Value |
|--------|-------|
| Total files | 496 |
| Actual videos | 0 |
| File type | Git LFS pointers |
| LFS pull result | `404 Object does not exist on the server` |

### 2. Generation Never Completed

From `generation_status.json`:
```json
{
  "total": 88,
  "completed": 0,
  "failed": 0,
  "in_progress": 8
}
```

### 3. Duration Variants Are Duplicates

All duration variants (5s, 10s, 30s) of the same video ID have **identical SHA256 hashes**:

```
C01_5s.mp4:  sha256:e4429563316346c16e5b914b7bd03866fa1b4cbff73db2a3fb4ae274a57fd880
C01_10s.mp4: sha256:e4429563316346c16e5b914b7bd03866fa1b4cbff73db2a3fb4ae274a57fd880
C01_30s.mp4: sha256:e4429563316346c16e5b914b7bd03866fa1b4cbff73db2a3fb4ae274a57fd880
```

**Expected:** Different hashes for different durations
**Actual:** 207 unique hashes across 496 files

---

## Required Actions

### Phase 1: Locate or Generate Videos

**Option A: Videos exist elsewhere**
- Check the Cosmos generation machine for completed videos
- If found, copy to this directory and push to LFS:
  ```bash
  git lfs push --all origin
  ```

**Option B: Videos need generation**
- Use the existing infrastructure in `data/synthetic/cosmos/`
- See generation instructions below

### Phase 2: Fix Duration Variants

Each prompt ID needs **three separate generations**:
- `{ID}_5s.mp4` - 5 second clip (120 frames @ 24fps)
- `{ID}_10s.mp4` - 10 second clip (240 frames @ 24fps)
- `{ID}_30s.mp4` - 30 second clip (720 frames @ 24fps, autoregressive)

The current prompts in `prompts/generated/` correctly specify different `num_output_frames`, but generation must run separately for each.

---

## Generation Infrastructure (Ready to Use)

### Files Available

| File | Purpose |
|------|---------|
| `generation_manifest.yaml` | 167 video definitions with prompts |
| `prompts/generated/*.json` | 501 ready-to-use Cosmos input files |
| `batch_generate.sh` | Batch generation script |
| `parallel_generate.py` | 8-GPU parallel generation |
| `monitor.sh` | Progress monitoring |
| `HANDOFF.md` | Original setup documentation |

### Quick Start

```bash
# On B300/H200 machine with Cosmos installed:
cd /path/to/cosmos-predict2.5

# Copy prompts
cp -r /path/to/nemotron/data/synthetic/cosmos/prompts/generated/* inputs/

# Run generation (single GPU)
./batch_generate.sh

# Or parallel (8 GPU)
python parallel_generate.py --gpus 8
```

### Hardware Requirements

| GPU | VRAM | Notes |
|-----|------|-------|
| B300 | 267GB | Docker required (sm_103) |
| H200 | 141GB | Native or Docker |
| H100 | 80GB | May need reduced batch size |

---

## Video Categories

### Presentation Videos (48 total)

| Scenario | Count | Purpose |
|----------|-------|---------|
| Threat Escalation | 12 | Risk scoring demo (P01-P12) |
| Cross-Camera Tracking | 12 | ReID demo (P13-P24) |
| Household Recognition | 12 | Face matching demo (P25-P36) |
| Vehicle + Person | 12 | Full pipeline demo (P37-P48) |

### Training Videos (40 total)

| Category | Count | Purpose |
|----------|-------|---------|
| Threat Patterns | 10 | Weapons, aggression (T01-T10) |
| Tracking Sequences | 8 | ReID training (T11-T18) |
| Additional | 22 | Various scenarios |

### Core Detection Videos (119 total)

| Series | Range | Purpose |
|--------|-------|---------|
| C-series | C01-C119 | Core detection scenarios |

---

## Prompt Quality Notes

The prompts are well-designed for security camera footage:

**Good:**
- Perspective-centric (no camera visible in frame)
- Consistent negative prompts blocking artifacts
- Proper motion speed (real-time, no slow-mo)
- IR-tinted night footage

**Verify after generation:**
- Subject visibility and clarity
- Action completion within duration
- Scene consistency across frames
- No Cosmos hallucination artifacts

---

## Post-Generation Checklist

After videos are generated:

1. [ ] Verify each video plays correctly with ffprobe
2. [ ] Confirm duration matches filename (5s/10s/30s)
3. [ ] Check that duration variants are actually different
4. [ ] Extract sample frames for visual QA
5. [ ] Push to Git LFS: `git lfs push --all origin`
6. [ ] Update `generation_status.json` with completion status

---

## Contact

For questions about:
- **Cosmos model issues:** Check NVIDIA Cosmos documentation
- **Prompt adjustments:** Edit `prompts/templates/` and regenerate with `generate_prompts.py`
- **This codebase:** See main `CLAUDE.md` and `AGENTS.md`
