# Track Service API Design

**Date:** 2025-01-31
**Status:** Draft
**Priority:** HIGH
**Complexity:** Lightweight

## Problem Statement

The Track Service (`backend/services/track_service.py`) manages object motion tracking but has 8 unexposed methods. Frontend cannot:

- View active tracks per camera
- See track history and movement paths
- Display track statistics
- Visualize motion patterns

## Goals

1. Expose track data via REST API
2. Add track visualization to entity detail view
3. Show active track counts on camera cards

## Non-Goals

- Real-time track streaming (use existing WebSocket)
- Track editing/correction
- Custom track algorithms

## API Design

### New Endpoints

```
GET /api/tracks
  - List tracks with filters
  - Query: camera_id?, status?, limit, cursor
  - Returns: { tracks: [...], next_cursor }

GET /api/tracks/{track_id}
  - Get track details with full history
  - Returns: { id, camera_id, object_type, status, detections: [...], metrics }

GET /api/tracks/{track_id}/history
  - Get detection history for track
  - Returns: { detections: [{ timestamp, bbox, confidence }] }

GET /api/cameras/{camera_id}/tracks
  - List tracks for specific camera
  - Query: status?, limit
  - Returns: { tracks: [...], active_count, lost_count }

GET /api/cameras/{camera_id}/tracks/active
  - Get only active tracks
  - Returns: { tracks: [...], count }

GET /api/cameras/{camera_id}/tracks/stats
  - Get track statistics for camera
  - Returns: { active_count, total_today, avg_duration_seconds, by_object_type: {...} }
```

### Backend Implementation

1. Create `backend/api/routes/tracks.py`
2. Wrap `TrackService` methods
3. Add aggregation queries for stats

```python
@router.get("/cameras/{camera_id}/tracks/stats")
async def get_camera_track_stats(
    camera_id: str,
    track_service: TrackService = Depends(get_track_service)
):
    return {
        "active_count": await track_service.get_active_track_count(camera_id),
        "total_today": await track_service.get_track_count_since(camera_id, today()),
        "avg_duration_seconds": await track_service.get_avg_track_duration(camera_id),
        "by_object_type": await track_service.get_track_counts_by_type(camera_id),
    }
```

## Frontend Implementation

### Entity Detail Enhancement

Add "Movement History" section to EntityDetailModal:

```typescript
<EntityDetailModal>
  {/* Existing content */}
  <TrackHistorySection entityId={entity.id} />
</EntityDetailModal>
```

### Camera Card Enhancement

Show active track count badge:

```typescript
<CameraCard>
  <ActiveTracksBadge count={activeTracksCount} />
</CameraCard>
```

### New Components

1. `TrackHistorySection` - Timeline of track positions
2. `TrackPathVisualization` - SVG overlay showing movement path
3. `ActiveTracksBadge` - Small badge showing count

### New Hooks

```typescript
// useTracks.ts
export function useCameraTracksStats(cameraId: string) {
  return useQuery({
    queryKey: ['camera-tracks-stats', cameraId],
    queryFn: () => fetchApi(`/api/cameras/${cameraId}/tracks/stats`),
  });
}

export function useTrackHistory(trackId: string) {
  return useQuery({
    queryKey: ['track-history', trackId],
    queryFn: () => fetchApi(`/api/tracks/${trackId}/history`),
    enabled: !!trackId,
  });
}
```

## Track Path Visualization

For entity detail, show movement path as SVG overlay on camera snapshot:

```typescript
function TrackPathVisualization({ detections, imageWidth, imageHeight }) {
  const path = detections.map(d => {
    const centerX = (d.bbox[0] + d.bbox[2]) / 2 * imageWidth;
    const centerY = (d.bbox[1] + d.bbox[3]) / 2 * imageHeight;
    return `${centerX},${centerY}`;
  }).join(' L ');

  return (
    <svg>
      <polyline points={`M ${path}`} stroke="blue" fill="none" />
      {/* Dots at each position */}
    </svg>
  );
}
```

## Testing

- Unit tests for API routes
- Integration test for track queries
- Frontend component tests for visualization

## Rollout

1. Backend API endpoints (1 issue)
2. Frontend hooks and API client (1 issue)
3. Track visualization components (1 issue)
4. Camera card badge integration (1 issue)

## Open Questions

1. How far back should track history go? **24 hours default, configurable**
2. Should path visualization be animated? **Nice to have, not MVP**
