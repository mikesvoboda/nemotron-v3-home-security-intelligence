---
title: Entities Page
description: Track and manage people and vehicles detected across your cameras
source_refs:
  - frontend/src/components/entities/EntitiesPage.tsx
  - frontend/src/components/entities/EntityCard.tsx
  - frontend/src/components/entities/EntityDetailModal.tsx
  - frontend/src/components/entities/EntityTimeline.tsx
  - frontend/src/components/entities/EntityStatsCard.tsx
---

# Entities Page

The Entities page displays all people and vehicles that the AI has tracked across your cameras. Each entity is a unique individual or vehicle that has been detected and re-identified across multiple camera views and time periods.

---

## Accessing Entities

1. Click **Entities** in the left sidebar navigation
2. The page displays a grid of tracked entities
3. Use filters to narrow down results

---

## Understanding Entities

### What is an Entity?

An entity represents a unique person or vehicle that the system has identified and tracked. The AI uses re-identification technology to:

- Match the same person across different cameras
- Track vehicles by appearance characteristics
- Build a history of where and when each entity was seen

### Entity Types

| Type    | Icon | Description                                   |
| ------- | ---- | --------------------------------------------- |
| Person  | User | Individual people detected by the AI          |
| Vehicle | Car  | Cars, trucks, motorcycles, and other vehicles |

---

## Entity Statistics Card

At the top of the page, a statistics card provides an overview:

| Metric         | Description                          |
| -------------- | ------------------------------------ |
| Total Entities | Count of unique people and vehicles  |
| People Count   | Number of unique persons tracked     |
| Vehicle Count  | Number of unique vehicles tracked    |
| Most Active    | Entity with highest appearance count |

Click the **Stats** toggle button to show or hide this card.

---

## Entity Grid

Entities are displayed in a responsive grid of cards. Each card shows:

### Entity Card Components

| Element     | Location    | Description                          |
| ----------- | ----------- | ------------------------------------ |
| Type Badge  | Top-left    | Person or Vehicle indicator          |
| Trust Badge | Top-left    | Trusted, Suspicious, or Unknown      |
| Entity ID   | Top-right   | Unique identifier (truncated)        |
| Thumbnail   | Center      | Representative image of entity       |
| Appearances | Below image | Number of times seen                 |
| Cameras     | Below image | Number of cameras that detected them |
| Last Seen   | Bottom      | When entity was most recently seen   |
| First Seen  | Bottom      | When entity was first detected       |

### Trust Status Badges

| Badge      | Color | Meaning                           |
| ---------- | ----- | --------------------------------- |
| Trusted    | Green | Known/approved person or vehicle  |
| Suspicious | Amber | Flagged as potentially concerning |
| (No badge) | -     | Unknown/unclassified entity       |

---

## Filtering Entities

The filter bar provides multiple ways to narrow down the entity list:

### Entity Type Filter

Toggle buttons to filter by type:

| Filter   | Shows                     |
| -------- | ------------------------- |
| All      | Both persons and vehicles |
| Persons  | Only people               |
| Vehicles | Only cars, trucks, etc.   |

### Time Range Filter

Dropdown to filter by when entities were last seen:

| Option   | Shows Entities Seen In    |
| -------- | ------------------------- |
| All Time | All historical entities   |
| Last 1h  | Past hour only            |
| Last 24h | Past day only             |
| Last 7d  | Past week only            |
| Last 30d | Past month only           |
| Custom   | Your specified date range |

### Custom Date Range

When "Custom" is selected, date pickers appear:

1. Select the **start date** for your range
2. Select the **end date** for your range
3. Results update automatically

### Camera Filter

Filter entities seen by a specific camera:

- Select **All Cameras** to see all entities
- Select a specific camera to see only entities it detected

### Data Source Filter

Control where entity data comes from:

| Source      | Description                        |
| ----------- | ---------------------------------- |
| All Sources | Combine real-time and historical   |
| Real-time   | Recent entities from Redis (24h)   |
| Historical  | Older entities from database (30d) |

### Trust Status Filter

Filter by entity classification:

| Filter     | Shows                             | Count        |
| ---------- | --------------------------------- | ------------ |
| All Trust  | All entities regardless of status | (total)      |
| Trusted    | Only trusted entities             | (trusted)    |
| Suspicious | Only flagged entities             | (suspicious) |
| Unknown    | Only unclassified entities        | (unknown)    |

### Sort Options

Control the order of displayed entities:

| Sort By     | Order                          |
| ----------- | ------------------------------ |
| Last Seen   | Most recently seen first       |
| First Seen  | Most recently discovered first |
| Appearances | Most frequently seen first     |

---

## Entity Detail Modal

Click any entity card to open the detail modal with comprehensive information.

### Modal Header

Shows:

- Entity thumbnail (circular)
- Entity type (Person/Vehicle)
- Full entity ID
- Trust status badge
- Trust action buttons

### Trust Classification Buttons

If you have permission, you can classify entities:

| Button             | Action                          |
| ------------------ | ------------------------------- |
| Mark as Trusted    | Flag as known/approved          |
| Mark as Suspicious | Flag as potentially concerning  |
| Reset              | Clear classification to unknown |

### Statistics Row

Four cards showing key metrics:

| Card        | Shows                                |
| ----------- | ------------------------------------ |
| Appearances | Total times this entity was detected |
| Cameras     | Number of different cameras          |
| First Seen  | When entity was first detected       |
| Last Seen   | Most recent detection                |

### Cameras List

Badges showing all cameras that have detected this entity:

- Each badge shows the camera name
- Hover for additional details
- Click to filter by that camera

### Detection History

A visual history of all detection images:

| Element         | Description                           |
| --------------- | ------------------------------------- |
| Main Image      | Large view of selected detection      |
| Navigation      | Left/right arrows to browse           |
| Metadata        | Camera, time, object type, confidence |
| Thumbnail Strip | Quick access to all detections        |
| Load More       | Fetch additional detection history    |

#### Navigating Detections

1. Click **left arrow** to see earlier detections
2. Click **right arrow** to see later detections
3. Click any **thumbnail** to jump to that detection
4. Click **View Full Size** to open in lightbox

### Appearance Timeline

A chronological list showing each appearance:

| Column   | Shows                            |
| -------- | -------------------------------- |
| Time     | When the appearance occurred     |
| Camera   | Which camera detected the entity |
| Duration | How long the entity was visible  |

---

## Working with Trust Classification

### Why Classify Entities?

Trust classification helps you:

- Distinguish family members from strangers
- Flag suspicious individuals for review
- Filter out known entities in the timeline
- Reduce false alerts from trusted persons

### Best Practices

**Mark as Trusted:**

- Family members and regular visitors
- Delivery drivers you recognize
- Your own vehicles
- Neighbors you know

**Mark as Suspicious:**

- Unknown persons lingering on property
- Vehicles casing the area
- People attempting to access restricted areas
- Anyone who triggered a genuine alert

**Leave Unknown:**

- First-time visitors until identified
- Entities with insufficient data
- Ambiguous detections

---

## Infinite Scroll

The Entities page uses infinite scroll for large entity lists:

1. Scroll down to load more entities
2. A loading indicator appears while fetching
3. The total count shows loaded vs total entities
4. "You've seen all entities" appears when complete

---

## Auto-Refresh

The page automatically refreshes every 30 seconds to show new entities:

- A subtle "Updating..." indicator appears during refresh
- Your scroll position is preserved
- Filters remain applied

Click the **Refresh** button to manually update immediately.

---

## Empty States

### No Entities at All

If no entities have been tracked:

- Check that cameras are online and capturing images
- Verify AI detection is enabled in settings
- Wait for activity in camera views

### No Entities Match Filters

If filters return no results:

- Try broadening the time range
- Remove camera-specific filters
- Change the trust status filter
- Click **Clear Filters** to reset all filters

---

## Performance Tips

### For Large Entity Counts

1. Use **time range filters** to limit results
2. Filter by **specific camera** when investigating
3. Use **trust status** to hide classified entities
4. Sort by **appearances** to see most active first

### Loading Optimization

The page loads entities in batches of 50. For faster initial load:

1. Apply filters before scrolling
2. Use shorter time ranges
3. Select specific cameras when needed

---

## Troubleshooting

### Entities Not Appearing

**Check:**

- Cameras are online and capturing images
- AI detection is enabled
- Sufficient activity has occurred
- Filters are not too restrictive

### Same Person as Multiple Entities

**This can happen when:**

- Person's appearance changed significantly
- Different lighting conditions
- Camera angles too different
- Insufficient training data

**The system improves over time** as it collects more samples.

### Entity Detail Modal Empty

**Check:**

- Network connectivity
- Backend services running
- Entity still exists in database

### Trust Changes Not Saving

**Check:**

- Network connectivity
- Permissions to modify entities
- Backend API health

---

## Privacy Considerations

Entity tracking stores:

- Detection images and thumbnails
- Appearance timestamps
- Camera locations
- Re-identification embeddings

**To protect privacy:**

- Only family members should have access
- Review and delete entities as needed
- Set appropriate data retention policies
- Use trust classification responsibly

---

## Related Documentation

- [Event Investigation](event-investigation.md) - Investigate specific events
- [Dashboard Overview](dashboard-overview.md) - Main dashboard features
- [Understanding Alerts](understanding-alerts.md) - Risk scoring explained
- [Detection Zones](zones.md) - Focus detection on specific areas

---

[Back to User Hub](../user/README.md)
