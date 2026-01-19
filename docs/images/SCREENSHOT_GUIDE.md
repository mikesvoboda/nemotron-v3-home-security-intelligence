# Screenshot Capture Guide

This document lists all screenshots needed for the user documentation. Each entry includes detailed capture instructions to ensure consistency across all images.

## General Guidelines

- **Theme:** Always use dark mode (NVIDIA dark theme #121212 background)
- **Browser:** Use Chrome or Firefox at 100% zoom
- **Resolution:** Capture at 2x resolution for retina displays if possible
- **Window Size:** Maximize the browser window for full-page captures
- **Data:** Use realistic sample data with varied risk levels and camera names
- **Annotations:** Add numbered callouts or highlights where specified

---

## Dashboard Screenshots

### 1. placeholder-dashboard-overview.png

**File:** `docs/ui/dashboard.md`
**Location:** Main dashboard page (http://localhost:5173/)
**Size:** 1400x900 pixels (16:9 aspect ratio)

**Shows:**

- Complete dashboard view with all sections visible
- Header with system status indicator
- Sidebar navigation with Dashboard selected
- Quick stats row (4 cards)
- Risk gauge with low score
- Camera grid with 3-4 cameras (mix of Online/Offline)
- Live activity feed with 3-4 events

**Alt text:** The main security dashboard showing the complete interface with navigation sidebar, quick stats cards, risk gauge, camera grid, and live activity feed

---

### 2. placeholder-header-health.png

**File:** `docs/ui/dashboard.md`
**Location:** Top header bar of the dashboard
**Size:** 800x200 pixels (4:1 aspect ratio)

**Shows:**

- NVIDIA logo on left
- "LIVE MONITORING" status with green pulsing dot
- GPU stats badge
- Tooltip popup showing individual service health (database, redis, detector, etc.)

**Capture:** Hover over status indicator to show tooltip

**Alt text:** The dashboard header showing system health status with a green pulsing dot indicating live monitoring, and the tooltip displaying individual service health

---

### 3. placeholder-quick-stats.png

**File:** `docs/ui/dashboard.md`
**Location:** Below the page title on main dashboard
**Size:** 1200x150 pixels (8:1 aspect ratio)

**Shows:**

- Four stat cards in a row:
  1. Active Cameras (with camera icon, count like "4")
  2. Events Today (count like "23")
  3. Current Risk Score (with colored badge)
  4. System Status (with green dot)

**Alt text:** Four quick stat cards showing active cameras count, events today count, current risk score with colored badge, and system status indicator

---

### 4. placeholder-risk-gauge.png

**File:** `docs/ui/dashboard.md`
**Location:** Top-left area of main dashboard content
**Size:** 400x400 pixels (1:1 aspect ratio)

**Shows:**

- Circular risk gauge with score (e.g., 18) in center
- Green colored arc (partially filled)
- "Low" text label below
- Sparkline chart showing recent risk history

**Alt text:** Circular risk gauge showing current security risk level with score number in center, colored arc indicator, risk level label, and trend sparkline

---

### 5. placeholder-risk-gauge-states.png

**File:** `docs/ui/dashboard.md`
**Location:** N/A - composite image
**Size:** 800x250 pixels (3.2:1 aspect ratio)

**Shows:**

- Four risk gauges side by side showing different states:
  1. Low (green, score ~15)
  2. Medium (yellow, score ~42)
  3. High (orange, score ~68)
  4. Critical (red with glow, score ~89)

**Note:** This is a composite image - may need to be created by combining screenshots or using design software

**Alt text:** Four risk gauge examples showing Low (green), Medium (yellow), High (orange), and Critical (red) risk levels

---

### 6. placeholder-camera-grid.png

**File:** `docs/ui/dashboard.md`
**Location:** Middle section of main dashboard
**Size:** 1000x350 pixels (2.9:1 aspect ratio)

**Shows:**

- Camera grid with 3-4 camera cards
- Each card shows:
  - Thumbnail image
  - Status badge (mix of Online/Offline)
  - Camera name (e.g., "Front Door", "Backyard")
  - Last seen timestamp
- One camera selected (green border)

**Alt text:** Camera grid showing multiple security cameras with thumbnails, status indicators, and one selected camera highlighted with green border

---

## Activity Feed & Events Screenshots

### 7. placeholder-activity-feed.png

**File:** `docs/ui/timeline.md`
**Location:** Bottom section of main dashboard
**Size:** 600x500 pixels (1.2:1 aspect ratio)

**Shows:**

- "Live Activity" title
- Pause button
- 3-4 event cards showing:
  - Thumbnail
  - Camera name
  - Risk badge (varied colors)
  - AI summary text
  - Relative timestamp ("Just now", "5 mins ago")

**Alt text:** Live Activity feed showing recent security events with thumbnails, risk level badges, AI-generated summaries, and timestamps

---

### 8. placeholder-event-timeline.png

**File:** `docs/ui/timeline.md`
**Location:** Timeline page (click Timeline in sidebar)
**Size:** 1200x800 pixels (3:2 aspect ratio)

**Shows:**

- Page title
- "Show Filters" button (expanded)
- Filter dropdowns visible
- Results summary with risk badges
- Event cards grid (2-3 columns)
- Pagination at bottom

**Alt text:** Event Timeline page showing filter controls, search bar, results summary with event counts by risk level, and grid of event cards

---

### 9. placeholder-timeline-filters.png

**File:** `docs/ui/timeline.md`
**Location:** Filter panel on Timeline page (expanded)
**Size:** 1000x200 pixels (5:1 aspect ratio)

**Shows:**

- Expanded filter panel with:
  - Camera dropdown
  - Risk Level dropdown
  - Status dropdown
  - Object Type dropdown
  - Start Date picker
  - End Date picker
  - "Clear All Filters" button

**Alt text:** Timeline filter controls showing dropdowns for camera, risk level, status, object type, and date range pickers

---

### 10. placeholder-event-detail-modal.png

**File:** `docs/ui/timeline.md`
**Location:** Modal popup when clicking any event
**Size:** 900x800 pixels (9:8 aspect ratio)

**Shows:**

- Header: camera name, timestamp, duration, risk badge, close X
- Large detection image with bounding boxes
- Thumbnail strip
- AI Summary section
- AI Reasoning highlighted box
- Detected Objects list
- Notes section with Save button
- Navigation buttons (Previous/Next)

**Alt text:** Event detail modal showing detection image with object highlighting, AI analysis summary, reasoning explanation, detected objects list, and notes section

---

### 11. placeholder-detection-image.png

**File:** `docs/ui/timeline.md`
**Location:** Image section of Event Detail Modal
**Size:** 700x500 pixels (7:5 aspect ratio)

**Shows:**

- Detection image with AI-drawn bounding boxes
- Boxes around detected objects (person, vehicle, etc.)
- Labels showing object type and confidence percentage

**Alt text:** Security camera image with AI-highlighted detection boxes showing identified objects with confidence scores

---

## Alerts Screenshots

### 12. placeholder-alerts-page.png

**File:** `docs/user-guide/understanding-alerts.md`
**Location:** Alerts page (click Alerts in sidebar)
**Size:** 1200x700 pixels (12:7 aspect ratio)

**Shows:**

- Page title with warning triangle icon
- Severity filter dropdown
- Refresh button
- Results summary showing counts (Critical, High)
- Event cards with orange and red left borders

**Alt text:** Alerts page showing high and critical risk events with orange and red severity indicators, filter dropdown, and event cards

---

### 13. placeholder-risk-level-guide.png

**File:** `docs/user-guide/understanding-alerts.md`
**Location:** N/A - infographic
**Size:** 1000x200 pixels (5:1 aspect ratio)

**Shows:**

- Horizontal bar divided into four sections:
  1. Low (green, 0-29)
  2. Medium (yellow, 30-59)
  3. High (orange, 60-84)
  4. Critical (red, 85-100)
- Each section includes level name, score range, and simple icon

**Note:** This is an infographic - may need design software

**Alt text:** Risk level color guide showing four sections - green for Low (0-29), yellow for Medium (30-59), orange for High (60-84), and red for Critical (85-100)

---

### 14. placeholder-alert-cards-comparison.png

**File:** `docs/user-guide/understanding-alerts.md`
**Location:** N/A - composite showing 4 sample alert cards
**Size:** 1000x400 pixels (2.5:1 aspect ratio)

**Shows:**

- Four event cards side by side:
  1. Low (green left border)
  2. Medium (yellow left border)
  3. High (orange left border)
  4. Critical (red left border with glow)
- Each shows: camera name, timestamp, risk badge, brief summary

**Note:** Composite image

**Alt text:** Four example alert cards showing Low (green), Medium (yellow), High (orange), and Critical (red) risk levels with their distinctive border colors

---

## Settings Screenshots

### 15. placeholder-settings-page.png

**File:** `docs/ui/settings.md`
**Location:** Settings page (click Settings in sidebar)
**Size:** 1200x700 pixels (12:7 aspect ratio)

**Shows:**

- Four tabs: CAMERAS (selected/green), PROCESSING, AI MODELS, NOTIFICATIONS
- Camera list table with:
  - Name column
  - Folder Path column
  - Status badges (Online/green, Offline/gray)
  - Last Seen timestamps
  - Edit/Delete action buttons

**Alt text:** Settings page with tabbed navigation showing Cameras, Processing, and AI Models tabs, with camera configuration table displayed

---

### 16. placeholder-settings-cameras.png

**File:** `docs/ui/settings.md`
**Location:** Settings page > Cameras tab
**Size:** 1000x400 pixels (2.5:1 aspect ratio)

**Shows:**

- Camera list table focused
- Columns: Name, Folder Path, Status, Last Seen, Actions
- Edit pencil and Delete trash icons

**Alt text:** Camera settings table showing configured cameras with their names, paths, status indicators, and edit/delete action buttons

---

### 17. placeholder-settings-ai-models.png

**File:** `docs/ui/settings.md`
**Location:** Settings page > AI Models tab
**Size:** 1000x500 pixels (2:1 aspect ratio)

**Shows:**

- Two model cards:
  1. RT-DETRv2 Object Detection (status, memory, FPS)
  2. Nemotron Risk Analysis (status, memory, speed)
- Total GPU memory usage bar at bottom

**Alt text:** AI Models settings showing RT-DETRv2 and Nemotron model cards with status indicators, memory usage, and performance metrics

---

## User Guide Screenshots

### 18. placeholder-dashboard-full-overview.png

**File:** `docs/ui/dashboard.md`
**Location:** Main dashboard page
**Size:** 1400x900 pixels (16:9 aspect ratio)

**Shows:**

- Complete dashboard view
- All sections visible: header, sidebar, stats, gauge, GPU stats, cameras, activity

**Alt text:** Complete security dashboard showing all main components including navigation, statistics, risk gauge, cameras, and activity feed

---

### 19. placeholder-dashboard-risk-gauge.png

**File:** `docs/ui/dashboard.md`
**Location:** Top-left of main dashboard content
**Size:** 400x450 pixels (8:9 aspect ratio)

**Shows:**

- Risk gauge with score (e.g., 23)
- Green arc
- "Low" label
- Sparkline trend

**Alt text:** Circular risk gauge showing current security risk level with score, colored arc, risk level label, and trend sparkline

---

### 20. placeholder-dashboard-camera-grid.png

**File:** `docs/ui/dashboard.md`
**Location:** Middle section of dashboard
**Size:** 1000x400 pixels (2.5:1 aspect ratio)

**Shows:**

- Camera cards (3-4)
- Thumbnails, status badges, names, timestamps
- One selected with green border

**Alt text:** Camera grid showing multiple security camera cards with thumbnails, status indicators, names, and timestamps

---

### 21. placeholder-dashboard-gpu-stats.png

**File:** `docs/ui/dashboard.md`
**Location:** Top-right area of dashboard
**Size:** 400x350 pixels (8:7 aspect ratio)

**Shows:**

- GPU statistics card:
  - Utilization percentage bar
  - Memory usage bar
  - Temperature (color-coded)
  - Power usage
  - Inference FPS

**Alt text:** GPU statistics panel showing utilization, memory, temperature, power, and inference performance metrics

---

### 22. placeholder-dashboard-activity-feed.png

**File:** `docs/ui/dashboard.md`
**Location:** Bottom section of dashboard
**Size:** 600x450 pixels (4:3 aspect ratio)

**Shows:**

- "Live Activity" title
- Pause/Resume button
- 3-4 event cards with varied risk levels

**Alt text:** Live activity feed showing recent security events with thumbnails, risk indicators, and AI-generated summaries

---

### 23. placeholder-getting-started-dashboard.png

**File:** `docs/user-guide/getting-started.md`
**Location:** Main dashboard page after first login
**Size:** 1400x900 pixels (16:9 aspect ratio)

**Shows:**

- Complete dashboard as new user would see it

**Alt text:** The main security dashboard showing the complete interface a new user will see when first opening the application

---

### 24. placeholder-getting-started-gauge.png

**File:** `docs/user-guide/getting-started.md`
**Location:** Risk gauge on main dashboard
**Size:** 300x300 pixels (1:1 aspect ratio)

**Shows:**

- Risk gauge in calm/low state
- Score around 15-20
- "Low" label

**Alt text:** Risk gauge showing a low risk score with green coloring, indicating normal activity

---

### 25. placeholder-dashboard-tutorial-annotated.png

**File:** `docs/ui/dashboard.md`
**Location:** Main dashboard with annotations
**Size:** 1400x900 pixels (16:9 aspect ratio)

**Shows:**

- Full dashboard with numbered callouts:
  1. Header/status area
  2. Sidebar navigation
  3. Quick stats row
  4. Risk gauge
  5. GPU stats
  6. Camera grid
  7. Activity feed

**Note:** Requires adding annotation overlays

**Alt text:** Annotated dashboard overview showing all major sections with numbered callouts for learning the interface

---

### 26. placeholder-event-detail-complete.png

**File:** `docs/ui/dashboard.md`
**Location:** Event detail modal
**Size:** 900x850 pixels (~1:1 aspect ratio)

**Shows:**

- Complete event detail modal with all sections

**Alt text:** Complete event detail modal showing all sections including detection image, AI analysis, detected objects, and user notes area

---

### 27. placeholder-alerts-page-view.png

**File:** `docs/ui/dashboard.md`
**Location:** Alerts page
**Size:** 1200x700 pixels (12:7 aspect ratio)

**Shows:**

- Alerts page with warning icon
- Severity filter dropdown with options visible
- Event cards with colored borders

**Alt text:** Alerts page showing filtered view of high and critical risk events with severity dropdown and colored event cards

---

### 28. placeholder-sidebar-navigation.png

**File:** `docs/ui/dashboard.md`
**Location:** Left sidebar of dashboard
**Size:** 300x500 pixels (3:5 aspect ratio)

**Shows:**

- Navigation items: Dashboard (selected/green), Timeline, Entities (with WIP badge), Alerts, Logs, System, Settings

**Alt text:** Sidebar navigation showing menu items with Dashboard selected and highlighted in green

---

### 29. placeholder-timeline-full-page.png

**File:** `docs/ui/timeline.md`
**Location:** Timeline page
**Size:** 1400x900 pixels (16:9 aspect ratio)

**Shows:**

- Complete Timeline page with search, filters, results, cards, pagination

**Alt text:** Event Timeline page showing search bar, filters, results summary, and grid of event cards with pagination

---

### 30. placeholder-event-card-detail.png

**File:** `docs/ui/timeline.md`
**Location:** Single event card on Timeline
**Size:** 400x350 pixels (~8:7 aspect ratio)

**Shows:**

- Single event card with all elements:
  - Checkbox
  - Camera name with icon
  - Timestamp, duration
  - Risk badge with score
  - Colored left border
  - Object type badges
  - AI summary text
  - Detection list

**Alt text:** Single event card showing all information including risk badge, object detections, AI summary, and action checkbox

---

### 31. placeholder-timeline-filters-expanded.png

**File:** `docs/ui/timeline.md`
**Location:** Filter panel on Timeline (expanded)
**Size:** 1100x250 pixels (~4:1 aspect ratio)

**Shows:**

- All filter dropdowns visible:
  - Camera, Risk Level, Status, Object Type
  - Min Confidence, Sort By
  - Start/End Date pickers
  - Clear All Filters button

**Alt text:** Expanded filter panel showing all available filter options for narrowing down event results

---

### 32. placeholder-understanding-risk-scale.png

**File:** `docs/user-guide/understanding-alerts.md`
**Location:** N/A - infographic
**Size:** 1000x300 pixels (~3:1 aspect ratio)

**Shows:**

- Thermometer-style or horizontal bar design
- 0-100 risk scale with four colored sections
- Icons and action descriptions for each level

**Alt text:** Risk score scale visualization showing four risk levels from Low (green) to Critical (red) with score ranges and recommended actions

---

### 33. placeholder-ai-reasoning-section.png

**File:** `docs/user-guide/understanding-alerts.md`
**Location:** Event detail modal > AI Reasoning section
**Size:** 700x200 pixels (3.5:1 aspect ratio)

**Shows:**

- AI Reasoning highlighted box (green tint)
- Example reasoning text explaining risk assignment

**Alt text:** AI Reasoning section showing the system's explanation for assigning a particular risk score to an event

---

### 34. placeholder-alerts-notifications-page.png

**File:** `docs/user-guide/alerts-notifications.md`
**Location:** Alerts page
**Size:** 1200x800 pixels (3:2 aspect ratio)

**Shows:**

- Alerts page with warning icon, filter, refresh
- Critical and High event counts
- Event cards with colored borders

**Alt text:** Alerts page showing high and critical risk events with severity filter, refresh button, and color-coded event cards

---

### 35. placeholder-notification-settings.png

**File:** `docs/user-guide/alerts-notifications.md`
**Location:** Settings > NOTIFICATIONS tab
**Size:** 1000x600 pixels (5:3 aspect ratio)

**Shows:**

- Email configuration section (status, SMTP details, test button)
- Webhook configuration section (status, URL, test button)
- Available Channels summary

**Alt text:** Notification settings showing email and webhook configuration status with test buttons and available channels summary

---

### 36. placeholder-settings-full-overview.png

**File:** `docs/user-guide/settings.md`
**Location:** Settings page
**Size:** 1200x700 pixels (12:7 aspect ratio)

**Shows:**

- Four tabs (CAMERAS selected)
- Camera configuration table

**Alt text:** Settings page with tabbed navigation showing Cameras tab selected and camera configuration table

---

### 37. placeholder-settings-cameras-tab.png

**File:** `docs/user-guide/settings.md`
**Location:** Settings > CAMERAS tab
**Size:** 1100x400 pixels (~2.75:1 aspect ratio)

**Shows:**

- Camera table with all columns
- Add Camera button at top right

**Alt text:** Camera settings table showing configured cameras with status indicators and action buttons

---

### 38. placeholder-settings-ai-models-tab.png

**File:** `docs/user-guide/settings.md`
**Location:** Settings > AI MODELS tab
**Size:** 1000x500 pixels (2:1 aspect ratio)

**Shows:**

- RT-DETRv2 and Nemotron model cards
- GPU memory usage bar

**Alt text:** AI Models settings showing RT-DETRv2 and Nemotron model cards with status, memory, and performance metrics

---

### 39. placeholder-search-interface.png

**File:** `docs/user-guide/search.md`
**Location:** Timeline page > Full-Text Search panel
**Size:** 1200x700 pixels (12:7 aspect ratio)

**Shows:**

- Search bar with magnifying glass
- Help (?) button
- Filters button with "Active" badge
- Expanded filter dropdowns
- Search results with relevance scores

**Alt text:** Full-text search interface showing search bar, filter controls, and search results with relevance scoring

---

### 40. placeholder-search-results.png

**File:** `docs/user-guide/search.md`
**Location:** Search results area
**Size:** 1000x500 pixels (2:1 aspect ratio)

**Shows:**

- Result count header
- "Back to browse" link
- Result cards with:
  - Relevance percentage badges (color-coded)
  - Risk badges
  - Summaries with search terms
  - Camera/timestamp info

**Alt text:** Search results showing event cards with relevance scores, risk indicators, and highlighted search terms

---

### 41. placeholder-logs-dashboard-full.png

**File:** `docs/user-guide/logs-dashboard.md`
**Location:** Logs page
**Size:** 1400x900 pixels (16:9 aspect ratio)

**Shows:**

- Four statistics cards:
  1. Errors Today (red when >0)
  2. Warnings Today (yellow when >0)
  3. Total Today (green)
  4. Most Active Component
- Filter panel with dropdowns
- Logs table with:
  - Timestamp column
  - Level badge (color-coded)
  - Component (green monospace)
  - Truncated message
- Pagination controls

**Alt text:** Logs dashboard showing statistics cards, filter controls, and log entries table with color-coded severity levels

---

### 42. placeholder-log-detail-modal.png

**File:** `docs/user-guide/logs-dashboard.md`
**Location:** Modal after clicking log row
**Size:** 700x600 pixels (~7:6 aspect ratio)

**Shows:**

- Header: component name, timestamp, level badge, close X
- Full message text
- Log Details metadata table
- User Agent section (for frontend logs)
- Additional Data section with JSON highlighting

**Alt text:** Log detail modal showing complete log information including metadata, message, and additional JSON data

---

## Image Checklist

Use this checklist to track screenshot capture progress:

- [ ] placeholder-dashboard-overview.png
- [ ] placeholder-header-health.png
- [ ] placeholder-quick-stats.png
- [ ] placeholder-risk-gauge.png
- [ ] placeholder-risk-gauge-states.png (composite)
- [ ] placeholder-camera-grid.png
- [ ] placeholder-activity-feed.png
- [ ] placeholder-event-timeline.png
- [ ] placeholder-timeline-filters.png
- [ ] placeholder-event-detail-modal.png
- [ ] placeholder-detection-image.png
- [ ] placeholder-alerts-page.png
- [ ] placeholder-risk-level-guide.png (infographic)
- [ ] placeholder-alert-cards-comparison.png (composite)
- [ ] placeholder-settings-page.png
- [ ] placeholder-settings-cameras.png
- [ ] placeholder-settings-ai-models.png
- [ ] placeholder-dashboard-full-overview.png
- [ ] placeholder-dashboard-risk-gauge.png
- [ ] placeholder-dashboard-camera-grid.png
- [ ] placeholder-dashboard-gpu-stats.png
- [ ] placeholder-dashboard-activity-feed.png
- [ ] placeholder-getting-started-dashboard.png
- [ ] placeholder-getting-started-gauge.png
- [ ] placeholder-dashboard-tutorial-annotated.png (annotated)
- [ ] placeholder-event-detail-complete.png
- [ ] placeholder-alerts-page-view.png
- [ ] placeholder-sidebar-navigation.png
- [ ] placeholder-timeline-full-page.png
- [ ] placeholder-event-card-detail.png
- [ ] placeholder-timeline-filters-expanded.png
- [ ] placeholder-understanding-risk-scale.png (infographic)
- [ ] placeholder-ai-reasoning-section.png
- [ ] placeholder-alerts-notifications-page.png
- [ ] placeholder-notification-settings.png
- [ ] placeholder-settings-full-overview.png
- [ ] placeholder-settings-cameras-tab.png
- [ ] placeholder-settings-ai-models-tab.png
- [ ] placeholder-search-interface.png
- [ ] placeholder-search-results.png
- [ ] placeholder-logs-dashboard-full.png
- [ ] placeholder-log-detail-modal.png

**Total: 42 screenshots** (38 actual screenshots + 4 composite/infographic images)

---

## Notes for Capture Team

1. **Sample Data:** Ensure the system has varied sample data:

   - Multiple cameras with different statuses
   - Events across all risk levels (Low, Medium, High, Critical)
   - Recent events with different timestamps
   - Various object types detected

2. **Consistent State:** Before capturing, ensure:

   - Dark mode is active
   - System shows "LIVE MONITORING" status
   - No error states unless specifically needed

3. **Composite Images:** Items marked as "composite" or "infographic" may need:

   - Design software (Figma, Photoshop, etc.)
   - Multiple screenshots combined
   - Custom graphics or icons

4. **Annotated Images:** The annotated dashboard image needs:
   - Numbered callout overlays
   - Lines or arrows pointing to sections
   - Consider using a screenshot annotation tool
