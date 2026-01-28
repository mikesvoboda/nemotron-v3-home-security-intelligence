# 5-Minute Video Production - Quick Start

**Complete workflow to create your NVIDIA hackathon presentation video**

---

## Prerequisites Checklist

- [ ] NVIDIA API key set: `export NVIDIA_API_KEY="your-key"`
- [ ] Nemotron mascot image placed: `docs/images/nemotron-mascot.jpg`
- [ ] Dashboard running with test data: `http://localhost:5173`
- [ ] Synthetic video available: `data/synthetic/threats/package_theft_*/media/001.mp4`
- [ ] Screen recording software ready (QuickTime/ScreenFlow)
- [ ] Presentation software ready (Keynote/PowerPoint/Figma)

---

## Phase 1: Generate VEO3 Animations (~20 minutes)

### Step 1: Preview Videos
```bash
# List all 9 videos to be generated
./scripts/generate_presentation_videos.sh --list

# Preview a specific prompt
./scripts/generate_presentation_videos.sh --preview scene04-what-if-moment
```

### Step 2: Generate All Videos
```bash
# Generate all 9 VEO3 videos in parallel (3 at a time)
./scripts/generate_presentation_videos.sh --generate-all --parallel 3
```

**Expected time:** 15-20 minutes for all 9 videos

### Step 3: Verify Outputs
```bash
# Should show 9 videos
ls -lh docs/plans/veo3-output/mascot-branded/
ls -lh docs/plans/veo3-output/architecture-tech/

# Play and review each video
open docs/plans/veo3-output/mascot-branded/scene04-what-if-moment.mp4
```

**Checklist:**
- [ ] 6 mascot-branded videos generated
- [ ] 3 architecture-tech videos generated
- [ ] All videos playable and look good
- [ ] Mascot appears correctly in branded videos

---

## Phase 2: Record UI Screenshots (~45-60 minutes)

### Preparation
```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Generate test events (if needed)
# Trigger some detections to populate the dashboard

# Open dashboard
open http://localhost:5173
```

### Essential Recordings (15 recordings)

Use the detailed guide in `docs/plans/video-generation-breakdown.md` for each recording.

**Dashboard & Core (5 recordings):**
1. [ ] Dashboard overview - live activity (15s → 8s)
2. [ ] Clean dashboard state (8s → 6s)
3. [ ] Dashboard during detection (15s → 7s)
4. [ ] Nemotron processing animation (20s → 12s)
5. [ ] Risk score animation (12s → 8s)

**Event Details (3 recordings):**
6. [ ] Event details with full reasoning (25s → 16s) - **CRITICAL**
7. [ ] Alert notification (12s → 7s)
8. [ ] Timeline page (15s → 8s)

**DevOps (2 recordings):**
9. [ ] Terminal - docker-compose up (25s → 8s, speed up 3x)
10. [ ] Grafana GPU metrics (12s → 8s)

**Monitoring (1 recording):**
11. [ ] Pyroscope flame graph (10s → 6s)

**Documentation (1 recording):**
12. [ ] GitHub repository (10s → 6s)

**Optional Advanced (4 recordings):**
13. [ ] Multi-camera entity tracking (12s → 8s) - if available
14. [ ] Zone intelligence (10s → 8s) - if configured
15. [ ] API documentation (8s)
16. [ ] System health dashboard (8s)

**Recording Settings:**
- Resolution: 1920x1080
- Frame rate: 30fps minimum
- Record longer than needed (gives editing buffer)
- No audio needed (music will be added later)

---

## Phase 3: Create Static Slides (~30-45 minutes)

### Tools
- Keynote, PowerPoint, or Figma
- Export as 1920x1080 video with animations

### Required Slides (15 slides)

**Opening & Problem (3 slides):**
1. [ ] Scene 1: Opening title card (5s)
2. [ ] Scene 2: Alert overload phone screen (7s)
3. [ ] Scene 3: The bigger problem - text reveals (8s)

**Stats & Metrics (6 slides):**
4. [ ] Scene 21: Test coverage stats (8s)
5. [ ] Scene 22: Development velocity graph (6s)
6. [ ] Scene 26: Hardware accessibility grid (8s)
7. [ ] Scene 31: Performance metrics (8s)
8. [ ] Scene 32: Market opportunity with globe (7s)
9. [ ] Scene 33: Privacy crisis quick cuts (8s)

**Vision & Impact (6 slides):**
10. [ ] Scene 34: Comparison table (7s)
11. [ ] Scene 35: Strategic value (8s)
12. [ ] Scene 36: Beyond home security icons (6s)
13. [ ] Scene 37: Vision statement (7s)
14. [ ] Scene 38: Call to action (6s)
15. [ ] Scene 39: Closing title with QR code (3s)

**Animation Types:**
- Text reveals: fade in, slide in
- Numbers: animated counters
- Checkmarks: appear with bounce
- Images: Ken Burns zoom/pan

---

## Phase 4: Edit Synthetic Footage (~10 minutes)

### Edit Package Theft Video
```bash
# Source file
data/synthetic/threats/package_theft_20260125_181949/media/001.mp4

# Extract best 12 seconds
ffmpeg -i 001.mp4 -ss 00:00:05 -t 00:00:12 -c copy package_theft_12s.mp4

# Add timestamp overlay
ffmpeg -i package_theft_12s.mp4 \
  -vf "drawtext=text='Front Door - 2\:47 AM':x=20:y=20:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5" \
  scene12_package_theft.mp4
```

**Checklist:**
- [ ] Best 12-second segment extracted
- [ ] Timestamp overlay added
- [ ] Shows: approach → look around → grab → leave
- [ ] Optional: Slight slow-motion on grab moment

---

## Phase 5: Assemble Final Video (~30 minutes)

### Step 1: Organize All Clips

Create a directory with all clips:
```bash
mkdir final-assembly
cd final-assembly

# Copy VEO3 videos
cp ../docs/plans/veo3-output/mascot-branded/*.mp4 .
cp ../docs/plans/veo3-output/architecture-tech/*.mp4 .

# Copy UI recordings
cp ~/Desktop/ui-recordings/*.mp4 .

# Copy static slides
cp ~/Desktop/slides-export/*.mp4 .

# Copy synthetic footage
cp scene12_package_theft.mp4 .
```

### Step 2: Normalize All Clips

Ensure all clips are same format:
```bash
# Normalize script
for file in *.mp4; do
  ffmpeg -i "$file" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" \
    -r 30 -c:v libx264 -preset slow -crf 18 \
    "normalized_$file"
done
```

### Step 3: Create Concat File

Create `clips.txt` in order (see `docs/plans/5-minute-video-breakdown.md` for exact order):

```
file 'normalized_scene01_title.mp4'
file 'normalized_scene02_problem.mp4'
file 'normalized_scene03_bigger_problem.mp4'
file 'normalized_scene04_what_if_moment.mp4'
...
(all 39-44 scenes in order)
```

### Step 4: Stitch with Background Music

```bash
# Concatenate all clips
ffmpeg -f concat -safe 0 -i clips.txt -c copy concatenated.mp4

# Add background music
ffmpeg -i concatenated.mp4 \
       -i background_music.mp3 \
       -filter_complex "[1:a]volume=0.25[music];[0:a][music]amix=inputs=2:duration=first" \
       -c:v copy -c:a aac -b:a 192k \
       final_video_with_music.mp4
```

### Step 5: Add Transitions (Optional)

For smooth transitions between clips, use video editing software:
- DaVinci Resolve (free)
- Final Cut Pro
- Adobe Premiere

Or use ffmpeg with xfade filter (more complex).

### Step 6: Final Encode

```bash
# High-quality final encode
ffmpeg -i final_video_with_music.mp4 \
  -c:v libx264 -preset slow -crf 18 \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  NVIDIA_Hackathon_Video_Final.mp4
```

---

## Phase 6: Review & Finalize (~15 minutes)

### Quality Checklist

- [ ] Total duration: Exactly 5:00 (300 seconds)
- [ ] Resolution: 1920x1080
- [ ] Frame rate: Consistent 30fps
- [ ] Audio: Background music at appropriate volume (~25%)
- [ ] All transitions smooth
- [ ] No visible glitches or artifacts
- [ ] Text readable on all slides
- [ ] Mascot appears correctly in branded scenes
- [ ] Nemotron reasoning fully visible in Scene 17

### Content Checklist

**Opening (0:00-1:30):**
- [ ] Title card professional
- [ ] Problem clearly stated
- [ ] "What if" moment impactful
- [ ] Dashboard looks clean
- [ ] AI pipeline visualization clear

**Demo (1:30-2:50):**
- [ ] Package theft video clear
- [ ] Detection appears smoothly
- [ ] Nemotron processing visible
- [ ] Risk score animation smooth
- [ ] **Full reasoning text legible** (most important!)
- [ ] Alert notification clear

**Technology (2:50-4:15):**
- [ ] Test coverage stats impressive
- [ ] Development velocity shown
- [ ] Monitoring dashboards visible
- [ ] GitHub repo looks professional

**Impact (4:15-5:00):**
- [ ] Market stats clear
- [ ] Privacy crisis compelling
- [ ] Vision statement inspiring
- [ ] Call to action strong
- [ ] Closing with QR code clear

---

## Backup Plans

### If VEO3 Generation Fails
- Use static images with zoom/pan animations
- Create animations in After Effects or Motion
- Use the architecture diagram images directly with Ken Burns effect

### If UI Recording Issues
- Use screenshots with simulated animations
- Record in sections and stitch together
- Ask for help if specific features aren't working

### If Timing Issues
- Reduce transition durations (0.5s → 0.3s)
- Trim static slides by 1-2s each
- Combine similar scenes
- Priority: Keep full demo section (1:18-2:50)

---

## File Organization

```
docs/plans/
├── veo3-video-specs.json              # VEO3 prompts
├── veo3-output/                       # Generated VEO3 videos
│   ├── mascot-branded/
│   └── architecture-tech/
├── 5-minute-video-breakdown.md        # Second-by-second timing
├── video-generation-breakdown.md      # Full production guide
├── VEO3-GENERATION-GUIDE.md          # VEO3 specific guide
└── VIDEO-PRODUCTION-QUICKSTART.md     # This file

~/Desktop/
├── ui-recordings/                     # Your UI screen recordings
├── slides-export/                     # Exported slide videos
└── synthetic-edited/                  # Edited synthetic footage

final-assembly/
├── All normalized clips
├── clips.txt                          # Concat file
├── background_music.mp3
└── NVIDIA_Hackathon_Video_Final.mp4   # Final output
```

---

## Music Recommendations

**Characteristics needed:**
- Instrumental (no vocals)
- Tech/inspirational mood
- 120-130 BPM
- Dynamic range that matches video energy
- 5+ minutes duration

**Zones:**
- 0:00-0:30: Tension building to hope
- 0:30-1:30: Confident, professional
- 1:30-2:50: Active, engaging (demo section)
- 2:50-4:15: Professional, impressive
- 4:15-5:00: Inspirational, building to climax

**Sources:**
- Epidemic Sound (subscription)
- Artlist (subscription)
- YouTube Audio Library (free)
- Free Music Archive (free, check licenses)

---

## Time Estimates

| Phase | Duration | Can Start |
|-------|----------|-----------|
| VEO3 Generation | 15-20 min | Immediately |
| UI Recordings | 45-60 min | After services running |
| Static Slides | 30-45 min | Anytime |
| Synthetic Edit | 10 min | Anytime |
| Assembly | 30 min | After all clips ready |
| Review & Polish | 15-30 min | After assembly |
| **TOTAL** | **2.5-3.5 hours** | |

---

## Next Steps

1. [ ] **Right now:** Generate VEO3 videos
   ```bash
   ./scripts/generate_presentation_videos.sh --generate-all --parallel 3
   ```

2. [ ] **While VEO3 generates:** Create static slides

3. [ ] **After VEO3 done:** Start UI recordings

4. [ ] **After recordings:** Edit synthetic footage

5. [ ] **Final:** Assemble everything with ffmpeg

---

## Getting Help

**Detailed guides:**
- `docs/plans/5-minute-video-breakdown.md` - Second-by-second breakdown
- `docs/plans/video-generation-breakdown.md` - Complete production guide
- `docs/plans/VEO3-GENERATION-GUIDE.md` - VEO3 generation details

**Common issues:**
- VEO3 failures: See VEO3-GENERATION-GUIDE.md troubleshooting
- UI recording tips: See video-generation-breakdown.md recording instructions
- FFmpeg commands: See assembly section in this guide

**Scripts:**
- `./scripts/generate_presentation_videos.sh` - VEO3 generation
- Custom ffmpeg commands - See Phase 5 above

---

## Success Criteria

Your video is ready when:
- ✅ Exactly 5:00 minutes
- ✅ Professional quality (1080p, 30fps)
- ✅ All features showcased
- ✅ Nemotron's strengths highlighted
- ✅ Music enhances without overpowering
- ✅ Story flows: Problem → Solution → Demo → Technology → Impact
- ✅ Call to action clear
- ✅ Ready to submit to NVIDIA hackathon

**Good luck! 🎬**
