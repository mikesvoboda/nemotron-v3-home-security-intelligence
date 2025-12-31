---
title: Dashboard Overview
description: Understanding the main security dashboard interface
source_refs:
  - frontend/src/components/dashboard/DashboardPage.tsx:36
  - frontend/src/components/dashboard/RiskGauge.tsx:78
  - frontend/src/components/dashboard/CameraGrid.tsx:171
  - frontend/src/components/dashboard/ActivityFeed.tsx:37
  - frontend/src/components/dashboard/GpuStats.tsx:144
---

# Dashboard Overview

The Security Dashboard is your central command center for monitoring home security. It displays real-time information from all connected cameras, AI detection results, and system health in one unified view.

<!-- Nano Banana Pro Prompt:
"Dark mode security dashboard showing real-time camera feeds with risk gauge and activity feed, vertical crop, NVIDIA aesthetic, clean minimalist interface"
-->

## Dashboard Layout

When you open the dashboard, you will see four main sections arranged from top to bottom:

```mermaid
flowchart TB
    subgraph Dashboard["Security Dashboard"]
        direction TB

        subgraph TopRow["Top Section"]
            RG[Risk Gauge]
            GPU[GPU Statistics]
        end

        subgraph Middle["Camera Section"]
            CG[Camera Grid]
        end

        subgraph Bottom["Activity Section"]
            AF[Live Activity Feed]
        end
    end

    TopRow --> Middle
    Middle --> Bottom

    style RG fill:#76B900,color:#000
    style GPU fill:#3B82F6,color:#fff
    style CG fill:#1E1E1E,color:#fff
    style AF fill:#1E1E1E,color:#fff
```

## Risk Gauge

The **Risk Gauge** appears in the top-left corner of the dashboard. It displays the current security risk level from 0 to 100.

### Understanding Risk Levels

> See [Risk Levels Reference](../reference/config/risk-levels.md) for the canonical definition and configuration options.

| Score Range | Level    | Color  | Meaning                                       |
| ----------- | -------- | ------ | --------------------------------------------- |
| 0-29        | Low      | Green  | Normal activity, no concerns                  |
| 30-59       | Medium   | Yellow | Unusual activity detected, review recommended |
| 60-84       | High     | Orange | Suspicious activity, prompt review needed     |
| 85-100      | Critical | Red    | Immediate attention required                  |

### Reading the Gauge

- The **circular indicator** fills based on the current risk score
- The **number in the center** shows the exact score (0-100)
- The **label below** displays the risk level in words (Low, Medium, High, Critical)
- When risk is high or critical, the gauge adds a subtle glow effect to draw attention

### Risk History Sparkline

Below the main gauge, you may see a small chart showing how risk has changed over recent events. This helps you understand if risk is increasing, decreasing, or staying stable.

## Camera Grid

The **Camera Grid** shows all your connected security cameras in a responsive grid layout.

### Camera Status Indicators

Each camera card displays:

- **Thumbnail image**: The most recent snapshot from the camera
- **Status badge**: Appears in the top-right corner of each camera

| Status    | Color  | Meaning                                |
| --------- | ------ | -------------------------------------- |
| Online    | Green  | Camera is connected and sending images |
| Offline   | Gray   | Camera is not sending images           |
| Recording | Yellow | Camera is actively recording an event  |
| Error     | Red    | Camera has encountered a problem       |

### Camera Information

Below each thumbnail, you will see:

- **Camera name**: The friendly name you assigned (e.g., "Front Door")
- **Last seen time**: When the camera last sent an image

### Interacting with Cameras

- **Click a camera**: Select it to view more details
- **Selected camera**: Shows a green border and subtle glow

If no cameras are configured, you will see a message prompting you to add cameras through the Settings page.

## GPU Statistics

The **GPU Statistics** panel in the top-right shows how your AI processing hardware is performing.

### Key Metrics

| Metric        | Description                  | Good Values           |
| ------------- | ---------------------------- | --------------------- |
| Utilization   | How busy the GPU is          | Varies with activity  |
| Memory        | RAM being used for AI models | Depends on model size |
| Temperature   | GPU heat level               | Below 70C (green)     |
| Power Usage   | Electricity consumption      | Below 150W (green)    |
| Inference FPS | Frames analyzed per second   | Higher is better      |

### Temperature Color Coding

- **Green**: Below 70C - normal operation
- **Yellow**: 70-80C - moderate load
- **Red**: Above 80C - high load, may throttle

### Power Color Coding

- **Green**: Below 150W - normal operation
- **Yellow**: 150-250W - moderate load
- **Red**: Above 250W - high load

### Metrics History

The GPU panel includes tabs to view historical charts:

1. **Utilization**: Shows GPU usage over time
2. **Temperature**: Shows heat levels over time
3. **Memory**: Shows RAM usage over time

Use the **Pause/Resume** button to stop or start collecting history data.

## Live Activity Feed

The **Activity Feed** at the bottom of the dashboard shows a scrolling list of recent security events as they happen.

### Event Information

Each event in the feed shows:

- **Thumbnail**: A small image from the event
- **Camera name**: Which camera detected the event
- **Risk badge**: Color-coded severity indicator
- **Summary**: AI-generated description of what was detected
- **Timestamp**: When the event occurred (relative time like "5 mins ago")

### Auto-Scroll Feature

The activity feed automatically scrolls to show new events as they arrive.

- **Pause button**: Stops auto-scroll so you can read older events
- **Resume button**: Restarts auto-scroll

### Viewing Event Details

Click any event in the feed to open the Event Detail Modal with full information, including:

- Full-size image or video
- All detected objects
- AI reasoning
- Option to mark as reviewed

## Quick Stats Row

Above the main content, you may see a row of quick statistics:

- **Active Cameras**: Number of cameras currently online
- **Events Today**: Total security events detected today
- **Current Risk**: Your current risk score
- **System Status**: Overall health of the security system

## Connection Status

At the top of the dashboard, a status indicator shows whether you are receiving real-time updates:

- **Connected**: Everything is working normally
- **Disconnected**: Real-time updates paused; data may be stale

If disconnected, the dashboard will still show the most recent data but will not update automatically until connection is restored.

## Tips for Using the Dashboard

1. **Check regularly**: Glance at the dashboard periodically to stay aware of security status
2. **Watch the risk gauge**: If it turns yellow, orange, or red, investigate the activity feed
3. **Review events promptly**: High and critical events should be reviewed quickly
4. **Monitor GPU temperature**: High temperatures may indicate the system needs attention
5. **Use the pause button**: When investigating events, pause auto-scroll to prevent losing your place
