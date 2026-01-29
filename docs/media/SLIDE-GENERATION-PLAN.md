# Static Slide Generation Plan

**Purpose:** Generate NVIDIA-branded static images for presentation slides
**Tool:** nvidia-image-gen (Gemini via NVIDIA API)
**Output:** Multiple variants per scene for selection

---

## NVIDIA Brand Guidelines

**Colors:**
- Primary: NVIDIA Green `#76B900`
- Background: Dark `#111111` or `#000000`
- Accent: White `#FFFFFF` for text
- Secondary: Gray `#1A1A1A` for panels

**Typography:**
- Headings: Bold, sans-serif (NVIDIA font family if available)
- Body: Clean, readable sans-serif
- Hierarchy: Large titles, medium subtitles, smaller body text

**Logo:**
- NVIDIA logo placement: Top-left or bottom-right corner
- Minimum clearance space around logo
- Never distort or recolor the logo

**Style:**
- Clean, modern, tech-focused
- High contrast for readability
- Minimal but impactful
- Professional presentation aesthetic

---

## Static Slide Scenes (17 total)

### ACT 1: THE HOOK

**Scene 1: Opening Title Card** (0:00-0:05)
- Directory: `docs/media/slides/scene-01-title/`
- Content: "AI for Everyone" title, Nemotron v3 Nano subtitle, NVIDIA logo
- Style: Black background, dramatic reveal
- Variants: 3 (different text layouts)

**Scene 2: Alert Overload** (0:05-0:12)
- Directory: `docs/media/slides/scene-02-problem/`
- Content: Phone with 50+ notifications, "50+ alerts per day. You ignore 95% of them."
- Style: Split screen or focused phone mockup
- Variants: 3 (different phone angles/layouts)

**Scene 3: The Bigger Problem** (0:12-0:20)
- Directory: `docs/media/slides/scene-03-problem-big/`
- Content: Three text lines about current AI limitations
- Style: Dark background with text reveals
- Variants: 3 (different text arrangements)

### ACT 2: THE SOLUTION

**Scene 8: Nemotron Hero Moment** (0:52-1:02)
- Directory: `docs/media/slides/scene-08-nemotron-specs/`
- Content: Nemotron specs (30B params, 128K context, 18GB VRAM, 50-100 tok/s)
- Style: Spec sheet with dramatic reveal
- Variants: 3 (different layouts)

### ACT 4: THE TECHNOLOGY

**Scene 21: Engineering Excellence** (2:50-2:58)
- Directory: `docs/media/slides/scene-21-test-coverage/`
- Content: 45,000+ tests, 95% backend, 83% frontend, 1.70:1 ratio
- Style: Animated stats with checkmarks
- Variants: 3 (different visualizations)

**Scene 22: Development Velocity** (2:58-3:04)
- Directory: `docs/media/slides/scene-22-dev-velocity/`
- Content: 1,051 commits in 38 days, 27.66/day, 3,200+ Linear issues
- Style: GitHub-style contribution graph
- Variants: 3 (different graph styles)

**Scene 26: Hardware Accessibility** (3:24-3:32)
- Directory: `docs/media/slides/scene-26-hardware/`
- Content: RTX GPU grid (3080, 4070 Ti, 4090) with checkmarks
- Style: Product showcase
- Variants: 3 (different grid layouts)

**Scene 30: NVIDIA Ecosystem** (3:52-4:00)
- Directory: `docs/media/slides/scene-30-ecosystem/`
- Content: NVIDIA technology stack (Nemotron, CUDA, YOLO26, Florence-2, CLIP)
- Style: Logo/tech stack display
- Variants: 3 (different arrangements)

**Scene 31: Performance Metrics** (4:00-4:08)
- Directory: `docs/media/slides/scene-31-performance/`
- Content: Key performance numbers (3-6s alerts, 30-50ms YOLO, 50-100 tok/s, 96% GPU util)
- Style: Metric cards
- Variants: 3 (different card layouts)

### ACT 5: THE IMPACT

**Scene 32: Market Opportunity** (4:08-4:15)
- Directory: `docs/media/slides/scene-32-market/`
- Content: $7B → $15B by 2030, 100M+ cameras, RTX GPUs in homes
- Style: Globe with stats
- Variants: 3 (different globe/stat combos)

**Scene 33: Privacy Crisis** (4:15-4:23)
- Directory: `docs/media/slides/scene-33-privacy-crisis/`
- Content: Ring, Eufy, ADT issues (3 slides for quick cuts)
- Style: Issue callouts
- Variants: 9 (3 per competitor)

**Scene 34: The Solution - Local AI** (4:23-4:30)
- Directory: `docs/media/slides/scene-34-comparison/`
- Content: Comparison table (Ring/Nest vs This Project)
- Style: Clean comparison chart
- Variants: 3 (different table styles)

**Scene 35: Strategic Value for NVIDIA** (4:30-4:38)
- Directory: `docs/media/slides/scene-35-strategic-value/`
- Content: 4 value propositions (First Nano showcase, RTX adoption, etc.)
- Style: Bullet points or cards
- Variants: 3 (different layouts)

**Scene 36: Beyond Home Security** (4:38-4:44)
- Directory: `docs/media/slides/scene-36-beyond/`
- Content: Other applications (retail, healthcare, industrial, automotive)
- Style: Icon montage
- Variants: 3 (different icon arrangements)

**Scene 37: The Vision** (4:44-4:51)
- Directory: `docs/media/slides/scene-37-vision/`
- Content: Vision statement about accessible AI
- Style: Centered inspirational text
- Variants: 3 (different text treatments)

**Scene 38: Call to Action** (4:51-4:57)
- Directory: `docs/media/slides/scene-38-cta/`
- Content: "This isn't a vision. It's working software. Today."
- Style: Bold statement
- Variants: 3 (different emphasis styles)

**Scene 39: Closing Title** (4:57-5:00)
- Directory: `docs/media/slides/scene-39-closing/`
- Content: "AI for Everyone" + GitHub QR code + contact
- Style: Clean closing card
- Variants: 3 (different layouts)

---

## Generation Strategy

**Batch 1 (Priority - Opening/Closing):**
- Scene 1: Title card
- Scene 39: Closing card

**Batch 2 (Act 1 - Hook):**
- Scene 2: Alert overload
- Scene 3: Bigger problem

**Batch 3 (Act 4 - Technology):**
- Scene 21: Test coverage
- Scene 22: Dev velocity
- Scene 26: Hardware
- Scene 30: Ecosystem
- Scene 31: Performance

**Batch 4 (Act 5 - Impact):**
- Scene 32: Market
- Scene 33: Privacy crisis (9 variants)
- Scene 34: Comparison
- Scene 35: Strategic value
- Scene 36: Beyond
- Scene 37: Vision
- Scene 38: CTA

**Batch 5 (Act 2 - Solution):**
- Scene 8: Nemotron specs

---

## Directory Structure

```
docs/media/slides/
├── scene-01-title/
│   ├── variant-01.png
│   ├── variant-02.png
│   └── variant-03.png
├── scene-02-problem/
│   ├── variant-01.png
│   ├── variant-02.png
│   └── variant-03.png
└── [etc...]
```

---

## NVIDIA Brand Prompt Template

```
Create a professional presentation slide with NVIDIA branding:

BRAND REQUIREMENTS:
- NVIDIA green (#76B900) as primary color
- Dark background (#111111 or black)
- White text for high contrast
- NVIDIA logo in [top-left/bottom-right]
- Clean, modern, tech-focused aesthetic
- Professional presentation quality

CONTENT:
[Specific content for this scene]

STYLE:
[Specific visual style for this scene]

LAYOUT:
- 16:9 aspect ratio (1920x1080)
- Generous whitespace
- Clear visual hierarchy
- Readable from a distance

RESTRICTIONS:
- No distorted NVIDIA logo
- No off-brand colors
- Professional corporate quality
- Tech conference presentation standard
```

---

## Next Steps

1. ✅ Create directory structure
2. ⏳ Generate Batch 1 (title/closing)
3. ⏳ Review and select best variants
4. ⏳ Generate remaining batches
5. ⏳ Export final selections
