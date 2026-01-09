# Dashboard Customization

> Personalize your security dashboard by customizing widgets, understanding heatmaps, and interpreting analytics charts.

This guide helps you tailor the dashboard to show the information most important to you and understand the visualizations that display your security data.

**Time to read:** ~15 minutes

---

## Widget Overview

The dashboard is built from modular widgets that you can show, hide, and reorder based on your preferences. Each widget displays a specific type of security information.

### Available Widgets

| Widget                 | Description                                                                                 | Default |
| ---------------------- | ------------------------------------------------------------------------------------------- | ------- |
| **Stats Row**          | Key metrics: active cameras, events today, current risk level with sparkline, system status | Visible |
| **Camera Grid**        | Live camera thumbnails with status indicators (online/offline/recording/error)              | Visible |
| **Activity Feed**      | Real-time scrolling feed of recent security events with thumbnails and risk badges          | Visible |
| **GPU Statistics**     | GPU utilization, memory, temperature, power usage, and inference metrics                    | Hidden  |
| **Pipeline Telemetry** | AI pipeline latency, throughput, and error metrics                                          | Hidden  |
| **Pipeline Queues**    | Detection and analysis queue depths                                                         | Hidden  |

### Opening the Configuration Modal

1. Look for the **Configure** button in the top-right corner of the dashboard (next to the page title)
2. Click the button (shows a gear icon on mobile)
3. The configuration modal opens with all available widgets

### Customizing Widget Visibility

In the configuration modal:

1. **Toggle widgets on/off** - Use the switch next to each widget name
   - Green switch = widget is visible on dashboard
   - Gray switch = widget is hidden
2. Widgets that are turned on will have a highlighted border (green accent)
3. Click **Save Changes** to apply your selections

### Reordering Widgets

Change the order widgets appear on your dashboard:

1. In the configuration modal, find the widget you want to move
2. Use the **up/down arrow buttons** on the right side of each widget row
   - Up arrow moves the widget higher in the list
   - Down arrow moves the widget lower in the list
3. The first widget in the list appears at the top of your dashboard
4. Click **Save Changes** to apply the new order

### Resetting to Defaults

If you want to start fresh:

1. Open the configuration modal
2. Click **Reset to Defaults** in the bottom-left corner
3. This restores the original widget visibility and order
4. Click **Save Changes** to confirm

### Configuration Persistence

Your dashboard configuration is automatically saved to your browser's local storage. This means:

- Your preferences persist across page refreshes
- Your settings are retained even after closing the browser
- Clearing browser data will reset to defaults
- Settings are specific to each browser/device

---

## Understanding the Stats Row

The Stats Row provides at-a-glance metrics across four clickable cards:

### Active Cameras Card

- **Icon:** Camera (green)
- **Shows:** Number of cameras currently online and monitoring
- **Click action:** Opens Settings page for camera management
- **Color:** NVIDIA green accent

### Events Today Card

- **Icon:** Calendar (blue)
- **Shows:** Total count of security events detected today
- **Click action:** Opens Timeline page with today's events
- **Note:** Count updates in real-time as new events arrive

### Current Risk Card

- **Icon:** Shield (color varies by risk level)
- **Shows:** Current risk score (0-100) with risk level label
- **Click action:** Opens Alerts page
- **Features:**
  - Color-coded by risk level (green/yellow/orange/red)
  - Includes a sparkline showing recent risk history when data is available

#### Risk Sparkline

The small chart next to the risk score shows the trend of recent risk scores:

- **Green line** = Low risk history (scores 0-29)
- **Yellow line** = Medium risk history (scores 30-59)
- **Orange line** = High risk history (scores 60-84)
- **Red line** = Critical risk history (scores 85-100)

This helps you quickly see if risk has been trending up or down.

### System Status Card

- **Icon:** Activity monitor + status indicator
- **Shows:** Current system health status
- **Click action:** Opens System monitoring page
- **Status indicators:**
  - **Online** (green, pulsing) = System is healthy and all services running
  - **Degraded** (yellow) = Some services may have issues
  - **Offline** (red) = System needs immediate attention
  - **Unknown** (gray) = Status cannot be determined

---

## Heatmaps

Heatmaps provide visual representations of activity patterns over time, helping you understand when your property typically sees activity.

### Activity Heatmap

Found on the Analytics page, the Activity Heatmap shows a 24x7 grid displaying activity levels:

#### How to Read the Heatmap

- **Rows:** Days of the week (Monday through Sunday)
- **Columns:** Hours of the day (midnight to 11pm)
- **Each cell:** Represents one hour on one day

#### Color Coding

| Color        | Meaning                          |
| ------------ | -------------------------------- |
| Dark gray    | No activity or insufficient data |
| Light green  | Low activity                     |
| Medium green | Normal activity                  |
| Bright green | Above-average activity           |
| Orange/Red   | Peak activity hours              |

#### What the Colors Tell You

- **Gray cells:** Either no detections during that time period, or the system is still learning (needs more data)
- **Green gradient:** Normal activity levels - darker means less activity, brighter means more
- **Orange cells:** Peak hours - these are times when you consistently see the most activity

#### Hovering for Details

Hover over any cell to see:

- Day and time (e.g., "Mon 8a")
- Average detection count for that period
- Sample count (how many data points)
- Whether it's marked as a "PEAK" hour

#### Learning Status

The heatmap shows a "Learning" badge when:

- The system is still collecting baseline data
- Shows progress as "X / 168 slots" (168 = 24 hours x 7 days)
- Once learning completes, patterns become more reliable

#### Practical Uses

- **Identify normal patterns:** Know when to expect activity (morning routines, after-school times, etc.)
- **Spot anomalies:** Activity at unusual hours becomes more obvious
- **Optimize alerts:** Adjust sensitivity for times you expect more/less activity

---

## Analytics Charts

The Analytics page provides several charts to help you understand detection patterns and system performance.

### Class Frequency Chart

Shows the distribution of detected object types across your cameras.

#### What It Shows

- **Bar chart:** Each bar represents an object class (person, vehicle, animal, etc.)
- **Bar height:** Represents relative frequency of detections
- **Color coding:** Different colors for each object class
  - Person: Green
  - Vehicle/Car: Amber/Orange
  - Animal/Pet: Purple
  - Other objects: Gray

#### Reading the Chart

- **Longer bars** = More frequently detected objects
- **Most common class** highlighted in the header
- **Sample counts** show how many detections contributed to each bar

#### Object Class Colors

| Class       | Color                 |
| ----------- | --------------------- |
| Person      | Green (#76B900)       |
| Vehicle/Car | Amber (#F59E0B)       |
| Truck       | Orange (#D97706)      |
| Motorcycle  | Dark Orange (#B45309) |
| Bicycle     | Brown (#92400E)       |
| Animal      | Purple (#8B5CF6)      |
| Dog         | Violet (#7C3AED)      |
| Cat         | Purple (#6D28D9)      |
| Bird        | Dark Purple (#5B21B6) |

### Pipeline Latency Panel

Shows how fast the AI pipeline processes your images.

#### Pipeline Stages

| Stage            | What It Measures                            |
| ---------------- | ------------------------------------------- |
| Watch to Detect  | Time from camera upload to object detection |
| Detect to Batch  | Time from detection to batch grouping       |
| Batch to Analyze | Time from batch completion to AI analysis   |
| Total Pipeline   | End-to-end processing time                  |

#### Latency Metrics

For each stage, you'll see:

- **Avg:** Average processing time
- **P50:** Median time (50% of images processed faster)
- **P95:** 95th percentile (only 5% take longer)
- **P99:** 99th percentile (only 1% take longer)
- **Samples:** Number of measurements

#### Color Coding

- **Green bars:** Stage is performing well
- **"Bottleneck" tag:** Stage causing the most delay

#### Time Range Selection

Use the dropdown to view latency for:

- Last 1 hour
- Last 6 hours
- Last 24 hours

#### Historical Trend

The right side shows how latency has changed over time as a mini bar chart for each stage.

### Detection Distribution Chart (Insights)

On the AI Insights page, the donut chart shows detection class distribution:

- **Visual breakdown:** Proportional segments for each object type
- **Total count:** Sum of all detections
- **Legend:** Lists top 5 most common classes

### Risk Score Distribution Chart (Insights)

Shows how events are distributed across risk levels:

#### Reading the Chart

- **Four bars:** Low, Medium, High, Critical
- **Bar height:** Relative count of events at each level
- **Clicking a bar:** Navigates to Timeline filtered to that risk level

#### Risk Level Colors

| Level    | Color  | Score Range |
| -------- | ------ | ----------- |
| Low      | Green  | 0-29        |
| Medium   | Yellow | 30-59       |
| High     | Orange | 60-84       |
| Critical | Red    | 85-100      |

---

## GPU Statistics Widget

When enabled, the GPU Statistics widget shows detailed information about your AI processing hardware.

### Metrics Displayed

| Metric            | Description                  | Healthy Range                                           |
| ----------------- | ---------------------------- | ------------------------------------------------------- |
| **Utilization**   | Percentage of GPU being used | Varies with activity                                    |
| **Memory**        | Used/Total GPU memory in GB  | Below 90%                                               |
| **Temperature**   | GPU temperature in Celsius   | Below 70C (green), 70-80C (yellow), Above 80C (red)     |
| **Power Usage**   | Current power draw in Watts  | Below 150W (green), 150-250W (yellow), Above 250W (red) |
| **Inference FPS** | Frames analyzed per second   | Higher is better                                        |

### History Charts

Toggle between three history views:

- **Utilization tab:** GPU usage percentage over time (green area chart)
- **Temperature tab:** Temperature trend (amber area chart)
- **Memory tab:** Memory usage trend (blue area chart)

### Controls

- **Pause/Resume:** Stop or start data collection
- **Clear:** Reset the history chart data

---

## Pipeline Queues Widget

Shows the current backlog of images waiting to be processed.

### Queue Types

| Queue               | Purpose                                     |
| ------------------- | ------------------------------------------- |
| **Detection Queue** | Images waiting for RT-DETR object detection |
| **Analysis Queue**  | Batches waiting for Nemotron AI analysis    |

### Queue Status Colors

| Depth | Color  | Meaning                             |
| ----- | ------ | ----------------------------------- |
| 0     | Gray   | Empty queue                         |
| 1-5   | Green  | Normal operation                    |
| 6-10  | Yellow | Building up                         |
| 10+   | Red    | Backlog - processing may be delayed |

### Warning Indicators

A warning message appears when queues exceed the threshold (default: 10), indicating:

- Processing is falling behind
- Events may be delayed
- Check system health

---

## Tips for Effective Dashboard Use

### For Everyday Monitoring

1. Keep **Stats Row** and **Camera Grid** visible for quick overview
2. Enable **Activity Feed** if you want to see events in real-time
3. Hide technical widgets (GPU, Pipeline) unless troubleshooting

### For Technical Monitoring

1. Enable **GPU Statistics** to monitor AI hardware health
2. Add **Pipeline Telemetry** to track processing performance
3. Use **Pipeline Queues** to spot processing bottlenecks

### Understanding Patterns Over Time

1. Check the **Activity Heatmap** weekly to understand normal patterns
2. Review **Class Frequency Chart** to see what's most commonly detected
3. Use **Risk Distribution** to gauge overall threat levels

---

## Related Guides

- [Dashboard Overview](dashboard-overview.md) - Basic dashboard introduction
- [Using the Dashboard](using-the-dashboard.md) - Complete feature walkthrough
- [Understanding Alerts](understanding-alerts.md) - Risk levels and responses
- [Settings](settings.md) - Camera and system configuration

---

_The dashboard is designed to give you the information you need at a glance. Customize it to match how you prefer to monitor your security._
