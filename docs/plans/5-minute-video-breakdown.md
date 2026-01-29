# 5-Minute NVIDIA Hackathon Video - Second-by-Second Breakdown

**Project:** Home Security Intelligence - Nemotron v3 Nano Showcase
**Total Duration:** 300 seconds (5:00)
**Pacing:** Moderate/Professional (5-8 seconds per scene)
**Music:** Instrumental background (tech/inspirational, 120-130 BPM)

---

## Recording Instructions Summary

| Recording Type | Total Duration Needed | Scenes |
|----------------|----------------------|--------|
| UI Screen Recordings | ~145 seconds | 15 recordings |
| VEO3 Animations (8s max) | ~56 seconds | 7 animations |
| Synthetic Video Clips | ~30 seconds | 3-4 clips |
| Static Slides with Motion | ~69 seconds | 9 slides |

---

## ACT 1: THE HOOK (0:00 - 0:30)

### Scene 1: Opening Title Card (0:00 - 0:05)
**Duration:** 5 seconds

**Visual Content:**
- Black background fade in
- Title: "AI for Everyone"
- Subtitle: "Nemotron v3 Nano • Home Security Intelligence"
- NVIDIA logo + Project logo

**Creation Method:** Static slide with fade-in animation
**Transition:** Fade to black (0.5s)
**Music:** Intro buildup begins

---

### Scene 2: The Problem - Alert Overload (0:05 - 0:12)
**Duration:** 7 seconds

**Visual Content:**
- Split screen: Phone with 50+ motion alert notifications
- Text overlay: "50+ alerts per day. You ignore 95% of them."
- Quick cuts showing dismissing notifications

**Recording Instructions:**
- Option A: Mock up phone screen with alerts in Figma/design tool
- Option B: Use existing screenshot from docs/plans/presentation-images/slide2-notification-overload.png
**Creation Method:** Static image with zoom + pan effect
**Transition:** Quick fade (0.3s)
**Music:** Tension/problem music

---

### Scene 3: The Bigger Problem (0:12 - 0:20)
**Duration:** 8 seconds

**Visual Content:**
- Text overlay on dark background with subtle particle effects:
  - "Today's AI requires $30K datacenter GPUs"
  - "Or uploads your video to the cloud"
  - "Privacy violations. Subscriptions. Trust issues."

**Creation Method:** Static slide with animated text reveals (2-3s per line)
**Transition:** Fade (0.5s)
**Music:** Continue tension

---

### Scene 4: The "What If" Moment (0:20 - 0:30)
**Duration:** 10 seconds

**Visual Content:**
- RTX GPU glamour shot (slow rotate/zoom)
- Text overlay fades in: "What if state-of-the-art AI reasoning..."
- Text overlay: "...could run on YOUR hardware"
- Text overlay: "...with your data NEVER leaving home?"

**Recording Instructions:**
- Use VEO3 to animate arch-system-overview.png with emphasis on "YOUR HOME NETWORK" boundary
- OR: Create static slide with GPU image + animated text
**Creation Method:** VEO3 animation (8s) + 2s static hold
**Transition:** Bright flash transition (0.3s)
**Music:** Build to hopeful/inspiring shift

---

## ACT 2: THE SOLUTION (0:30 - 1:30)

### Scene 5: Dashboard Overview (0:30 - 0:38)
**Duration:** 8 seconds

**Visual Content:**
- Full dashboard view showing live system
- Camera grid, activity feed, risk gauge
- Real-time metrics updating

**Recording Instructions:**
- Record dashboard at http://localhost:5173
- Ensure some activity is visible (recent events)
- **Record for 10 seconds** (use middle 8s in edit)
**Creation Method:** Screen recording
**Transition:** Smooth zoom in (0.5s)
**Music:** Energetic but professional

---

### Scene 6: AI Stack Animation (0:38 - 0:46)
**Duration:** 8 seconds

**Visual Content:**
- Animated flow diagram showing:
  ```
  CAMERA → YOLO26 → NEMOTRON → SMART ALERT
  (motion)  (30-50ms)  (2-5s)     (contextual)
  ```
- Each stage lights up sequentially
- Performance metrics appear

**Recording Instructions:**
- Use VEO3 to animate flow-batch-aggregator.png or ai-pipeline-hero.png
- Emphasize the speed metrics appearing
**Creation Method:** VEO3 animation (8s)
**Transition:** Wipe right (0.3s)
**Music:** Tech/building momentum

---

### Scene 7: Model Zoo Overview (0:46 - 0:52)
**Duration:** 6 seconds

**Visual Content:**
- Animated visualization of AI model stack
- Show models loading/unloading with VRAM bars
- Text: "9+ AI models, 24GB VRAM, 100% local"

**Recording Instructions:**
- Use VEO3 to animate arch-model-zoo.png
- Show models as blocks filling VRAM visualization
**Creation Method:** VEO3 animation (6s)
**Transition:** Fade (0.5s)
**Music:** Continue momentum

---

### Scene 8: Nemotron Hero Moment (0:52 - 1:02)
**Duration:** 10 seconds

**Visual Content:**
- Nemotron specs slide with dramatic reveal:
  - 30 billion parameters
  - 128K context window
  - ~18GB VRAM
  - 50-100 tokens/second
- Text overlay: "Datacenter reasoning on desktop hardware"

**Creation Method:** Static slide with animated spec reveals
**Transition:** Fade (0.5s)
**Music:** Emphasize with music swell

---

### Scene 9: Privacy by Design (1:02 - 1:10)
**Duration:** 8 seconds

**Visual Content:**
- Architecture diagram showing data flow
- Animated boundary box around "YOUR HOME NETWORK"
- Text: "NOTHING LEAVES THIS BOX"
- Red X animations over "Ring", "Eufy", "Nest" with cloud icons

**Recording Instructions:**
- Use VEO3 to animate arch-system-overview.png
- Emphasize network boundary containment
**Creation Method:** VEO3 animation (8s)
**Transition:** Fade (0.5s)
**Music:** Confident/secure tone

---

### Scene 10: One Command Deploy (1:10 - 1:18)
**Duration:** 8 seconds

**Visual Content:**
- Terminal screen with simple commands:
  ```bash
  git clone <repo>
  docker-compose up
  ```
- Show containers starting (speed up 2-3x)
- Green checkmarks appear as services become healthy

**Recording Instructions:**
- Record terminal showing docker-compose up output
- Speed up to fit 8 seconds
- **Record for 20-30 seconds** (speed up in edit)
**Creation Method:** Screen recording (terminal)
**Transition:** Fade to white (0.5s)
**Music:** Build anticipation

---

## ACT 3: THE DEMO - FULL PIPELINE (1:18 - 3:30)

### Scene 11: Demo Introduction (1:18 - 1:24)
**Duration:** 6 seconds

**Visual Content:**
- Dashboard view with empty/clean state
- Text overlay: "Let's watch the AI pipeline in action"
- Highlight camera feed area

**Recording Instructions:**
- Record clean dashboard state
- **Record for 8 seconds** (use 6s in edit)
**Creation Method:** Screen recording
**Transition:** None (continuous)
**Music:** Anticipatory

---

### Scene 12: Synthetic Threat Video - Package Theft (1:24 - 1:36)
**Duration:** 12 seconds

**Visual Content:**
- Full screen: Play synthetic package theft video
- Show person approaching, looking around, taking package
- Slight slow-motion on key moment (grabbing package)

**Recording Instructions:**
- Use: data/synthetic/threats/package_theft_20260125_181949/media/001.mp4
- Crop to most interesting 12 seconds
- Add subtle timestamp overlay (e.g., "Front Door - 2:47 AM")
**Creation Method:** Synthetic video with editing
**Transition:** None (continuous to detection)
**Music:** Subtle tension

---

### Scene 13: YOLO26 Detection in Real-Time (1:36 - 1:43)
**Duration:** 7 seconds

**Visual Content:**
- Split screen or picture-in-picture:
  - Left: Same video playing
  - Right: Dashboard showing detection appearing
- Bounding boxes appear on person and package
- Detection labels: "person (0.94)", "package (0.87)"
- Show inference timing: "34ms"

**Recording Instructions:**
- Record dashboard while synthetic video plays
- Ensure detection events are visible in activity feed
- **Record for 10 seconds** (use best 7s)
**Creation Method:** Screen recording (dashboard during detection)
**Transition:** None (continuous)
**Music:** Tech/active

---

### Scene 14: Batch Aggregation Visualization (1:43 - 1:51)
**Duration:** 8 seconds

**Visual Content:**
- Animated visualization of detections accumulating
- Show Redis queue filling with detection events
- Timer showing batch window: "Aggregating: 6 detections over 45s"
- Progress bar filling toward batch trigger

**Recording Instructions:**
- Option A: Use VEO3 to animate flow-batch-aggregator.png with timer overlay
- Option B: Screen record actual Redis queue view or system metrics
**Creation Method:** VEO3 animation OR screen recording
**Transition:** Fade (0.5s)
**Music:** Building tension

---

### Scene 15: Nemotron Analysis - Processing (1:51 - 2:03)
**Duration:** 12 seconds

**Visual Content:**
- Dashboard view showing "Analyzing event..." status
- Show LLM processing visualization:
  - Token generation progress
  - Context window utilization (e.g., "2,847 tokens")
  - Inference time counting up
- Background: Subtle matrix-style data visualization

**Recording Instructions:**
- Record dashboard during actual Nemotron analysis
- Capture the "processing" state
- **Record for 15 seconds** (use best 12s)
- May need to trigger analysis manually and be ready to record
**Creation Method:** Screen recording
**Transition:** None (continuous)
**Music:** Tension/processing

---

### Scene 16: Risk Score Reveal (2:03 - 2:11)
**Duration:** 8 seconds

**Visual Content:**
- Risk gauge animates from 0 to final score (e.g., 78/100)
- Color shifts: Green → Yellow → Orange → Red
- Risk level appears: "HIGH RISK"
- Text overlay: "Package theft detected"

**Recording Instructions:**
- Record risk gauge animation on dashboard
- Ensure score lands in HIGH range (70-85)
- **Record for 10 seconds** (use best 8s)
**Creation Method:** Screen recording
**Transition:** None (continuous)
**Music:** Dramatic reveal

---

### Scene 17: Nemotron Reasoning - The Intelligence (2:11 - 2:27)
**Duration:** 16 seconds

**Visual Content:**
- Full event details modal/card showing:
  - Camera: "Front Door"
  - Time: "2:47 AM"
  - Objects: "Unknown person, package"
  - Context: "Person approached, looked around (suspicious behavior), took package, left quickly"
  - Risk reasoning: "Unknown individual at unusual hour exhibiting suspicious surveillance behavior before package theft. High risk of criminal activity."
  - Recommended action: "Review footage, contact authorities if package confirmed stolen"

**Recording Instructions:**
- Record event detail view with full Nemotron analysis
- Slowly scroll through reasoning text to show depth
- **Record for 20 seconds** (use best 16s)
- May need to expand/collapse sections to show depth
**Creation Method:** Screen recording
**Transition:** Fade (0.5s)
**Music:** Confident/intelligent tone

---

### Scene 18: Alert Delivery (2:27 - 2:34)
**Duration:** 7 seconds

**Visual Content:**
- Show alert notification appearing
- Dashboard bell icon animates
- Alert card slides in with thumbnail, risk score, and summary
- Comparison text overlay: "Not '50 dumb alerts' - ONE intelligent alert"

**Recording Instructions:**
- Record alert appearing in dashboard
- Capture notification animation
- **Record for 10 seconds** (use best 7s)
**Creation Method:** Screen recording
**Transition:** Fade (0.5s)
**Music:** Resolution/completion

---

### Scene 19: Timeline View - Event History (2:34 - 2:42)
**Duration:** 8 seconds

**Visual Content:**
- Switch to timeline page showing event in context
- Show previous events (normal activity vs. this anomaly)
- Highlight how this event stands out
- Show filtering/search capabilities briefly

**Recording Instructions:**
- Navigate to timeline page
- Show event list with the package theft event highlighted
- **Record for 10 seconds** (use best 8s)
**Creation Method:** Screen recording
**Transition:** Fade (0.5s)
**Music:** Professional/analytical

---

### Scene 20: Cross-Camera Intelligence (Optional) (2:42 - 2:50)
**Duration:** 8 seconds

**Visual Content:**
- Show entity tracking across multiple cameras (if available)
- Person re-identification in action
- Map view showing person's path across property

**Recording Instructions:**
- If multi-camera setup available: record entity tracking
- If not available: Skip this scene and extend Scene 19 to 2:50
- **Record for 10 seconds** (use best 8s)
**Creation Method:** Screen recording
**Transition:** Fade (0.5s)
**Music:** Tech/sophisticated

---

## ACT 4: THE TECHNOLOGY (2:50 - 4:15)

### Scene 21: Engineering Excellence - Test Coverage (2:50 - 2:58)
**Duration:** 8 seconds

**Visual Content:**
- Animated stats appearing:
  - "45,000+ test cases"
  - "95% backend coverage"
  - "83% frontend coverage"
  - "1.70:1 test-to-source ratio"
- Code editor split with test files
- Green checkmarks appearing

**Creation Method:** Static slide with animated text/numbers
**Transition:** Fade (0.5s)
**Music:** Professional/confident

---

### Scene 22: Development Velocity (2:58 - 3:04)
**Duration:** 6 seconds

**Visual Content:**
- GitHub-style contribution graph animating
- Stats appearing:
  - "1,051 commits in 38 days"
  - "27.66 commits/day average"
  - "3,200+ Linear issues"
  - "Production-ready quality"

**Creation Method:** Static slide with animated graph/stats
**Transition:** Fade (0.5s)
**Music:** Continue confidence

---

### Scene 23: CI/CD Pipeline (3:04 - 3:10)
**Duration:** 6 seconds

**Visual Content:**
- GitHub Actions workflow visualization
- Show parallel test jobs running
- Green checkmarks cascading
- Text: "40 automated workflows - Security, Testing, Performance"

**Recording Instructions:**
- Option A: Screen record actual GitHub Actions page
- Option B: Create animated visualization of CI pipeline
**Creation Method:** Screen recording OR static animation
**Transition:** Fade (0.5s)
**Music:** Tech/momentum

---

### Scene 24: Observability Stack (3:10 - 3:18)
**Duration:** 8 seconds

**Visual Content:**
- Grafana dashboard showing GPU metrics
- Live graphs: utilization, temperature, VRAM usage
- Show 96% GPU utilization metric
- Multiple panels with metrics

**Recording Instructions:**
- Record Grafana dashboard (if available at monitoring URL)
- Show live metrics updating
- **Record for 10 seconds** (use best 8s)
- If not available: Use static screenshot with animated overlays
**Creation Method:** Screen recording (Grafana) OR static with animation
**Transition:** Fade (0.5s)
**Music:** Professional

---

### Scene 25: Pyroscope Profiling (3:18 - 3:24)
**Duration:** 6 seconds

**Visual Content:**
- Pyroscope flame graph showing performance profile
- Zoom into specific function calls
- Text: "Continuous profiling - Debug like a datacenter"

**Recording Instructions:**
- Record Pyroscope UI (if available)
- **Record for 8 seconds** (use best 6s)
- If not available: Use screenshot from docs/images/screenshots/pyroscope.png
**Creation Method:** Screen recording OR static image with zoom
**Transition:** Fade (0.5s)
**Music:** Tech/sophisticated

---

### Scene 26: Hardware Accessibility (3:24 - 3:32)
**Duration:** 8 seconds

**Visual Content:**
- Grid of RTX GPUs with checkmarks:
  - ✓ RTX 3080 (12GB) - "Works with Mini 4B"
  - ✓ RTX 4070 Ti (16GB) - "Full stack"
  - ✓ RTX 4090 (24GB) - "All models concurrent"
- Text overlay: "No datacenter required. No cloud subscription."

**Creation Method:** Static slide with animated checkmarks
**Transition:** Fade (0.5s)
**Music:** Accessible/inclusive tone

---

### Scene 27: Open Source (3:32 - 3:38)
**Duration:** 6 seconds

**Visual Content:**
- GitHub repository page
- Show README, stars, license (Apache 2.0)
- Text overlay: "100% Open Source - Verify the code yourself"

**Recording Instructions:**
- Screen record GitHub repo page
- Scroll slowly through README highlights
- **Record for 8 seconds** (use best 6s)
**Creation Method:** Screen recording
**Transition:** Fade (0.5s)
**Music:** Open/inviting

---

### Scene 28: Full System Architecture (3:38 - 3:46)
**Duration:** 8 seconds

**Visual Content:**
- Complete system architecture diagram animated
- Show all layers: Frontend, Backend, AI Services, Data
- Emphasize "YOUR HOME NETWORK" boundary
- All processing local

**Recording Instructions:**
- Use VEO3 to animate arch-system-overview.png with layer-by-layer reveal
**Creation Method:** VEO3 animation (8s)
**Transition:** Fade (0.5s)
**Music:** Building to climax

---

### Scene 29: Container Architecture (3:46 - 3:52)
**Duration:** 6 seconds

**Visual Content:**
- Container architecture diagram
- Show Docker containers with GPU passthrough
- Emphasize one-command deployment

**Recording Instructions:**
- Use static image from docs/images/architecture/container-architecture.png
- Add animated overlays showing containers connecting
**Creation Method:** Static with animation overlay
**Transition:** Fade (0.5s)
**Music:** Technical confidence

---

### Scene 30: NVIDIA Ecosystem (3:52 - 4:00)
**Duration:** 8 seconds

**Visual Content:**
- NVIDIA technology stack:
  - Nemotron v3 Nano (hero position)
  - CUDA acceleration
  - YOLO26 detection
  - Florence-2, CLIP
- Text: "Powered by NVIDIA's AI Platform"

**Creation Method:** Static slide with animated logos/stack
**Transition:** Fade (0.5s)
**Music:** Proud/showcase tone

---

### Scene 31: Performance Metrics (4:00 - 4:08)
**Duration:** 8 seconds

**Visual Content:**
- Key performance numbers animating in:
  - "3-6 seconds: Fast path alerts"
  - "30-50ms: YOLO26 detection"
  - "50-100 tok/s: Nemotron inference"
  - "96% GPU utilization"
  - "20-30 FPS detection throughput"

**Creation Method:** Static slide with animated numbers
**Transition:** Fade (0.5s)
**Music:** Impressive/powerful

---

## ACT 5: THE IMPACT (4:08 - 5:00)

### Scene 32: Market Opportunity (4:08 - 4:15)
**Duration:** 7 seconds

**Visual Content:**
- Market stats:
  - "$7B+ current market → $15B+ by 2030"
  - "100M+ IP cameras sold annually"
  - "Tens of millions of RTX GPUs in homes"
- Globe visualization with connection points

**Creation Method:** Static slide with animated stats and globe
**Transition:** Fade (0.5s)
**Music:** Expansive/opportunity

---

### Scene 33: The Privacy Crisis (4:15 - 4:23)
**Duration:** 8 seconds

**Visual Content:**
- Quick cuts showing competitor issues:
  - "Ring: Warrantless police access"
  - "Eufy: Secret cloud uploads - $500K fine"
  - "ADT: Employee spying on customers"
- Text overlay: "The market is moving to local processing"

**Creation Method:** Static slides with quick cuts
**Transition:** Quick cuts (0.2s between)
**Music:** Problem/tension

---

### Scene 34: The Solution - Local AI (4:23 - 4:30)
**Duration:** 7 seconds

**Visual Content:**
- Comparison table:
  - Ring/Nest: Cloud ❌ | Subscription ❌ | Privacy ❌
  - This Project: Local ✓ | Free ✓ | Private ✓
- Text: "NVIDIA can lead the cloud-to-edge transition"

**Creation Method:** Static slide with animated checkmarks
**Transition:** Fade (0.5s)
**Music:** Solution/positive shift

---

### Scene 35: Strategic Value for NVIDIA (4:30 - 4:38)
**Duration:** 8 seconds

**Visual Content:**
- Value propositions:
  - "First production showcase of Nemotron v3 Nano"
  - "Drives RTX GPU adoption beyond gaming"
  - "Reference architecture for edge AI"
  - "Counter-narrative: AI is helpful, private, accessible"

**Creation Method:** Static slide with animated text reveals
**Transition:** Fade (0.5s)
**Music:** Strategic/important

---

### Scene 36: Beyond Home Security (4:38 - 4:44)
**Duration:** 6 seconds

**Visual Content:**
- Quick montage of other applications:
  - Retail security
  - Healthcare (HIPAA compliance)
  - Industrial monitoring
  - Automotive dash cams
- Text: "A template for NVIDIA's edge AI future"

**Creation Method:** Static slide with icon animations
**Transition:** Fade (0.5s)
**Music:** Expansive/visionary

---

### Scene 37: The Vision (4:44 - 4:51)
**Duration:** 7 seconds

**Visual Content:**
- Powerful statement centered:
  - "A future where powerful AI is accessible to everyone"
  - "Not locked in datacenters"
  - "Not behind subscriptions"
  - "Not uploading your private data"
- Background: Soft home/family imagery

**Creation Method:** Static slide with text animation
**Transition:** Fade (0.5s)
**Music:** Inspirational build

---

### Scene 38: Call to Action (4:51 - 4:57)
**Duration:** 6 seconds

**Visual Content:**
- Text appearing line by line:
  - "This isn't a vision."
  - "It's working software."
  - "Today."
- NVIDIA logo + Nemotron logo

**Creation Method:** Static slide with text animation
**Transition:** Fade (0.5s)
**Music:** Climax building

---

### Scene 39: Closing Title (4:57 - 5:00)
**Duration:** 3 seconds

**Visual Content:**
- Black background
- Text: "AI for Everyone"
- Subtitle: "Powered by NVIDIA Nemotron v3 Nano"
- GitHub QR code + URL
- Contact info

**Creation Method:** Static slide with fade out
**Transition:** Fade to black (1s)
**Music:** Final resolution

---

## Recording Checklist

### UI Screen Recordings Needed

| Scene | Content | Duration to Record | Notes |
|-------|---------|-------------------|-------|
| 5 | Dashboard overview | 10s | Show live activity |
| 10 | Terminal - docker-compose up | 20-30s | Speed up in edit |
| 11 | Clean dashboard state | 8s | Empty/ready state |
| 13 | Dashboard during detection | 10s | Capture detection appearing |
| 15 | Nemotron processing | 15s | "Analyzing event" state |
| 16 | Risk gauge animation | 10s | Score reveal |
| 17 | Event details with reasoning | 20s | Scroll through reasoning |
| 18 | Alert notification | 10s | Capture alert appearing |
| 19 | Timeline page | 10s | Show event in context |
| 20 | Multi-camera tracking (optional) | 10s | If available |
| 24 | Grafana dashboard | 10s | GPU metrics |
| 25 | Pyroscope flame graph | 8s | If available |
| 27 | GitHub repository | 8s | README highlights |

**Total UI recording time needed:** ~2-3 minutes of raw footage

---

### VEO3 Animations Needed

| Scene | Source Image | Animation Prompt | Duration |
|-------|-------------|------------------|----------|
| 4 | arch-system-overview.png | Camera feed flowing through AI pipeline inside "YOUR HOME NETWORK" boundary box, with data never crossing the boundary. Emphasize local processing. | 8s |
| 6 | ai-pipeline-hero.png OR flow-batch-aggregator.png | Show sequential flow from camera to YOLO26 to Nemotron to alert. Each stage lights up with performance metrics appearing (30-50ms, 2-5s). Tech blueprint style. | 8s |
| 7 | arch-model-zoo.png | AI models as glowing blocks loading into VRAM visualization. Show models appearing and filling GPU memory bars. Tech/futuristic style. | 6s |
| 9 | arch-system-overview.png | Animated boundary box around "YOUR HOME NETWORK" with data flowing inside. Show red X marks over cloud icons outside the boundary. Privacy emphasis. | 8s |
| 14 | flow-batch-aggregator.png | Detection events accumulating in Redis queue, timer counting up, progress bar filling. Batch window visualization. | 8s |
| 28 | arch-system-overview.png | Layer-by-layer reveal of full architecture: Frontend → Backend → AI Services → Data. Emphasize "YOUR HOME NETWORK" boundary. Tech blueprint with highlights. | 8s |

**Total VEO3 animations needed:** 6 animations × 6-8 seconds each

---

### Static Slides Needed

| Scene | Content | Notes |
|-------|---------|-------|
| 1 | Title card | Simple fade in |
| 2 | Alert overload | Use existing image + zoom |
| 3 | Problem statement | Animated text reveals |
| 8 | Nemotron specs | Dramatic stat reveals |
| 21 | Test coverage stats | Animated numbers |
| 22 | Development velocity | GitHub-style graph |
| 26 | Hardware grid | GPU checklist |
| 30 | NVIDIA ecosystem | Logo stack |
| 31 | Performance metrics | Animated numbers |
| 32 | Market opportunity | Globe with stats |
| 33 | Privacy crisis | Quick cut slides |
| 34 | Comparison table | Checkmarks animation |
| 35 | Strategic value | Text reveals |
| 36 | Beyond home security | Icon montage |
| 37 | Vision statement | Centered text |
| 38 | Call to action | Line-by-line text |
| 39 | Closing title | Fade out |

---

### Synthetic Video Clips Needed

| Scene | Source File | Duration | Edit Notes |
|-------|------------|----------|------------|
| 12 | data/synthetic/threats/package_theft_20260125_181949/media/001.mp4 | 12s | Crop to best moment, add timestamp overlay |

**Alternative threat videos available:**
- Lock picking: cosmos_R09_lock_picking_20260128
- Aggressive stance: cosmos_T04_aggressive_stance_20260128
- Window check: cosmos_R07_window_check_20260128
- Pry bar: cosmos_T07_pry_bar_20260128

---

## Music Zones

| Timestamp | Zone | Mood | Energy |
|-----------|------|------|--------|
| 0:00-0:30 | Hook | Tension → Hope | Medium → Building |
| 0:30-1:30 | Solution | Confident, Professional | Medium-High |
| 1:30-2:42 | Demo | Active, Tech, Engaging | High |
| 2:42-4:08 | Technology | Professional, Impressive | Medium-High |
| 4:08-4:44 | Impact | Strategic, Expansive | Medium |
| 4:44-5:00 | Close | Inspirational, Resolution | Building → Climax |

**Recommended track:** Single instrumental track with dynamic range that matches these zones

---

## Transition Styles

| Transition Type | Usage | Duration |
|----------------|-------|----------|
| Fade | Scene changes, topic shifts | 0.5s |
| Quick fade | Problem → solution moments | 0.3s |
| Wipe | Tech transitions | 0.3s |
| Flash | "What if" moment | 0.3s |
| Quick cuts | Multi-part content (Scene 33) | 0.2s |
| None (continuous) | Demo flow (Scenes 11-18) | - |

---

## FFmpeg Assembly Strategy

### Step 1: Prepare All Clips
```bash
# Ensure all clips are same format (1920x1080, 30fps, h264)
# Normalize audio levels
# Add fade in/out where needed
```

### Step 2: Create Concat File
```
# clips.txt
file 'scene01_title.mp4'
file 'scene02_problem.mp4'
file 'scene03_bigger_problem.mp4'
# ... etc
```

### Step 3: Stitch with Background Music
```bash
ffmpeg -f concat -safe 0 -i clips.txt \
       -i background_music.mp3 \
       -filter_complex "[1:a]volume=0.3[music];[0:a][music]amix=inputs=2:duration=first" \
       -c:v libx264 -crf 18 -preset slow \
       -c:a aac -b:a 192k \
       final_video.mp4
```

---

## Next Steps

1. **UI Recordings:** Set up dashboard with synthetic data, record all 13 UI scenes
2. **VEO3 Animations:** Submit 6 animation requests with architecture diagrams
3. **Static Slides:** Create 17 slides in presentation software with animations
4. **Synthetic Clips:** Extract and edit package theft video
5. **Music:** Select background track with appropriate energy zones
6. **Assembly:** Use ffmpeg to stitch all clips with transitions and music

---

## Timing Validation

| Act | Duration | Scene Count | Avg per Scene |
|-----|----------|-------------|---------------|
| Act 1: Hook | 30s | 4 scenes | 7.5s |
| Act 2: Solution | 60s | 6 scenes | 10s |
| Act 3: Demo | 132s | 10 scenes | 13.2s |
| Act 4: Technology | 85s | 11 scenes | 7.7s |
| Act 5: Impact | 53s | 8 scenes | 6.6s |
| **Total** | **300s** | **39 scenes** | **7.7s avg** |

Pacing is moderate/professional (5-8 seconds per scene) with longer scenes for demo depth.
