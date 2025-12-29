# Frontend Components Directory

## Purpose

Root directory for all React components in the NVIDIA Security Intelligence home security monitoring dashboard. Components are organized by feature domain and shared functionality.

## Directory Structure

| Directory      | Purpose                                          | Key Components                                                                         |
| -------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------- |
| **alerts/**    | Alert management page                            | AlertsPage                                                                             |
| **common/**    | Shared UI components used across the application | RiskBadge, ObjectTypeBadge, ServiceStatusAlert                                         |
| **dashboard/** | Main dashboard page and monitoring widgets       | DashboardPage, RiskGauge, CameraGrid, ActivityFeed, GpuStats, StatsRow, PipelineQueues |
| **detection/** | Object detection visualization components        | BoundingBoxOverlay, DetectionImage, DetectionThumbnail                                 |
| **entities/**  | Entity tracking page (WIP)                       | EntitiesPage                                                                           |
| **events/**    | Security event components                        | EventCard, EventTimeline, EventDetailModal, ThumbnailStrip                             |
| **layout/**    | Application shell components                     | Layout, Header, Sidebar                                                                |
| **logs/**      | Logging dashboard and viewer                     | LogsDashboard, LogsTable, LogFilters, LogStatsCards, LogDetailModal                    |
| **settings/**  | Configuration pages                              | SettingsPage, CamerasSettings, AIModelsSettings, ProcessingSettings, DlqMonitor        |
| **system/**    | System monitoring page                           | SystemMonitoringPage, ObservabilityPanel                                               |
| **video/**     | Video playback components                        | VideoPlayer                                                                            |

## Component Hierarchy

\`\`\`
App
└── Layout (layout/)
├── Header
│ └── uses useSystemStatus, useHealthStatus hooks
└── Sidebar
└── NavLink (react-router-dom)

Routes:
├── / -> DashboardPage (dashboard/)
│ ├── StatsRow
│ ├── RiskGauge
│ ├── GpuStats
│ ├── CameraGrid
│ └── ActivityFeed
│ └── RiskBadge (common/)
├── /timeline -> EventTimeline (events/)
│ ├── EventCard
│ │ └── RiskBadge, ObjectTypeBadge (common/)
│ ├── ThumbnailStrip
│ └── EventDetailModal
├── /entities -> EntitiesPage (entities/)
├── /alerts -> AlertsPage (alerts/)
├── /logs -> LogsDashboard (logs/)
│ ├── LogStatsCards
│ ├── LogFilters
│ ├── LogsTable
│ └── LogDetailModal
├── /system -> SystemMonitoringPage (system/)
│ └── ObservabilityPanel
└── /settings -> SettingsPage (settings/)
├── CamerasSettings
├── AIModelsSettings
├── ProcessingSettings
└── DlqMonitor
\`\`\`

## Styling Approach

All components use:

- **Tailwind CSS** for utility-first styling
- **Tremor** library for data visualization (ProgressBar, Card, AreaChart, Badge)
- **Headless UI** for accessible interactive components (Dialog, Tab)
- **lucide-react** for icons
- **clsx** for conditional class composition

### NVIDIA Dark Theme

- Darkest background: \`#0E0E0E\` (app shell)
- Panel background: \`#1A1A1A\` (cards, sidebar)
- Content background: \`#121212\` (page content)
- Primary accent: \`#76B900\` (NVIDIA green)
- Borders: \`border-gray-800\`
- Text: white, \`text-gray-300\`, \`text-gray-400\`, \`text-gray-500\`

### Risk Level Colors

- Low: green (\`#76B900\` / Tailwind green)
- Medium: yellow (\`#FFB800\` / Tailwind yellow)
- High: orange (\`#E74856\` / Tailwind orange)
- Critical: red (\`#ef4444\` / Tailwind red-500)

## Testing

Test files are co-located with their components using the \`.test.tsx\` extension:

- **Framework:** Vitest
- **Library:** React Testing Library
- **Coverage:** 95% requirement enforced in CI

## File Inventory by Directory

### alerts/

- \`AlertsPage.tsx\` - Alert management page with filtering

### common/

- \`RiskBadge.tsx\` - Risk level badge with icon and optional score
- \`ObjectTypeBadge.tsx\` - Detected object type badge (person, vehicle, animal, etc.)
- \`ServiceStatusAlert.tsx\` - Service health notification banner (deprecated, not wired to backend)
- \`index.ts\` - Barrel exports

### dashboard/

- \`DashboardPage.tsx\` - Main dashboard page orchestrating all widgets
- \`RiskGauge.tsx\` - Circular SVG gauge for risk score with sparkline
- \`CameraGrid.tsx\` - Responsive camera thumbnail grid with status indicators
- \`ActivityFeed.tsx\` - Scrolling event feed with auto-scroll
- \`GpuStats.tsx\` - GPU metrics display with utilization history chart
- \`StatsRow.tsx\` - Key metrics cards (cameras, events, risk, status)
- \`PipelineQueues.tsx\` - AI pipeline queue depth display
- \`RiskGauge.example.tsx\` - Example usage for RiskGauge

### detection/

- \`BoundingBoxOverlay.tsx\` - SVG overlay for drawing detection boxes
- \`DetectionImage.tsx\` - Image component with bounding box overlay
- \`DetectionThumbnail.tsx\` - Thumbnail with detection annotations
- \`Example.tsx\` - Example usage
- \`index.ts\` - Barrel exports
- \`README.md\` - Documentation

### entities/

- \`EntitiesPage.tsx\` - Entity tracking page (work in progress)

### events/

- \`EventCard.tsx\` - Security event card with detections and thumbnails
- \`EventTimeline.tsx\` - Timeline view of security events with filtering
- \`EventDetailModal.tsx\` - Full event detail modal with detections
- \`ThumbnailStrip.tsx\` - Horizontal scrolling thumbnail strip
- \`index.ts\` - Barrel exports

### layout/

- \`Layout.tsx\` - Main layout wrapper composing Header + Sidebar + content
- \`Header.tsx\` - Top navigation with branding, health status, GPU stats
- \`Sidebar.tsx\` - Left navigation menu with route links

### logs/

- \`LogsDashboard.tsx\` - Main logs page
- \`LogsTable.tsx\` - Paginated log entries table
- \`LogFilters.tsx\` - Log filtering controls
- \`LogStatsCards.tsx\` - Log statistics summary cards
- \`LogDetailModal.tsx\` - Full log entry detail modal

### settings/

- \`SettingsPage.tsx\` - Settings page with tab navigation
- \`CamerasSettings.tsx\` - Camera configuration management
- \`AIModelsSettings.tsx\` - AI model configuration
- \`ProcessingSettings.tsx\` - Processing pipeline settings
- \`DlqMonitor.tsx\` - Dead letter queue monitoring
- \`index.ts\` - Barrel exports

### system/

- \`SystemMonitoringPage.tsx\` - System health monitoring page
- \`ObservabilityPanel.tsx\` - Observability metrics panel
- \`index.ts\` - Barrel exports

### video/

- \`VideoPlayer.tsx\` - HLS/MP4 video player with controls
- \`index.ts\` - Barrel exports

## Navigation

Each subdirectory contains its own \`AGENTS.md\` with detailed component documentation:

- \`common/AGENTS.md\` - Shared component patterns and APIs
- \`dashboard/AGENTS.md\` - Dashboard widget details and data flow
- \`layout/AGENTS.md\` - Application shell and navigation
- \`events/AGENTS.md\` - Event component hierarchy
- \`detection/AGENTS.md\` - Detection visualization components
- \`settings/AGENTS.md\` - Settings page structure
- \`logs/AGENTS.md\` - Logging dashboard components
- \`system/AGENTS.md\` - System monitoring components

## Entry Points

**Start here:** \`layout/Layout.tsx\` - Understand the application shell
**Then explore:** \`dashboard/DashboardPage.tsx\` - See how the main page is assembled
**For components:** \`common/RiskBadge.tsx\` - Example of a reusable component
