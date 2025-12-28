# Audit Report: Home Security Intelligence

**Date:** 2025-12-27
**Auditor:** Gemini Agent

## Executive Summary

The audit identified **2 Critical (P0)** issues that prevent the core real-time functionality from working, **2 High (P1)** issues regarding documentation accuracy and monitoring, and **2 Medium (P2)** issues related to configuration and test coverage.

The most critical finding is a **complete breakage of the real-time event pipeline** due to mismatched Redis channels and WebSocket payload schemas. The frontend dashboard will not receive any updates.

## Prioritized Issues

### P0: Redis Channel Mismatch Breaking Real-time Events

- **Impact:** Critical. The "Real-time Dashboard" feature is non-functional.
- **Evidence:**
  - `backend/services/nemotron_analyzer.py`: Publishes to channel `"events"`.
  - `backend/services/event_broadcaster.py`: Subscribes to channel `"security_events"`.
- **Remediation:** Change `NemotronAnalyzer` to publish to `"security_events"`.

### P0: WebSocket Payload Contract Mismatch

- **Impact:** Critical. Even if the channel is fixed, the frontend will reject/ignore events due to schema validation failure.
- **Evidence:**
  - **Frontend (`frontend/src/hooks/useEventStream.ts`):** Expects `{ id, camera_name, timestamp, ... }`.
  - **Backend (`backend/services/nemotron_analyzer.py`):** Sends `{ event_id, camera_id, started_at, ... }`.
- **Remediation:** Update `NemotronAnalyzer._broadcast_event` to match the frontend's `SecurityEvent` interface exactly.

### P1: AI Service Port Documentation Drift

- **Impact:** High. Users following `docs/AI_SETUP.md` will start services on 8001/8002, but the backend tries 8090/8091.
- **Evidence:**
  - `docs/AI_SETUP.md`: Claims ports 8001/8002.
  - `backend/core/config.py` & `README.md`: Defaults to 8090/8091.
- **Remediation:** Update `docs/AI_SETUP.md` to match the codebase (8090/8091) and verify `scripts/start-ai.sh` uses the correct ports.

### P1: Fake AI Health Checks

- **Impact:** High. The system reports "healthy" even if the critical AI inference engine is down.
- **Evidence:**
  - `backend/api/routes/system.py`: `check_ai_services_health` returns a hardcoded "healthy" status.
- **Remediation:** Implement real HTTP health checks to `RTDETR_URL` and `NEMOTRON_URL` in `check_ai_services_health`.

### P2: Environment Variable Confusion (CAMERA_ROOT vs FOSCAM_BASE_PATH)

- **Impact:** Medium. Potential for misconfiguration if users set `CAMERA_ROOT` expecting it to work.
- **Evidence:**
  - `docker-compose.yml`: Sets `CAMERA_ROOT`.
  - `backend/core/config.py`: Uses `FOSCAM_BASE_PATH`.
- **Remediation:** Update `config.py` to check `CAMERA_ROOT` as a fallback or aliases, or update `docker-compose.yml` to use `FOSCAM_BASE_PATH`.

### P2: Integration Test Gaps

- **Impact:** Medium. Critical bugs (like the P0s above) passed CI.
- **Evidence:** `scripts/test-runner.sh` passed, but the pipeline is broken. Existing integration tests likely mock Redis or the Broadcaster too aggressively.
- **Remediation:** Add an E2E test that verifies `Detection -> Redis -> Broadcaster -> WebSocket Message`.

## Beads Plan

I will create a master Epic for this remediation and child tasks for each issue.
