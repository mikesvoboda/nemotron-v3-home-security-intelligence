# NEM-5073: TDD Tests for WebSocket Event Expansion

**Date:** 2026-02-01
**Status:** RED PHASE COMPLETE (Tests Written, All Failing)
**Next Step:** GREEN PHASE (Implement features to make tests pass)

## Overview

This document summarizes the TDD red phase tests written for the 8 new WebSocket event types as part of the Platform Enhancement Strategy (Phase 2: WebSocket Event Expansion).

## New Event Types

### Zone Events (zones channel)

1. **zone.crossing** - Line zone crossed
2. **zone.dwell_started** - Entity entered zone
3. **zone.dwell_alert** - Dwell threshold exceeded
4. **zone.approach** - Entity approaching zone

### Entity Events (entities channel)

5. **entity.matched** - Re-ID match found
6. **entity.track_updated** - Track position updated

### AI Events (ai channel)

7. **ai.threat_detected** - Weapon/threat found
8. **ai.action_recognized** - X-CLIP action detected

## Test Files Created

### Backend Unit Tests

#### 1. Event Type Registry Tests

**File:** `backend/tests/unit/core/websocket/test_new_event_types.py`

**Test Classes:**

- `TestNewZoneEventTypes` - Tests for zone event type enum values and naming
- `TestNewEntityEventTypes` - Tests for entity event type enum values
- `TestNewAIEventTypes` - Tests for AI event type enum values
- `TestNewEventTypeMetadata` - Tests for EVENT_TYPE_METADATA entries

**Total Tests:** 23 tests

**Key Assertions:**

- Event type enum constants exist (e.g., `WebSocketEventType.ZONE_CROSSING`)
- Event type values follow naming convention (e.g., "zone.crossing")
- Event channels are correctly assigned (zones, entities, ai)
- All new channels exist in channel registry
- Metadata entries are complete with required fields
- Required payload fields are defined for each event type

**Expected Failures:**

```
AssertionError: assert False
 +  where False = hasattr(WebSocketEventType, 'ZONE_CROSSING')
```

#### 2. Payload Schema Validation Tests

**File:** `backend/tests/unit/core/websocket/test_new_event_schemas.py`

**Test Classes:**

- `TestZoneCrossingPayloadSchema` - Validation for zone.crossing payload
- `TestZoneDwellStartedPayloadSchema` - Validation for zone.dwell_started payload
- `TestZoneDwellAlertPayloadSchema` - Validation for zone.dwell_alert payload
- `TestZoneApproachPayloadSchema` - Validation for zone.approach payload
- `TestEntityMatchedPayloadSchema` - Validation for entity.matched payload
- `TestEntityTrackUpdatedPayloadSchema` - Validation for entity.track_updated payload
- `TestAIThreatDetectedPayloadSchema` - Validation for ai.threat_detected payload
- `TestAIActionRecognizedPayloadSchema` - Validation for ai.action_recognized payload
- `TestNewEventPayloadSchemaMapping` - Tests for schema registry mapping

**Total Tests:** 27 tests

**Key Assertions:**

- Pydantic schemas validate required fields
- Optional fields work correctly
- Range validation for numeric fields (confidence, similarity_score, duration, etc.)
- Missing required fields raise ValidationError
- Invalid field types raise ValidationError
- Schemas are registered in EVENT_PAYLOAD_SCHEMAS mapping
- validate_payload() function works for all new event types

**Expected Failures:**

```
NameError: name 'ZoneCrossingPayload' is not defined
```

#### 3. Event Broadcaster Tests

**File:** `backend/tests/unit/services/test_event_broadcaster_new_events.py`

**Test Classes:**

- `TestBroadcastZoneEvents` - Broadcasting zone events
- `TestBroadcastEntityEvents` - Broadcasting entity events
- `TestBroadcastAIEvents` - Broadcasting AI events
- `TestNewEventRouting` - Channel routing for new events
- `TestNewEventPayloadValidation` - Payload validation in broadcast methods

**Total Tests:** 14 tests

**Key Assertions:**

- `broadcast_zone_crossing()` publishes to correct channel
- `broadcast_zone_dwell_started()` publishes with correct event type
- `broadcast_zone_dwell_alert()` includes threshold fields
- `broadcast_zone_approach()` includes direction/speed/ETA
- `broadcast_entity_matched()` includes similarity score
- `broadcast_entity_track_updated()` includes position/bbox
- `broadcast_ai_threat_detected()` includes threat type/severity
- `broadcast_ai_action_recognized()` includes action type/confidence
- Events route to correct channels (zones, entities, ai)
- Invalid payloads raise validation errors

**Expected Failures:**

```
AttributeError: 'EventBroadcaster' object has no attribute 'broadcast_zone_crossing'
```

### Frontend Unit Tests

#### 4. Zone Events WebSocket Hook Tests

**File:** `frontend/src/hooks/__tests__/useZoneEventsWebSocket.test.ts`

**Test Suites:**

- `zone.crossing events` - Receiving and validating zone crossing events
- `zone.dwell_alert events` - Receiving and validating dwell alert events
- `multiple event subscriptions` - Handling multiple zone event types
- `cleanup` - Unsubscribing and removing handlers on unmount
- `type guards` - Type guard validation for event payloads
- `connection state` - Connection state information

**Total Tests:** 10 tests

**Key Assertions:**

- Hook subscribes to zone event types
- Event handlers receive correctly formatted data
- Type guards validate event structure before calling handlers
- Invalid data is rejected and doesn't trigger handlers
- Multiple event types can be subscribed simultaneously
- Cleanup properly unsubscribes on unmount
- Connection state (isConnected, reconnectCount) is available

**Expected Failures:**

```
Error: Failed to resolve import "../useZoneEventsWebSocket" from "src/hooks/__tests__/useZoneEventsWebSocket.test.ts". Does the file exist?
```

## Test Execution Results

All tests are currently FAILING (as expected in TDD red phase):

### Backend Tests

```bash
# Event type tests
uv run pytest backend/tests/unit/core/websocket/test_new_event_types.py
# Result: 23 failed

# Schema tests
uv run pytest backend/tests/unit/core/websocket/test_new_event_schemas.py
# Result: 27 failed

# Broadcaster tests
uv run pytest backend/tests/unit/services/test_event_broadcaster_new_events.py
# Result: 14 failed
```

### Frontend Tests

```bash
cd frontend && npm test -- --run useZoneEventsWebSocket.test.ts
# Result: Failed to resolve import (hook doesn't exist yet)
```

## Implementation Requirements

To move to GREEN PHASE, the following must be implemented:

### Backend Implementation

#### 1. Event Types (`backend/core/websocket/event_types.py`)

Add to `WebSocketEventType` enum:

```python
# Zone events
ZONE_CROSSING = "zone.crossing"
ZONE_DWELL_STARTED = "zone.dwell_started"
ZONE_DWELL_ALERT = "zone.dwell_alert"
ZONE_APPROACH = "zone.approach"

# Entity events
ENTITY_MATCHED = "entity.matched"
ENTITY_TRACK_UPDATED = "entity.track_updated"

# AI events
AI_THREAT_DETECTED = "ai.threat_detected"
AI_ACTION_RECOGNIZED = "ai.action_recognized"
```

Add to `EVENT_TYPE_METADATA` dictionary with complete metadata entries.

Update `get_all_channels()` to include: "zones", "entities", "ai"

#### 2. Event Schemas (`backend/core/websocket/event_schemas.py`)

Create Pydantic payload schemas:

- `ZoneCrossingPayload`
- `ZoneDwellStartedPayload`
- `ZoneDwellAlertPayload` (with duration/threshold validation)
- `ZoneApproachPayload` (with direction/speed/ETA validation)
- `EntityMatchedPayload` (with similarity_score 0-1 validation)
- `EntityTrackUpdatedPayload` (with position/bbox/velocity)
- `AIThreatDetectedPayload` (with threat_type/severity/confidence validation)
- `AIActionRecognizedPayload` (with action_type/confidence validation)

Register all schemas in `EVENT_PAYLOAD_SCHEMAS` mapping.

#### 3. Event Broadcaster (`backend/services/event_broadcaster.py`)

Add broadcast methods:

- `async def broadcast_zone_crossing(payload: dict) -> int`
- `async def broadcast_zone_dwell_started(payload: dict) -> int`
- `async def broadcast_zone_dwell_alert(payload: dict) -> int`
- `async def broadcast_zone_approach(payload: dict) -> int`
- `async def broadcast_entity_matched(payload: dict) -> int`
- `async def broadcast_entity_track_updated(payload: dict) -> int`
- `async def broadcast_ai_threat_detected(payload: dict) -> int`
- `async def broadcast_ai_action_recognized(payload: dict) -> int`

Each method should:

1. Validate payload against schema
2. Wrap in event envelope with correct type
3. Publish to Redis channel
4. Return subscriber count

### Frontend Implementation

#### 4. Zone Events Hook (`frontend/src/hooks/useZoneEventsWebSocket.ts`)

Create hook that:

- Accepts event handler callbacks (onZoneCrossing, onZoneDwellAlert, etc.)
- Subscribes to WebSocket for zone event types
- Validates incoming events with type guards
- Calls appropriate handlers with validated data
- Returns connection state (isConnected, reconnectCount, etc.)
- Cleans up subscriptions on unmount

#### 5. Type Definitions (`frontend/src/types/websocket-events.ts`)

Add TypeScript interfaces:

```typescript
interface ZoneCrossingPayload {
  zone_id: string;
  zone_name?: string;
  entity_id: string;
  entity_type: string;
  camera_id: string;
  timestamp: string;
  direction: string;
  bbox?: BoundingBox;
}

// ... similar interfaces for all 8 event types
```

Add event type constants to WSEventType enum.

## Coverage Goals

- Backend unit test coverage: Target 85%+ for new modules
- Frontend test coverage: Target 80%+ for new hooks
- All new event types must have:
  - Enum definition
  - Metadata entry
  - Pydantic schema
  - Broadcaster method
  - Frontend type definition
  - Type guard validation

## Design Document Reference

Implementation should follow:

- **Design Doc:** `docs/plans/2026-02-01-platform-enhancement-strategy-design.md`
- **MQTT Topic Structure:** Section on "New WebSocket Events" (lines 161-177)
- **Event Specifications:** Lines 163-176 define exact event names and purposes

## Next Steps

1. **GREEN PHASE:** Implement features to make all tests pass
2. **REFACTOR PHASE:** Optimize and clean up implementation
3. **Integration:** Connect to actual services (zone_service, reid_service, threat detection)
4. **Documentation:** Update API docs with new event types
5. **End-to-End Testing:** Add integration tests for full event flow

## Notes

- All tests follow existing patterns from current WebSocket infrastructure
- Tests use same mocking approach as existing test files
- Payload validation uses Pydantic's built-in validators
- Event routing leverages existing Redis pub/sub infrastructure
- Frontend tests use vitest + @testing-library/react patterns
- Type guards ensure runtime type safety in frontend
