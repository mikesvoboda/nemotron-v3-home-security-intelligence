# Dashboard

The main monitoring view showing real-time security status across all cameras.

## What You're Looking At

The Dashboard is your central hub for home security monitoring. It provides:

- **Risk Gauge** - Current overall threat level (0-100)
- **Camera Grid** - Live status of all connected cameras
- **Activity Feed** - Recent detection events

## Key Components

### Risk Gauge

The circular gauge in the top-left shows the current risk score from 0-100:

- **0-30 (Green)**: Normal activity, no concerns
- **31-60 (Yellow)**: Elevated activity, worth monitoring
- **61-100 (Red)**: High-risk event detected, review immediately

The risk score is calculated by the Nemotron AI model analyzing detected objects, time of day, and historical patterns.

### Camera Grid

Each camera card shows:

- **Camera name** - Location identifier
- **Last activity** - Time since last detection
- **Status indicator** - Green (active), Yellow (idle), Red (offline)

Click any camera to view its recent events in the Timeline.

### Activity Feed

The right panel shows the most recent detection events:

- **Timestamp** - When the event occurred
- **Camera** - Which camera captured it
- **Detection** - What was detected (person, vehicle, animal, etc.)
- **Risk score** - AI-assigned threat level

## Settings & Configuration

Dashboard settings are available in [Settings > Dashboard](settings.md#dashboard):

- **Refresh interval** - How often to poll for updates (default: 5 seconds)
- **Camera grid layout** - Grid size (2x2, 3x3, or auto)
- **Activity feed limit** - Number of recent events to show

## Troubleshooting

### Risk Gauge shows "--"

The AI service may be starting up or disconnected. Check the health indicator in the header.

### Camera shows "Offline"

1. Verify the camera is powered on
2. Check FTP upload settings on the camera
3. Ensure the camera's folder exists at `/export/foscam/{camera_name}/`

### Activity Feed is empty

No events have been detected in the selected time range. Try expanding the time filter.

---

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **Event Processing**: [Event Pipeline Architecture](../architecture/event-pipeline.md)
- **AI Risk Scoring**: [Nemotron Risk Analysis](../architecture/risk-scoring.md)
- **Real-time Updates**: [WebSocket Implementation](../architecture/websockets.md)

### Related Code

- Frontend: `frontend/src/pages/DashboardPage.tsx`
- Components: `frontend/src/components/dashboard/`
- Backend API: `backend/api/routes/dashboard.py`
- Risk Service: `backend/services/risk_scoring_service.py`
