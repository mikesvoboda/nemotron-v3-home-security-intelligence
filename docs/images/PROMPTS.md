# Image Generation Prompts

This file contains AI image generation prompts and screenshot specifications extracted from user documentation. Use these prompts with image generation tools (DALL-E, Midjourney, Stable Diffusion) or as guidance for manual screenshot capture.

## Nano Banana Pro Prompts (Hero Images)

These prompts generate hero/banner images for documentation pages. They use the NVIDIA dark theme aesthetic.

### Settings Page

**Source:** `docs/user-guide/settings.md`

```
"Dark mode application settings interface with tabbed navigation (Cameras, Processing, AI Models tabs), form inputs with sliders and toggles, camera list table with status indicators, NVIDIA dark theme #121212 background with #76B900 green accent on selected tab, clean administrative interface, vertical 2:3 aspect ratio, no text overlays"
```

### Event Timeline Page

**Source:** `docs/ui/timeline.md`

```
"Dark mode security event timeline interface, showing chronological list of security events with risk level color coding (green low, yellow medium, orange high, red critical), thumbnail previews on left, event summaries on right, date filters at top, NVIDIA dark theme #121212 background with #76B900 green accents, clean card-based layout, vertical 2:3 aspect ratio, no text overlays"
```

### Event Investigation Page

**Source:** `docs/ui/timeline.md`

```
"Dark mode security investigation interface showing video playback controls, entity tracking timeline with person silhouettes connected across multiple camera feeds, thumbnail filmstrip at bottom, forensic analysis aesthetic, NVIDIA dark theme #121212 background with #76B900 green accents and blue (#3B82F6) highlight for selected entity, clean modern UI, vertical 2:3 aspect ratio, no text overlays"
```

---

## Screenshot Specifications

These specifications describe screenshots to capture from the running application. Each includes location, content requirements, dimensions, and alt text.

### Settings Page Screenshots

#### Settings Page Overview

**Source:** `docs/user-guide/settings.md`

| Property  | Value                                                                                                                                                                                                                                                                           |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Settings page (click Settings in sidebar)                                                                                                                                                                                                                                       |
| Shows     | Complete Settings page with: four tabs (CAMERAS selected with green background, PROCESSING, AI MODELS, NOTIFICATIONS), camera list table showing cameras with name, folder path, status badges, last seen timestamps, and Edit/Delete action buttons                           |
| Size      | 1200x700 pixels (12:7 aspect ratio)                                                                                                                                                                                                                                             |
| Alt text  | Settings page with tabbed navigation showing Cameras tab selected and camera configuration table                                                                                                                                                                                |

#### Cameras Tab Detail

**Source:** `docs/user-guide/settings.md`

| Property  | Value                                                                                                                                                                                                                                                          |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Settings page > CAMERAS tab                                                                                                                                                                                                                                    |
| Shows     | Camera configuration table with columns: Name, Folder Path, Status (with colored badges), Last Seen (timestamps), Actions (Edit pencil and Delete trash icons). Show "Add Camera" button at top right                                                         |
| Size      | 1100x400 pixels (~2.75:1 aspect ratio)                                                                                                                                                                                                                         |
| Alt text  | Camera settings table showing configured cameras with status indicators and action buttons                                                                                                                                                                     |

#### AI Models Tab

**Source:** `docs/user-guide/settings.md`

| Property  | Value                                                                                                                                                                                              |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Settings page > AI MODELS tab                                                                                                                                                                      |
| Shows     | Two model status cards side by side: RT-DETRv2 (Object Detection) and Nemotron (Risk Analysis). Each card shows: status badge (Loaded/green), memory usage, inference speed/FPS. Bottom shows total GPU memory usage bar |
| Size      | 1000x500 pixels (2:1 aspect ratio)                                                                                                                                                                 |
| Alt text  | AI Models settings showing RT-DETRv2 and Nemotron model cards with status, memory, and performance metrics                                                                                         |

---

### Event Timeline Screenshots

#### Event Timeline Full Page

**Source:** `docs/ui/timeline.md`

| Property  | Value                                                                                                                                                                                                                                      |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Location  | Timeline page (click Timeline in sidebar)                                                                                                                                                                                                  |
| Shows     | Complete Timeline page with: page header, full-text search bar, expanded filter controls, results summary showing event counts and risk level badges, event cards grid (2-3 columns), and pagination controls at bottom                   |
| Size      | 1400x900 pixels (16:9 aspect ratio)                                                                                                                                                                                                        |
| Alt text  | Event Timeline page showing search bar, filters, results summary, and grid of event cards with pagination                                                                                                                                  |

#### Event Card Detail

**Source:** `docs/ui/timeline.md`

| Property  | Value                                                                                                                                                                                                                                                          |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Any event card on Timeline page                                                                                                                                                                                                                                |
| Shows     | Single event card showing: checkbox, camera name with icon, timestamp, duration, risk badge with score, colored left border, object type badges (Person, Vehicle), AI summary text, and detection list with confidence percentages                            |
| Size      | 400x350 pixels (~8:7 aspect ratio)                                                                                                                                                                                                                             |
| Alt text  | Single event card showing all information including risk badge, object detections, AI summary, and action checkbox                                                                                                                                             |

#### Timeline Filters Expanded

**Source:** `docs/ui/timeline.md`

| Property  | Value                                                                                                                                                                                                                                                                                  |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Filter panel on Timeline page (expanded state)                                                                                                                                                                                                                                         |
| Shows     | Expanded filter section with: Camera dropdown, Risk Level dropdown, Status dropdown (Reviewed/Unreviewed), Object Type dropdown, Min Confidence dropdown, Sort By dropdown, Start Date picker, End Date picker, and "Clear All Filters" button                                        |
| Size      | 1100x250 pixels (~4:1 aspect ratio)                                                                                                                                                                                                                                                    |
| Alt text  | Expanded filter panel showing all available filter options for narrowing down event results                                                                                                                                                                                            |

---

### Alerts Page Screenshots

#### Alerts Page Full View

**Source:** `docs/user-guide/alerts-notifications.md`

| Property  | Value                                                                                                                                                                                                                                                                      |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Alerts page (click Alerts in sidebar)                                                                                                                                                                                                                                      |
| Shows     | Complete Alerts page with: page title with warning triangle icon, severity filter dropdown, refresh button, results summary showing counts of Critical and High alerts, and event cards grid with orange and red left borders                                              |
| Size      | 1200x800 pixels (3:2 aspect ratio)                                                                                                                                                                                                                                         |
| Alt text  | Alerts page showing high and critical risk events with severity filter, refresh button, and color-coded event cards                                                                                                                                                        |

#### Notification Settings Tab

**Source:** `docs/user-guide/alerts-notifications.md`

| Property  | Value                                                                                                                                                                                                                                                                                                                   |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Settings page > NOTIFICATIONS tab                                                                                                                                                                                                                                                                                       |
| Shows     | Notifications tab showing: Email configuration section (status badge, SMTP host, port, from address, TLS status, recipients, "Send Test Email" button), Webhook configuration section (status badge, URL, timeout, "Send Test Webhook" button), and Available Channels summary at bottom                               |
| Size      | 1000x600 pixels (5:3 aspect ratio)                                                                                                                                                                                                                                                                                      |
| Alt text  | Notification settings showing email and webhook configuration status with test buttons and available channels summary                                                                                                                                                                                                   |

---

### AI Enrichment Screenshots

#### AI Enrichment Panel

**Source:** `docs/ui/dashboard.md`

| Property  | Value                                                                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Event Detail Modal, below Detected Objects section                                                                                                               |
| Shows     | AI Enrichment Analysis panel with expandable accordion sections for Vehicle, Person, License Plate, etc. with confidence badges                                  |
| Size      | 800x400 pixels (2:1 aspect ratio)                                                                                                                                |
| Alt text  | AI Enrichment Analysis panel showing collapsible sections for different types of enrichment data with confidence percentages                                     |

#### Vehicle Enrichment Section

**Source:** `docs/ui/dashboard.md`

| Property  | Value                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Location  | Expanded Vehicle section in AI Enrichment panel                                                                  |
| Shows     | Vehicle accordion expanded showing Type, Color, Damage fields with confidence badge                              |
| Size      | 600x200 pixels (3:1 aspect ratio)                                                                                |
| Alt text  | Vehicle enrichment section showing sedan type, silver color, and commercial vehicle badge                        |

#### Person Enrichment Section

**Source:** `docs/ui/dashboard.md`

| Property  | Value                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Location  | Expanded Person section in AI Enrichment panel                                                                   |
| Shows     | Person accordion expanded showing Clothing, Action, Carrying fields with flag badges                             |
| Size      | 600x250 pixels (2.4:1 aspect ratio)                                                                              |
| Alt text  | Person enrichment section showing clothing description, action, and suspicious attire warning badge              |

#### License Plate Enrichment Section

**Source:** `docs/ui/dashboard.md`

| Property  | Value                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Location  | Expanded License Plate section in AI Enrichment panel                                                            |
| Shows     | License Plate accordion expanded showing OCR text in highlighted monospace font                                  |
| Size      | 600x150 pixels (4:1 aspect ratio)                                                                                |
| Alt text  | License plate enrichment showing detected plate number ABC-1234 with confidence percentage                       |

#### Pet Enrichment Section

**Source:** `docs/ui/dashboard.md`

| Property  | Value                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Location  | Expanded Pet section in AI Enrichment panel                                                                      |
| Shows     | Pet accordion expanded showing Type (Dog) and Breed fields with confidence badge                                 |
| Size      | 600x150 pixels (4:1 aspect ratio)                                                                                |
| Alt text  | Pet enrichment section showing detected dog with confidence percentage                                           |

---

### System Monitoring Screenshots

#### System Monitoring Page Overview

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                                                                                                                                                                    |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | System monitoring page (http://localhost:5173/system)                                                                                                                                                                                                    |
| Shows     | Complete System Monitoring page with header, time range selector, Grafana banner, and the grid layout showing System Health, GPU Stats, AI Models, Pipeline Metrics, Databases, Containers, Host System, and Circuit Breakers panels                    |
| Size      | 1400x900 pixels (16:9 aspect ratio)                                                                                                                                                                                                                      |
| Alt text  | System Monitoring page showing comprehensive system health view with multiple monitoring panels                                                                                                                                                          |

#### Grafana Banner

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Location  | Blue callout banner below the header                                                                             |
| Shows     | Blue banner with BarChart2 icon, "Monitoring Dashboard Available" title, and "Open Grafana" link with external link icon |
| Size      | 1200x80 pixels (15:1 aspect ratio)                                                                               |
| Alt text  | Blue Grafana integration banner with link to open advanced monitoring dashboard                                  |

#### Performance Alerts Banner

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                                                                        |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Location  | Below Grafana banner when alerts are active                                                                                                                  |
| Shows     | Orange/red warning banner with alert icon, showing metrics like "GPU Temperature: 88C (threshold: 85C)" or "Queue Depth: 45 (threshold: 10)"                 |
| Size      | 1200x80 pixels (15:1 aspect ratio)                                                                                                                           |
| Alt text  | Performance alerts banner showing active system warnings                                                                                                     |

#### System Health Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Location  | Top-left panel on System page                                                                                    |
| Shows     | System Health card with Activity icon, uptime display, camera/events/detections counts in a 2x2 grid, services health list with status badges |
| Size      | 400x350 pixels (1.1:1 aspect ratio)                                                                              |
| Alt text  | System Health panel showing uptime, statistics, and service status list                                          |

#### GPU Stats Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Location  | Second panel in top row                                                                                          |
| Shows     | GPU Stats card with GPU name (e.g., "NVIDIA RTX A5500"), utilization percentage with progress bar, memory used/total, temperature gauge, and power usage |
| Size      | 400x300 pixels (1.3:1 aspect ratio)                                                                              |
| Alt text  | GPU Statistics panel showing utilization, memory, temperature, and power metrics                                 |

#### AI Models Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Location  | Top-right spanning two columns                                                                                   |
| Shows     | AI Models panel with two cards: RT-DETRv2 (showing status badge, inference time, latency metrics) and Nemotron (showing status, tokens/sec, context window) |
| Size      | 800x250 pixels (3.2:1 aspect ratio)                                                                              |
| Alt text  | AI Models panel showing RT-DETRv2 object detection and Nemotron LLM status                                       |

#### Model Zoo Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Location  | Below AI Models, spanning two columns                                                                            |
| Shows     | Model Zoo panel with summary bar (loaded/unloaded/disabled counts, VRAM usage), followed by model status cards showing individual enrichment models with their status badges |
| Size      | 800x300 pixels (2.7:1 aspect ratio)                                                                              |
| Alt text  | Model Zoo panel showing enrichment model status with VRAM tracking                                               |

#### Pipeline Metrics Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                                                                                                                        |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Location  | Middle row, left side spanning two columns                                                                                                                                                                   |
| Shows     | Pipeline Metrics panel with queue depths (Detect/Analyze badges), latency grid (Detection/Batch/Analysis with avg/p95/p99), throughput chart with area graph, and optional queue backup warning             |
| Size      | 600x350 pixels (1.7:1 aspect ratio)                                                                                                                                                                          |
| Alt text  | Pipeline Metrics showing queue depths, latency statistics, and throughput over time                                                                                                                          |

#### Databases Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                                                                                                               |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Middle row, right side spanning two columns                                                                                                                                                         |
| Shows     | Databases panel with PostgreSQL section (status badge, connection pool bar, query latency, active queries) and Redis section (status badge, memory usage, ops/sec, hit ratio)                      |
| Size      | 600x300 pixels (2:1 aspect ratio)                                                                                                                                                                   |
| Alt text  | Databases panel showing PostgreSQL and Redis metrics side by side                                                                                                                                   |

#### Workers Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                                                                                                                                       |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Lower row, left side spanning two columns                                                                                                                                                                                   |
| Shows     | Workers panel with collapsible header showing "8/8 Running", worker status dots with labels (Det, Ana, Batch, Clean, Watch, GPU, Metr, Bcast), and optional expanded list view                                              |
| Size      | 600x250 pixels (2.4:1 aspect ratio)                                                                                                                                                                                         |
| Alt text  | Background Workers panel showing worker status dots and running count                                                                                                                                                       |

#### Containers Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                                                                    |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Lower row, right side spanning two columns                                                                                                               |
| Shows     | Containers panel with status summary (e.g., "5/5 Running") and container list showing name, status, CPU%, Memory, and restart count for each container  |
| Size      | 600x250 pixels (2.4:1 aspect ratio)                                                                                                                      |
| Alt text  | Containers panel showing Docker container status table                                                                                                   |

#### Host System Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                                                                           |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Full-width row below Workers and Containers                                                                                                                     |
| Shows     | Host System panel with three horizontal progress bars: CPU (percentage), Memory (used/total GB with percentage), Disk (used/total GB with percentage)          |
| Size      | 1200x150 pixels (8:1 aspect ratio)                                                                                                                              |
| Alt text  | Host System panel showing CPU, Memory, and Disk usage progress bars                                                                                             |

#### Circuit Breaker Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                                                   |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Bottom row, left side spanning two columns                                                                                              |
| Shows     | Circuit Breaker panel with status summary (e.g., "4/4 Closed") and breaker table showing name, state (closed/open/half_open), and failure count |
| Size      | 600x200 pixels (3:1 aspect ratio)                                                                                                       |
| Alt text  | Circuit Breakers panel showing circuit states and failure counts                                                                        |

#### Severity Config Panel

**Source:** `docs/user-guide/system-monitoring.md`

| Property  | Value                                                                                                                               |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Bottom row, right side spanning two columns                                                                                         |
| Shows     | Severity Configuration panel showing severity level thresholds and colors (Low, Medium, High, Critical) with score ranges           |
| Size      | 600x200 pixels (3:1 aspect ratio)                                                                                                   |
| Alt text  | Severity Configuration panel showing risk level thresholds                                                                          |

---

### Event Investigation Screenshots

#### Event Detail Modal Video Tab

**Source:** `docs/ui/timeline.md`

| Property  | Value                                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------------------- |
| Location  | Event Detail Modal > Video Clip tab                                                                              |
| Shows     | Video player with playback controls, duration display, file size, download button                                |
| Size      | 800x500 pixels                                                                                                   |
| Alt text  | Video clip tab showing video player with playback controls and download option                                   |

#### Detection Thumbnail Strip

**Source:** `docs/ui/timeline.md`

| Property  | Value                                                                                                                                 |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Location  | Event Detail Modal > below main image                                                                                                 |
| Shows     | Horizontal strip of detection thumbnails with timestamps, confidence badges, video icon for video detections                          |
| Size      | 800x120 pixels                                                                                                                        |
| Alt text  | Thumbnail strip showing sequence of detections with timestamps and confidence scores                                                  |

---

## Design System Colors

Reference colors used throughout the application:

| Name              | Hex       | Usage                              |
| ----------------- | --------- | ---------------------------------- |
| Background        | `#121212` | Main dark theme background         |
| NVIDIA Green      | `#76B900` | Primary accent, success states     |
| Blue Accent       | `#3B82F6` | Secondary accent, links, selection |
| Risk Low          | Green     | 0-29 risk score                    |
| Risk Medium       | Yellow    | 30-59 risk score                   |
| Risk High         | Orange    | 60-84 risk score                   |
| Risk Critical     | Red       | 85-100 risk score                  |
| Status Healthy    | Green     | Healthy/loaded states              |
| Status Degraded   | Yellow    | Warning/degraded states            |
| Status Unhealthy  | Red       | Error/unhealthy states             |

---

## Usage Guidelines

### For AI Image Generation

1. Use the exact prompts provided in the "Nano Banana Pro Prompts" section
2. Maintain consistent NVIDIA dark theme aesthetic
3. Use 2:3 vertical aspect ratio for hero images
4. Avoid text overlays in generated images

### For Screenshot Capture

1. Use the running application at the specified location
2. Capture at the exact dimensions specified
3. Include all elements listed in the "Shows" field
4. Use the alt text for accessibility documentation

### For Documentation Updates

1. Reference this file when creating new documentation
2. Add new screenshot specifications here when documenting new features
3. Keep prompts synchronized with actual UI appearance
