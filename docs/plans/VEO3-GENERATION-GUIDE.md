# VEO3 Video Generation Guide

Complete guide for generating the VEO3-animated scenes for your 5-minute NVIDIA hackathon presentation video.

---

## Quick Start

```bash
# 1. Set your NVIDIA API key
export NVIDIA_API_KEY="your-api-key-here"

# 2. List all videos to be generated
./scripts/generate_presentation_videos.sh --list

# 3. Preview a specific video's prompt
./scripts/generate_presentation_videos.sh --preview scene04-what-if-moment

# 4. Generate all videos (3 at a time)
./scripts/generate_presentation_videos.sh --generate-all --parallel 3

# 5. Find your generated videos
ls docs/plans/veo3-output/
```

---

## Prerequisites

### 1. NVIDIA API Key

Get your API key from NVIDIA's AI platform:
- Visit: https://build.nvidia.com/
- Sign in with NVIDIA account
- Generate an API key
- Set environment variable:

```bash
export NVIDIA_API_KEY="nvapi-xxxxxxxxxxxxx"
# OR
export NVAPIKEY="nvapi-xxxxxxxxxxxxx"
```

### 2. Nemotron Mascot Image

**Required for mascot-branded videos (6 out of 9 scenes)**

Place your Nemotron mascot reference image at:
```
docs/images/nemotron-mascot.jpg
```

**Image Requirements:**
- Format: JPEG or PNG
- Resolution: 512x512 or higher (1024x1024 recommended)
- Content: Clear, high-quality image of the Nemotron mascot
- Background: Preferably transparent or clean background

**What if I don't have the mascot image?**
- The script will create a placeholder
- Videos will still generate but won't have the branded mascot
- Consider using a generic AI character or robot illustration

### 3. Python Environment

The generator script requires Python 3.10+ with httpx:

```bash
# Using uv (recommended)
uv pip install httpx

# Or using pip
pip install httpx
```

---

## Video Catalog

### Mascot-Branded Videos (6 scenes)

These feature the Nemotron mascot as a presenter/character.

| Scene ID | Title | Duration | Use In Final Video |
|----------|-------|----------|-------------------|
| `scene04-what-if-moment` | What If Moment with Mascot | 8s | 0:20-0:30 |
| `scene06-ai-pipeline-presenter` | AI Pipeline with Mascot Presenter | 8s | 0:38-0:46 |
| `scene07-model-zoo-conductor` | Model Zoo with Mascot | 6s | 0:46-0:52 |
| `scene08-nemotron-hero` | Nemotron Hero Moment | 8s | 0:52-1:02 |
| `scene28-full-architecture` | Full Architecture with Mascot | 8s | 3:38-3:46 |
| `scene30-nvidia-ecosystem` | NVIDIA Ecosystem with Mascot | 8s | 3:52-4:00 |

### Architecture-Tech Videos (3 scenes)

Pure technical visualizations without mascot.

| Scene ID | Title | Duration | Use In Final Video |
|----------|-------|----------|-------------------|
| `scene09-privacy-design` | Privacy by Design Architecture | 8s | 1:02-1:10 |
| `scene14-batch-aggregation` | Batch Aggregation Visualization | 8s | 1:43-1:51 |
| `scene29-container-architecture` | Container Architecture | 6s | 3:46-3:52 |

---

## Usage Examples

### List All Videos

```bash
./scripts/generate_presentation_videos.sh --list
```

Output:
```
MASCOT-BRANDED VIDEOS
======================================
  scene04-what-if-moment          - What If Moment with Mascot
  scene06-ai-pipeline-presenter   - AI Pipeline with Mascot Presenter
  ...

ARCHITECTURE-TECH VIDEOS
======================================
  scene09-privacy-design          - Privacy by Design Architecture
  ...

Total: 9 videos
```

### Preview Video Prompts

Before generating, preview what VEO3 will create:

```bash
./scripts/generate_presentation_videos.sh --preview scene04-what-if-moment
```

Output shows:
- Video title
- Use case / scene timing
- Full VEO3 prompt text

### Generate All Videos

**Recommended: Generate all 9 videos in parallel**

```bash
./scripts/generate_presentation_videos.sh --generate-all --parallel 3
```

**Options:**
- `--parallel N`: Generate N videos concurrently (default: 3)
  - Higher numbers = faster but may hit rate limits
  - Recommended: 3-5 for optimal speed
- `--force`: Regenerate videos even if they already exist
- `--dry-run`: Preview generation without actually creating videos

**Time Estimate:**
- VEO3 typically takes 3-5 minutes per video
- With `--parallel 3`: ~15-20 minutes for all 9 videos
- With `--parallel 5`: ~10-15 minutes for all 9 videos

### Generate by Category

**Mascot-branded videos only (6 videos):**
```bash
./scripts/generate_presentation_videos.sh --generate-mascot --parallel 3
```

**Architecture-tech videos only (3 videos):**
```bash
./scripts/generate_presentation_videos.sh --generate-arch --parallel 2
```

### Generate Single Video

Test with one video first:

```bash
./scripts/generate_presentation_videos.sh --generate-single scene04-what-if-moment
```

---

## Generation Process

### What Happens When You Generate

1. **Environment Setup**
   - Script checks for API key
   - Verifies mascot image exists
   - Creates temporary working directory

2. **VEO3 Submission**
   - Submits generation requests to NVIDIA's VEO 3.1 API
   - Uses mascot image as reference for branded videos
   - Uses architecture diagram descriptions for tech videos

3. **Polling & Download**
   - Polls VEO3 API for completion (every 10 seconds)
   - Downloads completed videos
   - Saves to output directory

4. **Output Organization**
   ```
   docs/plans/veo3-output/
   ├── mascot-branded/
   │   ├── scene04-what-if-moment.mp4
   │   ├── scene06-ai-pipeline-presenter.mp4
   │   ├── scene07-model-zoo-conductor.mp4
   │   ├── scene08-nemotron-hero.mp4
   │   ├── scene28-full-architecture.mp4
   │   └── scene30-nvidia-ecosystem.mp4
   └── architecture-tech/
       ├── scene09-privacy-design.mp4
       ├── scene14-batch-aggregation.mp4
       └── scene29-container-architecture.mp4
   ```

---

## Customizing Prompts

### Editing Prompts

Prompts are defined in: `docs/plans/veo3-video-specs.json`

**Structure:**
```json
{
  "id": "scene04-what-if-moment",
  "title": "What If Moment with Mascot",
  "use_case": "Scene 4 (0:20-0:30) - Opening hook",
  "prompt": "The Nemotron mascot stands confidently..."
}
```

**To modify a prompt:**
1. Edit the `prompt` field in `veo3-video-specs.json`
2. Preview changes: `./scripts/generate_presentation_videos.sh --preview scene04-what-if-moment`
3. Regenerate: `./scripts/generate_presentation_videos.sh --generate-single scene04-what-if-moment --force`

### Prompt Writing Tips for VEO3

**Good prompt characteristics:**
- **Specific camera movements:** "Camera slowly pushes in", "Camera follows gesture left to right"
- **Clear subject:** "The Nemotron mascot" is always mentioned for branded videos
- **Visual style:** "Tech blueprint aesthetic", "Futuristic data center aesthetic"
- **Color palette:** "Blue and cyan glows", "NVIDIA green accents", "Red X marks"
- **Action sequence:** Describe what happens over time
- **Text overlays:** Mention any text that should appear
- **Lighting:** "Dramatic lighting with spotlight", "Glowing effects"

**Example of a good prompt:**
```
The Nemotron mascot stands heroically in center frame with arms crossed confidently,
surrounded by floating holographic spec displays that materialize around it:
'30 billion parameters', '128K context window'. Each spec appears with a blue glow effect.
Dramatic lighting with spotlight on mascot. Text overlay: 'Datacenter reasoning on
desktop hardware'. Epic hero shot aesthetic with NVIDIA green accents.
```

---

## Troubleshooting

### API Key Issues

**Error: "NVIDIA_API_KEY or NVAPIKEY environment variable required"**

Solution:
```bash
export NVIDIA_API_KEY="your-key-here"
# Verify it's set
echo $NVIDIA_API_KEY
```

**Error: "Authentication failed - check your API key"**

Solutions:
- Verify key is valid at https://build.nvidia.com/
- Key may have expired - generate a new one
- Ensure no extra spaces or quotes in the key

### Generation Failures

**Error: "Video generation failed"**

Possible causes:
- Rate limiting (too many requests too fast)
- API quota exceeded
- Invalid prompt (too long, forbidden content)
- Service outage

Solutions:
- Wait 5 minutes and retry
- Reduce `--parallel` count to 1-2
- Check NVIDIA status page
- Simplify prompt if too complex

**Error: "Timeout waiting for video generation"**

VEO3 can take 5-10 minutes per video during peak times.

Solution:
- The script times out after 10 minutes
- Increase timeout in generator script if needed
- Or regenerate failed videos individually

### Mascot Image Issues

**Warning: "Mascot image not found"**

Impact:
- Mascot-branded videos will use placeholder
- May not match your brand

Solution:
1. Find or create Nemotron mascot image
2. Save as: `docs/images/nemotron-mascot.jpg`
3. Regenerate with: `--force` flag

**Mascot doesn't look right in generated video**

VEO3 uses reference images to maintain consistency but may interpret artistically.

Solutions:
- Use higher resolution reference image (1024x1024+)
- Try different reference images (front-facing works best)
- Adjust prompt to be more specific about mascot appearance
- Accept some variation as artistic interpretation

### Output Location Issues

**Can't find generated videos**

Check:
```bash
# Should show video files
ls -lh docs/plans/veo3-output/mascot-branded/
ls -lh docs/plans/veo3-output/architecture-tech/

# Check full path
find docs/plans/veo3-output -name "*.mp4"
```

---

## Advanced Usage

### Using Original Generator Script Directly

If you prefer to use the original script from slack-channel-fetcher:

```bash
cd /Users/msvoboda/gitlab/slack-channel-fetcher

# Copy specs file
cp ~/github/home_security_intelligence/docs/plans/veo3-video-specs.json \
   clb-vibecode/nano-videos/video-specs.json

# Copy mascot image
cp ~/github/home_security_intelligence/docs/images/nemotron-mascot.jpg \
   clb-vibecode/Untitled.jpg

# Generate
uv run scripts/generate_nano_videos.py generate --all --parallel 3

# Copy outputs back
cp -r clb-vibecode/nano-videos/veo3-output \
      ~/github/home_security_intelligence/docs/plans/
```

### Batch Generation Strategy

**Strategy 1: Test First**
```bash
# Generate one video to test
./scripts/generate_presentation_videos.sh --generate-single scene04-what-if-moment

# If good, generate rest
./scripts/generate_presentation_videos.sh --generate-all --parallel 5
```

**Strategy 2: By Category**
```bash
# Start with tech videos (no mascot needed)
./scripts/generate_presentation_videos.sh --generate-arch

# Then mascot videos when you have the image
./scripts/generate_presentation_videos.sh --generate-mascot
```

**Strategy 3: Overnight Generation**
```bash
# Generate all with low parallelism to avoid rate limits
nohup ./scripts/generate_presentation_videos.sh --generate-all --parallel 2 > generation.log 2>&1 &

# Check progress
tail -f generation.log
```

---

## Cost Estimation

VEO3 pricing (as of 2026-01):
- **Cost per video:** ~$0.10 - $0.50 (depending on duration)
- **Total for 9 videos:** ~$1 - $5

**Note:** Pricing subject to change. Check NVIDIA's current pricing at https://build.nvidia.com/

---

## Quality Settings

Default settings in `veo3-video-specs.json`:

```json
"defaults": {
  "duration_seconds": 8,
  "resolution": "720p",
  "aspect_ratio": "16:9"
}
```

**To change:**
1. Edit `docs/plans/veo3-video-specs.json`
2. Regenerate videos

**Resolution options:**
- `360p` - Low quality, fastest (not recommended)
- `720p` - Good quality, reasonable speed (recommended)
- `1080p` - High quality, slower

**Duration:**
- Most scenes: 8 seconds
- Scene 7 and 29: 6 seconds (shorter content)
- Can adjust per video if needed

---

## Integration with Final Video

After generating all VEO3 videos:

1. **Verify outputs:**
   ```bash
   find docs/plans/veo3-output -name "*.mp4" | wc -l
   # Should show: 9
   ```

2. **Review each video:**
   - Open each .mp4 and verify quality
   - Check that mascot appears correctly in branded videos
   - Verify timing matches expectations

3. **Post-production edits (if needed):**
   - Some videos may need 2s static hold added (Scene 8: Nemotron hero)
   - Trim to exact durations specified in breakdown
   - Adjust brightness/contrast if needed

4. **Move to video assembly:**
   - Follow instructions in `docs/plans/video-generation-breakdown.md`
   - These VEO3 videos integrate with UI recordings and static slides
   - Use ffmpeg to assemble final 5-minute video

---

## Next Steps After Generation

Once all 9 VEO3 videos are generated:

1. ✅ **VEO3 videos complete** (9 scenes, ~72 seconds total)
2. ⏭️ **Record UI screens** (19 recordings, ~165 seconds)
3. ⏭️ **Create static slides** (15 slides, ~51 seconds)
4. ⏭️ **Edit synthetic footage** (1 clip, 12 seconds)
5. ⏭️ **Assemble with ffmpeg** (all clips + music)

See: `docs/plans/video-generation-breakdown.md` for complete production workflow.

---

## Support & Feedback

**Issues with generation:**
- Check NVIDIA's API status
- Review error messages in terminal
- Simplify prompts if generation fails

**Improving video quality:**
- Use higher resolution reference images
- Refine prompts to be more specific
- Adjust visual style descriptions
- Try different camera movement descriptions

**Questions about the workflow:**
- See: `docs/plans/5-minute-video-breakdown.md` - Second-by-second breakdown
- See: `docs/plans/video-generation-breakdown.md` - Complete production guide
- See: `docs/plans/2025-01-21-nvidia-executive-presentation.md` - Full presentation design

---

## Files Reference

| File | Purpose |
|------|---------|
| `docs/plans/veo3-video-specs.json` | Video definitions and prompts |
| `scripts/generate_presentation_videos.sh` | Generation wrapper script |
| `docs/plans/veo3-output/` | Generated video output directory |
| `docs/images/nemotron-mascot.jpg` | Mascot reference image |
| `docs/plans/VEO3-GENERATION-GUIDE.md` | This guide |
| `docs/plans/video-generation-breakdown.md` | Full production breakdown |
| `docs/plans/5-minute-video-breakdown.md` | Second-by-second timing |
