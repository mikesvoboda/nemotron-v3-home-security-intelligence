# AI Performance

> Monitor AI model performance, latency metrics, and pipeline health.

**Time to read:** ~15 min
**Prerequisites:** [Dashboard Basics](dashboard-basics.md)

---

## Overview

The AI Performance page provides real-time monitoring of the AI models that power your security system. Here you can track:

- Model health status (RT-DETRv2 and Nemotron)
- Processing latency and queue depths
- Detection and event statistics
- Risk score distribution
- **Model Zoo** - 18+ specialized AI models for enhanced detection

---

## Accessing the AI Performance Page

Click the **Brain icon** or **AI Performance** in the left sidebar, or navigate directly to `/ai`.

<!-- SCREENSHOT: AI Performance Page Overview
Location: /ai page (http://localhost:5173/ai)
Shows: Full AI Performance page with header, Grafana banner, Model Status Cards, Latency Panel, and Model Zoo section visible
Size: 1400x900 pixels (16:9 aspect ratio)
Alt text: AI Performance page showing comprehensive AI monitoring dashboard with model status, latency metrics, and Model Zoo sections
-->
<!-- Screenshot: AI Performance page overview with all main sections visible -->

_Caption: The AI Performance page gives you complete visibility into your AI system's health and performance._

---

## Page Sections

### Model Status Cards

At the top of the page, two cards show the health of your AI models:

| Model         | Purpose                                    |
| ------------- | ------------------------------------------ |
| **RT-DETRv2** | Object detection (person, vehicle, animal) |
| **Nemotron**  | Risk analysis and reasoning                |

Each card displays:

- Health status badge (Healthy, Degraded, Unhealthy, Unknown)
- Average and percentile latency (p95, p99)
- Brief model description

### Latency Panel

Detailed latency metrics with visual progress bars:

- **AI Service Latency** - Time for RT-DETRv2 detection and Nemotron analysis
- **Pipeline Stage Latency** - Time at each stage (watch, detect, batch, analyze)
- **Total Pipeline** - End-to-end processing time

### Pipeline Health Panel

Queue depths and error monitoring:

- Detection and Analysis queue depths
- Total detections and events processed
- Pipeline errors by type
- Dead Letter Queue (DLQ) items

---

## Insights Charts

The Insights Charts section displays two visualizations.

### Detection Class Distribution

A donut chart showing the breakdown of detected objects:

- **Person** - Human detections
- **Vehicle** - Cars, trucks, motorcycles
- **Animal** - Pets and wildlife
- **Package** - Delivery items

This helps you understand what types of activity your cameras are capturing.

### Risk Score Distribution

A bar chart showing how many events fall into each risk category:

| Risk Level   | Score Range | Color  | Description                     |
| ------------ | ----------- | ------ | ------------------------------- |
| **Low**      | 0-29        | Green  | Normal, routine activity        |
| **Medium**   | 30-59       | Yellow | Unusual but likely harmless     |
| **High**     | 60-84       | Orange | Concerning, warrants attention  |
| **Critical** | 85-100      | Red    | Immediate attention recommended |

---

## Clickable Risk Score Bars

The risk score distribution chart is interactive. Each bar and count is clickable.

### How It Works

1. **Click any bar** in the chart to navigate to the Event Timeline
2. The Timeline automatically filters to show only events at that risk level
3. You can quickly investigate all events of a specific severity

### Navigation Behavior

When you click a risk level bar or count:

| Click Target           | Navigates To                    |
| ---------------------- | ------------------------------- |
| **Low bar/count**      | `/timeline?risk_level=low`      |
| **Medium bar/count**   | `/timeline?risk_level=medium`   |
| **High bar/count**     | `/timeline?risk_level=high`     |
| **Critical bar/count** | `/timeline?risk_level=critical` |

### Visual Feedback

- **Hover tooltip** - Shows "Click to view X events" on hover
- **Scale effect** - Bar slightly enlarges on hover
- **Pointer cursor** - Indicates the bar is clickable
- **Focus ring** - Green outline when using keyboard navigation

### Accessibility

The bars are implemented as buttons for full keyboard accessibility:

- **Tab** to navigate between bars
- **Enter** or **Space** to select
- Screen readers announce the event count and click action

### Example Use Cases

**Investigating High-Risk Events:**
Click the orange "High" bar to instantly see all high-risk events. Review them to ensure nothing requires immediate action.

**Reviewing Normal Activity:**
Click the green "Low" bar to browse routine events. Useful for verifying your system is working correctly.

**Critical Event Response:**
Click the red "Critical" bar to jump directly to events requiring immediate attention.

---

## Summary Counts

Below the bar chart, you see four clickable summary cards showing the exact count for each risk level. These are also clickable and navigate to the same filtered Timeline view.

---

## Model Zoo Section

The Model Zoo contains 18+ specialized AI models that enhance your security detections beyond basic object detection. These models extract additional details like license plates, faces, clothing, and vehicle types.

<!-- SCREENSHOT: Model Zoo Section Overview
Location: Middle of AI Performance page, Model Zoo section
Shows: Model Zoo summary card with title, status counts (loaded/unloaded/disabled), VRAM usage display, latency chart with dropdown selector, and grid of model status cards
Size: 1200x500 pixels (2.4:1 aspect ratio)
Alt text: Model Zoo section showing summary statistics, latency chart with model selector dropdown, and grid of model status cards organized by Active and Disabled sections
-->
<!-- Screenshot: Model Zoo section with summary, latency chart, and model cards -->

_Caption: The Model Zoo shows all specialized AI models and their current status._

### Summary Bar

The Model Zoo summary bar at the top displays key statistics:

| Indicator    | Description                                  |
| ------------ | -------------------------------------------- |
| **Loaded**   | Models currently in GPU memory (green dot)   |
| **Unloaded** | Available models not currently loaded (gray) |
| **Disabled** | Temporarily disabled models (yellow)         |
| **VRAM**     | GPU memory usage (used/budget)               |

**VRAM (Video RAM)** is the GPU memory used by loaded models. The Model Zoo has a dedicated budget of 1650 MB separate from core AI models.

### Latency Chart

The latency chart shows inference time trends for any Model Zoo model:

1. **Select a model** using the dropdown menu at the top right
2. **View timing data** displayed as three lines:
   - **Avg (ms)** - Average inference time (emerald green)
   - **P50 (ms)** - Median inference time (blue)
   - **P95 (ms)** - 95th percentile time (amber)
3. **Time axis** shows the last 60 minutes of data

<!-- SCREENSHOT: Model Zoo Latency Chart
Location: Model Zoo section, latency chart component
Shows: Area chart with three colored lines (Avg, P50, P95) showing latency over time, dropdown selector showing selected model name, and time axis showing last hour
Size: 800x300 pixels (2.7:1 aspect ratio)
Alt text: Model Zoo latency chart showing average, median, and 95th percentile inference times over the last hour for a selected model
-->
<!-- Screenshot: Model Zoo latency chart with model selector dropdown -->

_Caption: The latency chart helps you monitor model performance over time._

**Chart Legend:**

| Line Color  | Metric     | Meaning                                 |
| ----------- | ---------- | --------------------------------------- |
| **Emerald** | Average    | Typical inference time                  |
| **Blue**    | P50/Median | Half of inferences are faster than this |
| **Amber**   | P95        | 95% of inferences are faster than this  |

> **No data?** If a model shows "No data available," it either has not been used recently or is disabled.

### Model Status Cards

Below the chart, each Model Zoo model appears as a status card:

<!-- SCREENSHOT: Model Status Card Closeup
Location: Model Zoo section, individual model card
Shows: Single model card showing model name (e.g., "YOLO11 License Plate"), status indicator with colored dot and label, VRAM amount (e.g., "300MB"), last used timestamp, and category badge
Size: 300x150 pixels (2:1 aspect ratio)
Alt text: Model status card showing model name, status indicator, memory usage, last used time, and category badge
-->
<!-- Screenshot: Individual model status card showing all elements -->

_Caption: Each model card shows status, memory usage, and recent activity._

**Card Elements:**

| Element          | Description                                        |
| ---------------- | -------------------------------------------------- |
| **Model Name**   | Human-readable name of the model                   |
| **Status Dot**   | Color-coded health indicator                       |
| **Status Label** | Current state (Loaded, Unloaded, Loading, etc.)    |
| **VRAM**         | GPU memory required when loaded                    |
| **Last Used**    | Time since model was last used ("2h ago", "Never") |
| **Category**     | Model type (Detection, Classification, etc.)       |

### Model Status Indicators

| Status       | Dot Color      | Meaning                          |
| ------------ | -------------- | -------------------------------- |
| **Loaded**   | Green          | Model is in GPU memory and ready |
| **Loading**  | Blue (pulsing) | Model is currently being loaded  |
| **Unloaded** | Gray           | Model available but not loaded   |
| **Disabled** | Yellow         | Model is turned off              |
| **Error**    | Red            | Model failed to load             |

### Active vs Disabled Models

Models are organized into two sections:

- **Active Models** - Enabled and available for use
- **Disabled Models** - Turned off (grayed out, appear at bottom)

**Why are some models disabled?**

Models may be disabled for several reasons:

- Incompatible with current software versions
- Moved to a dedicated service
- Not yet released
- Temporarily turned off for maintenance

---

## Model Zoo Categories

The Model Zoo contains models organized by function:

### Detection Models

| Model                    | VRAM    | Purpose                         |
| ------------------------ | ------- | ------------------------------- |
| YOLO11 License Plate     | 300 MB  | Find license plates on vehicles |
| YOLO11 Face              | 200 MB  | Detect faces on people          |
| YOLO World S             | 1500 MB | Open vocabulary detection       |
| Vehicle Damage Detection | 2000 MB | Find damage on vehicles         |

### Classification Models

| Model                      | VRAM    | Purpose                      |
| -------------------------- | ------- | ---------------------------- |
| Violence Detection         | 500 MB  | Identify violent activity    |
| Weather Classification     | 200 MB  | Determine weather conditions |
| Fashion CLIP               | 500 MB  | Classify clothing types      |
| Vehicle Segment Classifier | 1500 MB | Identify vehicle types       |
| Pet Classifier             | 200 MB  | Distinguish cats and dogs    |

### Other Specialized Models

| Model             | VRAM    | Category           | Purpose               |
| ----------------- | ------- | ------------------ | --------------------- |
| SegFormer Clothes | 1500 MB | Segmentation       | Clothing segmentation |
| ViTPose Small     | 1500 MB | Pose               | Human pose estimation |
| Depth Anything V2 | 150 MB  | Depth              | Distance estimation   |
| CLIP ViT-L        | 800 MB  | Embedding          | Visual embeddings     |
| PaddleOCR         | 100 MB  | OCR                | Read text from plates |
| X-CLIP Base       | 2000 MB | Action Recognition | Recognize activities  |

---

## Understanding Model Memory (VRAM)

Models load into your GPU's video memory (VRAM) when needed:

- **VRAM Budget:** 1650 MB for the Model Zoo
- **Loading Strategy:** One model loads at a time (sequential)
- **Automatic Management:** Models load/unload based on demand

**Why does this matter?**

- **Loaded models** respond instantly
- **Unloaded models** need time to load before first use
- **VRAM constraints** limit how many models can be loaded simultaneously

> **Note:** The core RT-DETRv2 (~650 MB) and Nemotron (~21,700 MB) models have separate VRAM allocations and are always loaded.

---

## Model Zoo Analytics

Below the Model Zoo status cards, you see additional analytics:

### Model Contribution Chart

A bar chart showing which models contribute most to event enrichment:

- **Higher bars** = More frequently used models
- **Sorted by contribution** = Most useful models at top
- **Hover for details** = See exact percentage

### Model Leaderboard

A sortable table ranking models by contribution:

| Column           | Description                              |
| ---------------- | ---------------------------------------- |
| **Rank**         | Position (top 3 have badges)             |
| **Model**        | Model name                               |
| **Contribution** | Percentage of events this model enriched |
| **Events**       | Number of events processed               |
| **Quality**      | Correlation with good AI assessments     |

Click column headers to sort by that metric.

---

## Troubleshooting Model Zoo Issues

### Model Showing "Error" Status

**Symptoms:** Model card shows red dot and "Error" label.

**Possible causes:**

- Model file is missing or corrupted
- Insufficient GPU memory
- Model incompatible with current GPU

**What to do:**

1. Check the System page for GPU memory status
2. Note the model name and check system logs
3. Restart the AI service if multiple models show errors

### Model Never Loads

**Symptoms:** Model stays "Unloaded" even when its function should trigger.

**Possible causes:**

- No detections that require this model (e.g., no license plates seen)
- Model is disabled in configuration
- Queue is backed up with other processing

**What to do:**

1. Check if the model is in the "Disabled Models" section
2. Wait for normal detection activity
3. Check the Pipeline Health panel for queue issues

### High Latency on a Model

**Symptoms:** Latency chart shows consistently high times (P95 above 500ms for detection models).

**Possible causes:**

- GPU under heavy load
- Model being loaded/unloaded frequently
- Large number of objects in images

**What to do:**

1. Check GPU utilization on the System page
2. Look for patterns in the latency chart
3. Normal during high-activity periods

### "No Data Available" for Model Latency

**Symptoms:** Latency chart shows "No data available for [model name]"

**This is normal when:**

- The model has not been used in the last hour
- The model is disabled
- No detections have triggered this model type

**What to do:**
Nothing - this is informational. Data appears when the model is used.

---

## Refresh and Updates

The page automatically refreshes every 5 seconds. You can also:

- Click the **Refresh** button in the header for immediate update
- See "Last updated" timestamp at the bottom

---

## Grafana Integration

For detailed historical metrics, click the **Open Grafana** link in the blue banner at the top of the page. Grafana provides:

- Historical trend analysis
- GPU utilization graphs
- Custom time range selection
- Alerting configuration

---

## Next Steps

- [Understanding Alerts](understanding-alerts.md) - Risk levels and how to respond
- [Viewing Events](viewing-events.md) - Navigate and filter the Event Timeline
- [AI Audit](ai-audit.md) - Quality metrics and improvement recommendations

---

## See Also

- [Dashboard Basics](dashboard-basics.md) - Main dashboard overview
- [AI Enrichment Data](ai-enrichment.md) - Detailed AI analysis in event details
- [Risk Levels Reference](../reference/config/risk-levels.md) - Technical details on risk scoring

---

[Back to User Hub](../user-hub.md)
