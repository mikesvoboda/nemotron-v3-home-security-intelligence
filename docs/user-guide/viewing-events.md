# Viewing Events

> How to view, filter, and interact with security events.

**Time to read:** ~10 min
**Prerequisites:** [Dashboard Basics](dashboard-basics.md)

---

## Live Activity Feed

The Live Activity Feed shows security events as they happen in real-time.

<!-- SCREENSHOT: Live Activity Feed
Location: Bottom section of main dashboard
Shows: The Live Activity feed panel with "Live Activity" title, Pause button, and 3-4 event cards showing: thumbnail, camera name, risk badge (varied colors), AI summary text, and relative timestamp
Size: 600x500 pixels (1.2:1 aspect ratio)
Alt text: Live Activity feed showing recent security events with thumbnails, risk level badges, AI-generated summaries, and timestamps
-->
<!-- Screenshot: Live Activity feed panel with event cards showing thumbnails, risk badges, summaries, and timestamps -->

_Caption: The Live Activity feed shows security events as they happen._

### Understanding the Feed

Each event in the feed shows:

1. **Thumbnail** - Small image from when event occurred
2. **Camera Name** - Which camera detected activity
3. **Risk Badge** - Colored label showing risk level
4. **Summary** - Brief AI-generated description
5. **Timestamp** - When it occurred ("Just now", "5 mins ago", etc.)

### Using the Feed

- Click any event to see full details in a popup
- Events appear with newest at the bottom (the feed auto-scrolls to keep you at the latest)
- Feed shows up to 10 recent events

### Auto-Scroll Feature

The feed automatically scrolls when new events arrive:

- Click **Pause** to stop auto-scrolling (useful when reading)
- Click **Resume** to turn auto-scrolling back on

When paused, you can manually scroll through events.

---

## Event Timeline

The Event Timeline page shows a complete history of all security events with powerful filtering.

<!-- SCREENSHOT: Event Timeline Page
Location: Timeline page (click Timeline in sidebar)
Shows: Full Timeline page with: page title, "Show Filters" button (expanded showing filter dropdowns), results summary with risk badges, event cards grid (3 columns), and pagination at bottom
Size: 1200x800 pixels (3:2 aspect ratio)
Alt text: Event Timeline page showing filter controls, search bar, results summary with event counts by risk level, and grid of event cards
-->
<!-- Screenshot: Event Timeline page with filter controls, results summary, event cards grid, and pagination -->

_Caption: The Event Timeline shows all your security events with powerful filtering options._

### Accessing the Timeline

Click **Timeline** in the left sidebar.

### Filtering Events

Click **Show Filters** to reveal filtering options:

<!-- SCREENSHOT: Timeline Filter Controls
Location: Filter panel on Timeline page (expanded)
Shows: Expanded filter panel with dropdowns for Camera, Risk Level, Status, Object Type, date pickers for Start/End dates, and "Clear All Filters" button
Size: 1000x200 pixels (5:1 aspect ratio)
Alt text: Timeline filter controls showing dropdowns for camera, risk level, status, object type, and date range pickers
-->
<!-- Screenshot: Timeline filter panel with dropdowns for camera, risk level, status, object type, and date pickers -->

_Caption: Use filters to narrow down events by camera, risk level, status, object type, or date range._

| Filter          | What It Does                                  |
| --------------- | --------------------------------------------- |
| **Camera**      | Show events from one specific camera          |
| **Risk Level**  | Show only Low, Medium, High, or Critical      |
| **Status**      | Show only Reviewed or Unreviewed              |
| **Object Type** | Filter by detection (Person, Vehicle, Animal) |
| **Start Date**  | Show events from this date forward            |
| **End Date**    | Show events up to this date                   |

You can combine multiple filters. For example: "High risk events from Front Porch camera this week."

### Searching Events

Use the search box to find events by keywords in the AI summary. For example, search for "delivery" to find all package deliveries.

### Results Summary

Above the event list you see:

- Total count of matching events
- Colored badges showing events at each risk level
- Note when filters are active

### Working with Events

**Selecting Multiple Events:**

1. Click the checkbox on any event to select it
2. Use "Select all" to select all visible events
3. Selected events can be marked as reviewed in bulk

**Exporting Events:**
Click **Quick Export** (CSV) to download filtered events as a spreadsheet. Use **Advanced Export** for more export options.

### Pagination

Events are shown 20 at a time. Use **Previous** and **Next** buttons at the bottom to navigate pages.

---

## Event Details

When you click any event (in the feed, timeline, or alerts), a detailed popup appears.

<!-- SCREENSHOT: Event Detail Modal
Location: Modal popup that appears when clicking any event
Shows: Full event detail modal with: header (camera name, timestamp, duration, risk badge, close X), large detection image with bounding boxes, thumbnail strip, AI Summary section, AI Reasoning highlighted box, Detected Objects list, Notes section with Save button, and navigation buttons
Size: 900x800 pixels (9:8 aspect ratio)
Alt text: Event detail modal showing detection image with object highlighting, AI analysis summary, reasoning explanation, detected objects list, and notes section
-->
<!-- Screenshot: Event detail modal with detection image, AI analysis, detected objects, and notes section -->

_Caption: Click any event to see full details including the AI analysis and detection image._

### Header Section

- **Camera Name** - Large title showing which camera
- **Timestamp** - Exact date and time
- **Duration** - How long the event lasted
- **Risk Badge** - Large colored badge with score
- **Close Button** (X) - Click to close popup

### Detection Image

Full-size image from the event. If the AI detected objects, they are highlighted with colored boxes and labels (like "Person 95%").

<!-- SCREENSHOT: Detection Image with Bounding Boxes
Location: Image section of Event Detail Modal
Shows: A detection image with AI-drawn bounding boxes around detected objects (person, vehicle, etc.) with labels showing object type and confidence percentage
Size: 700x500 pixels (7:5 aspect ratio)
Alt text: Security camera image with AI-highlighted detection boxes showing identified objects with confidence scores
-->
<!-- Screenshot: Detection image with AI-drawn bounding boxes around detected objects with confidence scores -->

_Caption: The AI highlights detected objects with boxes and confidence scores._

### Detection Sequence

If multiple images were captured, you see a strip of thumbnails. Click any thumbnail to view that moment.

### AI Summary

A paragraph explaining what the AI observed, written in plain language.

### AI Reasoning

A highlighted box explaining WHY the AI assigned this risk score. This helps you understand the AI's thinking.

### Detected Objects

A list of everything the AI identified:

- Object type (Person, Vehicle, Animal, etc.)
- Confidence percentage (how sure the AI is)

### AI Enrichment Analysis

Below the Detected Objects list, you may see an **AI Enrichment Analysis** panel with additional context extracted by specialized AI models. This includes vehicle types, person clothing, license plates, pet identification, weather conditions, and image quality.

For detailed information on enrichment data, see [AI Enrichment Data in Event Details](ai-enrichment.md).

### Notes Section

A text box where you can add your own notes. Click **Save Notes** to store them.

### Event Details

Technical information:

- Event ID number
- Camera name
- Risk score out of 100
- Duration
- Review status

---

## Navigation Within Events

While viewing event details:

- Use **Previous** and **Next** buttons to move between events
- Press **left/right arrow keys** for quick navigation
- Press **Escape** to close the popup

---

## Actions You Can Take

| Action               | How To                                  |
| -------------------- | --------------------------------------- |
| **Mark as Reviewed** | Click green button to acknowledge event |
| **Flag Event**       | Mark for later follow-up                |
| **Download Media**   | Save images to your computer            |
| **Add Notes**        | Type in Notes section, click Save       |

---

## Event Lifecycle

How events flow through the system:

```
Camera Detects Motion
        |
        v
AI Analyzes Image
        |
        v
Risk Score Assigned
        |
        v
Event Appears in Feed
        |
        v
Click to View Details
        |
        v
Mark as Reviewed
```

---

## Next Steps

- [Understanding Alerts](understanding-alerts.md) - Risk levels and how to respond
- [Dashboard Settings](dashboard-settings.md) - Configure the system

---

## See Also

- [AI Enrichment Data](ai-enrichment.md) - Detailed AI analysis in event details
- [Dashboard Basics](dashboard-basics.md) - Main dashboard overview
- [Risk Levels Reference](../reference/config/risk-levels.md) - Technical details on risk scoring
- [Troubleshooting Index](../reference/troubleshooting/index.md) - Common problems and solutions

---

[Back to User Hub](../user-hub.md)
