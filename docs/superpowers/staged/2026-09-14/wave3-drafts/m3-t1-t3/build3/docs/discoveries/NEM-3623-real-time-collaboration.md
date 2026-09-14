# Discovery: Limited Real-Time Collaboration Features

**Issue:** NEM-3623
**Epic:** NEM-3530 (Platform Integration Gaps & Production Readiness)
**Date:** 2026-01-26

## Summary

The system lacks multi-user annotations and shared views. However, this is **by design** given the project's stated "single-user local deployment" architecture.

## Current Real-Time Features

### WebSocket Infrastructure (Well-Implemented)

- Multiple WebSocket endpoints at `/ws/events`, `/ws/system`, `/ws/detections`, `/ws/jobs/{job_id}/logs`
- Authentication support via API key and token
- Rate limiting and connection lifecycle management
- Subscription/filtering system for selective event delivery
- Sequence tracking for message ordering and gap detection
- Circuit breaker pattern with retry logic for broadcast reliability
- Message buffer (100-message replay) for reconnection scenarios
- Server-initiated heartbeat pings to detect disconnections

### Broadcast Architecture

- Event broadcaster service with Redis pub/sub backbone
- System status broadcaster for infrastructure events
- Support for multiple event types: alerts, detections, camera status, worker status, scene changes, batch analysis progress

### User Interaction Features

- Event feedback system with 5 feedback types
- Enhanced feedback with calibration data
- Audit logging for all event actions
- User calibration tracking

## What's Missing for Multi-User Collaboration

### No Multi-User Annotations

- No annotation model in database (searched all 43 model files)
- No annotation creation/storage endpoints
- No drawing/markup frontend components for media

### No Shared Views/Sessions

- No user/session model
- No shared investigation sessions
- No collaborative timeline viewing
- No presence indicators

### No Multi-User Awareness

- No user identity/authentication system
- No role-based access control beyond API key auth
- No comment threads or discussion features

## Architecture Context

From CLAUDE.md, the project is explicitly designed for:

- **"No auth: Single-user local deployment"** (stated as key design decision)
- Fully containerized single-machine deployment
- Single home security operator per installation

## Assessment

**This is NOT a gap** - This is a design boundary. The "limited real-time collaboration" is by architectural design choice.

### Why This Gap Exists

1. Home security systems typically operate as single-user per installation
2. Collaborative features add significant complexity: user management, conflict resolution, concurrent editing, permissions
3. WebSocket infrastructure is already mature for single-client scenarios
4. Adding multi-user support would require: authentication system, session management, optimistic locking, operational complexity

## Recommendation

**Classify as design boundary, not feature gap.** If future multi-dwelling/shared installations are planned, this should be noted as a _prerequisite for future scaling_, not a current deficiency.

## Status

**Assessment:** Not applicable for current single-user architecture. Close as "Won't Fix" or "By Design".
