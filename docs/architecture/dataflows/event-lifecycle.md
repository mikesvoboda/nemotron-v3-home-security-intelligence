# Event Lifecycle

This document describes the complete lifecycle of a security event from creation through deletion, including state transitions, data transformations, and retention policies.

![Event Lifecycle Overview](../../images/architecture/dataflows/flow-event-lifecycle.png)

<!-- Image predates the soft-delete model: it shows "resolve" and "archive to table"
steps that do not exist in backend/api/routes/events.py or cleanup_service.py. -->

## Event State Machine

Events carry no status column. Their lifecycle is driven by boolean/timestamp fields on `backend/models/event.py` (`reviewed`, `flagged`, `snooze_until`, `deleted_at`) plus the retention cleanup job.

```mermaid
stateDiagram-v2
    [*] --> Created: LLM analysis complete
    Created --> Broadcasted: WebSocket notification sent
    Broadcasted --> Reviewed: PATCH /api/events/{id} sets reviewed=true
    Broadcasted --> SoftDeleted: DELETE sets deleted_at
    SoftDeleted --> Broadcasted: POST /api/events/{id}/restore
    Reviewed --> SoftDeleted: DELETE sets deleted_at
    Broadcasted --> Purged: retention_days (default 30) elapsed
    Reviewed --> Purged: retention_days (default 30) elapsed
    SoftDeleted --> Purged: cleanup DELETE
    Purged --> [*]
```

There is no resolve step: alert _instances_ are acknowledged or dismissed via `POST /api/alerts/{alert_id}/acknowledge` and `POST /api/alerts/{alert_id}/dismiss` (`backend/api/routes/alerts.py:566, 657`); events themselves are reviewed or snoozed.

## Event Creation

![Event States](../../images/architecture/dataflows/concept-event-states.png)

<!-- Image shows an acknowledge/resolve state machine; the Event model has no status
column — see the state diagram above for the field-driven lifecycle. -->

**Source:** `backend/services/nemotron_analyzer.py:6-17`

### Creation Trigger

Events are created after successful LLM analysis of a detection batch:

```python
# backend/services/nemotron_analyzer.py:6-17
# Analysis Flow:
#     1. Fetch batch detections from Redis/database
#     2. Enrich context with zones, baselines, and cross-camera activity
#     3. Run enrichment pipeline for license plates, faces, OCR (optional)
#     4. Format prompt with enriched detection details
#     5. Acquire shared AI inference semaphore (NEM-1463)
#     6. POST to llama.cpp completion endpoint (with retry on transient failures)
#     7. Release semaphore
#     8. Parse JSON response
#     9. Create Event with risk assessment    <-- Event Created
#     10. Store Event in database
#     11. Broadcast via WebSocket (if available)
```

### Event Data Model

```python
# Core event fields
Event:
    id: int                    # Primary key, auto-increment
    batch_id: str              # Links to detection batch (e.g., "batch-a1b2c3d4")
    camera_id: str             # Normalized camera ID (e.g., "front_door")
    risk_score: int            # 0-100, from LLM analysis
    risk_level: str            # Derived: "low", "medium", "high", "critical"
    summary: str               # Human-readable description
    reasoning: str             # LLM reasoning for assessment
    started_at: datetime       # First detection in batch
    ended_at: datetime | None  # Last detection in batch (optional)
    reviewed: bool             # Marked reviewed by a user (also drives hsi_events_reviewed_total)
    snooze_until: datetime     # NEM-2359 — suppress until this time
    deleted_at: datetime       # Soft delete (restorable until cleanup purges it)
    version: int               # Optimistic-locking counter (NEM-3625)
    # Event has no created_at column — started_at is the event's time reference.
```

### Risk Level Derivation

The Nemotron response supplies `risk_score`/`risk_level`; `Event.computed_risk_level`
(`backend/models/event.py:367-399`) re-derives the level from configurable thresholds
(`severity_low_max`/`severity_medium_max`/`severity_high_max`, `backend/core/config.py:2288-2303`):

| Score Range | Risk Level |
| ----------- | ---------- |
| 0-29        | low        |
| 30-59       | medium     |
| 60-84       | high       |
| 85-100      | critical   |

Safety override (NEM-5566): a fire detection forces `risk_score = 100` and
`risk_level = "critical"` regardless of LLM output
(`backend/services/nemotron_analyzer.py:2845-2860`).

## Event Broadcasting

**Source:** `backend/services/event_broadcaster.py:335-400`

### Broadcast Sequence

```mermaid
sequenceDiagram
    participant NA as NemotronAnalyzer
    participant EB as EventBroadcaster
    participant Redis as Redis Pub/Sub
    participant WS1 as WebSocket Client 1
    participant WS2 as WebSocket Client 2

    NA->>EB: broadcast_event(event_data)
    EB->>EB: Add sequence number
    EB->>EB: Check requires_ack
    EB->>EB: Buffer message
    EB->>Redis: PUBLISH to channel
    Redis-->>WS1: Message
    Redis-->>WS2: Message

    alt High-priority (risk_score >= 80)
        WS1-->>EB: ACK
        WS2-->>EB: ACK
        EB->>EB: Track ACKs
    end
```

### Message Format

```json
{
  "type": "event",
  "sequence": 42,
  "requires_ack": true,
  "data": {
    "id": 1,
    "event_id": 1,
    "batch_id": "batch_abc123",
    "camera_id": "front_door",
    "risk_score": 85,
    "risk_level": "critical",
    "summary": "Person detected at front door",
    "reasoning": "Unknown individual approaching entrance during nighttime hours",
    "started_at": "2025-12-23T12:00:00Z"
  }
}
```

### Acknowledgment Requirements

**Source:** `backend/services/event_broadcaster.py:296-323`

```python
# backend/services/event_broadcaster.py:296-323
def requires_ack(message: dict[str, Any]) -> bool:
    """Determine if a message requires client acknowledgment.

    High-priority messages that require acknowledgment:
    - Events with risk_score >= 80
    - Events with risk_level == 'critical'
    """
    if message.get("type") != "event":
        return False

    data = message.get("data")
    if not data:
        return False

    # Check risk_score >= 80
    risk_score = data.get("risk_score", 0)
    if risk_score >= 80:
        return True

    # Check risk_level == 'critical'
    risk_level = data.get("risk_level", "")
    return bool(risk_level == "critical")
```

### Message Sequencing and Buffering

**Source:** `backend/services/event_broadcaster.py:68-69, 398-401`

```python
# backend/services/event_broadcaster.py:68-69
# Buffer size for message replay on reconnection (NEM-1688)
MESSAGE_BUFFER_SIZE = 100

# backend/services/event_broadcaster.py:398-401
# Message sequencing and buffering (NEM-1688)
self._sequence_counter = 0
self._message_buffer: deque[dict[str, Any]] = deque(maxlen=self.MESSAGE_BUFFER_SIZE)
self._client_acks: dict[WebSocket, int] = {}
```

**Features:**

- Monotonically increasing sequence numbers
- Last 100 messages buffered for replay
- Per-client ACK tracking for delivery confirmation

## Event Review / Acknowledgment

### Review Flow

"Viewing" an event has no backend effect; the dashboard marks events reviewed
by PATCHing the event itself (`backend/api/routes/events.py:1869-2060`):

```mermaid
sequenceDiagram
    participant User as Frontend User
    participant FE as Frontend App
    participant API as Backend API
    participant DB as PostgreSQL

    User->>FE: Mark reviewed / add notes / snooze
    FE->>API: PATCH /api/events/{id} {reviewed: true, version: N}
    API->>DB: UPDATE event (audit log + commit)
    DB-->>API: Success (version incremented)
    API-->>FE: 200 OK (updated EventResponse)
```

### API Endpoint

```
PATCH /api/events/{event_id}

Body (all optional): reviewed, notes, snooze_until, version
  - Include `version` for optimistic locking (NEM-3625): a stale version
    returns 409 with {"detail": {"current_version": N}}.

Response: the full updated Event (risk fields plus reviewed/notes/snooze_until).
Side effects: hsi_events_reviewed_total and hsi_events_acknowledged_total are
recorded when reviewed flips to true (NEM-770 / NEM-3288); cache is invalidated
(NEM-1938). No WebSocket broadcast is sent for the update.
```

## Event Deletion (Soft Delete)

Events are soft-deleted and restorable; there is no "resolved" state.

```
DELETE /api/events/{event_id}            → sets deleted_at
POST   /api/events/{event_id}/restore    → clears deleted_at (409 if not deleted)
GET    /api/events/deleted               → list soft-deleted events
DELETE /api/events/bulk                  → per-item results (207 Multi-Status)
```

Rows stay until the cleanup job hard-deletes them once `started_at` is older
than the retention cutoff. Alert-instance workflow (acknowledge/dismiss) is
separate: `backend/api/routes/alerts.py:566, 657`.

## Event Archival

### Retention Policy

**Default retention:** 30 days

There is no archive table: old rows are deleted outright by the cleanup service.

### Cleanup Process

```mermaid
sequenceDiagram
    participant Scheduler as Cleanup Scheduler
    participant CS as CleanupService
    participant DB as PostgreSQL
    participant RS as Redis (job status)

    Scheduler->>CS: Run cleanup job
    CS->>RS: start_job (cleanup-YYYYMMDD-HHMMSS, data_cleanup)
    CS->>DB: DELETE detections WHERE detected_at < cutoff
    CS->>DB: DELETE events WHERE started_at < cutoff
    CS->>DB: DELETE gpu_stats WHERE recorded_at < cutoff
    CS->>DB: DELETE old logs
    CS->>CS: Delete thumbnail/image files from disk
    CS-->>RS: progress updates, job complete
```

### Cleanup Service

Retention comes from settings, not constants
(`backend/services/cleanup_service.py:141, 487`):

```python
settings.retention_days        # default 30 — events, detections (config.py:927-932)
settings.log_retention_days    # default 7  — logs (config.py:1948-1951)
```

Cutoff is `now(UTC) - timedelta(days=retention_days)`; events are matched on
`started_at`, detections on `detected_at` (`cleanup_service.py:266-298`). A dry
run mode (`cleanup_service.py:398`) reports what would be deleted without
deleting it.

## Event Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Event Lifecycle                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Detection Batch     LLM Analysis      Event Creation                │
│  ┌─────────────┐    ┌───────────┐    ┌──────────────┐               │
│  │ detections  │ -> │ Nemotron  │ -> │ PostgreSQL   │               │
│  │ (batch-id)  │    │ (risk)    │    │ INSERT       │               │
│  └─────────────┘    └───────────┘    └──────────────┘               │
│                                             │                        │
│                                             v                        │
│                                      ┌──────────────┐                │
│                                      │ EventBroad-  │                │
│                                      │ caster       │                │
│                                      └──────────────┘                │
│                                             │                        │
│         ┌───────────────────────────────────┼───────────────────┐   │
│         │                                   │                   │   │
│         v                                   v                   v   │
│  ┌──────────────┐                ┌──────────────┐      ┌───────────┐│
│  │ WebSocket    │                │ WebSocket    │      │ WebSocket ││
│  │ Client 1     │                │ Client 2     │      │ Client N  ││
│  └──────────────┘                └──────────────┘      └───────────┘│
│                                                                      │
│  User Interaction                                                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │
│  │ Review       │ -> │ SoftDelete   │ -> │ Purge        │           │
│  │ (reviewed=1) │    │ (deleted_at) │    │ (30 days)    │           │
│  └──────────────┘    └──────────────┘    └──────────────┘           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Event Timestamps

| Field          | Description              | Set When                                                     |
| -------------- | ------------------------ | ------------------------------------------------------------ |
| `started_at`   | First detection in batch | From batch metadata (no `created_at` column exists on Event) |
| `ended_at`     | Last detection in batch  | From batch metadata                                          |
| `snooze_until` | Suppressed until         | User snoozes the event (NEM-2359)                            |
| `deleted_at`   | Soft-deleted at          | `DELETE /api/events/{id}`                                    |
| `version`      | Optimistic-lock counter  | Increments on every update (NEM-3625)                        |

## Event Relationships

```
Event (1) ─────────┬───────── (*) Detection  (many-to-many via event_detections)
                   │
                   ├───────── (1) Camera           (events.camera_id FK)
                   │
                   ├───────── (1) EventAudit       (one quality audit per event)
                   │
                   ├───────── (1) EventFeedback    (one feedback row per event)
                   │
                   └───────── (*) Alert            (alerts triggered by AlertRules)
```

`batch_id` is a plain string column linking the event to its upstream detection
batch — there is no `batches` table or FK.

## Error Handling

### Broadcast Failures

**Source:** `backend/services/event_broadcaster.py:155-254`

```python
# backend/services/event_broadcaster.py:155-163 (abridged)
async def broadcast_with_retry[T](
    broadcast_func: Callable[[], Awaitable[T]],
    message_type: str,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,  # 3
    base_delay: float = DEFAULT_BASE_DELAY,   # 1.0s
    max_delay: float = DEFAULT_MAX_DELAY,     # 30.0s
    metrics: BroadcastRetryMetrics | None = None,
) -> T:
    """Execute a broadcast function with retry logic and exponential backoff."""
```

### Retry Configuration

| Parameter             | Value | Source                                     |
| --------------------- | ----- | ------------------------------------------ |
| `DEFAULT_MAX_RETRIES` | 3     | `backend/services/event_broadcaster.py:82` |
| `DEFAULT_BASE_DELAY`  | 1.0s  | `backend/services/event_broadcaster.py:83` |
| `DEFAULT_MAX_DELAY`   | 30.0s | `backend/services/event_broadcaster.py:84` |

### Error Recovery

| Error             | Handling            | User Impact                               |
| ----------------- | ------------------- | ----------------------------------------- |
| WebSocket closed  | Buffer message      | Client reconnects, gets buffered messages |
| Redis unavailable | Retry with backoff  | Events still created, broadcast delayed   |
| Database error    | Fail event creation | Detection batch lost                      |

## Metrics and Observability

### Event Metrics

- `hsi_events_created_total` - Total events created (`backend/core/metrics.py:294`)
- `hsi_events_by_risk_level_total` - Events by risk level (`backend/core/metrics.py:462`)
- `hsi_events_by_camera_total` - Events by camera (`backend/core/metrics.py:652`)
- `hsi_events_reviewed_total` / `hsi_events_acknowledged_total` - Review tracking
  (NEM-770 / NEM-3288, `backend/core/metrics.py:659, 667`)

### Broadcast Metrics

```python
# backend/services/event_broadcaster.py:89-110 (abridged)
@dataclass
class BroadcastRetryMetrics:
    total_attempts: int = 0
    successful_broadcasts: int = 0
    failed_broadcasts: int = 0
    retries_exhausted: int = 0
    retry_counts: dict[int, int] = field(
        default_factory=lambda: {0: 0, 1: 0, 2: 0, 3: 0}
    )  # Count by retry attempts needed
```

## Related Documents

- [image-to-event.md](image-to-event.md) - Event creation flow
- [websocket-message-flow.md](websocket-message-flow.md) - Broadcast details
- [api-request-flow.md](api-request-flow.md) - API interaction
