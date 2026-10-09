# Risk Analysis

> How a closed batch becomes a risk-scored Event: the `VlmAnalyzer` +
> `VlmClient` path that runs today.

**Time to read:** ~15 min
**Prerequisites:** [Batching Logic](batching-logic.md)

For the full hop-by-hop pipeline this page sits inside, see
[AI pipeline current state](../architecture/ai-pipeline-current-state.md).

---

## What the VLM Does

`VlmAnalyzer.analyze_batch()` (`backend/services/vlm_analyzer.py:380`) takes
one closed batch and asks the `ai-vlm` verification server one question. The
model answers with a constrained JSON verdict containing:

1. `verdict` — `confirmed` / `rejected` / `uncertain`
   (`backend/services/vlm_verdict.py:27`)
2. `risk_score` — 0-100
3. `summary` — human-readable one-liner
4. `reasoning` — the explanation stored with the Event
5. `description` — scene description (lands in `EventVerification`)
6. `criteria` — per-criterion `{name, passed, evidence}` checks

`risk_level` is **not** a model output: `SeverityService` derives it from
`risk_score` (`backend/services/severity.py:137`). The model never sees or
emits a level.

---

## The Serving Setup

One container answers the question — llama.cpp with a vision GGUF plus its
mmproj projector, in the default compose set:

| Item           | Value                                                                                                    |
| -------------- | -------------------------------------------------------------------------------------------------------- |
| Model          | `Qwen3VL-8B-Instruct-Q4_K_M.gguf` (`VLM_MODEL_PATH`, `.env.example:338`)                                 |
| Projector      | `mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf` (`VLM_MMPROJ_PATH`)                                               |
| Endpoint       | `AI_VLM_URL` → `http://ai-vlm:8098` in Docker (`backend/core/config.py:1057`)                            |
| Context budget | `VLM_CTX_SIZE=32768` ÷ `VLM_PARALLEL=2` per slot (`.env.example:358-359`, `backend/core/config.py:1353`) |
| Read timeout   | `AI_VLM_READ_TIMEOUT=25.0` (`.env.example:246`)                                                          |

The server must have been started with its mmproj — `/health` answers `200`
even for a text-only start. Check `podman logs ai-vlm | grep -i mmproj`
before trusting a green check.

---

## Analysis Flow

```
Batch closed (analysis:stream)
      |
      v
Load batch detections + zones + household context
      |
      v
Select 1-4 key frames (backend/services/key_frame_selector.py:73)
      |
      v
Collect specialist lookup lines: faces / plates / person_reid
(backend/services/vlm_specialists.py:884)
      |
      v
Render + fit the prompt (VlmClient._render_prompt,
backend/services/vlm_client.py:625)
      |
      v
POST /v1/chat/completions on ai-vlm (json_schema constrained)
      |
      v
apply_verdict_invariants (backend/services/vlm_analyzer.py:255)
      |
      v
Event + EventVerification + event_detections (one transaction)
      |
      v
WebSocket broadcast — LAST, best-effort (backend/services/vlm_analyzer.py:754)
```

---

## The Prompt

Built in code by `VlmClient._render_prompt`
(`backend/services/vlm_client.py:625`) — one template, one code path for
production and replay. It carries:

- **Camera / Time / Zones**: capture moment in the camera timezone, zone names
  and whether a zone crossing occurred
- **Detections**: the batch rows as JSON, each optionally naming the attached
  frame it appears on (1-based) and the detector's grounded box
- **Household context**: zone owner/allowed members/allowed vehicles
- **Specialist outputs**: three short lines — `faces`, `plates`,
  `person_reid` — computed in-process as database lookups, labelled as
  detector evidence the model must not invent
- **Attached frames**: up to 4 selected stills as base64 image parts

If the rendered text would exceed the served slot, the client keeps the
highest-confidence detections and appends an explicit omission marker
(`backend/services/vlm_client.py:880-892`). The analyzer stores the exact sent
text verbatim as `Event.llm_prompt` — what you read on the event detail page
is the question that was actually asked, truncation marker included.

---

## The Wire Call

**Endpoint:** `POST {AI_VLM_URL}/v1/chat/completions`
(`backend/services/vlm_client.py:98`)

**Request body** (`backend/services/vlm_client.py:950-963`):

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } },
        { "type": "text", "text": "<rendered prompt>" }
      ]
    }
  ],
  "temperature": 0.0,
  "max_tokens": 1024,
  "response_format": {
    "type": "json_schema",
    "json_schema": { "name": "vlm_verdict", "schema": { "...": "VlmVerdict wire schema" } }
  }
}
```

`max_tokens: 2048` is pinned at `backend/services/vlm_client.py:141`. On a fast
transport fault (connection refused, `ConnectTimeout`, 5xx) or a complete reply
that violates the schema, the client retries **once** at `temperature: 0.0` and
nothing else (`backend/services/vlm_client.py:965-972`) — the retry never
re-asks with a different budget, and a slow reply is not retried at all. A
separate `max_tokens: 1` wake ping (`backend/services/vlm_client.py:1154`)
rouses a sleeping server before the real call.

**Response:** the content is validated strictly against `VlmVerdict`
(`backend/services/vlm_verdict.py:55`) — no extra keys, no defaults, every
field required. `provenance.engine` / `provenance.model_id` carry the served
engine's own reported identity.

```json
{
  "verdict": "confirmed",
  "risk_score": 65,
  "summary": "Unknown person detected approaching front door at night",
  "reasoning": "Single person detection at 2:15 AM is unusual...",
  "description": "A hooded figure walks the front walk holding a bag.",
  "criteria": [
    { "name": "person_detected", "passed": true, "evidence": "full-body figure on walk" }
  ],
  "provenance": { "engine": "llama-server@b4xxx", "model_id": "Qwen3VL-8B-Instruct-Q4_K_M" }
}
```

---

## Risk Level Mapping

| Score Range | Level      | Description                        |
| ----------- | ---------- | ---------------------------------- |
| 0-29        | `low`      | Normal activity, no concern        |
| 30-59       | `medium`   | Unusual but not threatening        |
| 60-84       | `high`     | Suspicious, needs attention        |
| 85-100      | `critical` | Potential threat, immediate action |

The boundaries are configuration: `SEVERITY_LOW_MAX` (29),
`SEVERITY_MEDIUM_MAX` (59), `SEVERITY_HIGH_MAX` (84), validated to ascend
(`backend/services/severity.py:130`). The canonical wording lives in
[Risk Levels Reference](../reference/config/risk-levels.md).

---

## Verdict Invariants

`apply_verdict_invariants()` (`backend/services/vlm_analyzer.py:255`) is the
rule table between model output and stored row:

- **`rejected` clamps the score, it does not drop the event.** A rejected
  verdict may not present above the LOW band; the score is capped at
  `severity.low_max` and the clamp stays VISIBLE in the stored reasoning.
- **`verdict=None` (the ladder bottomed out) writes the Event anyway**, with
  `risk_score` and `risk_level` NULL and honest
  "VLM verification failed; this event needs review." text — never a
  fabricated low score.
- **`risk_level` is derived** from the (possibly clamped) score via
  `SeverityService`.

---

## Failure Handling

The client never fabricates a verdict; it raises. The analyzer catches the
degradable classes — `VlmClientError` (transport, schema, truncation,
unavailable, image) and `ConstrainedDecodingNotEnforced`
(`backend/services/vlm_analyzer.py:89`) — bumps
`record_pipeline_error("vlm_verification_failed")`
(`backend/services/vlm_analyzer.py:657`), and writes the
`verification_failed` row. Anything else propagates loud.

| Failure                        | Behavior                                                     |
| ------------------------------ | ------------------------------------------------------------ |
| Fast transport/HTTP failure    | One retry at temp 0, then `verification_failed` (NULL score) |
| Slow reply (read/write budget) | Raised once, breaker untouched — never retried               |
| Schema-invalid JSON            | Same ladder; truncated replies raise without burning retries |
| Context overflow (HTTP 400)    | Raised immediately as unmeasured — the engine is fine        |
| Circuit breaker `ai-vlm` OPEN  | Refused without I/O, `VlmUnavailableError` → degraded row    |
| Broadcast failure              | Logged; the committed Event stands                           |

---

## What Gets Written

One transaction per batch (`backend/services/vlm_analyzer.py:580`):

- **`events`** — `batch_id` (unique), `camera_id`, `started_at`/`ended_at`,
  `risk_score`/`risk_level` (nullable by design), `summary`, `reasoning`,
  `llm_prompt` (the sent text + key-frame paths, never image bytes),
  `reviewed=false` (`backend/models/event.py:36`)
- **`event_verifications`** — `verdict`, `scene_description`, `criteria`,
  `key_frame_detection_ids`, `engine`, `model_id`, `latency_ms`
  (`backend/models/event_verification.py:94`)
- **`event_detections`** — the Event↔detection junction, inserted
  `ON CONFLICT DO NOTHING` so a re-run batch cannot double
  (`backend/services/vlm_analyzer.py:617`)

Idempotency is checked before analysis and set after the write; the unique
`events.batch_id` constraint is the backstop.

---

## WebSocket Broadcast

Broadcast happens after commit, best-effort (`backend/services/vlm_analyzer.py:754`):

```json
{
  "type": "event",
  "data": {
    "id": 42,
    "event_id": 42,
    "batch_id": "b-...",
    "camera_id": "front_door",
    "risk_score": 65,
    "risk_level": "high",
    "summary": "Unknown person detected...",
    "reasoning": "...",
    "started_at": "2026-10-02T14:30:00+00:00",
    "verification": { "verdict": "confirmed", "criteria": [] }
  }
}
```

A failed broadcast never undoes the commit — clients catch up via
`GET /api/events`.

---

## Source Files

- `backend/services/vlm_analyzer.py` — batch → verdict → Event
- `backend/services/vlm_client.py` — the only dialer of ai-vlm
- `backend/services/vlm_verdict.py` — the verdict schema
- `backend/services/vlm_specialists.py` — faces/plates/person_reid lookups
- `backend/services/key_frame_selector.py` — 1-4 still selection
- `backend/services/severity.py` — score → level bands

---

## Next Steps

- [Pipeline Overview](pipeline-overview.md) - Full pipeline context
- [Batching Logic](batching-logic.md) - Batch aggregation details

---

## See Also

- [Risk Levels Reference](../reference/config/risk-levels.md) - Canonical risk level definitions
- [AI Overview](../operator/ai-overview.md) - AI deployment overview
- [Alerts](alerts.md) - How risk scores trigger alerts
- [Understanding Alerts](../ui/understanding-alerts.md) - User-friendly risk level guide

---

[Back to Developer Hub](README.md)
