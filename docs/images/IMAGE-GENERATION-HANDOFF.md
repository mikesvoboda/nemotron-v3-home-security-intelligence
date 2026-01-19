# Image Generation Handoff Document

This document provides all specifications for generating AI images for the Home Security Intelligence documentation. Hand off to an agent with access to the NVIDIA_API_KEY environment variable.

---

## Prerequisites

**Required Environment Variable:**

```bash
export NVIDIA_API_KEY="your-nvidia-api-key"  # pragma: allowlist secret
# Alternative: export NVAPIKEY="your-nvidia-api-key"
```

**Required Tool:**
The nvidia-image-gen skill uses NVIDIA's LLM Gateway with Gemini 3 Pro Image Preview.

**Script Location:**

```bash
~/.claude/skills/nvidia-image-gen/scripts/generate_image.py
```

---

## Generation Command Template

```bash
uv run ~/.claude/skills/nvidia-image-gen/scripts/generate_image.py \
  "[PROMPT]" \
  --output [OUTPUT_PATH]
```

All images should be saved to the project's `docs/images/` directory.

---

## Images to Generate

### 1. Installation Workflow Diagram

**Output Path:** `docs/images/installation-workflow.png`

**Prompt:**

```
Technical illustration of software installation workflow, four connected steps: 1. Clone Repository (git icon), 2. Setup Environment (terminal with checkmarks), 3. Download Models (download arrow with AI brain), 4. Configure (settings gear). Excalidraw hand-drawn style with slightly wobbly lines, dark background #0a0a0f, NVIDIA green #76B900 accent arrows connecting steps, electric cyan #22d3ee highlights, clean minimalist infographic, horizontal flow left to right, no text labels, 16:9 aspect ratio
```

**Referenced In:** `docs/getting-started/installation.md`

---

### 2. AI Pipeline Architecture

**Output Path:** `docs/images/ai-pipeline-hero.png`

**Prompt:**

```
Technical illustration of AI detection pipeline, showing flow: Camera icon -> Object Detection box (RT-DETRv2) -> Entity Clustering -> Risk Analysis box (Nemotron LLM) -> Security Events. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 primary flow lines, electric cyan #22d3ee secondary connections, accent purple #8b5cf6 for AI processing nodes, clean tech diagram aesthetic, horizontal flow, no text labels, 16:9 aspect ratio
```

**Referenced In:** `docs/architecture/ai-pipeline.md`, `docs/architecture/overview.md`

---

### 3. Real-Time WebSocket Architecture

**Output Path:** `docs/images/websocket-architecture.png`

**Prompt:**

```
Technical illustration of WebSocket real-time architecture, central Redis node with pub/sub channels radiating to multiple browser clients, bidirectional arrows showing event flow, backend server connected to Redis. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 for data flows, electric cyan #22d3ee for client connections, clean network diagram, radial layout, no text labels, 16:9 aspect ratio
```

**Referenced In:** `docs/architecture/real-time.md`

---

### 4. Dashboard Hero Image

**Output Path:** `docs/images/dashboard-hero.png`

**Prompt:**

```
Dark mode security dashboard interface mockup, showing grid of camera feed thumbnails with detection bounding boxes highlighting people and vehicles, real-time event feed on right side with risk level color indicators (green/yellow/orange/red), top navigation bar, NVIDIA dark theme #121212 background with #76B900 green accent on active elements, modern clean security operations center aesthetic, 16:9 aspect ratio, no text overlays
```

**Referenced In:** `docs/ui/dashboard.md`

---

### 5. Event Timeline Hero Image

**Output Path:** `docs/images/timeline-hero.png`

**Prompt:**

```
Dark mode security event timeline interface, showing chronological list of security events with risk level color coding (green low, yellow medium, orange high, red critical), thumbnail previews on left, event summaries on right, date filters at top, NVIDIA dark theme #121212 background with #76B900 green accents, clean card-based layout, vertical 2:3 aspect ratio, no text overlays
```

**Referenced In:** `docs/ui/timeline.md`

---

### 6. Event Investigation Hero Image

**Output Path:** `docs/images/investigation-hero.png`

**Prompt:**

```
Dark mode security investigation interface showing video playback controls, entity tracking timeline with person silhouettes connected across multiple camera feeds, thumbnail filmstrip at bottom, forensic analysis aesthetic, NVIDIA dark theme #121212 background with #76B900 green accents and blue #3B82F6 highlight for selected entity, clean modern UI, vertical 2:3 aspect ratio, no text overlays
```

**Referenced In:** `docs/ui/timeline.md`

---

### 7. Settings Page Hero Image

**Output Path:** `docs/images/settings-hero.png`

**Prompt:**

```
Dark mode application settings interface with tabbed navigation (Cameras, Processing, AI Models tabs), form inputs with sliders and toggles, camera list table with status indicators, NVIDIA dark theme #121212 background with #76B900 green accent on selected tab, clean administrative interface, vertical 2:3 aspect ratio, no text overlays
```

**Referenced In:** `docs/ui/settings.md`

---

### 8. GPU Setup Architecture

**Output Path:** `docs/images/gpu-setup-architecture.png`

**Prompt:**

```
Technical illustration of GPU container architecture, showing NVIDIA GPU at bottom with driver layer, Container Runtime (Docker/Podman) in middle with CDI/nvidia-container-toolkit, AI containers (RT-DETRv2, Nemotron) at top receiving GPU access. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 for GPU elements, electric cyan #22d3ee for container layers, vertical stack layout, no text labels, 9:16 aspect ratio
```

**Referenced In:** `docs/operator/gpu-setup.md`

---

### 9. Deployment Modes Comparison

**Output Path:** `docs/images/deployment-modes.png`

**Prompt:**

```
Technical illustration comparing three deployment modes side by side: Development (laptop icon), Production (server rack), Hybrid (laptop connected to server). Each with container stacks and AI model indicators. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 accents, electric cyan #22d3ee for connections, clean comparison diagram, horizontal layout with three columns, no text labels, 16:9 aspect ratio
```

**Referenced In:** `docs/operator/deployment-modes.md`

---

### 10. Data Model Entity Relationship

**Output Path:** `docs/images/data-model-hero.png`

**Prompt:**

```
Technical illustration of database entity relationships, showing connected boxes: Events (center), Detections (many arrows to Events), Entities (connected to Detections), Cameras (arrows to Events), Summaries (arrow from Events). Excalidraw hand-drawn ERD style, dark background #0a0a0f, NVIDIA green #76B900 for primary relationships, electric cyan #22d3ee for foreign keys, clean database diagram aesthetic, no text labels, 16:9 aspect ratio
```

**Referenced In:** `docs/architecture/data-model.md`

---

### 11. System Monitoring Overview

**Output Path:** `docs/images/system-monitoring-hero.png`

**Prompt:**

```
Dark mode system monitoring dashboard with multiple metric panels: GPU utilization gauge, CPU/Memory bars, real-time graphs with upward trends, container status grid with green healthy indicators, circuit breaker status panel. NVIDIA dark theme #121212 background with #76B900 green for healthy states, orange and red for alerts, clean operations dashboard aesthetic, 16:9 aspect ratio, no text overlays
```

**Referenced In:** `docs/ui/operations.md`

---

### 12. Alerts and Notifications

**Output Path:** `docs/images/alerts-hero.png`

**Prompt:**

```
Dark mode alerts interface showing notification cards with severity indicators (critical red, high orange, medium yellow), bell icon with notification badge, filter dropdown, event thumbnails with warning overlays. NVIDIA dark theme #121212 background with #76B900 green accents, urgency-focused UI, clean card layout, 16:9 aspect ratio, no text overlays
```

**Referenced In:** `docs/ui/alerts.md`

---

### 13. First Run Quick Start

**Output Path:** `docs/images/first-run-hero.png`

**Prompt:**

```
Technical illustration of system startup sequence, showing numbered steps: 1. Docker containers starting (stacked boxes), 2. AI models loading (brain with loading indicator), 3. Camera connections establishing (camera icons with connection lines), 4. Dashboard ready (monitor with checkmark). Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 for progress indicators, vertical timeline layout, no text labels, 9:16 aspect ratio
```

**Referenced In:** `docs/getting-started/first-run.md`

---

### 14. Architecture Overview

**Output Path:** `docs/images/architecture-overview.png`

**Prompt:**

```
Technical illustration of full system architecture, showing three tiers: Frontend (React browser), Backend (FastAPI with Redis and PostgreSQL), AI Services (RT-DETRv2, Nemotron, CLIP on GPU). Connections showing data flow between layers. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 for primary data paths, electric cyan #22d3ee for secondary flows, accent purple #8b5cf6 for AI tier, clean three-tier architecture diagram, no text labels, 16:9 aspect ratio
```

**Referenced In:** `docs/architecture/overview.md`

---

### 15. Batch Processing Flow

**Output Path:** `docs/images/batch-processing.png`

**Prompt:**

```
Technical illustration of batch processing timeline, showing: Detection accumulation (stacking boxes over 90 seconds), batch window closing, LLM analysis (brain processing), event creation (output arrow). Timeline axis at bottom showing seconds. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 for active processing, electric cyan #22d3ee for timeline, clean process flow diagram, horizontal layout, no text labels, 16:9 aspect ratio
```

**Referenced In:** `docs/architecture/ai-pipeline.md`

---

## Execution Script

For convenience, here's a bash script to generate all images:

```bash
#!/bin/bash
# generate-all-images.sh
# Requires: NVIDIA_API_KEY environment variable set

set -e

SCRIPT="$HOME/.claude/skills/nvidia-image-gen/scripts/generate_image.py"
OUTPUT_DIR="docs/images"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

echo "Generating documentation images..."

# 1. Installation Workflow
echo "[1/15] Generating installation-workflow.png..."
uv run "$SCRIPT" \
  "Technical illustration of software installation workflow, four connected steps: 1. Clone Repository (git icon), 2. Setup Environment (terminal with checkmarks), 3. Download Models (download arrow with AI brain), 4. Configure (settings gear). Excalidraw hand-drawn style with slightly wobbly lines, dark background #0a0a0f, NVIDIA green #76B900 accent arrows connecting steps, electric cyan #22d3ee highlights, clean minimalist infographic, horizontal flow left to right, no text labels, 16:9 aspect ratio" \
  --output "$OUTPUT_DIR/installation-workflow.png"

# 2. AI Pipeline Architecture
echo "[2/15] Generating ai-pipeline-hero.png..."
uv run "$SCRIPT" \
  "Technical illustration of AI detection pipeline, showing flow: Camera icon -> Object Detection box (RT-DETRv2) -> Entity Clustering -> Risk Analysis box (Nemotron LLM) -> Security Events. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 primary flow lines, electric cyan #22d3ee secondary connections, accent purple #8b5cf6 for AI processing nodes, clean tech diagram aesthetic, horizontal flow, no text labels, 16:9 aspect ratio" \
  --output "$OUTPUT_DIR/ai-pipeline-hero.png"

# 3. WebSocket Architecture
echo "[3/15] Generating websocket-architecture.png..."
uv run "$SCRIPT" \
  "Technical illustration of WebSocket real-time architecture, central Redis node with pub/sub channels radiating to multiple browser clients, bidirectional arrows showing event flow, backend server connected to Redis. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 for data flows, electric cyan #22d3ee for client connections, clean network diagram, radial layout, no text labels, 16:9 aspect ratio" \
  --output "$OUTPUT_DIR/websocket-architecture.png"

# 4. Dashboard Hero
echo "[4/15] Generating dashboard-hero.png..."
uv run "$SCRIPT" \
  "Dark mode security dashboard interface mockup, showing grid of camera feed thumbnails with detection bounding boxes highlighting people and vehicles, real-time event feed on right side with risk level color indicators (green/yellow/orange/red), top navigation bar, NVIDIA dark theme #121212 background with #76B900 green accent on active elements, modern clean security operations center aesthetic, 16:9 aspect ratio, no text overlays" \
  --output "$OUTPUT_DIR/dashboard-hero.png"

# 5. Timeline Hero
echo "[5/15] Generating timeline-hero.png..."
uv run "$SCRIPT" \
  "Dark mode security event timeline interface, showing chronological list of security events with risk level color coding (green low, yellow medium, orange high, red critical), thumbnail previews on left, event summaries on right, date filters at top, NVIDIA dark theme #121212 background with #76B900 green accents, clean card-based layout, vertical 2:3 aspect ratio, no text overlays" \
  --output "$OUTPUT_DIR/timeline-hero.png"

# 6. Investigation Hero
echo "[6/15] Generating investigation-hero.png..."
uv run "$SCRIPT" \
  "Dark mode security investigation interface showing video playback controls, entity tracking timeline with person silhouettes connected across multiple camera feeds, thumbnail filmstrip at bottom, forensic analysis aesthetic, NVIDIA dark theme #121212 background with #76B900 green accents and blue #3B82F6 highlight for selected entity, clean modern UI, vertical 2:3 aspect ratio, no text overlays" \
  --output "$OUTPUT_DIR/investigation-hero.png"

# 7. Settings Hero
echo "[7/15] Generating settings-hero.png..."
uv run "$SCRIPT" \
  "Dark mode application settings interface with tabbed navigation (Cameras, Processing, AI Models tabs), form inputs with sliders and toggles, camera list table with status indicators, NVIDIA dark theme #121212 background with #76B900 green accent on selected tab, clean administrative interface, vertical 2:3 aspect ratio, no text overlays" \
  --output "$OUTPUT_DIR/settings-hero.png"

# 8. GPU Setup Architecture
echo "[8/15] Generating gpu-setup-architecture.png..."
uv run "$SCRIPT" \
  "Technical illustration of GPU container architecture, showing NVIDIA GPU at bottom with driver layer, Container Runtime (Docker/Podman) in middle with CDI/nvidia-container-toolkit, AI containers (RT-DETRv2, Nemotron) at top receiving GPU access. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 for GPU elements, electric cyan #22d3ee for container layers, vertical stack layout, no text labels, 9:16 aspect ratio" \
  --output "$OUTPUT_DIR/gpu-setup-architecture.png"

# 9. Deployment Modes
echo "[9/15] Generating deployment-modes.png..."
uv run "$SCRIPT" \
  "Technical illustration comparing three deployment modes side by side: Development (laptop icon), Production (server rack), Hybrid (laptop connected to server). Each with container stacks and AI model indicators. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 accents, electric cyan #22d3ee for connections, clean comparison diagram, horizontal layout with three columns, no text labels, 16:9 aspect ratio" \
  --output "$OUTPUT_DIR/deployment-modes.png"

# 10. Data Model Hero
echo "[10/15] Generating data-model-hero.png..."
uv run "$SCRIPT" \
  "Technical illustration of database entity relationships, showing connected boxes: Events (center), Detections (many arrows to Events), Entities (connected to Detections), Cameras (arrows to Events), Summaries (arrow from Events). Excalidraw hand-drawn ERD style, dark background #0a0a0f, NVIDIA green #76B900 for primary relationships, electric cyan #22d3ee for foreign keys, clean database diagram aesthetic, no text labels, 16:9 aspect ratio" \
  --output "$OUTPUT_DIR/data-model-hero.png"

# 11. System Monitoring Hero
echo "[11/15] Generating system-monitoring-hero.png..."
uv run "$SCRIPT" \
  "Dark mode system monitoring dashboard with multiple metric panels: GPU utilization gauge, CPU/Memory bars, real-time graphs with upward trends, container status grid with green healthy indicators, circuit breaker status panel. NVIDIA dark theme #121212 background with #76B900 green for healthy states, orange and red for alerts, clean operations dashboard aesthetic, 16:9 aspect ratio, no text overlays" \
  --output "$OUTPUT_DIR/system-monitoring-hero.png"

# 12. Alerts Hero
echo "[12/15] Generating alerts-hero.png..."
uv run "$SCRIPT" \
  "Dark mode alerts interface showing notification cards with severity indicators (critical red, high orange, medium yellow), bell icon with notification badge, filter dropdown, event thumbnails with warning overlays. NVIDIA dark theme #121212 background with #76B900 green accents, urgency-focused UI, clean card layout, 16:9 aspect ratio, no text overlays" \
  --output "$OUTPUT_DIR/alerts-hero.png"

# 13. First Run Hero
echo "[13/15] Generating first-run-hero.png..."
uv run "$SCRIPT" \
  "Technical illustration of system startup sequence, showing numbered steps: 1. Docker containers starting (stacked boxes), 2. AI models loading (brain with loading indicator), 3. Camera connections establishing (camera icons with connection lines), 4. Dashboard ready (monitor with checkmark). Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 for progress indicators, vertical timeline layout, no text labels, 9:16 aspect ratio" \
  --output "$OUTPUT_DIR/first-run-hero.png"

# 14. Architecture Overview
echo "[14/15] Generating architecture-overview.png..."
uv run "$SCRIPT" \
  "Technical illustration of full system architecture, showing three tiers: Frontend (React browser), Backend (FastAPI with Redis and PostgreSQL), AI Services (RT-DETRv2, Nemotron, CLIP on GPU). Connections showing data flow between layers. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 for primary data paths, electric cyan #22d3ee for secondary flows, accent purple #8b5cf6 for AI tier, clean three-tier architecture diagram, no text labels, 16:9 aspect ratio" \
  --output "$OUTPUT_DIR/architecture-overview.png"

# 15. Batch Processing
echo "[15/15] Generating batch-processing.png..."
uv run "$SCRIPT" \
  "Technical illustration of batch processing timeline, showing: Detection accumulation (stacking boxes over 90 seconds), batch window closing, LLM analysis (brain processing), event creation (output arrow). Timeline axis at bottom showing seconds. Excalidraw hand-drawn style, dark background #0a0a0f, NVIDIA green #76B900 for active processing, electric cyan #22d3ee for timeline, clean process flow diagram, horizontal layout, no text labels, 16:9 aspect ratio" \
  --output "$OUTPUT_DIR/batch-processing.png"

echo ""
echo "All images generated successfully!"
echo "Output directory: $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"/*.png
```

---

## Validation Criteria

After generating each image, validate against these criteria:

### Visual Quality

- [ ] Dark background (#0a0a0f or #121212) is present
- [ ] NVIDIA green (#76B900) accents are visible
- [ ] No text overlays appear in the image
- [ ] Clean, professional aesthetic
- [ ] Correct aspect ratio for intended use

### Technical Accuracy

- [ ] Diagram elements match the described architecture
- [ ] Flow direction is correct (left-to-right or top-to-bottom)
- [ ] Component relationships are accurately represented
- [ ] Color coding matches risk levels or status states

### Documentation Integration

- [ ] Image dimensions work with markdown rendering
- [ ] Alt text is added to the markdown reference
- [ ] Image is referenced correctly in the documentation file

---

## Post-Generation Tasks

After all images are generated:

1. **Update Documentation Files:** Add image references to the documented source files
2. **Add Alt Text:** Each image reference should include descriptive alt text
3. **Verify Rendering:** Check that images render correctly in the documentation
4. **Commit:** Commit all generated images with message: `docs: add AI-generated documentation images`

---

## Troubleshooting

### "NVIDIA_API_KEY environment variable not set"

```bash
export NVIDIA_API_KEY="your-api-key"  # pragma: allowlist secret
# Then re-run the script
```

### "No image data found in response"

- Rephrase the prompt to be more specific
- Check API key permissions
- Verify network connectivity to inference-api.nvidia.com

### Images not matching expected style

- Ensure "Excalidraw hand-drawn style" is in the prompt
- Verify dark background colors are specified
- Re-generate with adjusted prompt if needed

---

## Color Reference

| Name              | Hex       | Usage                           |
| ----------------- | --------- | ------------------------------- |
| Background (dark) | `#0a0a0f` | Primary background for diagrams |
| Background (UI)   | `#121212` | UI mockup backgrounds           |
| NVIDIA Green      | `#76B900` | Primary accents, healthy states |
| Electric Cyan     | `#22d3ee` | Secondary accents, connections  |
| Accent Purple     | `#8b5cf6` | Highlights, AI elements         |
| Blue Accent       | `#3B82F6` | Selection, links                |
| Risk Low          | Green     | 0-29 risk score                 |
| Risk Medium       | Yellow    | 30-59 risk score                |
| Risk High         | Orange    | 60-84 risk score                |
| Risk Critical     | Red       | 85-100 risk score               |
