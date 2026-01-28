# Video Generation Breakdown - Production Guide

**Project:** Home Security Intelligence - NVIDIA Hackathon Video
**Total Duration:** 5 minutes (300 seconds)
**Last Updated:** 2026-01-28

---

## Quick Reference: Generation Methods

| Method | Scene Count | Total Duration | Purpose |
|--------|-------------|----------------|---------|
| **VEO3 + Mascot** | 6 scenes | ~48s | Branded animations with Nemotron mascot |
| **VEO3 Architecture** | 3 scenes | ~24s | Technical diagrams animated |
| **Synthetic Security Footage** | 1 scene | 12s | Real threat scenario |
| **UI Screen Recordings** | 18 scenes | ~165s | Dashboard, monitoring, features |
| **Static Slides + Motion** | 11 scenes | ~51s | Stats, text reveals, comparisons |

---

## VEO3 Animations with Nemotron Mascot

These scenes incorporate the Nemotron mascot for brand consistency and personality.

### Scene 4: "What If" Moment with Mascot (0:20-0:30)
**Duration:** 10 seconds (8s VEO3 + 2s static hold)

**VEO3 Generation:**
- **Reference Image:** Nemotron mascot (from your script)
- **Source Diagram:** `docs/images/arch-system-overview.png`
- **Prompt:**
```
The Nemotron mascot (a futuristic AI character) stands confidently in front of a holographic display showing the home security system architecture. The mascot gestures toward the "YOUR HOME NETWORK" boundary box, emphasizing data staying local. Glowing data streams flow within the network boundary but never cross it. Tech blueprint aesthetic with blue/cyan glows. Camera slowly pushes in on the mascot.
```
- **Settings:** 8 seconds, 720p, 16:9

---

### Scene 6: AI Pipeline with Mascot Presenter (0:38-0:46)
**Duration:** 8 seconds

**VEO3 Generation:**
- **Reference Image:** Nemotron mascot
- **Source Diagram:** `docs/images/ai-pipeline-hero.png` or `docs/images/flow-batch-aggregator.png`
- **Prompt:**
```
The Nemotron mascot presents the AI pipeline flow diagram, pointing to each stage as they light up sequentially: Camera → YOLO26 (30-50ms label appears) → Nemotron brain (2-5s label appears) → Smart Alert. The mascot stands to the side like a tech presenter. Each stage pulses with energy as it activates. Clean tech aesthetic with glowing connections. Camera follows the mascot's gesture from left to right.
```
- **Settings:** 8 seconds, 720p, 16:9

---

### Scene 7: Model Zoo with Mascot Managing Models (0:46-0:52)
**Duration:** 6 seconds

**VEO3 Generation:**
- **Reference Image:** Nemotron mascot
- **Source Diagram:** `docs/images/arch-model-zoo.png`
- **Prompt:**
```
The Nemotron mascot stands in front of a holographic VRAM visualization, orchestrating AI models like a conductor. Models appear as glowing 3D blocks that the mascot arranges in GPU memory. VRAM bars fill up as models load. The mascot gestures to show "9+ AI models, 24GB VRAM, 100% local" text. Futuristic data center aesthetic with the mascot as the intelligent orchestrator.
```
- **Settings:** 6 seconds, 720p, 16:9

---

### Scene 8: Nemotron Hero Moment - Mascot + Specs (0:52-1:02)
**Duration:** 10 seconds

**VEO3 Generation:**
- **Reference Image:** Nemotron mascot
- **Static Base:** Create slide with Nemotron specs
- **Prompt:**
```
The Nemotron mascot stands heroically in center frame with arms crossed, surrounded by floating holographic spec displays that materialize around it: "30 billion parameters", "128K context window", "~18GB VRAM", "50-100 tokens/second". Each spec appears with a glow effect. Dramatic lighting with spotlight on mascot. Text overlay: "Datacenter reasoning on desktop hardware". Epic hero shot aesthetic.
```
- **Settings:** 8 seconds, 720p, 16:9
- **Post-production:** Add 2s static hold at end

---

### Scene 28: Full System Architecture with Mascot (3:38-3:46)
**Duration:** 8 seconds

**VEO3 Generation:**
- **Reference Image:** Nemotron mascot
- **Source Diagram:** `docs/images/arch-system-overview.png`
- **Prompt:**
```
The Nemotron mascot stands in front of a large holographic display showing the complete system architecture. The mascot gestures as each layer illuminates sequentially: Frontend → Backend → AI Services → Data. The "YOUR HOME NETWORK" boundary box glows prominently. All data flows stay within the boundary. The mascot points to emphasize the local processing. Tech blueprint style with layered reveals.
```
- **Settings:** 8 seconds, 720p, 16:9

---

### Scene 30: NVIDIA Ecosystem with Mascot (3:52-4:00)
**Duration:** 8 seconds

**VEO3 Generation:**
- **Reference Image:** Nemotron mascot
- **Static Base:** NVIDIA tech stack logos
- **Prompt:**
```
The Nemotron mascot proudly presents the NVIDIA technology stack. The mascot stands to the side as each NVIDIA logo appears with a glow: Nemotron v3 Nano (center, largest), CUDA, YOLO26, Florence-2, CLIP. Text "Powered by NVIDIA's AI Platform" materializes. The mascot gestures with pride. Green NVIDIA brand colors with tech aesthetic. Camera slowly pushes in on the stack.
```
- **Settings:** 8 seconds, 720p, 16:9

---

## VEO3 Architecture Animations (No Mascot)

Pure technical diagrams animated without the mascot.

### Scene 9: Privacy by Design (1:02-1:10)
**Duration:** 8 seconds

**VEO3 Generation:**
- **Source Diagram:** `docs/images/arch-system-overview.png`
- **Prompt:**
```
Animated data flow visualization showing camera feeds and detections flowing through the AI pipeline, all contained within a glowing green boundary box labeled "YOUR HOME NETWORK". Outside the boundary, cloud service logos (Ring, Eufy, Nest) appear with red X marks crossing them out. Data streams never leave the boundary. Emphasis on containment and local processing. Clean tech blueprint style with green (safe/local) and red (blocked/cloud) color coding.
```
- **Settings:** 8 seconds, 720p, 16:9

---

### Scene 14: Batch Aggregation Visualization (1:43-1:51)
**Duration:** 8 seconds

**VEO3 Generation:**
- **Source Diagram:** `docs/images/flow-batch-aggregator.png`
- **Prompt:**
```
Visualization of detection events accumulating in a Redis queue. Small detection icons flow into a container that fills up over time. A timer counts up from 0s to 45s. A progress bar fills showing batch window progress. When the container is full, it flows into the Nemotron analysis stage. Clean data flow visualization with particle effects. Blue/cyan tech aesthetic.
```
- **Settings:** 8 seconds, 720p, 16:9

---

### Scene 29: Container Architecture (3:46-3:52)
**Duration:** 6 seconds

**VEO3 Generation:**
- **Source Diagram:** `docs/images/architecture/container-architecture.png`
- **Prompt:**
```
Docker containers materialize as glowing 3D boxes connecting together: Frontend, Backend, AI Services (YOLO26, Nemotron, Florence, CLIP), PostgreSQL, Redis. GPU passthrough visualized as a glowing yellow line connecting containers to a GPU chip. All containers link with animated connection lines. Text "One command deployment" appears. Clean container orchestration aesthetic with docker blue colors.
```
- **Settings:** 6 seconds, 720p, 16:9

---

## Synthetic Security Footage

Actual security camera footage showing threat scenarios.

### Scene 12: Package Theft Security Footage (1:24-1:36)
**Duration:** 12 seconds

**Source File:**
- `data/synthetic/threats/package_theft_20260125_181949/media/001.mp4`

**Post-Production Edits:**
1. Crop to most interesting 12-second segment showing:
   - Person approaching (2-3s)
   - Looking around suspiciously (3-4s)
   - Grabbing package (2-3s)
   - Leaving quickly (2-3s)
2. Add timestamp overlay: "Front Door - 2:47 AM" (top left)
3. Optional: Add slight slow-motion (1.2x slower) on key moment (grabbing package)
4. Color grade for security camera aesthetic (slight desaturation, add scanlines?)

**Alternative Footage Options:**
If package theft doesn't work well, use these alternatives:
- Lock picking: `cosmos_R09_lock_picking_20260128`
- Window check: `cosmos_R07_window_check_20260128`
- Pry bar: `cosmos_T07_pry_bar_20260128`
- Aggressive stance: `cosmos_T04_aggressive_stance_20260128`

---

## UI Screen Recordings - COMPREHENSIVE FEATURE SHOWCASE

**EXPANDED from original breakdown to showcase ALL features comprehensively**

### Dashboard & Core Features (5 recordings)

#### Recording 1: Dashboard Overview - Live Activity (Scene 5: 0:30-0:38)
**Duration to Record:** 15 seconds (use best 8s)
**URL:** `http://localhost:5173`

**What to Show:**
- Full dashboard layout with all components visible
- Camera grid showing 2-3 camera feeds
- Activity feed with recent events scrolling
- Risk gauge showing current risk level
- System status indicators (all green/healthy)
- Real-time metrics updating

**Recording Tips:**
- Ensure recent activity is visible (generate some test events first)
- Show risk gauge with a moderate score (30-50 range)
- Camera thumbnails should show interesting frames

---

#### Recording 2: Clean Dashboard State (Scene 11: 1:18-1:24)
**Duration to Record:** 8 seconds

**What to Show:**
- Same dashboard but in "waiting" state
- Empty or minimal activity feed
- Risk gauge at 0 or very low
- Highlight camera feed area that will soon show detection

**Recording Tips:**
- Clear recent events before recording
- Show the calm before the storm

---

#### Recording 3: Dashboard During Detection (Scene 13: 1:36-1:43)
**Duration to Record:** 15 seconds (use best 7s)

**What to Show:**
- Detection event appearing in real-time
- Bounding boxes on camera feed
- Detection labels with confidence scores
- Activity feed updating with new detection
- Detection inference timing displayed

**Recording Tips:**
- Time this recording to capture detection as it happens
- May need to trigger detection manually
- Capture the moment the event appears in the feed

---

#### Recording 4: Nemotron Analysis Processing (Scene 15: 1:51-2:03)
**Duration to Record:** 20 seconds (use best 12s)

**What to Show:**
- "Analyzing event..." status indicator
- LLM processing visualization:
  - Token generation progress bar
  - Context window utilization (e.g., "2,847 / 131,072 tokens")
  - Inference time counter ticking up
  - Status messages: "Loading context...", "Generating analysis...", etc.

**Recording Tips:**
- This is a key moment - show the AI thinking
- If available, show GPU utilization metrics during inference
- Capture the full processing state

---

#### Recording 5: Risk Score Animation (Scene 16: 2:03-2:11)
**Duration to Record:** 12 seconds (use best 8s)

**What to Show:**
- Risk gauge animating from 0 to final score (target: 75-82 range)
- Color transition: Green → Yellow → Orange → Red
- Risk level text appearing: "HIGH RISK"
- Event title appearing: "Package theft detected"

**Recording Tips:**
- Capture the full gauge animation
- Ensure score lands in HIGH range for drama
- Show smooth color transitions

---

### Event Details & Intelligence (3 recordings)

#### Recording 6: Event Details - Full Reasoning (Scene 17: 2:11-2:27)
**Duration to Record:** 25 seconds (use best 16s)

**What to Show:**
- Event detail modal/card with full information:
  - Camera name and location
  - Timestamp with date/time
  - All detected objects with confidence scores
  - Context section with behavioral analysis
  - Nemotron reasoning paragraph (the key content!)
  - Risk score breakdown
  - Recommended actions
- Slowly scroll through reasoning to show depth
- Expand/collapse sections if available

**Recording Tips:**
- THIS IS THE MONEY SHOT - take your time
- Show the full reasoning paragraph
- Let viewers read key phrases
- If reasoning is long, scroll slowly to show it all

---

#### Recording 7: Alert Notification (Scene 18: 2:27-2:34)
**Duration to Record:** 12 seconds (use best 7s)

**What to Show:**
- Alert notification appearing on dashboard
- Bell icon animating
- Alert card sliding in with:
  - Event thumbnail
  - Risk score badge
  - Summary text
  - Timestamp

**Recording Tips:**
- Capture the notification animation smoothly
- Show the alert in context of the dashboard

---

#### Recording 8: Timeline Page (Scene 19: 2:34-2:42)
**Duration to Record:** 15 seconds (use best 8s)

**What to Show:**
- Navigate to Timeline page
- Event list showing multiple events over time
- The package theft event highlighted/selected
- Show how this event stands out from normal activity
- Filtering options visible (date range, risk level, etc.)
- Search bar

**Recording Tips:**
- Have multiple test events to show context
- Show mix of LOW, MEDIUM, HIGH risk events
- Highlight how HIGH risk events are visually distinct

---

### Multi-Camera & Advanced Features (2 recordings)

#### Recording 9: Entity Tracking Across Cameras (Scene 20: 2:42-2:50)
**Duration to Record:** 12 seconds (use best 8s)

**What to Show:**
- Person re-identification across multiple cameras
- Map view showing person's path across property
- Entity profile with metadata
- Cross-camera timeline

**Recording Tips:**
- **If multi-camera setup NOT available:** SKIP this scene
- If available, show person detected on Camera 1 → matched on Camera 2
- Show entity ID linking both detections

**FALLBACK:** If this feature isn't available, extend Scene 19 (Timeline) to 2:50 to show more filtering/search capabilities.

---

#### Recording 10: Zone Intelligence (New Scene - Optional)
**Duration to Record:** 10 seconds
**Consider inserting after Scene 20**

**What to Show:**
- Zone configuration page
- Detection zones drawn on camera views
- Zone rules and alerts
- Dwell time tracking
- Line crossing detection

**Recording Tips:**
- If zones are configured, show them in action
- Highlight how zones add context to detections

---

### Deployment & DevOps (4 recordings)

#### Recording 11: Terminal - Docker Compose (Scene 10: 1:10-1:18)
**Duration to Record:** 25-30 seconds (speed up 2.5x to fit 8s)

**What to Show:**
```bash
# Clear screen first
clear

# Show the simple commands
cat << 'EOF'
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence
cd nemotron-v3-home-security-intelligence
docker-compose up
EOF

# Then run docker-compose up (or use pre-recorded startup)
docker-compose -f docker-compose.prod.yml up -d
```

- Container startup messages scrolling
- "Creating..." messages for each service
- Green checkmarks or "done" messages as services start
- Final "Started" summary

**Recording Tips:**
- Use a clean terminal with good color scheme
- Speed up in post-production to fit 8 seconds
- Show the simplicity of deployment

---

#### Recording 12: Grafana Dashboard - GPU Metrics (Scene 24: 3:10-3:18)
**Duration to Record:** 12 seconds (use best 8s)

**What to Show:**
- Grafana dashboard with GPU monitoring
- Live graphs updating:
  - GPU utilization (target: ~96%)
  - GPU temperature
  - VRAM usage with stacked models
  - Power consumption
- Multiple panels showing different metrics
- Time range selector showing "Last 5 minutes"

**Recording Tips:**
- If Grafana available: `http://localhost:3000` (check your setup)
- Show graphs actively updating
- Zoom in on 96% utilization metric

**FALLBACK:** If Grafana not available:
- Use screenshot from `docs/images/screenshots/` (if exists)
- Add animated overlay showing metrics updating
- OR skip and extend Scene 25 (Pyroscope) to 14 seconds

---

#### Recording 13: Pyroscope Continuous Profiling (Scene 25: 3:18-3:24)
**Duration to Record:** 10 seconds (use best 6s)

**What to Show:**
- Pyroscope flame graph UI
- Flame graph showing function call hierarchy
- Zoom into specific function calls
- CPU profile over time
- Text overlay: "Continuous profiling - Debug like a datacenter"

**Recording Tips:**
- If Pyroscope available: Check monitoring URL
- Show the flame graph as the main visual
- Briefly zoom or pan to show detail

**FALLBACK:** If Pyroscope not available:
- Use screenshot: `docs/images/screenshots/pyroscope.png`
- Add zoom animation to simulate interaction

---

#### Recording 14: Tempo Distributed Tracing (New Scene - Optional)
**Duration to Record:** 8 seconds
**Consider inserting after Scene 25**

**What to Show:**
- Tempo trace visualization
- Request flowing through services
- Timing breakdown by service
- Span details

**Recording Tips:**
- If Tempo/Jaeger available, show a detection request trace
- Highlight how detection flows through the system

---

### Documentation & Repository (3 recordings)

#### Recording 15: GitHub Repository (Scene 27: 3:32-3:38)
**Duration to Record:** 10 seconds (use best 6s)

**What to Show:**
- Repository homepage on GitHub
- Star count, fork count
- README with badges and screenshots
- License badge (Apache 2.0)
- Scroll slowly through README highlights:
  - Tech stack section
  - Quick start commands
  - Architecture diagram
  - Contributing section

**Recording Tips:**
- Use your actual repo URL
- Show social proof (stars/forks) if significant
- Keep scroll smooth and readable

---

#### Recording 16: API Documentation (New Scene)
**Duration to Record:** 8 seconds
**Consider inserting after Scene 27**

**What to Show:**
- FastAPI auto-generated docs: `http://localhost:8000/docs`
- Swagger UI with API endpoints listed
- Expand one endpoint to show request/response schema
- Show the "Try it out" functionality

**Recording Tips:**
- Scroll through endpoints to show breadth
- Expand the `/api/events` or `/api/detections` endpoint
- Show clean API design

---

#### Recording 17: Technical Documentation (New Scene)
**Duration to Record:** 8 seconds
**Consider inserting after Scene 16**

**What to Show:**
- Documentation site (if available) or open `docs/` in file browser
- Show documentation structure:
  - Architecture guides
  - API reference
  - Deployment guides
  - Development setup
- Navigate into one doc to show depth

**Recording Tips:**
- Shows production-ready documentation
- Navigate smoothly between docs

---

### System Health & Monitoring (2 recordings)

#### Recording 18: System Health Dashboard (New Scene)
**Duration to Record:** 8 seconds
**Consider inserting after Dashboard sections**

**What to Show:**
- System health page showing:
  - Service status (all green checkmarks)
  - API response times
  - Database connection status
  - Redis connection status
  - GPU service health
  - Uptime metrics

**Recording Tips:**
- Shows operational maturity
- All services healthy for demo

---

#### Recording 19: Logs & Debugging (New Scene - Optional)
**Duration to Record:** 6 seconds
**Consider inserting after monitoring sections**

**What to Show:**
- Loki logs viewer or terminal with structured logs
- Show logs during a detection event
- Highlight structured logging format
- Show log filtering capabilities

**Recording Tips:**
- Brief showcase of observability
- Shows operational readiness

---

## Static Slides with Motion Graphics

These slides don't require recordings - create in presentation software with animations.

### Stats & Metrics Slides (6 slides)

1. **Scene 2: Alert Overload** (0:05-0:12) - 7s
   - Phone with notifications
   - Use existing image: `docs/plans/presentation-images/slide2-notification-overload.png`
   - Add zoom + pan Ken Burns effect

2. **Scene 3: The Bigger Problem** (0:12-0:20) - 8s
   - Dark background with text reveals
   - "$30K datacenter GPUs" (2s)
   - "Uploads to the cloud" (2s)
   - "Privacy violations" (2s)

3. **Scene 21: Test Coverage** (2:50-2:58) - 8s
   - Animated stats appearing:
   - "45,000+ test cases"
   - "95% backend coverage"
   - "83% frontend coverage"
   - "1.70:1 test-to-source ratio"
   - Green checkmarks appearing

4. **Scene 22: Development Velocity** (2:58-3:04) - 6s
   - GitHub-style contribution graph
   - Stats reveal:
   - "1,051 commits in 38 days"
   - "27.66 commits/day"
   - "Production-ready"

5. **Scene 26: Hardware Accessibility** (3:24-3:32) - 8s
   - GPU grid with checkmarks:
   - ✓ RTX 3080 (12GB)
   - ✓ RTX 4070 Ti (16GB)
   - ✓ RTX 4090 (24GB)
   - Text: "No datacenter required"

6. **Scene 31: Performance Metrics** (4:00-4:08) - 8s
   - Numbers animating in:
   - "3-6 seconds: Fast alerts"
   - "30-50ms: Detection"
   - "50-100 tok/s: Inference"
   - "96% GPU utilization"

### Vision & Impact Slides (5 slides)

7. **Scene 32: Market Opportunity** (4:08-4:15) - 7s
   - Globe visualization with stats
   - "$7B → $15B by 2030"
   - "100M+ cameras sold annually"

8. **Scene 33: Privacy Crisis** (4:15-4:23) - 8s
   - Quick cuts (0.2s between):
   - "Ring: Warrantless access"
   - "Eufy: $500K fine"
   - "ADT: Employee spying"

9. **Scene 34: Comparison Table** (4:23-4:30) - 7s
   - Ring/Nest vs This Project
   - Animated checkmarks for features

10. **Scene 35: Strategic Value** (4:30-4:38) - 8s
    - Text reveals (2s each):
    - "First production Nemotron showcase"
    - "Drives RTX GPU adoption"
    - "Reference architecture"
    - "Counter-narrative"

11. **Scene 36: Beyond Home Security** (4:38-4:44) - 6s
    - Icon montage with labels:
    - Retail, Healthcare, Industrial, Automotive

---

## Title & Closing Cards (3 slides)

12. **Scene 1: Opening Title** (0:00-0:05) - 5s
    - Black background fade in
    - "AI for Everyone"
    - "Nemotron v3 Nano • Home Security Intelligence"
    - Logos

13. **Scene 37: Vision Statement** (4:44-4:51) - 7s
    - Centered text reveal:
    - "A future where powerful AI is accessible to everyone"
    - Soft home imagery background

14. **Scene 38: Call to Action** (4:51-4:57) - 6s
    - Text line by line:
    - "This isn't a vision."
    - "It's working software."
    - "Today."

15. **Scene 39: Closing Title** (4:57-5:00) - 3s
    - "AI for Everyone"
    - GitHub QR code + URL
    - Contact info
    - Fade to black

---

## Production Workflow

### Phase 1: VEO3 Generation (Total: 9 animations)

**With Nemotron Mascot (6 animations):**
1. Scene 4: What If moment (8s)
2. Scene 6: AI Pipeline presenter (8s)
3. Scene 7: Model Zoo conductor (6s)
4. Scene 8: Hero moment (8s)
5. Scene 28: Full architecture (8s)
6. Scene 30: NVIDIA ecosystem (8s)

**Architecture Only (3 animations):**
7. Scene 9: Privacy design (8s)
8. Scene 14: Batch aggregation (8s)
9. Scene 29: Container architecture (6s)

**Generation Script:**
```bash
# Navigate to your slack-channel-fetcher project
cd /Users/msvoboda/gitlab/slack-channel-fetcher

# Create video specs JSON with all 9 prompts
# (See detailed prompts in sections above)

# Generate all videos
uv run scripts/generate_nano_videos.py generate --all --parallel 3
```

---

### Phase 2: UI Screen Recordings (19 recordings)

**Essential Recordings (15):**
- 5 Dashboard recordings (Scenes 5, 11, 13, 15, 16)
- 3 Event detail recordings (Scenes 17, 18, 19)
- 1 Multi-camera (Scene 20) - optional
- 2 DevOps recordings (Scenes 10, 11)
- 2 Monitoring recordings (Scenes 24, 25)
- 1 Repository (Scene 27)

**Optional Advanced Recordings (4):**
- Zone intelligence
- API documentation
- System health
- Logs viewer

**Recording Tools:**
- Mac: QuickTime Screen Recording or ScreenFlow
- Settings: 1920x1080, 30fps minimum
- Audio: Not needed (will add music in post)

**Pro Tips:**
- Record longer than needed (gives buffer for editing)
- Use clean browser windows (close unnecessary tabs)
- Ensure UI is fully loaded before starting
- Do multiple takes for critical scenes

---

### Phase 3: Synthetic Footage Editing (1 clip)

**Scene 12: Package Theft**
- Source: `data/synthetic/threats/package_theft_20260125_181949/media/001.mp4`
- Duration: Extract best 12 seconds
- Edits:
  - Add timestamp overlay
  - Optional: Add security camera aesthetic
  - Optional: Slight slow-motion on key moment

---

### Phase 4: Static Slides Creation (15 slides)

**Tools:**
- Keynote, PowerPoint, or Figma
- Export as 1920x1080 video with animations

**Animation Types:**
- Text reveals (fade in, slide in)
- Number counters
- Checkmark appearances
- Zoom/pan on images

---

### Phase 5: Assembly with FFmpeg

**Step 1: Normalize all clips**
```bash
# Ensure all clips are 1920x1080, 30fps, h264
ffmpeg -i input.mp4 -vf scale=1920:1080 -r 30 -c:v libx264 -preset slow -crf 18 normalized.mp4
```

**Step 2: Create concat file**
```
# clips.txt
file 'scene01_title.mp4'
file 'scene02_problem.mp4'
# ... all scenes in order
```

**Step 3: Stitch with music**
```bash
ffmpeg -f concat -safe 0 -i clips.txt \
       -i background_music.mp3 \
       -filter_complex "[1:a]volume=0.25[music];[0:a][music]amix=inputs=2:duration=first" \
       -c:v libx264 -crf 18 -preset slow \
       -c:a aac -b:a 192k \
       final_video.mp4
```

---

## Updated Scene Count & Timing

| Generation Method | Original Scenes | With Additions | Total Duration |
|------------------|-----------------|----------------|----------------|
| VEO3 + Mascot | 6 | 6 | 48s |
| VEO3 Architecture | 3 | 3 | 24s |
| Synthetic Footage | 1 | 1 | 12s |
| UI Recordings | 13 | 19 | ~165s+ |
| Static Slides | 11 | 15 | ~51s |
| **TOTAL** | **34 scenes** | **44 scenes** | **300s (5:00)** |

**Note:** With optional advanced recordings, total could be 44-48 scenes. Adjust timing per scene to fit exactly 5:00.

---

## Feature Showcase Checklist

Use this to ensure you've captured all features:

### Dashboard
- [ ] Live camera grid
- [ ] Activity feed with events
- [ ] Risk gauge animation
- [ ] System status indicators
- [ ] Real-time metrics

### Events & Intelligence
- [ ] Detection bounding boxes
- [ ] Confidence scores
- [ ] Nemotron reasoning (full paragraph)
- [ ] Risk score breakdown
- [ ] Recommended actions
- [ ] Event timeline

### Advanced Features
- [ ] Multi-camera tracking (if available)
- [ ] Zone intelligence (if configured)
- [ ] Entity profiles
- [ ] Cross-camera matching

### Monitoring & DevOps
- [ ] Docker deployment simplicity
- [ ] Grafana GPU metrics
- [ ] Pyroscope profiling
- [ ] System health status
- [ ] Structured logging (optional)

### Documentation
- [ ] GitHub repository
- [ ] API documentation (Swagger)
- [ ] Technical docs structure
- [ ] Open source license

---

## Time Management

**Total Available:** 300 seconds

**Current Allocation:**
- VEO3 animations: 72s (24%)
- UI recordings: 165s (55%)
- Synthetic footage: 12s (4%)
- Static slides: 51s (17%)

**Buffer:** If recordings run long, reduce:
- Some static slide durations by 1-2s each
- Combine similar scenes
- Make scene transitions quicker (0.3s → 0.2s)

**Priority Order (if you need to cut):**
1. Keep all demo scenes (1:18-2:50) - this is the core
2. Keep Nemotron mascot scenes - brand identity
3. Keep key stats (test coverage, velocity)
4. Optional: Zone intelligence, advanced monitoring

---

## Next Steps

1. **Set up VEO3 generation** - Adapt your generate_nano_videos.py script
2. **Prepare UI for recording** - Generate test events, configure displays
3. **Record all UI scenes** - Follow the recording guide above
4. **Create static slides** - Use presentation software
5. **Edit synthetic footage** - Add overlays, crop to best moments
6. **Normalize and assemble** - FFmpeg pipeline
7. **Add background music** - Match energy zones
8. **Review and adjust timing** - Ensure exactly 5:00

---

## Questions to Answer Before Production

1. **Multi-camera setup:** Do you have entity tracking across cameras working?
   - If YES: Record Scene 20
   - If NO: Extend Scene 19 (Timeline) to 2:50

2. **Monitoring stack:** Is Grafana/Pyroscope running and accessible?
   - If YES: Record Scenes 24, 25
   - If NO: Use static screenshots with animated overlays

3. **Zone intelligence:** Are detection zones configured?
   - If YES: Add optional Scene (Zone Intelligence)
   - If NO: Skip

4. **API documentation:** Is Swagger UI accessible?
   - If YES: Add optional Scene (API Docs)
   - If NO: Skip

5. **Mascot image:** Do you have the Nemotron mascot image for VEO3?
   - Location for reference images
   - Ensure high resolution for best VEO3 results
