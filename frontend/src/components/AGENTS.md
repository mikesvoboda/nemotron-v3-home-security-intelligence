# Frontend Components Directory

## Purpose

Root directory for all React components in the NVIDIA Security Intelligence home security monitoring dashboard. Components are organized by feature domain and shared functionality.

## Directory Structure

| Directory           | Purpose                                          | Key Components                                                                                                                                                                                                                      |
| ------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ai/**             | AI Performance and Audit page components         | AIPerformancePage, AIAuditPage, ModelStatusCards, LatencyPanel, PipelineHealthPanel, InsightsCharts, ModelZooSection, BatchAuditModal, PromptPlayground, QualityScoreTrends, RecommendationsPanel, ModelLeaderboard                 |
| **ai-audit/**       | AI audit components (placeholder)                | index.ts barrel only (components live in ai/)                                                                                                                                                                                       |
| **ai-performance/** | AI performance summary row component             | AIPerformanceSummaryRow                                                                                                                                                                                                             |
| **alerts/**         | Alert management page                            | AlertsPage                                                                                                                                                                                                                          |
| **audit/**          | Audit log viewing and filtering                  | AuditLogPage, AuditTable, AuditFilters, AuditDetailModal, AuditStatsCards                                                                                                                                                           |
| **common/**         | Shared UI components used across the application | ErrorBoundary, RiskBadge, ConfidenceBadge, ObjectTypeBadge, WebSocketStatus, Lightbox, SecureContextWarning, ScheduleSelector, ServiceStatusAlert                                                                                   |
| **dashboard/**      | Main dashboard page and monitoring widgets       | DashboardPage, CameraGrid, ActivityFeed, GpuStats, StatsRow (with integrated risk sparkline), PipelineQueues, PipelineTelemetry                                                                                                     |
| **detection/**      | Object detection visualization components        | BoundingBoxOverlay, DetectionImage, DetectionThumbnail                                                                                                                                                                              |
| **entities/**       | Entity tracking page (WIP)                       | EntitiesPage                                                                                                                                                                                                                        |
| **events/**         | Security event components                        | EventCard, EventTimeline, EventDetailModal, ThumbnailStrip, ExportPanel                                                                                                                                                             |
| **layout/**         | Application shell components                     | Layout, Header, Sidebar                                                                                                                                                                                                             |
| **logs/**           | Logging dashboard and viewer                     | LogsDashboard, LogsTable, LogFilters, LogStatsCards, LogDetailModal                                                                                                                                                                 |
| **search/**         | Full-text search components                      | SearchBar, SearchResultCard, SearchResultsPanel                                                                                                                                                                                     |
| **settings/**       | Configuration pages                              | SettingsPage, CamerasSettings, AIModelsSettings, ProcessingSettings, DlqMonitor, NotificationSettings, StorageDashboard                                                                                                             |
| **system/**         | System monitoring page                           | SystemMonitoringPage, SystemSummaryRow, PipelineFlowVisualization, InfrastructureStatusGrid, WorkerStatusPanel, AiModelsPanel, ContainersPanel, DatabasesPanel, HostSystemPanel, ModelZooPanel, PipelineMetricsPanel, CircuitBreakerPanel, SeverityConfigPanel, PerformanceAlerts, TimeRangeSelector |
| **video/**          | Video playback components                        | VideoPlayer                                                                                                                                                                                                                         |
| **zones/**          | Zone management components                       | ZoneCanvas, ZoneEditor, ZoneForm, ZoneList                                                                                                                                                                                          |

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
│ ├── StatsRow (with integrated risk sparkline)
│ ├── GpuStats
│ ├── CameraGrid
│ ├── ActivityFeed
│ │ └── RiskBadge (common/)
│ └── PipelineTelemetry
├── /timeline -> EventTimeline (events/)
│ ├── EventCard
│ │ └── RiskBadge, ObjectTypeBadge (common/)
│ ├── ThumbnailStrip
│ ├── ExportPanel
│ └── EventDetailModal
├── /entities -> EntitiesPage (entities/)
├── /alerts -> AlertsPage (alerts/)
├── /audit -> AuditLogPage (audit/)
│ ├── AuditStatsCards
│ ├── AuditFilters
│ ├── AuditTable
│ └── AuditDetailModal
├── /logs -> LogsDashboard (logs/)
│ ├── LogStatsCards
│ ├── LogFilters
│ ├── LogsTable
│ └── LogDetailModal
├── /system -> SystemMonitoringPage (system/)
│ ├── HostSystemPanel
│ ├── ContainersPanel
│ ├── DatabasesPanel
│ ├── AiModelsPanel
│ ├── WorkerStatusPanel
│ ├── PerformanceAlerts
│ └── TimeRangeSelector
└── /settings -> SettingsPage (settings/)
├── CamerasSettings
├── AIModelsSettings
├── ProcessingSettings
├── DlqMonitor
├── NotificationSettings
└── StorageDashboard
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
- **Coverage:** 83%/77%/81%/84% thresholds (statements/branches/functions/lines)

## File Inventory by Directory

### alerts/

- `AlertsPage.tsx` - Alert management page with filtering
- `AlertsPage.test.tsx` - Test suite for AlertsPage

### audit/

- `AuditLogPage.tsx` - Main audit log page
- `AuditLogPage.test.tsx` - Test suite for AuditLogPage
- `AuditTable.tsx` - Paginated audit log table
- `AuditFilters.tsx` - Filtering controls for audit logs
- `AuditDetailModal.tsx` - Full audit entry detail modal
- `AuditStatsCards.tsx` - Audit statistics summary cards
- `index.ts` - Barrel exports

### common/

- `ErrorBoundary.tsx` - React error boundary for catching component errors
- `RiskBadge.tsx` - Risk level badge with icon and optional score
- `ConfidenceBadge.tsx` - Detection confidence score badge with color coding
- `ObjectTypeBadge.tsx` - Detected object type badge (person, vehicle, animal, etc.)
- `WebSocketStatus.tsx` - WebSocket connection status indicator with tooltip
- `Lightbox.tsx` - Full-size image viewer with navigation
- `SecureContextWarning.tsx` - Banner for insecure context (HTTP) detection
- `ScheduleSelector.tsx` - Time-based schedule configuration for alerts
- `ServiceStatusAlert.tsx` - Service health notification banner (deprecated)
- `index.ts` - Barrel exports (ErrorBoundary, RiskBadge, SecureContextWarning, WebSocketStatus)

### dashboard/

- `DashboardPage.tsx` - Main dashboard page orchestrating all widgets
- `DashboardPage.test.tsx` - Test suite for DashboardPage
- `CameraGrid.tsx` - Responsive camera thumbnail grid with status indicators
- `CameraGrid.test.tsx` - Test suite for CameraGrid
- `ActivityFeed.tsx` - Scrolling event feed with auto-scroll
- `ActivityFeed.test.tsx` - Test suite for ActivityFeed
- `GpuStats.tsx` - GPU metrics display with utilization history chart
- `GpuStats.test.tsx` - Test suite for GpuStats
- `StatsRow.tsx` - Key metrics cards (cameras, events, risk with sparkline, status)
- `StatsRow.test.tsx` - Test suite for StatsRow
- `PipelineQueues.tsx` - AI pipeline queue depth display
- `PipelineQueues.test.tsx` - Test suite for PipelineQueues
- `PipelineTelemetry.tsx` - Pipeline latency and throughput metrics display
- `PipelineTelemetry.test.tsx` - Test suite for PipelineTelemetry

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

- `Layout.tsx` - Main layout wrapper composing Header + Sidebar + content
- `Layout.test.tsx` - Test suite for Layout
- `Header.tsx` - Top navigation with branding, health status, GPU stats
- `Header.test.tsx` - Test suite for Header
- `Sidebar.tsx` - Left navigation menu with route links
- `Sidebar.test.tsx` - Test suite for Sidebar

### logs/

- `LogsDashboard.tsx` - Main logs page
- `LogsDashboard.test.tsx` - Test suite for LogsDashboard
- `LogsTable.tsx` - Paginated log entries table
- `LogsTable.test.tsx` - Test suite for LogsTable
- `LogFilters.tsx` - Log filtering controls
- `LogFilters.test.tsx` - Test suite for LogFilters
- `LogStatsCards.tsx` - Log statistics summary cards
- `LogStatsCards.test.tsx` - Test suite for LogStatsCards
- `LogDetailModal.tsx` - Full log entry detail modal
- `LogDetailModal.test.tsx` - Test suite for LogDetailModal

### settings/

- `SettingsPage.tsx` - Settings page with tab navigation
- `SettingsPage.test.tsx` - Test suite for SettingsPage
- `CamerasSettings.tsx` - Camera configuration management
- `CamerasSettings.test.tsx` - Test suite for CamerasSettings
- `AIModelsSettings.tsx` - AI model configuration
- `AIModelsSettings.test.tsx` - Test suite for AIModelsSettings
- `AIModelsSettings.example.tsx` - Example usage for AIModelsSettings
- `ProcessingSettings.tsx` - Processing pipeline settings
- `ProcessingSettings.test.tsx` - Test suite for ProcessingSettings
- `ProcessingSettings.example.tsx` - Example usage for ProcessingSettings
- `DlqMonitor.tsx` - Dead letter queue monitoring
- `DlqMonitor.test.tsx` - Test suite for DlqMonitor
- `NotificationSettings.tsx` - Email and webhook notification configuration
- `NotificationSettings.test.tsx` - Test suite for NotificationSettings
- `StorageDashboard.tsx` - Storage usage and cleanup dashboard
- `StorageDashboard.test.tsx` - Test suite for StorageDashboard
- `index.ts` - Barrel exports
- `README.md` - Documentation

### system/

- `SystemMonitoringPage.tsx` - System health monitoring page with new design
- `SystemMonitoringPage.test.tsx` - Test suite for SystemMonitoringPage
- `SystemSummaryRow.tsx` - Clickable summary indicators for system health
- `SystemSummaryRow.test.tsx` - Test suite for SystemSummaryRow
- `PipelineFlowVisualization.tsx` - Visual pipeline stages with worker status
- `PipelineFlowVisualization.test.tsx` - Test suite for PipelineFlowVisualization
- `InfrastructureStatusGrid.tsx` - Grid of infrastructure cards (PostgreSQL, Redis, Containers, Host, Circuit Breakers)
- `InfrastructureStatusGrid.test.tsx` - Test suite for InfrastructureStatusGrid
- `WorkerStatusPanel.tsx` - Background workers status display
- `WorkerStatusPanel.test.tsx` - Test suite for WorkerStatusPanel
- `HostSystemPanel.tsx` - Host OS and hardware metrics panel
- `HostSystemPanel.test.tsx` - Test suite for HostSystemPanel
- `ContainersPanel.tsx` - Container status and metrics panel
- `ContainersPanel.test.tsx` - Test suite for ContainersPanel
- `DatabasesPanel.tsx` - PostgreSQL and Redis metrics panel
- `DatabasesPanel.test.tsx` - Test suite for DatabasesPanel
- `AiModelsPanel.tsx` - AI model status panel
- `AiModelsPanel.test.tsx` - Test suite for AiModelsPanel
- `ModelZooPanel.tsx` - AI Model Zoo status table with VRAM usage
- `ModelZooPanel.test.tsx` - Test suite for ModelZooPanel
- `PipelineMetricsPanel.tsx` - Queue depths and latency percentiles
- `PipelineMetricsPanel.test.tsx` - Test suite for PipelineMetricsPanel
- `CircuitBreakerPanel.tsx` - Circuit breaker states for resilience
- `CircuitBreakerPanel.test.tsx` - Test suite for CircuitBreakerPanel
- `SeverityConfigPanel.tsx` - Severity threshold configuration
- `SeverityConfigPanel.test.tsx` - Test suite for SeverityConfigPanel
- `PerformanceAlerts.tsx` - Performance threshold alerts
- `PerformanceAlerts.test.tsx` - Test suite for PerformanceAlerts
- `TimeRangeSelector.tsx` - Time range selection for metrics
- `TimeRangeSelector.test.tsx` - Test suite for TimeRangeSelector
- `index.ts` - Barrel exports

### video/

- `VideoPlayer.tsx` - HLS/MP4 video player with controls
- `VideoPlayer.test.tsx` - Test suite for VideoPlayer
- `index.ts` - Barrel exports

## Navigation

Each subdirectory contains its own `AGENTS.md` with detailed component documentation:

- `ai/AGENTS.md` - AI Performance and Audit page components
- `ai-audit/AGENTS.md` - AI audit placeholder (components live in ai/)
- `ai-performance/AGENTS.md` - AI performance summary row component
- `common/AGENTS.md` - Shared component patterns and APIs (ErrorBoundary, RiskBadge, ObjectTypeBadge, Lightbox)
- `dashboard/AGENTS.md` - Dashboard widget details and data flow
- `layout/AGENTS.md` - Application shell and navigation (Layout, Header, Sidebar)
- `system/AGENTS.md` - System monitoring components with redesigned page

## Entry Points

**Start here:** \`layout/Layout.tsx\` - Understand the application shell
**Then explore:** \`dashboard/DashboardPage.tsx\` - See how the main page is assembled
**For components:** \`common/RiskBadge.tsx\` - Example of a reusable component
