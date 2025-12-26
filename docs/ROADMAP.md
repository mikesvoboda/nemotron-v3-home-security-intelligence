# Home Security Intelligence — Roadmap (Post-MVP Ideas)

**Audience:** Agents/engineers continuing work after the MVP phases in `docs/plans/`.

This document captures **ideas beyond the MVP** and provides enough context to help another agent:

- understand _why_ an idea matters,
- identify _where_ it would land in the codebase,
- estimate complexity / prerequisites,
- and avoid “nice idea, unclear next step” traps.

---

## Context (What MVP already establishes)

The MVP architecture is already oriented around **event-based reasoning**:

- Camera uploads arrive via FTP into `/export/foscam/{camera_name}/`
- A file watcher detects new media
- RT-DETRv2 produces per-frame detections
- Redis batching groups detections into an “event window”
- Nemotron produces a risk score + summary + reasoning
- Results persist in SQLite and are surfaced via APIs/WebSockets to the dashboard

This makes the system naturally extensible in three directions:

1. **Better signals** (more/cleaner context into the model and into heuristics)
2. **Better delivery** (alerts, workflows, investigation UX, reliability)
3. **Better understanding** (search, patterns, entities, continuity)

---

## Guiding principles (to keep scope sane)

If you’re an agent picking up roadmap work, treat these as constraints:

- **Local-first**: default to single-machine, SQLite + Redis, minimal ops burden.
- **Privacy-aware**: cameras are sensitive; prefer opt-in for identity features (faces/plates).
- **Event-centric**: keep “event” as the unit of human attention; avoid raw-frame firehose UX.
- **Measurable wins**: prioritize changes that reduce false positives, increase recall, or improve time-to-action.
- **Operational robustness**: a home system must recover from restarts, partial outages, and storage constraints.

---

## Roadmap Themes (Recommended ordering)

### 1) Alerting & escalation (turn insights into action)

**Why it matters**

- Without notifications and dedupe, the MVP stays a dashboard you have to watch.
- “Actionability” is the difference between a demo and a home security system.

**Key ideas**

- **Configurable alert rules**
  - Risk threshold (e.g., alert on `risk_score >= 70`)
  - Object-based rules (e.g., “person” near entryway after midnight)
  - Camera selection (some cameras are higher priority)
  - Schedules (quiet hours, vacation mode)
  - Cooldowns/deduping (avoid spam when someone is lingering)
- **Notification channels**
  - Email / push (mobile) / SMS
  - Optional local integrations: Home Assistant, webhook, MQTT
- **Severity taxonomy**
  - MVP uses low/medium/high; consider adding **critical** with explicit semantics
  - Provide a stable mapping from risk_score → severity for downstream systems

**Implementation notes**

- Backend: a notification service + rule evaluation; store alert deliveries to prevent duplicates
- Frontend: “Alerts” section (already in mock navigation), notification settings
- Data model: add an `alerts` table or event annotations (delivered_at, channels, etc.)

**Risks**

- Over-alerting kills trust. Dedupe and suppression logic is not optional.

---

### 2) Spatial intelligence & zones (reduce false positives)

**Why it matters**

- Pure “person detected” is not enough; “person near door/window at 2am” is.
- Zone context reduces LLM ambiguity and makes risk more consistent.

**Key ideas**

- **Per-camera zones**
  - Define polygons/rectangles (door, driveway, sidewalk)
  - Store as normalized coordinates relative to image size
  - Tag detections as “in zone” or “near zone”
- **Lightweight heuristics**
  - Dwell time: “person present continuously for >N seconds”
  - Line crossing (entering property)
  - Approach vector (moving toward entry points)

**Implementation notes**

- Add a “zones” concept tied to camera config (DB + settings UI)
- Enrich detection/event payload with zone tags and derived metrics
- Feed zone context into Nemotron prompt (“Person in DOOR_ZONE, distance approx …”)

**Risks**

- Zone UI can be surprisingly time-consuming; start with simple rectangles first.

---

### 3) Entity continuity (ReID-lite) and “same actor” reasoning

**Why it matters**

- Real threats are about sequences (driveway → porch → backyard), not single frames.
- Continuity enables smarter summaries and fewer duplicate events.

**Key ideas**

- **Within-camera tracking**
  - Track object IDs across consecutive detections (IoU association is a simple start)
  - Use these tracks to compute behavior features (loitering, repeated approach)
- **Cross-camera continuity (optional, harder)**
  - Re-identification embeddings to correlate a person/vehicle across cameras
  - This can start as “probable same subject” rather than hard IDs

**Implementation notes**

- Start with heuristics: IoU + time gap constraints
- Later: add an embedding model and store embeddings per detection

**Risks**

- ReID quality varies; avoid promising “identity” in UX without high confidence.

---

### 4) Pattern-of-life / anomaly detection (context beyond the frame)

**Why it matters**

- The best security signal is “unusual” relative to your own home’s norms.
- Works even when detection classes are imperfect.

**Key ideas**

- **Baseline activity modeling**
  - Per camera: activity rate by hour/day-of-week
  - Per class: “vehicles after midnight are rare”
  - Seasonal drift: allow rolling windows and decays
- **Anomaly scoring**
  - Combine anomaly score with Nemotron risk (e.g., risk floor increases when anomaly is high)
  - Use anomaly score to prioritize events in the UI

**Implementation notes**

- Keep it lightweight: SQL aggregates or periodic rollups into a small table
- Expose “anomaly evidence” to LLM prompt (e.g., “This time is in bottom 2% activity”)

**Risks**

- Avoid “ML for ML’s sake”; start with transparent stats and simple thresholds.

---

### 5) Search & investigations (make history usable)

**Why it matters**

- Users often ask: “When did this happen last?” and “Show me all night-time people.”
- Investigation workflows reduce time-to-understanding after an incident.

**Key ideas**

- **Full-text search**
  - Search over event summary/reasoning/notes, camera name, object types
- **Semantic search (optional)**
  - Embed event summaries and query in natural language
- **Case / incident workflow**
  - “Create case”, attach events, annotate, export timeline
  - Generate a consolidated “incident report” (LLM summarization)

**Implementation notes**

- Begin with SQLite FTS (fastest win)
- Consider a separate index only if needed (keep infra minimal)

---

### 6) Better media handling (clips, pre/post roll, video)

**Why it matters**

- Images are good; clips are better for confirmation.
- Practical security review often requires context immediately before/after detection.

**Key ideas**

- **Event clip generation**
  - On event close: create a short clip around detected frames (if video source exists)
  - Or stitch a sequence of images into an animation
- **Scrubber UX**
  - Display detection sequence with timestamps
  - Allow exporting media for law enforcement / insurance

**Implementation notes**

- If cameras upload videos, use ffmpeg to cut around timestamps
- If only images, create short MP4/GIF from frame sequence

**Risks**

- Storage growth; must integrate with retention and disk usage monitoring.

---

### 7) Reliability & operations (home-grade robustness)

**Why it matters**

- Home systems reboot, disks fill, networks flap.
- A system that fails silently is worse than one that’s noisy.

**Key ideas**

- **Backpressure & retries**
  - Clear semantics for Redis queues (dead-letter queue, retry policy)
  - Idempotency keys for processing steps
- **Observability**
  - Pipeline latency metrics (watch → detect → batch → analyze)
  - Health surfaces in `/api/system/*` and UI
- **Storage / retention tooling**
  - Disk usage dashboard
  - User-triggered cleanup (“clear old data now”)

**Implementation notes**

- Keep metrics simple: store periodic snapshots in SQLite or expose via endpoints

---

### 8) Security hardening (even for “local”)

**Why it matters**

- Cameras and home security data are highly sensitive.
- “Local” deployments often still have LAN exposure.

**Key ideas**

- **Auth** (already planned in Phase 8): API keys / basic auth
- **Audit logging**
  - Who changed settings, who marked events reviewed, etc.
- **Rate limiting**
  - Protect endpoints like media serving and WebSockets

---

## Bigger bets (longer-term / researchy)

These are compelling but should be treated as optional “bets” after core value is proven.

### Natural language “chat with your security history” (RAG)

- Query: “Did any unknown vehicles park in the driveway this week?”
- Requires: event/detection index + retrieval + summarization

### NIM / standardized inference deployment

- Replace ad-hoc llama.cpp process management with a production inference service/container
- Helps scaling and consistency; adds deployment complexity

### Digital twin reconstruction (USD / Omniverse)

- Generate structured 3D event reconstructions for replay/forensics
- Very cool demo; likely not a practical priority early

### Face recognition / license plates (privacy-sensitive)

- High user value, but high risk (ethics, accuracy, consent, compliance)
- Strongly recommend explicit opt-in and strong local-only guarantees

---

## How to pick “what next” (a pragmatic rubric)

If you’re choosing roadmap work, prioritize items that:

1. **Reduce false positives** (zones, anomaly scoring, dedupe)
2. **Reduce time-to-action** (alerts + escalation + better event summaries)
3. **Increase usability of history** (search, timeline workflows)
4. **Reduce operational friction** (model downloads, setup, reliability)

Avoid jumping into “big bets” until the above are solid.
