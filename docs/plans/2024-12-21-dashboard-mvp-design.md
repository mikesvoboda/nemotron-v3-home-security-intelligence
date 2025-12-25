# Home Security Intelligence - Dashboard MVP Design

**Date:** 2024-12-21
**Status:** Approved

## Overview

AI-powered home security monitoring dashboard that processes camera uploads through RT-DETRv2 for object detection and Nemotron for contextual risk assessment.

## Technology Stack

| Component    | Technology                                               |
| ------------ | -------------------------------------------------------- |
| Frontend     | React + TypeScript + Tailwind CSS + Headless UI + Tremor |
| Backend      | Python FastAPI                                           |
| Database     | SQLite (persistence) + Redis (queues, pub/sub)           |
| Real-time    | WebSockets                                               |
| Detection AI | RT-DETRv2 (~4GB VRAM)                                    |
| Reasoning AI | Nemotron via llama.cpp (~18GB VRAM, Q4_K_M)              |
| Deployment   | Docker (services) + Native (AI models)                   |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Home Security Intelligence                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    FTP     ┌──────────────────────────────────────────┐   │
│  │   Foscam    │ ────────── │  /export/foscam/{camera_name}/           │   │
│  │   Cameras   │  uploads   │  File Watcher (watchdog)                 │   │
│  └─────────────┘            └──────────────┬───────────────────────────┘   │
│                                            │                               │
│                                            ▼                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Processing Pipeline                              │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │   │
│  │  │  RT-DETRv2  │───▶│   Redis     │───▶│  Nemotron (llama.cpp)   │  │   │
│  │  │  (~4GB)     │    │   Queue     │    │  (~18GB) Q4_K_M         │  │   │
│  │  │  Detection  │    │  (batches   │    │  Risk + Reasoning       │  │   │
│  │  │  per frame  │    │  1-2 min)   │    │  per batch              │  │   │
│  │  └─────────────┘    └─────────────┘    └─────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                            │                               │
│                                            ▼                               │
│  ┌──────────────────┐    WebSocket    ┌─────────────────────────────────┐  │
│  │  SQLite          │◀───────────────▶│  FastAPI Backend                │  │
│  │  (events, config)│                 │  (REST + WebSocket)             │  │
│  └──────────────────┘                 └───────────────┬─────────────────┘  │
│                                                       │                    │
│                                                       ▼                    │
│                                       ┌─────────────────────────────────┐  │
│                                       │  React Dashboard                │  │
│                                       │  Tailwind + Tremor              │  │
│                                       └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. Cameras FTP upload images/videos to `/export/foscam/{camera_name}/`
2. File watcher detects new files, sends to RT-DETRv2
3. Detections accumulate in Redis queue
4. Every 1-2 minutes, batch sent to Nemotron for risk assessment + reasoning
5. Results stored in SQLite, pushed to dashboard via WebSocket

## Database Schema

```sql
-- Camera configuration
cameras (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    folder_path     TEXT NOT NULL,
    status          TEXT DEFAULT 'online',
    created_at      TIMESTAMP,
    last_seen_at    TIMESTAMP
)

-- Individual detections from RT-DETRv2
detections (
    id              INTEGER PRIMARY KEY,
    camera_id       TEXT REFERENCES cameras(id),
    file_path       TEXT NOT NULL,
    file_type       TEXT,
    detected_at     TIMESTAMP,
    object_type     TEXT,
    confidence      REAL,
    bbox_x          INTEGER,
    bbox_y          INTEGER,
    bbox_width      INTEGER,
    bbox_height     INTEGER,
    thumbnail_path  TEXT
)

-- Batched analysis from Nemotron
events (
    id              INTEGER PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    camera_id       TEXT REFERENCES cameras(id),
    started_at      TIMESTAMP,
    ended_at        TIMESTAMP,
    risk_score      INTEGER,
    risk_level      TEXT,
    summary         TEXT,
    reasoning       TEXT,
    detection_ids   TEXT,
    reviewed        BOOLEAN DEFAULT 0,
    notes           TEXT
)

-- GPU performance snapshots
gpu_stats (
    id              INTEGER PRIMARY KEY,
    recorded_at     TIMESTAMP,
    gpu_utilization REAL,
    memory_used     INTEGER,
    memory_total    INTEGER,
    temperature     REAL,
    inference_fps   REAL
)
```

## API Endpoints

### REST

```
── Events ──────────────────────────────────────────────────────────
GET    /api/events                  List events (paginated, filterable)
GET    /api/events/{id}             Get event detail with detections
PATCH  /api/events/{id}             Update event (mark reviewed, add notes)
GET    /api/events/stats            Aggregated stats

── Detections ──────────────────────────────────────────────────────
GET    /api/detections              List raw detections
GET    /api/detections/{id}         Get detection detail
GET    /api/detections/{id}/image   Serve detection image with bbox overlay

── Cameras ─────────────────────────────────────────────────────────
GET    /api/cameras                 List all cameras with status
GET    /api/cameras/{id}            Get camera detail
GET    /api/cameras/{id}/snapshot   Latest image from camera
POST   /api/cameras                 Add new camera
PATCH  /api/cameras/{id}            Update camera config
DELETE /api/cameras/{id}            Remove camera

── System ──────────────────────────────────────────────────────────
GET    /api/system/gpu              Current GPU stats
GET    /api/system/gpu/history      GPU stats over time
GET    /api/system/health           Service health check
GET    /api/system/config           Get system configuration
PATCH  /api/system/config           Update configuration

── Media ───────────────────────────────────────────────────────────
GET    /api/media/{path}            Serve images/videos from storage
```

### WebSocket

```
WS /ws/events
   ← new_event      {event object}
   ← detection      {detection object}

WS /ws/system
   ← gpu_stats      {utilization, temp, mem}
   ← camera_status  {camera_id, status}
```

## Processing Pipeline

```
1. FILE WATCHER (watchdog library)
   ├── Monitors: /export/foscam/{camera_name}/
   ├── Triggers on: new .jpg, .png, .mp4, .avi files
   ├── Debounce: 500ms
   └── Output: file_path, camera_id, timestamp

2. RT-DETRv2 DETECTION
   ├── Input: image/video frame
   ├── Processing: ~7ms per frame on A5500
   ├── Output: object_type, confidence, bounding_box, thumbnail
   └── Store: SQLite detections table + Redis queue

3. BATCH AGGREGATOR
   ├── Groups detections by camera
   ├── Window: 1-2 minutes (configurable)
   ├── Closes batch when window expires OR no detections for 30s
   └── Output: batch_id, detection_ids[], camera_id, time_range

4. NEMOTRON ANALYSIS
   ├── Input: batch summary + representative frames
   ├── Processing: ~2-5 seconds per batch
   ├── Output: risk_score, risk_level, summary, reasoning
   └── Store: SQLite events table

5. NOTIFICATION
   └── Push new event to dashboard via WebSocket
```

## Nemotron Prompt Template

```
SYSTEM:
You are a home security AI analyst. Analyze surveillance detections and assess risk.

You must respond in valid JSON with this exact structure:
{
  "risk_score": <0-100>,
  "risk_level": "<low|medium|high>",
  "summary": "<1-2 sentence description of activity>",
  "reasoning": "<detailed explanation of risk assessment>"
}

Risk Guidelines:
- LOW (0-33): Known routine activity, animals, delivery expected, normal traffic
- MEDIUM (34-66): Unknown persons, unexpected vehicles, unusual timing
- HIGH (67-100): Suspicious behavior, attempted entry, loitering, multiple unknowns

Consider these factors:
- Time of day (late night = higher baseline risk)
- Object type (person near entry points = higher than vehicle on street)
- Behavior patterns (lingering, approaching doors/windows, looking around)
- Count (multiple unknown persons = higher risk)

USER:
Camera: {camera_name}
Location: {camera_description}
Time: {timestamp}
Duration: {batch_duration}

Detections in this batch:
{detection_list}

Representative frame attached.

Analyze this activity and provide risk assessment.
```

## MVP Dashboard Panels

1. **Live Activity Feed** - Real-time event stream with risk badges
2. **Multi-Camera Grid** - 3x3 or 4x2 camera thumbnails with status
3. **Event Detail View** - Modal with image, bounding boxes, AI reasoning
4. **Risk Assessment Gauge** - Circular gauge (0-100) with 24h sparkline
5. **Entity Database** - Placeholder for v2 (categories only for MVP)
6. **GPU Performance** - Utilization, temperature, memory, inference FPS

## UI Design

### Color Scheme (NVIDIA-themed)

- Background: `#0E0E0E`
- Panel background: `#1A1A1A`
- Card background: `#1E1E1E`
- Primary accent: `#76B900` (NVIDIA Green)
- Risk Low: `#76B900`
- Risk Medium: `#FFB800`
- Risk High: `#E74856`
- Text: `#FFFFFF` / `#A0A0A0`

### Layout

- Header: Logo, system status, GPU quick stats, settings
- Left sidebar: Navigation (Dashboard, Timeline, Entities, Alerts, Settings)
- Main content: Flexible grid with panels

## Project Structure

```
home_security_intelligence/
├── docker-compose.yml
├── .env.example
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── api/
│   │   ├── routes/
│   │   │   ├── events.py
│   │   │   ├── detections.py
│   │   │   ├── cameras.py
│   │   │   ├── system.py
│   │   │   └── media.py
│   │   └── websocket.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── redis.py
│   ├── models/
│   │   ├── camera.py
│   │   ├── detection.py
│   │   ├── event.py
│   │   └── gpu_stats.py
│   ├── services/
│   │   ├── file_watcher.py
│   │   ├── detector.py
│   │   ├── batch_aggregator.py
│   │   ├── analyzer.py
│   │   ├── gpu_monitor.py
│   │   └── cleanup.py
│   └── data/
│       ├── security.db
│       └── thumbnails/
│
├── ai/
│   ├── start_detector.sh
│   ├── start_llm.sh
│   ├── rtdetr/
│   │   ├── model.py
│   │   └── weights/
│   └── nemotron/
│       └── config.json
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── layout/
│       │   ├── dashboard/
│       │   ├── events/
│       │   └── common/
│       ├── hooks/
│       ├── services/
│       └── styles/
│
└── scripts/
    ├── setup.sh
    ├── download_models.sh
    └── seed_cameras.py
```

## Docker Compose

```yaml
version: "3.8"

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/data:/app/data
      - /export/foscam:/cameras:ro
    environment:
      - DATABASE_URL=sqlite:///data/security.db
      - REDIS_URL=redis://redis:6379
      - DETECTOR_URL=http://host.docker.internal:8001
      - LLM_URL=http://host.docker.internal:8002
      - CAMERA_ROOT=/cameras
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000
      - VITE_WS_URL=ws://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  redis_data:
```

## Configuration

```bash
# Camera Configuration
CAMERA_ROOT=/export/foscam

# Database
DATABASE_URL=sqlite:///data/security.db

# Redis
REDIS_URL=redis://localhost:6379

# AI Services (native, not in Docker)
DETECTOR_URL=http://localhost:8001
LLM_URL=http://localhost:8002

# Processing
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
DETECTION_CONFIDENCE_THRESHOLD=0.5

# Retention
RETENTION_DAYS=30

# GPU Monitoring
GPU_POLL_INTERVAL_SECONDS=2
```

## Key Specifications

| Spec           | Value                           |
| -------------- | ------------------------------- |
| Cameras        | 5-8 Foscam cameras              |
| Camera Path    | `/export/foscam/{camera_name}/` |
| Batch Window   | 1-2 minutes                     |
| Data Retention | 30 days                         |
| Authentication | None (local single-user)        |
| Notifications  | Dashboard only (MVP)            |
| GPU            | RTX A5500 24GB (~22GB used)     |

## UI Mockups & Design Decisions

### Branding

- **App Name:** NVIDIA SECURITY
- **Tagline:** POWERED BY NEMOTRON
- Dark theme with NVIDIA green (#76B900) accent

### Approved Screens

#### 1. Main Dashboard

**Layout:**

```
┌────────┬──────────────────────────────────────────────────────┐
│        │ [Stats Row: Cameras | Latency | Risk Gauge | GPU]    │
│  NAV   ├────────────────────────┬─────────────────────────────┤
│        │ GPU Performance        │ Live Activity Feed          │
│ Dash   │ (charts, utilization)  │ (scrolling event cards      │
│ Time   │                        │  with AI summaries)         │
│ Entity ├────────────────────────┤                             │
│ Alerts │ Camera Grid            │                             │
│ Setti  │ (2x3 or 2x4 grid)      │                             │
└────────┴────────────────────────┴─────────────────────────────┘
```

**Key Components:**

- Prominent circular Risk Gauge (0-100) with color coding and 24h sparkline
- Live Activity Feed as primary panel with AI-generated summaries
- Multi-camera grid with status indicators
- GPU stats in header (utilization %, temperature, VRAM)
- "LIVE MONITORING" status indicator

**Decisions:**

- No entity recognition panel (v2 feature)
- Risk gauge replaces simple "Threat Level" display
- Camera grid shows thumbnails without bounding box overlays (detail in modal)

#### 2. Event Timeline (Approved)

**Features:**

- Filter bar: Camera, Time Range, Risk Level, Object Type, Search
- "Mark all as reviewed" bulk action
- Event count with risk summary badges (e.g., "3 HIGH RISK | 12 MEDIUM")
- Scrollable event cards with:
  - Thumbnail with bounding box overlay and timestamp
  - Camera name + relative time
  - Risk badge (HIGH/MEDIUM/LOW) color-coded
  - Object type badge (PERSON/VEHICLE/ANIMAL/PACKAGE)
  - AI-generated summary text (Nemotron output)
  - Duration and confidence metadata
  - Risk score progress bar (0-100)
  - "View Details" button
- Color-coded left border on cards by risk level

#### 3. Event Detail Modal (Approved)

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Event Analysis                                        [✕]      │
├─────────────────────────────┬───────────────────────────────────┤
│                             │ RISK ASSESSMENT                   │
│  [Main Image with           │ Score: 72 / 100  [MEDIUM]        │
│   bounding boxes]           │                                   │
│                             │ AI REASONING                      │
│  Label: PERSON: 94%         │ "The subject is identified..."   │
│  Label: OBJECT: 88%         │                                   │
├─────────────────────────────┤                                   │
│ DETECTION SEQUENCE          │                                   │
│ [thumb] [thumb] [thumb]     │ METADATA                          │
│  00:00   00:02   00:04      │ Camera, Time, Duration            │
├─────────────────────────────┴───────────────────────────────────┤
│ NOTES                                              [Edit]       │
│ User observations...                                            │
├─────────────────────────────────────────────────────────────────┤
│ [✓ Mark Reviewed]   [⚑ Flag Event]   [↓ Download Media]        │
└─────────────────────────────────────────────────────────────────┘
```

**Key Features:**

- Main image with labeled bounding boxes and confidence percentages
- Multi-object detection support (e.g., person + held object)
- AI Reasoning section prominently displayed
- Detection sequence thumbnail strip with timestamps
- User notes section
- Action buttons: Mark Reviewed, Flag, Download

#### 4. Settings Page (Approved)

**Tab Structure:**

1. **CAMERAS** - Table of configured cameras with:

   - Camera name, folder path (FTP), status, last seen
   - Edit/Delete actions
   - "+ Add Camera" button

2. **PROCESSING** - Sliders for:

   - Batch Window (default: 90 seconds)
   - Confidence Threshold (default: 0.50)
   - Idle Timeout (default: 30 seconds)
   - Retention Period (default: 30 days)
   - Storage usage indicator with "Clear Old Data" button

3. **AI MODELS** - Read-only status:
   - RT-DETRv2: endpoint, VRAM, FPS
   - Nemotron: endpoint, VRAM, quantization
   - GPU hardware info (RTX A5500)

**Footer:** Auto-save indicator, Discard, Save Changes buttons

### Navigation Structure

```
Sidebar:
├── Dashboard (home)
├── Timeline (event history)
├── Entities [WIP badge] (placeholder for v2)
├── Alerts (filtered timeline)
└── Settings (config)
```

### UI Component Library

- **Charts/Gauges:** Tremor + custom circular gauge
- **Styling:** Tailwind CSS
- **Components:** Headless UI
- **Icons:** Lucide React

## Deferred to v2

- Face recognition / entity identification
- License plate recognition
- Email/mobile push notifications
- RTSP live stream support
- Natural language search
- Analytics & activity heatmaps
- Configurable alert rules
