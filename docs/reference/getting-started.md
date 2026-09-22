# Getting Started Reference

> Quick reference for new users of Home Security Intelligence.

This page provides a quick overview and links to the detailed getting started documentation.

---

## Quick Links

| Guide                                                | Description                            |
| ---------------------------------------------------- | -------------------------------------- |
| [Prerequisites](../getting-started/prerequisites.md) | Hardware and software requirements     |
| [Installation](../getting-started/installation.md)   | Step-by-step installation guide        |
| [First Run](../getting-started/first-run.md)         | Starting the system for the first time |
| [Quick Start](../getting-started/quick-start.md)     | Get up and running in 5 minutes        |
| [Dashboard Tour](../getting-started/tour.md)         | Interactive tour of the dashboard      |
| [Upgrading](../getting-started/upgrading.md)         | Upgrade from previous versions         |

---

## System Overview

Home Security Intelligence is an AI-powered home security monitoring dashboard that:

- **Processes camera feeds** using YOLO26 object detection
- **Analyzes detections** with Nemotron LLM for risk assessment
- **Provides real-time alerts** via WebSocket connections
- **Tracks entities** (people, vehicles, pets) across cameras
- **Maintains activity baselines** for anomaly detection

### Architecture Components

Production AI runs as two containers: an AI **gateway** (Triton Inference Server on :8090)
serving detection and enrichment models behind path-routed endpoints, and a standalone
llama.cpp server for the LLM (:8091).

```
Camera Images
      |
      v
+------------------------------------------------------------------+
|              AI Gateway  (ai-gateway, :8090)                     |
|  /yolo26   /enrichment   /enrich-lt   /florence   /clip          |
|  detection  heavy models  light models  VLM       embeddings     |
+------------------------------------------------------------------+
      |
      v
+-----------------------------------------------------------+
|              Nemotron (ai-llm, :8091)                     |
|              Risk Analysis & Scoring                      |
+-----------------------------------------------------------+
                          |
                          v
                    Risk Events
```

---

## Minimum Requirements

### Hardware

| Component | Minimum                          | Recommended             |
| --------- | -------------------------------- | ----------------------- |
| GPU       | 8-12 GB VRAM (LLM partly on CPU) | 24 GB VRAM (full stack) |
| RAM       | 16 GB                            | 32 GB+                  |
| Storage   | 50 GB (core models)              | 100 GB+ (full zoo)      |
| CPU       | 4 cores                          | 8+ cores                |

Details and per-model VRAM breakdown: [Prerequisites](../getting-started/prerequisites.md).

### Software

| Component         | Version                     |
| ----------------- | --------------------------- |
| Python            | 3.14+                       |
| Node.js           | ^22.12.0 or >=24.0.0        |
| Container Runtime | Docker/Podman               |
| CUDA              | 12.0+ (GPU capability 7.0+) |

---

## Quick Start (5 Minutes)

```bash
# 1. Clone repository
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence

# 2. Run first-time setup (generates .env with real credentials + docker-compose.override.yml)
python setup.py

# 3. Download AI models (manifest: models.yml)
./ai/download_models.sh

# 4. Start services (docker works too — compose/podman compose both supported)
podman compose -f docker-compose.prod.yml up -d

# 5. Open the dashboard (HTTP on 8080, HTTPS on 8444 — configurable via
#    FRONTEND_HTTP_PORT / FRONTEND_HTTPS_PORT)
open http://localhost:8080
```

---

## Key Concepts

### Risk Scoring

The system assigns risk scores (0-100) to events:

| Score  | Level    | Description                         |
| ------ | -------- | ----------------------------------- |
| 0-29   | Low      | Normal activity, no concern         |
| 30-59  | Medium   | Unusual but not alarming            |
| 60-84  | High     | Requires attention                  |
| 85-100 | Critical | Immediate investigation recommended |

### Detection Classes

YOLO26 detects security-relevant objects:

```python
SECURITY_CLASSES = {
    "person", "car", "truck", "dog", "cat",
    "bird", "bicycle", "motorcycle", "bus"
}
```

### Entity Types

The system tracks these entity types:

| Type    | Description               |
| ------- | ------------------------- |
| person  | Human individuals         |
| vehicle | Cars, trucks, motorcycles |
| animal  | Pets and wildlife         |
| package | Delivered packages        |
| other   | Unclassified objects      |

---

## Keyboard Navigation

Press `?` anywhere to see keyboard shortcuts.

| Action          | Shortcut       |
| --------------- | -------------- |
| Command palette | `Cmd/Ctrl + K` |
| Go to Dashboard | `g d`          |
| Go to Timeline  | `g t`          |
| Help            | `?`            |

See [Keyboard Shortcuts](keyboard-shortcuts.md) for complete reference.

---

## Configuration Files

| File                         | Purpose                                    |
| ---------------------------- | ------------------------------------------ |
| `.env`                       | Environment configuration                  |
| `docker-compose.prod.yml`    | Container orchestration                    |
| `config/gpu-assignments.yml` | GPU assignments (generated reference file) |
| `pyproject.toml`             | Python dependencies                        |

---

## Common Tasks

### View Live Events

1. Open Dashboard (`g d`)
2. Activity feed shows real-time detections
3. Click event for details

### Check System Health

1. Navigate to System page (`g y`)
2. View GPU utilization, service status
3. Check AI model performance

### Configure Cameras

1. Go to Settings (`g s`)
2. Camera Management section
3. Add FTP upload paths

### Review Analytics

1. Open Analytics (`g n`)
2. View detection trends
3. Filter by date range

---

## Troubleshooting

| Issue                   | Solution                                                  |
| ----------------------- | --------------------------------------------------------- |
| No detections appearing | Check the AI gateway: `curl localhost:8090/yolo26/health` |
| High risk scores        | Review Nemotron prompts and thresholds                    |
| GPU out of memory       | Reduce batch size or use smaller model                    |
| WebSocket disconnects   | Check Redis connection and backend logs                   |

See [Troubleshooting Guide](troubleshooting/index.md) for detailed solutions.

---

## Next Steps

After initial setup:

1. **Configure zones** - Set up detection zones for each camera
2. **Add household members** - Register known people for smart alerts
3. **Set up notifications** - Configure webhook integrations
4. **Review baselines** - Let the system learn normal patterns (7 days)

---

## Related Documentation

- [Full Getting Started Guide](../getting-started/README.md)
- [AI Models Reference](models.md)
- [Environment Variables](config/env-reference.md)
- [Accessibility Features](accessibility.md)

---

[Back to Reference Hub](README.md)
