# Frontend Components Directory

## Purpose

Root directory for all React components in the NVIDIA Security Intelligence home security monitoring dashboard. Components are organized by feature domain and shared functionality.

## Root-Level Components

| File                         | Purpose                                           |
| ---------------------------- | ------------------------------------------------- |
| `ExportButton.tsx`           | Generic export button for data download           |
| `ExportButton.test.tsx`      | Test suite for ExportButton                       |
| `RetryIndicator.tsx`         | Retry status indicator component                  |
| `RetryIndicator.test.tsx`    | Test suite for RetryIndicator                     |
| `RetryingIndicator.tsx`      | Active retry progress indicator                   |
| `RetryingIndicator.test.tsx` | Test suite for RetryingIndicator                  |

## Directory Structure

| Directory             | Purpose                                          | Key Components                                                                                                                                                                                                                      |
| --------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ai/**               | AI Performance and Audit page components         | AIPerformancePage, AIAuditPage, ModelStatusCards, LatencyPanel, PipelineHealthPanel, InsightsCharts, ModelZooSection, BatchAuditModal, PromptPlayground, PromptABTest, ABTestStats, QualityScoreTrends, RecommendationsPanel, ModelLeaderboard, SuggestionDiffView, SuggestionExplanation |
| **ai-audit/**         | AI audit components (placeholder)                | index.ts barrel only (components live in ai/)                                                                                                                                                                                       |
| **ai-performance/**   | AI performance summary row component             | AIPerformanceSummaryRow                                                                                                                                                                                                             |
| **alerts/**           | Alert management and rule configuration          | AlertsPage, AlertCard, AlertActions, AlertFilters, AlertForm, AlertRuleForm                                                                                                                                                         |
| **analytics/**        | Analytics and baseline monitoring                | AnalyticsPage, ActivityHeatmap, ClassFrequencyChart, AnomalyConfigPanel, PipelineLatencyPanel, SceneChangePanel                                                                                                                     |
| **audit/**            | Audit log viewing and filtering                  | AuditLogPage, AuditTable, AuditFilters, AuditDetailModal, AuditStatsCards, EventAuditDetail                                                                                                                                         |
| **common/**           | Shared UI components used across the application | ErrorBoundary, ChunkLoadErrorBoundary, RiskBadge, ConfidenceBadge, ObjectTypeBadge, WebSocketStatus, Lightbox, SecureContextWarning, ScheduleSelector, TruncatedText, EmptyState, LoadingSpinner, RouteLoadingFallback, AlertBadge, AlertDrawer, BottomSheet, IconButton, WorkerStatusIndicator |
| **dashboard/**        | Main dashboard page and monitoring widgets       | DashboardPage, CameraGrid, ActivityFeed, GpuStats, StatsRow, PipelineQueues, PipelineTelemetry, DashboardConfigModal, DashboardLayout, ExpandableSummary, SeverityBadge, SummaryCards, SummaryBulletList, SummaryCardEmpty, SummaryCardError, SummaryCardSkeleton |
| **detection/**        | Object detection visualization components        | BoundingBoxOverlay, DetectionImage, DetectionThumbnail                                                                                                                                                                              |
| **developer-tools/**  | Developer tools page for debugging               | DeveloperToolsPage, ConfigInspectorPanel, LogLevelPanel, ProfilingPanel, RecordingDetailModal, RecordingReplayPanel, RecordingsList, ReplayResultsModal, TestDataPanel, CleanupRow, SeedRow, ConfirmWithTextDialog                  |
| **entities/**         | Entity tracking and re-identification            | EntitiesPage, EntityCard, EntityTimeline, EntityDetailModal, ReidHistoryPanel                                                                                                                                                      |
| **events/**           | Security event components                        | EventCard, EventTimeline, EventDetailModal, ThumbnailStrip, ExportPanel                                                                                                                                                             |
| **exports/**          | Export functionality components                  | ExportModal, ExportProgress                                                                                                                                                                                                         |
| **feedback/**         | User feedback components                         | FeedbackPanel                                                                                                                                                                                                                       |
| **jobs/**             | Background job monitoring components             | JobsPage, JobsList, JobsListItem, JobsEmptyState, JobsSearchBar, JobActions, JobHeader, JobDetailPanel, JobHistoryTimeline, JobLogsViewer, JobMetadata, ConnectionIndicator, ConfirmDialog, LogLine, StatusDot, TimelineEntry       |
| **layout/**           | Application shell components                     | Layout, Header, Sidebar                                                                                                                                                                                                             |
| **logs/**             | Logging dashboard and viewer                     | LogsDashboard, LogsTable, LogFilters, LogStatsCards, LogDetailModal                                                                                                                                                                 |
| **performance/**      | Performance monitoring dashboard                 | PerformanceDashboard, PerformanceCharts, PerformanceAlerts                                                                                                                                                                          |
| **search/**           | Full-text search components                      | SearchBar, SearchResultCard, SearchResultsPanel                                                                                                                                                                                     |
| **settings/**         | Configuration pages                              | SettingsPage, CamerasSettings, AIModelsSettings, ProcessingSettings, DlqMonitor, NotificationSettings, StorageDashboard                                                                                                             |
| **status/**           | AI service health status components              | AIServiceStatus                                                                                                                                                                                                                      |
| **system/**           | System monitoring page                           | SystemMonitoringPage, SystemSummaryRow, PipelineFlowVisualization, InfrastructureStatusGrid, WorkerStatusPanel, AiModelsPanel, ContainersPanel, DatabasesPanel, HostSystemPanel, ModelZooPanel, PipelineMetricsPanel, CircuitBreakerPanel, SeverityConfigPanel, PerformanceAlerts, TimeRangeSelector |
| **tracing/**          | Distributed tracing visualization page           | TracingPage                                                                                                                                                                                                                         |
| **video/**            | Video playback components                        | VideoPlayer                                                                                                                                                                                                                         |
| **zones/**            | Zone management components                       | ZoneCanvas, ZoneEditor, ZoneForm, ZoneList                                                                                                                                                                                          |

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
│   ├── EntityCard (grid of tracked entities)
│   └── EntityDetailModal
│       └── ReidHistoryPanel
├── /alerts -> AlertsPage (alerts/)
├── /analytics -> AnalyticsPage (analytics/)
│   ├── ActivityHeatmap
│   ├── ClassFrequencyChart
│   ├── AnomalyConfigPanel
│   ├── PipelineLatencyPanel
│   └── SceneChangePanel
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
├── /settings -> SettingsPage (settings/)
│ ├── CamerasSettings
│ ├── AIModelsSettings
│ ├── ProcessingSettings
│ ├── DlqMonitor
│ ├── NotificationSettings
│ └── StorageDashboard
├── /jobs -> JobsPage (jobs/)
│ ├── JobsList
│ ├── JobsSearchBar
│ ├── JobDetailPanel
│ └── JobLogsViewer
├── /dev-tools -> DeveloperToolsPage (developer-tools/)
│ ├── ConfigInspectorPanel
│ ├── LogLevelPanel
│ ├── ProfilingPanel
│ └── TestDataPanel
└── /performance -> PerformanceDashboard (performance/)
    ├── PerformanceCharts
    └── PerformanceAlerts
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

- `AlertsPage.tsx` - Main alerts page with infinite scroll and filtering
- `AlertsPage.test.tsx` - Test suite for AlertsPage
- `AlertCard.tsx` - Individual alert card with acknowledge/dismiss/snooze actions
- `AlertCard.test.tsx` - Test suite for AlertCard
- `AlertActions.tsx` - Bulk operation controls (select all, acknowledge, dismiss)
- `AlertActions.test.tsx` - Test suite for AlertActions
- `AlertFilters.tsx` - Severity-based filter buttons with counts
- `AlertFilters.test.tsx` - Test suite for AlertFilters
- `AlertForm.tsx` - Alert rule form with basic validation
- `AlertForm.test.tsx` - Test suite for AlertForm
- `AlertRuleForm.tsx` - Alert rule form with Zod/react-hook-form validation
- `AlertRuleForm.test.tsx` - Test suite for AlertRuleForm
- `index.ts` - Barrel exports for all components and types
- `AGENTS.md` - Directory documentation

### analytics/

- `AnalyticsPage.tsx` - Analytics dashboard with baseline visualization
- `AnalyticsPage.test.tsx` - Test suite for AnalyticsPage
- `ActivityHeatmap.tsx` - 24x7 activity pattern heatmap
- `ActivityHeatmap.test.tsx` - Test suite for ActivityHeatmap
- `ClassFrequencyChart.tsx` - Object class frequency distribution chart
- `ClassFrequencyChart.test.tsx` - Test suite for ClassFrequencyChart
- `AnomalyConfigPanel.tsx` - Anomaly detection configuration panel
- `AnomalyConfigPanel.test.tsx` - Test suite for AnomalyConfigPanel
- `PipelineLatencyPanel.tsx` - AI pipeline latency monitoring
- `PipelineLatencyPanel.test.tsx` - Test suite for PipelineLatencyPanel
- `SceneChangePanel.tsx` - Camera tampering detection panel
- `SceneChangePanel.test.tsx` - Test suite for SceneChangePanel
- `index.ts` - Barrel exports
- `AGENTS.md` - Directory documentation

### audit/

- `AuditLogPage.tsx` - Main audit log page
- `AuditLogPage.test.tsx` - Test suite for AuditLogPage
- `AuditTable.tsx` - Paginated audit log table
- `AuditFilters.tsx` - Filtering controls for audit logs
- `AuditDetailModal.tsx` - Full audit entry detail modal
- `AuditStatsCards.tsx` - Audit statistics summary cards
- `index.ts` - Barrel exports

### common/

- `ChunkLoadErrorBoundary.tsx` - Error boundary for dynamic import/chunk loading failures
- `ChunkLoadErrorBoundary.test.tsx` - Test suite for ChunkLoadErrorBoundary
- `EmptyState.tsx` - Reusable empty state component with icon and actions
- `EmptyState.test.tsx` - Test suite for EmptyState
- `ErrorBoundary.tsx` - React error boundary for catching component errors
- `ErrorBoundary.test.tsx` - Test suite for ErrorBoundary
- `LoadingSpinner.tsx` - Simple loading spinner for Suspense fallbacks
- `LoadingSpinner.test.tsx` - Test suite for LoadingSpinner
- `RouteLoadingFallback.tsx` - Loading indicator for lazy-loaded routes
- `RouteLoadingFallback.test.tsx` - Test suite for RouteLoadingFallback
- `RiskBadge.tsx` - Risk level badge with icon and optional score
- `RiskBadge.test.tsx` - Test suite for RiskBadge
- `ConfidenceBadge.tsx` - Detection confidence score badge with color coding
- `ConfidenceBadge.test.tsx` - Test suite for ConfidenceBadge
- `ObjectTypeBadge.tsx` - Detected object type badge (person, vehicle, animal, etc.)
- `ObjectTypeBadge.test.tsx` - Test suite for ObjectTypeBadge
- `WebSocketStatus.tsx` - WebSocket connection status indicator with tooltip
- `WebSocketStatus.test.tsx` - Test suite for WebSocketStatus
- `Lightbox.tsx` - Full-size image viewer with navigation
- `Lightbox.test.tsx` - Test suite for Lightbox
- `SecureContextWarning.tsx` - Banner for insecure context (HTTP) detection
- `SecureContextWarning.test.tsx` - Test suite for SecureContextWarning
- `ScheduleSelector.tsx` - Time-based schedule configuration for alerts
- `ScheduleSelector.test.tsx` - Test suite for ScheduleSelector
- `TruncatedText.tsx` - Text truncation with expand/collapse functionality
- `TruncatedText.test.tsx` - Test suite for TruncatedText
- `ServiceStatusAlert.tsx` - Service health notification banner (deprecated)
- `ServiceStatusAlert.test.tsx` - Test suite for ServiceStatusAlert (deprecated)
- `index.ts` - Barrel exports
- `.gitkeep` - Placeholder file
- `AGENTS.md` - Directory documentation

### dashboard/

- `DashboardPage.tsx` - Main dashboard page orchestrating all widgets
- `DashboardPage.test.tsx` - Test suite for DashboardPage
- `DashboardConfigModal.tsx` - Modal for dashboard configuration settings
- `DashboardConfigModal.test.tsx` - Test suite for DashboardConfigModal
- `DashboardLayout.tsx` - Responsive layout wrapper for dashboard widgets
- `DashboardLayout.test.tsx` - Test suite for DashboardLayout
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
- `ExpandableSummary.tsx` - Expandable summary section component
- `ExpandableSummary.test.tsx` - Test suite for ExpandableSummary
- `SeverityBadge.tsx` - Severity level badge component
- `SeverityBadge.test.tsx` - Test suite for SeverityBadge
- `SummaryCards.tsx` - Summary cards container
- `SummaryCards.test.tsx` - Test suite for SummaryCards
- `SummaryCards.a11y.test.tsx` - Accessibility tests for SummaryCards
- `SummaryCards.integration.test.tsx` - Integration tests for SummaryCards
- `SummaryCardsIntegration.test.tsx` - Additional integration tests
- `SummaryBulletList.tsx` - Bullet list component for summaries
- `SummaryBulletList.test.tsx` - Test suite for SummaryBulletList
- `SummaryCardEmpty.tsx` - Empty state for summary cards
- `SummaryCardEmpty.test.tsx` - Test suite for SummaryCardEmpty
- `SummaryCardError.tsx` - Error state for summary cards
- `SummaryCardError.test.tsx` - Test suite for SummaryCardError
- `SummaryCardSkeleton.tsx` - Loading skeleton for summary cards
- `SummaryCardSkeleton.test.tsx` - Test suite for SummaryCardSkeleton
- `index.ts` - Barrel exports

### detection/

- \`BoundingBoxOverlay.tsx\` - SVG overlay for drawing detection boxes
- \`DetectionImage.tsx\` - Image component with bounding box overlay
- \`DetectionThumbnail.tsx\` - Thumbnail with detection annotations
- \`Example.tsx\` - Example usage
- \`index.ts\` - Barrel exports
- \`README.md\` - Documentation

### entities/

- `EntitiesPage.tsx` - Main entity tracking and management page
- `EntitiesPage.test.tsx` - Test suite for EntitiesPage
- `EntityCard.tsx` - Card display for individual tracked entity
- `EntityCard.test.tsx` - Test suite for EntityCard
- `EntityTimeline.tsx` - Timeline of entity appearances across cameras
- `EntityTimeline.test.tsx` - Test suite for EntityTimeline
- `EntityDetailModal.tsx` - Modal showing entity details and history
- `EntityDetailModal.test.tsx` - Test suite for EntityDetailModal
- `ReidHistoryPanel.tsx` - Re-identification history display panel
- `ReidHistoryPanel.test.tsx` - Test suite for ReidHistoryPanel
- `index.ts` - Barrel exports
- `AGENTS.md` - Directory documentation

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

### status/

- `AIServiceStatus.tsx` - AI service health status with expandable service details
- `AIServiceStatus.test.tsx` - Test suite for AIServiceStatus

### video/

- `VideoPlayer.tsx` - HLS/MP4 video player with controls
- `VideoPlayer.test.tsx` - Test suite for VideoPlayer
- `index.ts` - Barrel exports

### developer-tools/

- `DeveloperToolsPage.tsx` - Main developer tools page
- `DeveloperToolsPage.test.tsx` - Test suite for DeveloperToolsPage
- `ConfigInspectorPanel.tsx` - Configuration inspector panel
- `ConfigInspectorPanel.test.tsx` - Test suite for ConfigInspectorPanel
- `LogLevelPanel.tsx` - Runtime log level control panel
- `LogLevelPanel.test.tsx` - Test suite for LogLevelPanel
- `ProfilingPanel.tsx` - Performance profiling panel
- `ProfilingPanel.test.tsx` - Test suite for ProfilingPanel
- `RecordingDetailModal.tsx` - Recording detail modal
- `RecordingDetailModal.test.tsx` - Test suite for RecordingDetailModal
- `RecordingReplayPanel.tsx` - Recording replay panel
- `RecordingReplayPanel.test.tsx` - Test suite for RecordingReplayPanel
- `RecordingsList.tsx` - List of recordings
- `RecordingsList.test.tsx` - Test suite for RecordingsList
- `ReplayResultsModal.tsx` - Replay results modal
- `ReplayResultsModal.test.tsx` - Test suite for ReplayResultsModal
- `TestDataPanel.tsx` - Test data seeding panel
- `TestDataPanel.test.tsx` - Test suite for TestDataPanel
- `CleanupRow.tsx` - Data cleanup row component
- `CleanupRow.test.tsx` - Test suite for CleanupRow
- `SeedRow.tsx` - Data seed row component
- `SeedRow.test.tsx` - Test suite for SeedRow
- `ConfirmWithTextDialog.tsx` - Confirmation dialog with text input
- `ConfirmWithTextDialog.test.tsx` - Test suite for ConfirmWithTextDialog
- `index.ts` - Barrel exports

### exports/

- `ExportModal.tsx` - Export modal component
- `ExportProgress.tsx` - Export progress indicator
- `index.ts` - Barrel exports
- `__tests__/ExportProgress.test.tsx` - Test suite for ExportProgress

### feedback/

- `FeedbackPanel.tsx` - User feedback panel component
- `FeedbackPanel.test.tsx` - Test suite for FeedbackPanel
- `index.ts` - Barrel exports

### jobs/

- `JobsPage.tsx` - Main background jobs monitoring page
- `JobsPage.test.tsx` - Test suite for JobsPage
- `JobsList.tsx` - Jobs list container
- `JobsListItem.tsx` - Individual job list item
- `JobsEmptyState.tsx` - Empty state for jobs list
- `JobsSearchBar.tsx` - Jobs search bar with filters
- `JobsSearchBar.test.tsx` - Test suite for JobsSearchBar
- `JobActions.tsx` - Job action buttons (cancel, retry, etc.)
- `JobActions.test.tsx` - Test suite for JobActions
- `JobHeader.tsx` - Job detail header
- `JobHeader.test.tsx` - Test suite for JobHeader
- `JobDetailPanel.tsx` - Job detail panel
- `JobHistoryTimeline.tsx` - Job execution history timeline
- `JobHistoryTimeline.test.tsx` - Test suite for JobHistoryTimeline
- `JobLogsViewer.tsx` - Job logs viewer with streaming
- `JobLogsViewer.test.tsx` - Test suite for JobLogsViewer
- `JobMetadata.tsx` - Job metadata display
- `JobMetadata.test.tsx` - Test suite for JobMetadata
- `ConnectionIndicator.tsx` - WebSocket connection indicator
- `ConnectionIndicator.test.tsx` - Test suite for ConnectionIndicator
- `ConfirmDialog.tsx` - Confirmation dialog component
- `ConfirmDialog.test.tsx` - Test suite for ConfirmDialog
- `LogLine.tsx` - Individual log line component
- `LogLine.test.tsx` - Test suite for LogLine
- `StatusDot.tsx` - Job status indicator dot
- `StatusDot.test.tsx` - Test suite for StatusDot
- `TimelineEntry.tsx` - Timeline entry component
- `TimelineEntry.test.tsx` - Test suite for TimelineEntry
- `index.ts` - Barrel exports

### performance/

- `PerformanceDashboard.tsx` - Performance monitoring dashboard
- `PerformanceDashboard.test.tsx` - Test suite for PerformanceDashboard
- `PerformanceCharts.tsx` - Performance metric charts
- `PerformanceCharts.test.tsx` - Test suite for PerformanceCharts
- `PerformanceAlerts.tsx` - Performance alerts display
- `PerformanceAlerts.test.tsx` - Test suite for PerformanceAlerts
- `index.ts` - Barrel exports

## Navigation

Each subdirectory contains its own `AGENTS.md` with detailed component documentation:

- `ai/AGENTS.md` - AI Performance and Audit page components (updated with A/B testing components)
- `ai-audit/AGENTS.md` - AI audit placeholder (components live in ai/)
- `ai-performance/AGENTS.md` - AI performance summary row component
- `alerts/AGENTS.md` - Alert management, modular architecture, and rule configuration
- `analytics/AGENTS.md` - Analytics, baseline monitoring, and anomaly detection (NEW)
- `audit/AGENTS.md` - Audit log viewing and filtering
- `common/AGENTS.md` - Shared component patterns and APIs (updated with loading/error boundaries)
- `dashboard/AGENTS.md` - Dashboard widget details and data flow
- `detection/AGENTS.md` - Bounding box overlays and detection visualization
- `entities/AGENTS.md` - Entity tracking and re-identification (updated with ReidHistoryPanel)
- `events/AGENTS.md` - Event cards, timeline, and detail modals
- `layout/AGENTS.md` - Application shell and navigation (Layout, Header, Sidebar)
- `logs/AGENTS.md` - Log viewing and filtering dashboard
- `search/AGENTS.md` - Full-text search components
- `settings/AGENTS.md` - Configuration pages and settings
- `status/AGENTS.md` - AI service health status and degradation display
- `system/AGENTS.md` - System monitoring components with redesigned page
- `tracing/AGENTS.md` - Distributed tracing and trace visualization
- `video/AGENTS.md` - Video playback components
- `zones/AGENTS.md` - Zone management and configuration

## Entry Points

**Start here:** \`layout/Layout.tsx\` - Understand the application shell
**Then explore:** \`dashboard/DashboardPage.tsx\` - See how the main page is assembled
**For components:** \`common/RiskBadge.tsx\` - Example of a reusable component
