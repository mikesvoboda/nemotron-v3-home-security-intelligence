# Home Security Intelligence - Roadmap

**Audience:** Agents/engineers continuing work after the MVP phases in `docs/plans/`.

This document captures **ideas beyond the MVP** and provides enough context to help another agent:

- understand _why_ an idea matters,
- identify _where_ it would land in the codebase,
- estimate complexity / prerequisites,
- and avoid "nice idea, unclear next step" traps.

---

## Context (What MVP already establishes)

The MVP architecture is already oriented around **event-based reasoning**:

- Camera uploads arrive via FTP into `/export/foscam/{camera_name}/`
- A file watcher detects new media
- YOLO26 produces per-frame detections
- Redis batching groups detections into an "event window"
- Nemotron produces a risk score + summary + reasoning
- Results persist in PostgreSQL and are surfaced via APIs/WebSockets to the dashboard

This makes the system naturally extensible in three directions:

1. **Better signals** (more/cleaner context into the model and into heuristics)
2. **Better delivery** (alerts, workflows, investigation UX, reliability)
3. **Better understanding** (search, patterns, entities, continuity)

---

## Guiding principles (to keep scope sane)

If you're an agent picking up roadmap work, treat these as constraints:

- **Local-first**: default to single-machine, PostgreSQL + Redis, minimal ops burden.
- **Privacy-aware**: cameras are sensitive; prefer opt-in for identity features (faces/plates).
- **Event-centric**: keep "event" as the unit of human attention; avoid raw-frame firehose UX.
- **Measurable wins**: prioritize changes that reduce false positives, increase recall, or improve time-to-action.
- **Operational robustness**: a home system must recover from restarts, partial outages, and storage constraints.

---

## Implemented Features (Post-MVP Complete)

The following features originally planned for post-MVP have been implemented:

### 1) Alerting & Escalation - IMPLEMENTED

**Location:** `backend/services/alert_engine.py`, `backend/services/notification.py`, `backend/models/alert.py`

**What's implemented:**

- **Alert rules engine** with multiple condition types:
  - Risk threshold (e.g., alert on `risk_score >= 70`)
  - Object-based rules (person, vehicle, animal)
  - Camera selection (specific cameras or all)
  - Time range/schedule support
  - Zone-based conditions
  - Minimum confidence thresholds
- **Alert deduplication** with cooldown/suppression logic (`backend/services/alert_dedup.py`)
- **Notification channels:**
  - Email via SMTP
  - Webhooks (HTTP POST with SSRF protection)
  - Push notifications (stubbed)
- **Severity taxonomy:** LOW, MEDIUM, HIGH, CRITICAL
- **Frontend:** AlertRulesSettings component, NotificationSettings

### 2) Spatial Intelligence & Zones - IMPLEMENTED

**Location:** `backend/models/zone.py`, `backend/services/zone_service.py`, `backend/api/routes/zones.py`

**What's implemented:**

- **Per-camera zones** with polygon/rectangle support
- **Zone types:** entry_point, driveway, sidewalk, yard, other
- **Normalized coordinates** (0-1 range) stored as JSONB
- **Spatial heuristics:**
  - Ray casting algorithm for point-in-polygon testing
  - Dwell time tracking
  - Line crossing detection
  - Approach vector calculation (direction, speed, ETA)
- **Zone context in alerts:** Rules can filter by zone_ids

### 3) Entity Continuity (ReID-lite) - IMPLEMENTED

**Location:** `backend/services/reid_service.py`, `backend/services/clip_client.py`

**What's implemented:**

- **CLIP ViT-L embeddings** (768-dimensional vectors) via ai-clip HTTP service
- **Cross-camera entity matching** with configurable similarity threshold (default: 0.85)
- **Redis storage** for embeddings with 24-hour TTL
- **Concurrency-based rate limiting** to prevent resource exhaustion
- **Entity attributes tracking** (clothing, color from vision extraction)

### 4) Pattern-of-Life / Anomaly Detection - IMPLEMENTED

**Location:** `backend/services/baseline.py`, `backend/models/baseline.py`

**What's implemented:**

- **Baseline activity modeling** with exponential moving average and configurable decay
- **Per-camera activity rates** by hour and day-of-week
- **Class-specific frequencies** (e.g., "vehicles after midnight are rare")
- **Rolling 30-day window** for baseline calculations
- **Anomaly scoring** with configurable threshold (default: 2.0 standard deviations)
- **Minimum sample requirements** for reliable detection

### 5) Search & Investigations - IMPLEMENTED

**Location:** `backend/services/search.py`, `backend/api/routes/events.py`

**What's implemented:**

- **PostgreSQL full-text search** with tsvector/tsquery
- **Search across:** summary, reasoning, object types, camera names
- **Phrase search** using double quotes
- **Boolean operators:** AND, OR, NOT
- **Filtering:** time range, camera IDs, severity levels, object types, reviewed status
- **Relevance-ranked results** with scores

### 6) Better Media Handling (Clips) - IMPLEMENTED

**Location:** `backend/services/clip_generator.py`, `backend/services/video_processor.py`

**What's implemented:**

- **Event clip generation** from video files using ffmpeg
- **Image sequence to video** conversion (MP4/GIF)
- **Configurable pre/post roll** (0-300 seconds)
- **Secure path validation** preventing command injection
- **Output formats:** mp4, gif with H.264 codec

### 7) Reliability & Operations - IMPLEMENTED

**Location:** `backend/services/circuit_breaker.py`, `backend/services/retry_handler.py`, `backend/core/redis.py`

**What's implemented:**

- **Circuit breaker pattern** with CLOSED/OPEN/HALF_OPEN states
- **Prometheus metrics** for circuit breaker monitoring
- **Retry handler** with exponential backoff and jitter
- **Dead-letter queue (DLQ)** for failed jobs with inspection API
- **Health endpoints** at `/api/system/health/*`
- **Pipeline latency metrics** and observability

### 8) Security Hardening - IMPLEMENTED

**Location:** `backend/api/middleware/auth.py`, `backend/api/middleware/rate_limit.py`, `backend/models/audit.py`

**What's implemented:**

- **API key authentication** (opt-in via `API_KEY_ENABLED`)
- **SHA-256 hashed key storage**
- **WebSocket authentication** via query parameter or Sec-WebSocket-Protocol
- **Rate limiting** using Redis sliding window algorithm
- **Audit logging** with comprehensive action types:
  - Event actions (reviewed, dismissed)
  - Settings changes
  - Authentication (login/logout)
  - API key management
  - Security events (rate limit exceeded, file magic rejected)
- **SSRF protection** for webhooks

---

## Future Enhancements (Not Yet Implemented)

### Natural language "chat with your security history" (RAG)

**Why it matters:**

- Query: "Did any unknown vehicles park in the driveway this week?"
- Requires: event/detection index + retrieval + summarization

**Implementation ideas:**

- Embed event summaries using existing CLIP service
- Vector similarity search for relevant events
- LLM summarization of retrieved context

**Complexity:** Medium-High (requires RAG infrastructure)

---

### NIM / Standardized Inference Deployment

**Why it matters:**

- Replace ad-hoc llama.cpp process management with production inference service
- Better scaling, consistency, and model versioning

**Implementation ideas:**

- NVIDIA NIM containers for standardized inference
- Model registry for version management
- Blue-green deployment for model updates

**Complexity:** Medium (deployment infrastructure)

---

### Digital Twin Reconstruction (USD / Omniverse)

**Why it matters:**

- Generate structured 3D event reconstructions for replay/forensics
- Very cool demo; likely not a practical priority early

**Prerequisites:**

- Accurate depth estimation (Depth Anything V2 already in model zoo)
- Camera calibration data
- 3D scene understanding

**Complexity:** High (requires significant new infrastructure)

---

### Face Recognition / License Plates (Privacy-Sensitive)

**Why it matters:**

- High user value for identifying known vs unknown visitors
- Requires careful privacy handling

**Current state:**

- YOLO Face model (41 MB) in model zoo for detection
- YOLO License Plate model (656 MB) in model zoo
- PaddleOCR (12 MB) for text recognition

**What's needed:**

- Opt-in consent flow and UI
- Face/plate database management
- Matching confidence thresholds
- Data retention policies

**Complexity:** Medium (models exist, need privacy-aware UX)

---

### Advanced Behavior Analysis

**Why it matters:**

- Detect complex behaviors like loitering patterns, tailgating, repeated visits
- Goes beyond single-event analysis

**Implementation ideas:**

- Temporal graph of entity movements
- Pattern matching on behavior sequences
- Long-term entity history

**Complexity:** High (requires temporal reasoning infrastructure)

---

### Home Automation Integration

**Why it matters:**

- Trigger smart home actions on security events
- Integration with Home Assistant, MQTT, etc.

**Implementation ideas:**

- MQTT publisher for events
- Home Assistant webhook integration
- Custom action rules based on event types

**Complexity:** Low-Medium (well-defined integration patterns)

---

## How to Pick "What Next" (A Pragmatic Rubric)

If you're choosing roadmap work, prioritize items that:

1. **Reduce false positives** (already done: zones, anomaly scoring, dedupe)
2. **Reduce time-to-action** (already done: alerts, notifications, search)
3. **Increase usability of history** (already done: search, timeline)
4. **Reduce operational friction** (already done: model downloads, setup, reliability)

The remaining items are truly "nice to have" enhancements. Focus on:

1. **User-requested features** - If users are asking for something specific
2. **Privacy-safe wins** - Home automation is lower risk than face recognition
3. **Demo value** - RAG/chat interface is impressive but complex

Avoid jumping into "big bets" until core stability is proven in production use.
