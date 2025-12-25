# Frontend Components Directory

## Purpose

Root directory for all React components in the NVIDIA Security Intelligence home security monitoring dashboard. Components are organized by feature domain and shared functionality.

## Directory Structure

- **common/** - Shared UI components used across the application (RiskBadge, ObjectTypeBadge)
- **dashboard/** - Main dashboard page and related components (RiskGauge, CameraGrid, ActivityFeed, GpuStats, StatsRow)
- **detection/** - Object detection visualization components (BoundingBoxOverlay, DetectionImage)
- **events/** - Event-related components (EventCard, EventTimeline, EventDetailModal, ThumbnailStrip)
- **layout/** - Application layout components (Header, Sidebar, Layout)
- **logs/** - Logging dashboard components (LogsDashboard, LogsTable, LogFilters, LogStatsCards, LogDetailModal)
- **settings/** - Settings page components (SettingsPage, CamerasSettings, AIModelsSettings, ProcessingSettings)

## Component Organization

Components are organized by feature domain to maintain clear separation of concerns:

- **Layout components** - Application structure, navigation (Header, Sidebar, Layout wrapper)
- **Detection components** - AI detection visualization (bounding boxes, detection overlays)
- **Dashboard components** - Main monitoring views (RiskGauge, CameraGrid, ActivityFeed, GpuStats, StatsRow)
- **Common components** - Reusable UI primitives (RiskBadge, ObjectTypeBadge)
- **Events components** - Security event displays (EventCard, EventTimeline, EventDetailModal, ThumbnailStrip)
- **Logs components** - System logging interface (LogsDashboard, LogsTable, LogFilters, LogStatsCards, LogDetailModal)
- **Settings components** - Configuration pages (SettingsPage, CamerasSettings, AIModelsSettings, ProcessingSettings)

## Styling Approach

All components use:

- **Tailwind CSS** for utility-first styling
- **Tremor** library for data visualization components (planned for dashboard metrics)
- **Custom dark theme** with NVIDIA brand colors:
  - Background: `#0E0E0E` (darkest) and `#1A1A1A` (panels)
  - Primary: `#76B900` (NVIDIA green)
  - Border: `gray-800` for subtle separations

## Testing

Test files are co-located with their components using the `.test.tsx` extension. All tests use:

- **Vitest** as the test runner
- **React Testing Library** for component testing
- **95% code coverage** requirement (enforced by pre-commit hooks)

## File Inventory

| Directory | Files |
|-----------|-------|
| common/ | RiskBadge.tsx, ObjectTypeBadge.tsx, index.ts |
| dashboard/ | DashboardPage.tsx, RiskGauge.tsx, CameraGrid.tsx, ActivityFeed.tsx, GpuStats.tsx, StatsRow.tsx, RiskGauge.example.tsx |
| detection/ | DetectionImage.tsx, BoundingBoxOverlay.tsx, Example.tsx, index.ts, README.md |
| events/ | EventCard.tsx, EventTimeline.tsx, EventDetailModal.tsx, ThumbnailStrip.tsx |
| layout/ | Header.tsx, Sidebar.tsx, Layout.tsx |
| logs/ | LogsDashboard.tsx, LogsTable.tsx, LogFilters.tsx, LogStatsCards.tsx, LogDetailModal.tsx |
| settings/ | SettingsPage.tsx, CamerasSettings.tsx, AIModelsSettings.tsx, ProcessingSettings.tsx, index.ts, README.md |

## Navigation

For detailed information about components in each subdirectory, see the AGENTS.md file in that directory.
