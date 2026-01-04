# System Monitoring

> Understanding the System Monitoring page for real-time visibility into pipeline health, infrastructure status, and AI performance.

**Time to read:** ~15 min
**Prerequisites:** [Dashboard Basics](dashboard-basics.md)

---

## Overview

The System Monitoring page provides comprehensive real-time visibility into your security system's health and performance. It helps you understand how images flow through the AI pipeline, monitor infrastructure components like databases and containers, and verify that all background services are running correctly.

Access it by clicking **System** in the sidebar navigation.

<!-- SCREENSHOT: System Monitoring Page Overview
Location: System monitoring page (http://localhost:5173/system)
Shows: Complete System Monitoring page with header, time range selector, Grafana banner, and the grid layout showing System Health, GPU Stats, AI Models, Pipeline Metrics, Databases, Containers, Host System, and Circuit Breakers panels
Size: 1400x900 pixels (16:9 aspect ratio)
Alt text: System Monitoring page showing comprehensive system health view with multiple monitoring panels
-->

_Caption: The System Monitoring page gives you complete visibility into your security system's health._

---

## Page Layout

The System Monitoring page is organized as a dense grid of panels, designed for at-a-glance monitoring:

```
+------------------------------------------------------------------+
| HEADER: System Monitoring                    [Time Range: 1H v]   |
+------------------------------------------------------------------+
| [i] Monitoring Dashboard Available - Open Grafana                 |
+------------------------------------------------------------------+
| [!] Performance Alerts (if any active)                            |
+------------------------------------------------------------------+
| System Health | GPU Stats    | AI Models (RT-DETRv2, Nemotron)    |
+---------------+--------------+------------------------------------+
| Model Zoo (Enrichment Models with VRAM Tracking)                  |
+------------------------------------------------------------------+
| Pipeline Metrics              | Database Metrics                  |
| (Queues, Latencies, Throughput)| (PostgreSQL, Redis)              |
+-------------------------------+-----------------------------------+
| Background Workers            | Containers                        |
+-------------------------------+-----------------------------------+
| Host System (CPU, RAM, Disk) - Full Width                         |
+------------------------------------------------------------------+
| Circuit Breakers              | Severity Configuration            |
+------------------------------------------------------------------+
```

---

## Time Range Selector

At the top-right corner, you can change the time range for historical data displayed in charts:

| Option  | Description           |
| ------- | --------------------- |
| **1H**  | Last 1 hour (default) |
| **6H**  | Last 6 hours          |
| **24H** | Last 24 hours         |
| **7D**  | Last 7 days           |

Changing the time range updates all charts and graphs on the page to show data for that period.

---

## Grafana Integration Banner

A blue banner at the top provides a link to Grafana for advanced monitoring:

<!-- SCREENSHOT: Grafana Banner
Location: Blue callout banner below the header
Shows: Blue banner with BarChart2 icon, "Monitoring Dashboard Available" title, and "Open Grafana" link with external link icon
Size: 1200x80 pixels (15:1 aspect ratio)
Alt text: Blue Grafana integration banner with link to open advanced monitoring dashboard
-->

_Caption: Click "Open Grafana" to access detailed historical metrics and dashboards._

Grafana provides:

- Detailed historical data visualization
- Custom dashboards and queries
- No login required (anonymous access enabled)

---

## Performance Alerts Banner

When system performance degrades, a warning banner appears below the Grafana link:

<!-- SCREENSHOT: Performance Alerts Banner
Location: Below Grafana banner when alerts are active
Shows: Orange/red warning banner with alert icon, showing metrics like "GPU Temperature: 88C (threshold: 85C)" or "Queue Depth: 45 (threshold: 10)"
Size: 1200x80 pixels (15:1 aspect ratio)
Alt text: Performance alerts banner showing active system warnings
-->

_Caption: Performance alerts notify you of system health issues._

Alert types include:

- **GPU Temperature** - Above safe threshold
- **Memory Usage** - System running low on RAM
- **Queue Depth** - Processing backlog building
- **Latency** - Processing taking longer than normal

---

## System Health Panel

The System Health panel shows overall system status at a glance.

<!-- SCREENSHOT: System Health Panel
Location: Top-left panel on System page
Shows: System Health card with Activity icon, uptime display, camera/events/detections counts in a 2x2 grid, services health list with status badges
Size: 400x350 pixels (1.1:1 aspect ratio)
Alt text: System Health panel showing uptime, statistics, and service status list
-->

_Caption: The System Health panel shows uptime, key statistics, and individual service status._

### Statistics Grid

| Metric         | Description                           |
| -------------- | ------------------------------------- |
| **Uptime**     | How long the system has been running  |
| **Cameras**    | Number of configured cameras          |
| **Events**     | Total security events in the database |
| **Detections** | Total object detections processed     |

### Service Health List

Shows each service with a status badge:

| Status        | Color  | Meaning                     |
| ------------- | ------ | --------------------------- |
| **Healthy**   | Green  | Service working normally    |
| **Degraded**  | Yellow | Service experiencing issues |
| **Unhealthy** | Red    | Service not responding      |

Services monitored include:

- **Database** - PostgreSQL connection
- **Redis** - Cache and queue server
- **RT-DETR Server** - Object detection AI
- **Nemotron** - Risk analysis AI

---

## GPU Statistics Panel

Shows NVIDIA graphics card performance powering the AI models.

<!-- SCREENSHOT: GPU Stats Panel
Location: Second panel in top row
Shows: GPU Stats card with GPU name (e.g., "NVIDIA RTX A5500"), utilization percentage with progress bar, memory used/total, temperature gauge, and power usage
Size: 400x300 pixels (1.3:1 aspect ratio)
Alt text: GPU Statistics panel showing utilization, memory, temperature, and power metrics
-->

_Caption: GPU Stats shows how hard your graphics card is working._

### GPU Metrics

| Metric          | Description             | Good Range      |
| --------------- | ----------------------- | --------------- |
| **Utilization** | How busy the GPU is     | 20-80%          |
| **Memory**      | VRAM used for AI models | Below 80%       |
| **Temperature** | GPU core temperature    | Below 85C       |
| **Power**       | Current power draw      | Varies by model |

A historical chart shows utilization trends over the selected time range.

---

## AI Models Panel

Shows the status of core AI inference engines.

<!-- SCREENSHOT: AI Models Panel
Location: Top-right spanning two columns
Shows: AI Models panel with two cards: RT-DETRv2 (showing status badge, inference time, latency metrics) and Nemotron (showing status, tokens/sec, context window)
Size: 800x250 pixels (3.2:1 aspect ratio)
Alt text: AI Models panel showing RT-DETRv2 object detection and Nemotron LLM status
-->

_Caption: AI Models shows the two core AI engines powering your security analysis._

### RT-DETRv2 (Object Detection)

Identifies objects in camera images (people, vehicles, animals, etc.).

| Metric              | Description                                 |
| ------------------- | ------------------------------------------- |
| **Status**          | Loaded, Loading, Error                      |
| **Inference Time**  | How long detection takes per image          |
| **Avg/P95 Latency** | Average and 95th percentile processing time |

### Nemotron (Risk Analysis)

Analyzes detected objects to determine security risk level.

| Metric             | Description                              |
| ------------------ | ---------------------------------------- |
| **Status**         | Loaded, Loading, Error                   |
| **Tokens/sec**     | Processing speed for text generation     |
| **Context Window** | Maximum prompt size the model can handle |

---

## Model Zoo Panel

Shows enrichment models that provide additional analysis beyond basic detection.

<!-- SCREENSHOT: Model Zoo Panel
Location: Below AI Models, spanning two columns
Shows: Model Zoo panel with summary bar (loaded/unloaded/disabled counts, VRAM usage), followed by model status cards showing individual enrichment models with their status badges
Size: 800x300 pixels (2.7:1 aspect ratio)
Alt text: Model Zoo panel showing enrichment model status with VRAM tracking
-->

_Caption: Model Zoo manages optional enrichment models for advanced analysis._

### Summary Bar

Shows at-a-glance counts:

- **Loaded** - Models currently in GPU memory
- **Unloaded** - Available but not loaded
- **Disabled** - Turned off by configuration
- **VRAM** - Total GPU memory used by loaded models

### Model Categories

| Category           | Examples                                 |
| ------------------ | ---------------------------------------- |
| **Detection**      | License Plate, Face, YOLO World, Damage  |
| **Classification** | Violence, Weather, Fashion, Vehicle, Pet |
| **Other**          | Segmentation, Pose, Depth, OCR, Action   |

### Model Status Indicators

| Status       | Color  | Description                        |
| ------------ | ------ | ---------------------------------- |
| **Loaded**   | Green  | In GPU memory, ready for inference |
| **Loading**  | Blue   | Currently loading into memory      |
| **Unloaded** | Gray   | Available but not in memory        |
| **Disabled** | Yellow | Turned off in configuration        |
| **Error**    | Red    | Failed to load or crashed          |

---

## Pipeline Metrics Panel

Shows how images flow through the AI processing pipeline. This is one of the key new features in the System page redesign.

<!-- SCREENSHOT: Pipeline Metrics Panel
Location: Middle row, left side spanning two columns
Shows: Pipeline Metrics panel with queue depths (Detect/Analyze badges), latency grid (Detection/Batch/Analysis with avg/p95/p99), throughput chart with area graph, and optional queue backup warning
Size: 600x350 pixels (1.7:1 aspect ratio)
Alt text: Pipeline Metrics showing queue depths, latency statistics, and throughput over time
-->

_Caption: Pipeline Metrics shows processing queues, latencies, and throughput._

### Understanding the Pipeline Flow

Your security system processes images through a four-stage pipeline:

```
+--------+     +--------+     +--------+     +---------+
| Files  | --> | Detect | --> | Batch  | --> | Analyze |
+--------+     +--------+     +--------+     +---------+
  Camera        RT-DETR       Group          Nemotron
  Uploads       Detection     Related        Risk
                             Detections      Analysis
```

1. **Files Stage** - Camera uploads arrive from FTP
2. **Detect Stage** - RT-DETRv2 identifies objects in images
3. **Batch Stage** - Related detections are grouped together (30-90 second windows)
4. **Analyze Stage** - Nemotron LLM assesses security risk

### Queue Depths Row

Shows how many items are waiting in each processing queue:

| Queue       | Good Range | Warning Sign   |
| ----------- | ---------- | -------------- |
| **Detect**  | 0-5        | > 10 = backlog |
| **Analyze** | 0-5        | > 10 = backlog |

Color coding:

- **Gray** - Queue is empty (0)
- **Green** - Queue is healthy (1-5)
- **Yellow** - Queue is building (6-10)
- **Red** - Queue is backed up (> 10)

### Latency Grid

Shows processing time statistics for each stage:

| Stage         | What It Measures                   | Typical Range |
| ------------- | ---------------------------------- | ------------- |
| **Detection** | Time to identify objects in images | 30-50ms       |
| **Batch**     | Time to group detections together  | 30-90 seconds |
| **Analysis**  | Time for Nemotron risk assessment  | 2-5 seconds   |

Each stage displays:

- **Avg** - Average processing time
- **P95** - 95% of requests complete within this time
- **P99** - 99% of requests complete within this time

Warning highlighting appears when latency exceeds normal thresholds (e.g., > 10 seconds).

### Throughput Chart

An area chart showing processing rates over time:

- **Emerald (green) line** - Detections per minute
- **Blue line** - Analyses per minute

This helps you understand processing volume trends.

### Queue Backup Warning

If queues grow too large, a yellow warning banner appears:

> [!] Queue backup detected. Processing may be delayed.

This indicates the system is processing slower than new images are arriving.

---

## Database Panels

Shows health and performance of data storage systems.

<!-- SCREENSHOT: Databases Panel
Location: Middle row, right side spanning two columns
Shows: Databases panel with PostgreSQL section (status badge, connection pool bar, query latency, active queries) and Redis section (status badge, memory usage, ops/sec, hit ratio)
Size: 600x300 pixels (2:1 aspect ratio)
Alt text: Databases panel showing PostgreSQL and Redis metrics side by side
-->

_Caption: Database panels show the health of your data storage systems._

### PostgreSQL Metrics

| Metric               | Description                 | Good Range |
| -------------------- | --------------------------- | ---------- |
| **Status**           | Connection health           | Healthy    |
| **Connections**      | Active/max pool connections | Below 80%  |
| **Cache Hit Ratio**  | Database query efficiency   | Above 90%  |
| **Transactions/min** | Database activity level     | Varies     |

### Redis Metrics

| Metric        | Description          | Good Range  |
| ------------- | -------------------- | ----------- |
| **Status**    | Cache server health  | Healthy     |
| **Clients**   | Active connections   | Below 100   |
| **Memory**    | RAM used for caching | Below 500MB |
| **Hit Ratio** | Cache effectiveness  | Above 80%   |

---

## Background Workers Panel

Shows the status of background processing services.

<!-- SCREENSHOT: Workers Panel
Location: Lower row, left side spanning two columns
Shows: Workers panel with collapsible header showing "8/8 Running", worker status dots with labels (Det, Ana, Batch, Clean, Watch, GPU, Metr, Bcast), and optional expanded list view
Size: 600x250 pixels (2.4:1 aspect ratio)
Alt text: Background Workers panel showing worker status dots and running count
-->

_Caption: Background Workers shows which processing services are running._

### Worker Status Summary

The header shows:

- **Running count** - e.g., "8/8 Running"
- **Status dots** - Quick visual of all workers

### Worker Status Dots

| Color  | Status   | Meaning                   |
| ------ | -------- | ------------------------- |
| Green  | Running  | Worker active and healthy |
| Yellow | Degraded | Running but with issues   |
| Red    | Stopped  | Worker has stopped        |

### Expand Details

Click "Expand Details" to see a full list of workers:

| Worker ID              | Display | Purpose                   |
| ---------------------- | ------- | ------------------------- |
| `detection_worker`     | Det     | Processes detection queue |
| `analysis_worker`      | Ana     | Processes analysis queue  |
| `batch_timeout_worker` | Batch   | Closes expired batches    |
| `cleanup_service`      | Clean   | Removes old data          |
| `file_watcher`         | Watch   | Monitors camera uploads   |
| `gpu_monitor`          | GPU     | Collects GPU statistics   |
| `metrics_worker`       | Metr    | Gathers system metrics    |
| `system_broadcaster`   | Bcast   | WebSocket status updates  |

---

## Containers Panel

Shows Docker container health for all system services.

<!-- SCREENSHOT: Containers Panel
Location: Lower row, right side spanning two columns
Shows: Containers panel with status summary (e.g., "5/5 Running") and container list showing name, status, CPU%, Memory, and restart count for each container
Size: 600x250 pixels (2.4:1 aspect ratio)
Alt text: Containers panel showing Docker container status table
-->

_Caption: The Containers panel shows the health of all Docker services._

### Container Table

| Column       | Description                                |
| ------------ | ------------------------------------------ |
| **Name**     | Container service name                     |
| **Status**   | running (green), stopped (red), restarting |
| **CPU**      | CPU utilization percentage                 |
| **Memory**   | RAM usage in MB                            |
| **Restarts** | Restart count (yellow if >= 3)             |

High restart counts may indicate a service is crashing repeatedly.

---

## Host System Panel

Shows system resource usage for the server running the security system.

<!-- SCREENSHOT: Host System Panel
Location: Full-width row below Workers and Containers
Shows: Host System panel with three horizontal progress bars: CPU (percentage), Memory (used/total GB with percentage), Disk (used/total GB with percentage)
Size: 1200x150 pixels (8:1 aspect ratio)
Alt text: Host System panel showing CPU, Memory, and Disk usage progress bars
-->

_Caption: Host System shows server resource utilization._

### Resource Bars

| Resource   | Color Thresholds                      |
| ---------- | ------------------------------------- |
| **CPU**    | Green < 75%, Yellow < 90%, Red >= 90% |
| **Memory** | Green < 75%, Yellow < 90%, Red >= 90% |
| **Disk**   | Green < 75%, Yellow < 90%, Red >= 90% |

> **Warning:** If any resource consistently shows red, consider upgrading server capacity or reducing processing load.

---

## Circuit Breakers Panel

The Circuit Breakers panel shows the health of protective mechanisms that prevent cascading failures.

<!-- SCREENSHOT: Circuit Breaker Panel
Location: Bottom row, left side spanning two columns
Shows: Circuit Breaker panel with status summary (e.g., "4/4 Closed") and breaker table showing name, state (closed/open/half_open), and failure count
Size: 600x200 pixels (3:1 aspect ratio)
Alt text: Circuit Breakers panel showing circuit states and failure counts
-->

_Caption: Circuit Breakers protect your system from cascading failures._

### What Are Circuit Breakers?

Circuit breakers protect your security system from getting overwhelmed when a service has problems. When a service fails repeatedly:

1. The circuit breaker "trips" (opens)
2. New requests to that service are blocked temporarily
3. The system waits before trying again
4. This prevents one failing service from bringing down everything else

### Circuit States

| State         | Color  | Meaning                                  |
| ------------- | ------ | ---------------------------------------- |
| **Closed**    | Green  | Normal operation - requests pass through |
| **Open**      | Red    | Blocking requests due to failures        |
| **Half-Open** | Yellow | Testing if service has recovered         |

### Circuit Breaker Table

| Column       | Description                                 |
| ------------ | ------------------------------------------- |
| **Name**     | Which service this circuit breaker protects |
| **State**    | Current state (closed, open, half_open)     |
| **Failures** | Count of consecutive failures               |

### Common Circuit Breakers

| Circuit Breaker | Protects                 | Impact When Open                     |
| --------------- | ------------------------ | ------------------------------------ |
| **rtdetr**      | Object detection service | New images won't be analyzed         |
| **nemotron**    | AI risk analysis         | Events use fallback risk scores (50) |
| **redis**       | Cache and message queue  | Real-time updates may be delayed     |

### Using the Reset Button

When a circuit breaker is open (red), you can click the **Reset** button to:

1. Force the circuit breaker back to **Closed** state
2. Clear the failure count
3. Allow requests through immediately

**When to reset:**

- You've fixed the underlying problem
- The service was temporarily down and is now back

**When NOT to reset:**

- The underlying service is still having problems
- You haven't investigated the root cause

---

## Severity Configuration Panel

Shows how the system classifies detection severity levels.

<!-- SCREENSHOT: Severity Config Panel
Location: Bottom row, right side spanning two columns
Shows: Severity Configuration panel showing severity level thresholds and colors (Low, Medium, High, Critical) with score ranges
Size: 600x200 pixels (3:1 aspect ratio)
Alt text: Severity Configuration panel showing risk level thresholds
-->

_Caption: Severity Configuration shows how risk scores map to alert levels._

This panel displays the configured severity thresholds:

| Level        | Score Range | Color  |
| ------------ | ----------- | ------ |
| **Low**      | 0-29        | Green  |
| **Medium**   | 30-59       | Yellow |
| **High**     | 60-84       | Orange |
| **Critical** | 85-100      | Red    |

---

## Understanding Health Status Colors

Throughout the System page, colors indicate health status:

| Color  | Status    | Action Needed                              |
| ------ | --------- | ------------------------------------------ |
| Green  | Healthy   | No action needed                           |
| Yellow | Degraded  | Monitor closely, may resolve automatically |
| Red    | Unhealthy | Investigate immediately                    |
| Gray   | Unknown   | Check connection to service                |

---

## Common Questions

### Why is my queue depth high?

High queue depth means images are arriving faster than they can be processed. This can happen when:

- Many cameras detect motion simultaneously
- GPU is overloaded with other tasks
- AI models are loading or restarting

Usually resolves automatically. If persistent, consider reducing camera sensitivity or upgrading GPU.

### Why is a circuit breaker open?

A circuit opens when a service fails repeatedly. Check:

1. The service logs for errors
2. Network connectivity
3. Available system resources

You can manually reset the circuit once the issue is resolved.

### What does "degraded" mean?

Degraded indicates a service is working but experiencing issues:

- Slow response times
- Intermittent errors
- High resource usage

The system continues operating but may be slower than normal.

### Why is a worker stopped?

A stopped worker (red dot) means that background service isn't running. Check:

1. Container status in the Containers panel
2. System logs for error messages
3. Available system resources

Restarting the container typically resolves this.

### Why are latencies high?

High latency (shown in yellow/red in the Pipeline Metrics) indicates slow processing:

- GPU may be overloaded
- Large batch of images being processed
- System resources constrained

Check GPU utilization and Host System panels for resource issues.

---

## Troubleshooting Quick Reference

| Symptom                      | Check These Panels                          |
| ---------------------------- | ------------------------------------------- |
| Events not appearing         | Pipeline Metrics, Workers, Circuit Breakers |
| Dashboard feels slow         | Host System, Database, Redis                |
| High risk scores incorrect   | AI Models, Nemotron circuit breaker         |
| Cameras not processing       | Workers, File Watcher, Detection queue      |
| System using too much memory | GPU Stats, Host System, Model Zoo           |

---

## Next Steps

- [AI Performance](ai-performance.md) - Deep dive into AI model performance and Model Zoo
- [Dashboard Settings](dashboard-settings.md) - Configure system options
- [Understanding Alerts](understanding-alerts.md) - Learn about risk levels

---

## See Also

- [AI Pipeline Architecture](../architecture/ai-pipeline.md) - Technical pipeline details
- [System Page Pipeline Visualization](../architecture/system-page-pipeline-visualization.md) - Developer documentation
- [Admin Monitoring Guide](../admin-guide/monitoring.md) - Advanced monitoring for administrators
- [Resilience Architecture](../architecture/resilience.md) - Technical details on circuit breakers

---

[Back to User Hub](../user-hub.md)
