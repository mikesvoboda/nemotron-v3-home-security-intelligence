# Notification Service API Design

**Date:** 2025-01-31
**Status:** Draft
**Priority:** HIGH
**Complexity:** Lightweight

## Problem Statement

The Notification Service (`backend/services/notification.py`) has 8 public methods but 0 are exposed via REST API. Operators cannot:

- Send test notifications
- Check which notification channels are configured
- View channel health status
- Trigger notifications programmatically

## Goals

1. Expose notification capabilities via REST API
2. Add channel status checking to frontend settings
3. Enable test notification sending from UI

## Non-Goals

- Notification templates (future)
- Notification history/audit log (separate feature)
- Per-user notification preferences (already exists)

## API Design

### New Endpoints

```
POST /api/notifications/send
  - Send notification via specified channel
  - Body: { channel: "email"|"webhook"|"push", recipient?: string, subject: string, body: string }
  - Returns: { success: boolean, message_id?: string, error?: string }

GET /api/notifications/channels
  - List available notification channels with status
  - Returns: { channels: [{ name: string, configured: boolean, healthy: boolean }] }

POST /api/notifications/test/{channel}
  - Send test notification to verify channel works
  - Returns: { success: boolean, latency_ms: number, error?: string }
```

### Backend Implementation

1. Create `backend/api/routes/notification_admin.py`
2. Add routes to FastAPI router
3. Wrap existing `NotificationService` methods

```python
@router.get("/channels")
async def get_channels(service: NotificationService = Depends(get_notification_service)):
    return {
        "channels": [
            {"name": "email", "configured": service.is_email_configured(), "healthy": True},
            {"name": "webhook", "configured": service.is_webhook_configured(), "healthy": True},
            {"name": "push", "configured": service.is_push_configured(), "healthy": True},
        ]
    }
```

## Frontend Implementation

### Settings Integration

Add "Channel Status" section to Notification Settings tab:

```typescript
// In NotificationSettings.tsx
<ChannelStatusCard channels={channels} onTest={handleTestChannel} />
```

### New Components

1. `ChannelStatusCard` - Display channel configuration status with test buttons
2. `TestNotificationModal` - Form to send test notification

### New Hook

```typescript
// useNotificationChannels.ts
export function useNotificationChannels() {
  return useQuery({
    queryKey: ['notification-channels'],
    queryFn: () => fetchApi('/api/notifications/channels'),
  });
}

export function useTestNotification() {
  return useMutation({
    mutationFn: (channel: string) =>
      fetchApi(`/api/notifications/test/${channel}`, { method: 'POST' }),
  });
}
```

## Testing

- Unit tests for new API routes
- Integration test for channel status endpoint
- Frontend component tests for ChannelStatusCard

## Rollout

1. Backend API endpoints (1 issue)
2. Frontend hook and API client (1 issue)
3. UI components in Settings (1 issue)

## Open Questions

None - straightforward feature.
