# Discovery: Event Snooze Workflow Not Fully Exposed to Frontend

**Issue:** NEM-3640
**Epic:** NEM-3530 (Platform Integration Gaps & Production Readiness)
**Date:** 2026-01-26

## Summary

The snoozing workflow is **functionally complete** but the **frontend exposure is inconsistent** between the events and alerts views, requiring refactoring to use shared components.

## Backend Implementation Status

### Event Model (snooze_until field)

- **File:** `backend/models/event.py`
- **Field:** `snooze_until: Mapped[datetime | None]`
- **Property:** `is_snoozed` property checks if event is currently snoozed
- **Database:** DateTime column with timezone support, nullable with default None

### Alert Model

- Alerts don't have their own snooze_until field
- Snoozing affects the event, which cascades to all related alerts

### API Endpoints

- **PATCH /api/events/{event_id}**: Updates event metadata including `snooze_until`
- Snooze changes are logged with before/after timestamps

## Frontend Implementation Status

### Snooze Utilities (`frontend/src/utils/snooze.ts`)

- `isSnoozed(snoozeUntil)` - Checks if event is currently snoozed
- `getSnoozeRemainingMs(snoozeUntil)` - Gets remaining snooze time
- `formatSnoozeEndTime(snoozeUntil)` - Formats end time for display
- `formatSnoozeRemaining(snoozeUntil)` - Formats duration remaining
- **Durations:** 15 min, 1 hour, 4 hours, 24 hours

### Custom Hook (`frontend/src/hooks/useSnoozeEvent.ts`)

- `snooze(eventId, seconds)` - Snooze event for duration
- `unsnooze(eventId)` - Clear snooze
- Returns loading state and error handling

### API Client (`frontend/src/services/api.ts`)

- `snoozeEvent(eventId, seconds)` - Computes snooze_until timestamp
- `clearSnooze(eventId)` - Sets snooze_until to null

### UI Components

**SnoozeBadge Component** - FULLY IMPLEMENTED

- Displays snooze status badge with remaining time
- Auto-updates every minute, hides when snooze expires

**SnoozeButton Component** - FULLY IMPLEMENTED

- Dropdown button with snooze duration options
- Shows snooze status, unsnooze option, keyboard navigation

### Integration Points

**EventDetailModal** - PARTIALLY INTEGRATED

- Uses SnoozeButton and SnoozeBadge
- Has onSnooze and onUnsnooze callbacks

**AlertCard** - CUSTOM IMPLEMENTATION

- Has custom snooze menu (NOT using SnoozeButton component)
- Snooze options hardcoded: 15 min, 30 min, 1 hour, 4 hours
- Does NOT display snooze status/badge

## Key Gaps Identified

1. **AlertCard uses custom implementation** instead of reusable SnoozeButton
2. **Snooze duration mismatch:**
   - SnoozeButton: 15 min, 1 hour, 4 hours, 24 hours
   - AlertCard: 15 min, 30 min, 1 hour, 4 hours
3. **SnoozeBadge not visible** in AlertCard
4. **No indication** in alerts list that an alert's event is snoozed

## Recommendations

1. **Standardize frontend snooze options** - Use same SNOOZE_OPTIONS across components
2. **Refactor AlertCard snooze UI** - Replace custom menu with SnoozeButton
3. **Add SnoozeBadge to AlertCard** - Display snooze status in alerts list
4. **Use shared hook** - Make AlertsPage use useSnoozeEvent hook
5. **Document the pattern** - Add ADR for "Snoozing is managed at event level"

## Status

**Assessment:** Functional but inconsistent. Requires frontend refactoring.
