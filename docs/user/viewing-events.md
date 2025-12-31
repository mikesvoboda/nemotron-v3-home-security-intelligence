# Viewing Events

> How to view, filter, and interact with security events.

**Time to read:** ~10 min
**Prerequisites:** [Dashboard Basics](dashboard-basics.md)

---

## Live Activity Feed

The Live Activity Feed shows security events as they happen in real-time.

### Understanding the Feed

Each event in the feed shows:

1. **Thumbnail** - Small image from when event occurred
2. **Camera Name** - Which camera detected activity
3. **Risk Badge** - Colored label showing risk level
4. **Summary** - Brief AI-generated description
5. **Timestamp** - When it occurred ("Just now", "5 mins ago", etc.)

### Using the Feed

- Click any event to see full details in a popup
- Events appear with newest at the top
- Feed shows up to 10 recent events

### Auto-Scroll Feature

The feed automatically scrolls when new events arrive:

- Click **Pause** to stop auto-scrolling (useful when reading)
- Click **Resume** to turn auto-scrolling back on

When paused, you can manually scroll through events.

---

## Event Timeline

The Event Timeline page shows a complete history of all security events with powerful filtering.

### Accessing the Timeline

Click **Timeline** in the left sidebar.

### Filtering Events

Click **Show Filters** to reveal filtering options:

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
Click **Export CSV** to download filtered events as a spreadsheet.

### Pagination

Events are shown 20 at a time. Use **Previous** and **Next** buttons at the bottom to navigate pages.

---

## Event Details

When you click any event (in the feed, timeline, or alerts), a detailed popup appears.

### Header Section

- **Camera Name** - Large title showing which camera
- **Timestamp** - Exact date and time
- **Duration** - How long the event lasted
- **Risk Badge** - Large colored badge with score
- **Close Button** (X) - Click to close popup

### Detection Image

Full-size image from the event. If the AI detected objects, they are highlighted with colored boxes and labels (like "Person 95%").

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
- [Back to User Hub](../user-hub.md)
