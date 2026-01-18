# Dashboard

The main monitoring view showing real-time security status across all cameras.

## What You're Looking At

The Dashboard is your central hub for home security monitoring. It provides a customizable layout with these default widgets:

- **Stats Row** - Key metrics including active cameras, events today, current risk level, and system status
- **Camera Grid** - Live status of all connected cameras with thumbnails
- **Activity Feed** - Real-time scrolling list of recent detection events

Additional widgets can be enabled via the **Configure** button:

- **GPU Statistics** - NVIDIA GPU utilization, memory, temperature, and inference metrics
- **Pipeline Telemetry** - AI pipeline latency, throughput, and queue metrics
- **Pipeline Queues** - Detection and analysis queue depths

## Key Components

### Stats Row

The Stats Row displays four clickable metric cards at the top of the dashboard:

| Card               | Shows                                    | Click Action          |
| ------------------ | ---------------------------------------- | --------------------- |
| **Active Cameras** | Number of online cameras                 | Opens Settings page   |
| **Events Today**   | Total events detected today              | Opens Timeline page   |
| **Current Risk**   | Latest risk score (0-100) with sparkline | Opens Alerts page     |
| **System Status**  | Service health (Online/Degraded/Offline) | Opens Operations page |

The **Risk Sparkline** displays a mini chart of the last 10 risk scores, providing a visual trend of recent activity levels.

### Risk Levels

The risk score is determined by the NVIDIA Nemotron LLM analyzing detected objects, time of day, location context, and behavioral patterns. Scores map to four severity levels:

| Score Range | Level        | Color  | Description                                        |
| ----------- | ------------ | ------ | -------------------------------------------------- |
| 0-29        | **Low**      | Green  | Normal activity, no concerns                       |
| 30-59       | **Medium**   | Yellow | Unusual but not threatening                        |
| 60-84       | **High**     | Orange | Suspicious activity requiring attention            |
| 85-100      | **Critical** | Red    | Potential security threat, immediate action needed |

**How Nemotron Calculates Risk:**

1. **Object Detection**: RT-DETRv2 identifies objects (persons, vehicles, animals) with confidence scores
2. **Batch Aggregation**: Related detections are grouped into up to 90-second time windows (closing after 30 seconds of idle or when max detections reached)
3. **Context Analysis**: Nemotron evaluates:
   - Time of day (e.g., 2 AM person detection vs noon)
   - Object types and confidence levels
   - Camera location (e.g., entry points vs backyard)
   - Detection frequency and patterns
4. **Risk Assessment**: LLM generates a score, level, summary, and reasoning

### Camera Grid

Each camera card displays:

- **Thumbnail** - Latest snapshot (refreshed on page load)
- **Camera name** - Location identifier (e.g., "Front Door")
- **Status badge** - Current connection status
- **Last seen time** - When the camera was last active

**Status Indicators:**

| Status    | Color  | Description                           |
| --------- | ------ | ------------------------------------- |
| Online    | Green  | Camera is connected and active        |
| Recording | Yellow | Camera is actively recording motion   |
| Offline   | Gray   | Camera is disconnected or powered off |
| Error     | Red    | Camera has a connection error         |
| Unknown   | Gray   | Status could not be determined        |

Click any camera card to navigate to the Timeline filtered to that camera's events.

### Activity Feed

The right panel shows a real-time scrolling list of recent security events:

- **Thumbnail** - Small preview image from the detection
- **Camera name** - Which camera captured it
- **Risk badge** - Color-coded severity level with score
- **Summary** - AI-generated description of the event
- **Timestamp** - Relative time (e.g., "5 mins ago") or absolute date

**Features:**

- **Auto-scroll**: New events automatically scroll into view (can be paused)
- **Click to expand**: Click any event to open it in the Timeline with full details
- **Event limit**: Shows the 10 most recent events by default

### GPU Statistics (Optional)

When enabled via Configure, displays real-time NVIDIA GPU metrics:

- **Utilization** - GPU compute usage percentage
- **Memory** - VRAM usage (used / total in GB)
- **Temperature** - GPU temperature with color coding (green < 70C, yellow < 80C, red >= 80C)
- **Power Usage** - Wattage consumption
- **Inference FPS** - AI model frames per second
- **History Charts** - Tabbed view of utilization, temperature, and memory trends

### Pipeline Telemetry (Optional)

When enabled via Configure, displays AI pipeline metrics:

- **Queue Depths** - Detection and analysis queue sizes
- **Processing Latency** - Average, p95, and p99 latencies for each stage
- **Throughput** - Detections and analyses per minute
- **Error Rate** - Pipeline error percentage
- **History Charts** - Detection latency, analysis latency, and throughput trends

## Customizing the Dashboard

Click the **Configure** button (gear icon) in the top-right corner to:

1. **Toggle widgets** - Show or hide any widget using the switches
2. **Reorder widgets** - Use up/down arrows to change display order
3. **Reset to defaults** - Restore the original layout

Configuration is saved to your browser's localStorage and persists across sessions.

**Default Configuration:**

| Widget             | Default State |
| ------------------ | ------------- |
| Stats Row          | Visible       |
| Camera Grid        | Visible       |
| Activity Feed      | Visible       |
| GPU Statistics     | Hidden        |
| Pipeline Telemetry | Hidden        |
| Pipeline Queues    | Hidden        |

## Real-Time Updates

The dashboard receives real-time updates via WebSocket connections:

- **Events channel** (`/ws/events`) - New security events as they're created
- **System channel** (`/ws/system`) - GPU stats, queue depths, service health every 5 seconds

A **(Disconnected)** indicator appears in the header when WebSocket connections are lost. Data will automatically refresh when connectivity is restored.

## Troubleshooting

### Risk score shows "0"

No events have been detected recently. This is normal when cameras are idle or the system just started.

### System Status shows "Unknown"

The system status WebSocket may still be connecting. This typically resolves within a few seconds of page load.

### Camera shows "Offline"

1. Verify the camera is powered on and connected to the network
2. Check FTP upload settings on the camera (should point to your server)
3. Ensure the camera's folder exists at `/export/foscam/{camera_name}/`
4. Check the backend logs for FTP connection errors

### Activity Feed is empty

No events have been detected in the current time range. Possible causes:

- Cameras are not detecting motion
- Detection confidence is below threshold (default 50%)
- AI services (RT-DETRv2 or Nemotron) are offline

### GPU Statistics shows "N/A"

- The GPU monitoring service may not have data yet (wait 5-10 seconds)
- NVIDIA drivers may not be properly configured on the host
- The AI services container may not have GPU access

### Dashboard looks different than expected

Your dashboard configuration is stored in localStorage. Click **Configure** > **Reset to Defaults** to restore the standard layout.

---

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **AI Pipeline**: [Detection, Batching, and Analysis Flow](../architecture/ai-pipeline.md)
- **Real-time Updates**: [WebSocket and Redis Pub/Sub](../architecture/real-time.md)
- **Risk Level Configuration**: See `frontend/src/utils/risk.ts` for threshold definitions

### Related Code

**Frontend:**

- Dashboard Page: `frontend/src/components/dashboard/DashboardPage.tsx`
- Dashboard Layout: `frontend/src/components/dashboard/DashboardLayout.tsx`
- Stats Row: `frontend/src/components/dashboard/StatsRow.tsx`
- Camera Grid: `frontend/src/components/dashboard/CameraGrid.tsx`
- Activity Feed: `frontend/src/components/dashboard/ActivityFeed.tsx`
- GPU Stats: `frontend/src/components/dashboard/GpuStats.tsx`
- Pipeline Telemetry: `frontend/src/components/dashboard/PipelineTelemetry.tsx`
- Configuration Modal: `frontend/src/components/dashboard/DashboardConfigModal.tsx`
- Configuration Store: `frontend/src/stores/dashboardConfig.ts`

**Hooks:**

- WebSocket Events: `frontend/src/hooks/useEventStream.ts`
- System Status: `frontend/src/hooks/useSystemStatus.ts`
- Risk Utilities: `frontend/src/utils/risk.ts`

**Backend:**

- Event Broadcasting: `backend/services/event_broadcaster.py`
- System Broadcasting: `backend/services/system_broadcaster.py`
- Nemotron Analyzer: `backend/services/nemotron_analyzer.py`
- Batch Aggregator: `backend/services/batch_aggregator.py`
