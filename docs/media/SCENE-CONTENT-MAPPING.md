# Scene Content Type Mapping

**Purpose:** Map all 39 scenes to their content generation method

---

## Summary

| Content Type | Count | Scenes |
|--------------|-------|--------|
| **Static Slides (nvidia-image-gen)** | 17 | 1, 2, 3, 8, 21, 22, 26, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39 |
| **VEO3 Architecture Animations** | 7 | 4, 6, 7, 9, 14, 28, 29 |
| **UI Screen Recordings** | 13 | 5, 10, 11, 13, 15, 16, 17, 18, 19, 20, 23, 24, 25, 27 |
| **Synthetic Video Clips** | 1 | 12 |

---

## ACT 1: THE HOOK (0:00-0:30)

### Scene 1: Opening Title Card (0:00-0:05)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-01-title/`
- **Content:** "AI for Everyone" title, Nemotron v3 Nano subtitle, NVIDIA logo

### Scene 2: Alert Overload (0:05-0:12)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-02-problem/`
- **Content:** Phone with 50+ notifications mockup

### Scene 3: The Bigger Problem (0:12-0:20)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-03-problem-big/`
- **Content:** Three text lines about AI limitations

### Scene 4: The "What If" Moment (0:20-0:30)
- **Method:** VEO3 Animation (ALREADY GENERATED)
- **Files:** `veo3-architecture-tech/arch04a-network-boundary.mp4` or `arch04b-data-containment.mp4`
- **Content:** Architecture diagram with "YOUR HOME NETWORK" boundary emphasis

---

## ACT 2: THE SOLUTION (0:30-1:30)

### Scene 5: Dashboard Overview (0:30-0:38)
- **Method:** UI Screen Recording
- **Content:** Live dashboard at localhost:5173

### Scene 6: AI Stack Animation (0:38-0:46)
- **Method:** VEO3 Animation (ALREADY GENERATED)
- **Files:** `veo3-architecture-tech/arch06a-pipeline-flow.mp4` or `arch06b-performance-metrics.mp4`
- **Content:** Pipeline flow with performance metrics

### Scene 7: Model Zoo Overview (0:46-0:52)
- **Method:** VEO3 Animation (ALREADY GENERATED)
- **Files:** `veo3-architecture-tech/arch07a-model-loading.mp4` or `arch07b-concurrent-models.mp4`
- **Content:** 24 AI models visualization

### Scene 8: Nemotron Hero Moment (0:52-1:02)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-08-nemotron-specs/`
- **Content:** Nemotron specs (30B params, 128K context, 18GB VRAM, 50-100 tok/s)

### Scene 9: Privacy by Design (1:02-1:10)
- **Method:** VEO3 Animation (ALREADY GENERATED)
- **Files:** `veo3-architecture-tech/arch09a-privacy-shield.mp4` or `arch09b-local-processing.mp4`
- **Content:** Privacy boundary visualization

### Scene 10: One Command Deploy (1:10-1:18)
- **Method:** UI Screen Recording
- **Content:** Terminal showing docker-compose up

---

## ACT 3: THE DEMO (1:18-3:30)

### Scene 11: Demo Introduction (1:18-1:24)
- **Method:** UI Screen Recording
- **Content:** Clean dashboard state

### Scene 12: Synthetic Threat Video (1:24-1:36)
- **Method:** Synthetic Video Clip
- **Source:** `data/synthetic/threats/package_theft_*/media/001.mp4`
- **Content:** Package theft scenario

### Scene 13: YOLO26 Detection (1:36-1:43)
- **Method:** UI Screen Recording
- **Content:** Dashboard showing real-time detection

### Scene 14: Batch Aggregation (1:43-1:51)
- **Method:** VEO3 Animation (ALREADY GENERATED)
- **Files:** `veo3-architecture-tech/arch14a-queue-filling.mp4` or `arch14b-batch-trigger.mp4`
- **Content:** Batch processing visualization

### Scene 15-20: Detection Pipeline
- **Method:** UI Screen Recordings
- **Content:** Dashboard views of processing, risk scoring, reasoning, alerts, timeline, tracking

---

## ACT 4: THE TECHNOLOGY (2:50-4:15)

### Scene 21: Engineering Excellence (2:50-2:58)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-21-test-coverage/`
- **Content:** Test coverage stats

### Scene 22: Development Velocity (2:58-3:04)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-22-dev-velocity/`
- **Content:** Commit stats and contribution graph

### Scene 23-25: CI/CD and Observability
- **Method:** UI Screen Recordings
- **Content:** GitHub Actions, Grafana, Pyroscope

### Scene 26: Hardware Accessibility (3:24-3:32)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-26-hardware/`
- **Content:** RTX GPU grid with compatibility

### Scene 27: Open Source (3:32-3:38)
- **Method:** UI Screen Recording
- **Content:** GitHub repository page

### Scene 28: Full System Architecture (3:38-3:46)
- **Method:** VEO3 Animation (ALREADY GENERATED)
- **Files:** `veo3-architecture-tech/arch28a-layer-reveal.mp4` or `arch28b-complete-system.mp4`
- **Content:** Complete architecture visualization

### Scene 29: Container Architecture (3:46-3:52)
- **Method:** VEO3 Animation (ALREADY GENERATED)
- **Files:** `veo3-architecture-tech/arch29a-container-flow.mp4` or `arch29b-docker-deployment.mp4`
- **Content:** Docker container orchestration

### Scene 30: NVIDIA Ecosystem (3:52-4:00)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-30-ecosystem/`
- **Content:** NVIDIA tech stack logos

### Scene 31: Performance Metrics (4:00-4:08)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-31-performance/`
- **Content:** Key performance numbers

---

## ACT 5: THE IMPACT (4:08-5:00)

### Scene 32: Market Opportunity (4:08-4:15)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-32-market/`
- **Content:** Market stats with globe

### Scene 33: Privacy Crisis (4:15-4:23)
- **Method:** Static Slide (nvidia-image-gen) - 3 quick cuts
- **Directory:** `docs/media/slides/scene-33-privacy-crisis/`
- **Content:** Ring, Eufy, ADT issues (3 separate images)

### Scene 34: The Solution - Local AI (4:23-4:30)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-34-comparison/`
- **Content:** Comparison table

### Scene 35: Strategic Value (4:30-4:38)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-35-strategic-value/`
- **Content:** Value propositions

### Scene 36: Beyond Home Security (4:38-4:44)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-36-beyond/`
- **Content:** Application icons

### Scene 37: The Vision (4:44-4:51)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-37-vision/`
- **Content:** Vision statement

### Scene 38: Call to Action (4:51-4:57)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-38-cta/`
- **Content:** "This isn't a vision. It's working software. Today."

### Scene 39: Closing Title (4:57-5:00)
- **Method:** Static Slide (nvidia-image-gen)
- **Directory:** `docs/media/slides/scene-39-closing/`
- **Content:** Closing card with QR code

---

## Production Status

✅ **VEO3 Architecture Videos:** 14 generated (scenes 4, 6, 7, 9, 14, 28, 29 - multiple variants)
⏳ **Static Slides:** 0 of 17 generated (ready to start)
⏳ **UI Screen Recordings:** 0 of 13 recorded (requires running system)
⏳ **Synthetic Videos:** 1 available (package theft scenario)

---

## Next Priority: Static Slides Batch 1

Generate opening and closing slides first (highest priority for testing workflow):
1. Scene 1: Opening Title Card (3 variants)
2. Scene 39: Closing Title Card (3 variants)
