# Frontend Source Directory - AI Agent Guide

## Purpose

This directory contains all React application source code including components, hooks, services, styles, and tests. It is the main workspace for frontend development.

## Entry Points

### Main Entry

- **`main.tsx`** - Application bootstrap
  - Imports React and ReactDOM
  - Imports global styles from `styles/index.css`
  - Renders `<App />` into `#root` div with `React.StrictMode`
  - Throws error if root element not found

### Root Component

- **`App.tsx`** - Root application component
  - Uses `BrowserRouter` for client-side routing
  - Wraps all routes in `<Layout />` component with error boundaries
  - Integrates React Query via `QueryClientProvider` with DevTools
  - Uses `ToastProvider` for global notifications
  - Implements lazy loading for all page components (code splitting)
  - Wraps routes in `ChunkLoadErrorBoundary` and `Suspense` for graceful loading
  - Includes `ProductTour` for first-time user onboarding
  - Defines routes for all pages (see Routes section)

### Tests

- **`App.test.tsx`** - Tests for root App component
- **`App.lazy.test.tsx`** - Tests for lazy-loaded route components

### Type Definitions

- **`vite-env.d.ts`** - Vite client type definitions for `import.meta.env`

## Directory Structure

### `/components/` - React Components

Components are organized by feature area. Each component directory contains:

- Component files (`.tsx`)
- Co-located test files (`.test.tsx`)
- Optional index files for barrel exports
- Optional README documentation

#### Feature Directories

| Directory           | Description                              |
| ------------------- | ---------------------------------------- |
| `ai/`               | AI performance and audit pages           |
| `ai-audit/`         | AI audit visualization components        |
| `ai-performance/`   | AI performance summary components        |
| `alerts/`           | Alert management page                    |
| `analytics/`        | Analytics dashboard and visualizations   |
| `audit/`            | Audit log viewer                         |
| `common/`           | Reusable UI components                   |
| `dashboard/`        | Main dashboard components                |
| `detection/`        | Object detection visualization           |
| `developer-tools/`  | Developer tools and debugging panels     |
| `entities/`         | Entity tracking page                     |
| `events/`           | Event list and detail components         |
| `exports/`          | Export modal and progress components     |
| `feedback/`         | User feedback collection components      |
| `forms/`            | Reusable form field components           |
| `jobs/`             | Background jobs management page          |
| `layout/`           | Layout, header, and sidebar              |
| `logs/`             | Application logs viewer                  |
| `performance/`      | Performance dashboard and charts         |
| `pyroscope/`        | Pyroscope profiling integration page     |
| `search/`           | Global search components                 |
| `settings/`         | Settings pages and forms                 |
| `status/`           | AI service status components             |
| `system/`           | System monitoring components             |
| `tracing/`          | Distributed tracing page                 |
| `video/`            | Video player component                   |
| `zones/`            | Zone management and visualization        |

#### `/components/common/`

Reusable UI components and utilities:

**Badges and Indicators:**
- `RiskBadge.tsx` - Displays risk level badges (low/medium/high/critical)
- `ConfidenceBadge.tsx` - Detection confidence score badge with color coding
- `ObjectTypeBadge.tsx` - Displays object type badges (person/vehicle/animal/package)
- `WebSocketStatus.tsx` - WebSocket connection status indicator with tooltip
- `ServiceStatusAlert.tsx` - Service status alert banner

**Error Handling:**
- `ErrorBoundary.tsx` - Generic error boundary with customizable title/description
- `ChunkLoadErrorBoundary.tsx` - Handles lazy-loaded chunk failures with retry
- `FeatureErrorBoundary.tsx` - Feature-specific error isolation

**Loading and Transitions:**
- `LoadingSpinner.tsx` - Animated loading indicator
- `RouteLoadingFallback.tsx` - Loading state for lazy-loaded routes
- `PageTransition.tsx` - Animated page transitions
- `Skeleton.tsx` - Content placeholder during loading

**Modals and Overlays:**
- `Lightbox.tsx` - Full-size image viewer with navigation
- `AnimatedModal.tsx` - Modal with entrance/exit animations
- `ShortcutsHelpModal.tsx` - Keyboard shortcuts help dialog
- `CommandPalette.tsx` - Command palette (Cmd+K) for quick navigation

**User Experience:**
- `ProductTour.tsx` - Interactive onboarding tour for first-time users
- `ToastProvider.tsx` - Global toast notification system
- `InstallBanner.tsx` - PWA installation prompt
- `OfflineFallback.tsx` - Offline state display
- `SecureContextWarning.tsx` - HTTPS requirement warning

**Content Display:**
- `EmptyState.tsx` - Empty state placeholder with icon and action
- `TruncatedText.tsx` - Text truncation with tooltip
- `AnimatedList.tsx` - Animated list with enter/exit transitions
- `Button.tsx` - Styled button component
- `ScheduleSelector.tsx` - Schedule time selection component

**Exports:**
- `index.ts` - Barrel export for all components

#### `/components/ai/`

AI performance monitoring and audit pages:

**Pages:**
- `AIPerformancePage.tsx` - Main AI performance monitoring dashboard
- `AIAuditPage.tsx` - AI decision audit and analysis page

**Model Monitoring:**
- `ModelStatusCards.tsx` - Model health and status cards
- `ModelZooSection.tsx` - Model zoo overview with VRAM stats
- `ModelLeaderboard.tsx` - Model performance ranking
- `ModelContributionChart.tsx` - Model contribution visualization

**Performance Metrics:**
- `LatencyPanel.tsx` - Inference latency metrics
- `PipelineHealthPanel.tsx` - AI pipeline health indicators
- `QualityScoreTrends.tsx` - Quality score trend charts
- `InsightsCharts.tsx` - AI insights visualizations

**Prompt Engineering:**
- `PromptPlayground.tsx` - Interactive prompt testing environment
- `PromptABTest.tsx` - A/B testing for prompts
- `ABTestStats.tsx` - A/B test statistics display
- `SuggestionDiffView.tsx` - Diff view for prompt suggestions
- `SuggestionExplanation.tsx` - Explanation for AI suggestions

**Audit:**
- `BatchAuditModal.tsx` - Batch audit modal dialog
- `RecommendationsPanel.tsx` - AI recommendations display

**Exports:**
- `index.ts` - Barrel export

#### `/components/ai-audit/`

AI audit visualization components:

- `AuditProgressBar.tsx` - Audit progress indicator
- `AuditResultsTable.tsx` - Audit results table display
- `ModelContributionChart.tsx` - Model contribution visualization
- `index.ts` - Barrel export

#### `/components/ai-performance/`

AI performance summary components:

- `AIPerformanceSummaryRow.tsx` - Performance summary row component

#### `/components/analytics/`

Analytics dashboard and visualization components:

- `AnalyticsPage.tsx` - Main analytics dashboard page
- `ActivityHeatmap.tsx` - Activity heatmap visualization
- `ClassFrequencyChart.tsx` - Detection class frequency chart
- `PipelineLatencyPanel.tsx` - Pipeline latency metrics panel
- `SceneChangePanel.tsx` - Scene change detection panel
- `AnomalyConfigPanel.tsx` - Anomaly detection configuration
- `index.ts` - Barrel export

#### `/components/layout/`

Application layout and navigation:

- `Layout.tsx` - Main layout wrapper with header and sidebar
- `Header.tsx` - Top navigation bar with branding and system status
- `Sidebar.tsx` - Left navigation menu with icon buttons

#### `/components/dashboard/`

Main dashboard components:

- `DashboardPage.tsx` - Main dashboard view with real-time monitoring
- `CameraGrid.tsx` - Multi-camera grid display
- `ActivityFeed.tsx` - Real-time event activity stream
- `GpuStats.tsx` - GPU utilization and metrics display
- `StatsRow.tsx` - Dashboard statistics row with integrated risk sparkline
- `PipelineQueues.tsx` - Pipeline queue depths visualization
- `PipelineTelemetry.tsx` - Pipeline performance telemetry display

#### `/components/detection/`

Object detection visualization:

- `BoundingBoxOverlay.tsx` - Renders detection boxes over images
- `DetectionImage.tsx` - Displays image with detection overlays
- `DetectionThumbnail.tsx` - Thumbnail with detection box
- `Example.tsx` - Example usage component
- `index.ts` - Barrel export
- `README.md` - Documentation

#### `/components/events/`

Event-related components:

- `EventCard.tsx` - Individual event card with thumbnail and risk badge
- `EventTimeline.tsx` - Chronological event list with filtering
- `EventDetailModal.tsx` - Full event details modal
- `ExportPanel.tsx` - Event data export functionality
- `ThumbnailStrip.tsx` - Horizontal strip of event thumbnails
- `index.ts` - Barrel export

#### `/components/logs/`

System logs viewing via Grafana/Loki:

- `LogsPage.tsx` - Main logs page embedding Grafana Loki dashboard
- `LogsPage.test.tsx` - Test suite for LogsPage

#### `/components/settings/`

Settings page components:

- `SettingsPage.tsx` - Main settings page with tabbed navigation
- `CamerasSettings.tsx` - Camera management (add, edit, delete)
- `AIModelsSettings.tsx` - AI model status and GPU memory
- `ProcessingSettings.tsx` - Batch processing and retention config
- `NotificationSettings.tsx` - Notification preferences
- `StorageDashboard.tsx` - Storage management and cleanup
- `DlqMonitor.tsx` - Dead letter queue monitoring
- `index.ts` - Barrel export
- `README.md` - Documentation
- `AIModelsSettings.example.tsx` - Example usage
- `ProcessingSettings.example.tsx` - Example usage

#### `/components/system/`

System monitoring:

- `SystemMonitoringPage.tsx` - System health and metrics page
- `WorkerStatusPanel.tsx` - Background workers status display
- `AiModelsPanel.tsx` - AI model status panel
- `ContainersPanel.tsx` - Container status panel
- `DatabasesPanel.tsx` - Database status panel
- `HostSystemPanel.tsx` - Host system metrics panel
- `PerformanceAlerts.tsx` - Performance alerts display
- `TimeRangeSelector.tsx` - Time range selection component
- `index.ts` - Barrel export

#### `/components/alerts/`

Alert management:

- `AlertsPage.tsx` - Alert listing and management

#### `/components/entities/`

Entity tracking:

- `EntitiesPage.tsx` - Entity tracking page

#### `/components/video/`

Video playback:

- `VideoPlayer.tsx` - Video player component with controls
- `index.ts` - Barrel export

#### `/components/audit/`

Audit log components:

- `AuditLogPage.tsx` - Main audit log page
- `AuditTable.tsx` - Audit log entries table
- `AuditFilters.tsx` - Audit log filtering controls
- `AuditDetailModal.tsx` - Audit entry detail modal
- `AuditStatsCards.tsx` - Audit statistics cards
- `index.ts` - Barrel export

#### `/components/search/`

Global search components:

- `SearchBar.tsx` - Main search bar with autocomplete
- `SearchResultCard.tsx` - Individual search result card
- `SearchResultsPanel.tsx` - Search results panel
- `index.ts` - Barrel export

#### `/components/developer-tools/`

Developer tools and debugging components:

- `DeveloperToolsPage.tsx` - Main developer tools page
- `CircuitBreakerDebugPanel.tsx` - Circuit breaker state debugging
- `ConfigInspectorPanel.tsx` - Configuration inspection panel
- `ConfirmWithTextDialog.tsx` - Confirmation dialog with text input
- `LogLevelPanel.tsx` - Log level configuration panel
- `MemorySnapshotPanel.tsx` - Memory snapshot debugging
- `ProfilingPanel.tsx` - Performance profiling panel
- `RecordingDetailModal.tsx` - Recording detail modal
- `RecordingReplayPanel.tsx` - Recording replay functionality
- `RecordingsList.tsx` - List of recordings
- `ReplayResultsModal.tsx` - Replay results display modal
- `CleanupRow.tsx` - Cleanup action row
- `SeedRow.tsx` - Seed data row
- `TestDataPanel.tsx` - Test data management panel
- `index.ts` - Barrel export

#### `/components/exports/`

Export functionality components:

- `ExportModal.tsx` - Export configuration modal
- `ExportProgress.tsx` - Export progress display
- `index.ts` - Barrel export

#### `/components/feedback/`

User feedback collection:

- `FeedbackPanel.tsx` - User feedback collection panel
- `index.ts` - Barrel export

#### `/components/forms/`

Reusable form components:

- `FormField.tsx` - Reusable form field wrapper
- `SubmitButton.tsx` - Form submit button with loading state
- `index.ts` - Barrel export

#### `/components/jobs/`

Background jobs management:

- `JobsPage.tsx` - Main jobs management page
- `JobsList.tsx` - List of background jobs
- `JobsListItem.tsx` - Individual job list item
- `JobDetailPanel.tsx` - Job detail side panel
- `JobHeader.tsx` - Job header display
- `JobMetadata.tsx` - Job metadata display
- `JobActions.tsx` - Job action buttons
- `JobLogsViewer.tsx` - Job logs viewer
- `JobHistoryTimeline.tsx` - Job history timeline
- `JobsSearchBar.tsx` - Jobs search and filter bar
- `JobsEmptyState.tsx` - Empty state for no jobs
- `ConfirmDialog.tsx` - Confirmation dialog
- `ConnectionIndicator.tsx` - Connection status indicator
- `StatusDot.tsx` - Job status indicator dot
- `TimelineEntry.tsx` - Timeline entry component
- `LogLine.tsx` - Log line display
- `index.ts` - Barrel export

#### `/components/performance/`

Performance monitoring dashboard:

- `PerformanceDashboard.tsx` - Main performance dashboard
- `PerformanceCharts.tsx` - Performance metric charts
- `PerformanceAlerts.tsx` - Performance alert display
- `index.ts` - Barrel export

#### `/components/pyroscope/`

Pyroscope profiling integration:

- `PyroscopePage.tsx` - Pyroscope profiling page
- `index.ts` - Barrel export

#### `/components/status/`

AI service status components:

- `AIServiceStatus.tsx` - AI service health status display

#### `/components/tracing/`

Distributed tracing components:

- `TracingPage.tsx` - Distributed tracing visualization page
- `index.ts` - Barrel export

#### `/components/zones/`

Zone management and visualization:

- `ZoneEditor.tsx` - Zone drawing and editing
- `ZoneCanvas.tsx` - Canvas for zone visualization
- `ZoneForm.tsx` - Zone configuration form
- `ZoneList.tsx` - List of zones
- `ZoneEditorSidebar.tsx` - Zone editor sidebar
- `CameraZoneOverlay.tsx` - Zone overlay on camera view
- `ZoneActivityHeatmap.tsx` - Zone activity heatmap
- `ZoneAlertFeed.tsx` - Zone alert feed
- `ZoneAnomalyAlert.tsx` - Zone anomaly alert display
- `ZoneAnomalyFeed.tsx` - Zone anomaly feed
- `ZoneCrossingFeed.tsx` - Zone crossing event feed
- `ZoneOwnershipPanel.tsx` - Zone ownership management
- `ZonePresenceIndicator.tsx` - Zone presence indicator
- `ZoneStatusCard.tsx` - Zone status card
- `ZoneTimelineScrubber.tsx` - Zone timeline scrubber
- `ZoneTrustMatrix.tsx` - Zone trust matrix visualization
- `zonePresenceUtils.ts` - Zone presence utility functions
- `index.ts` - Barrel export

### `/config/` - Application Configuration

| File                  | Purpose                                     |
| --------------------- | ------------------------------------------- |
| `env.ts`              | Environment variable validation and access  |
| `pageDocumentation.ts`| Page documentation configuration            |
| `tourSteps.ts`        | Product tour step definitions               |

### `/contexts/` - React Contexts

Global state management via React Context:

| File                      | Purpose                        |
| ------------------------- | ------------------------------ |
| `AnnouncementContext.tsx` | System announcements           |
| `CameraContext.tsx`       | Camera state and selection     |
| `DebugModeContext.tsx`    | Debug mode toggle              |
| `HealthContext.tsx`       | System health state            |
| `MetricsContext.tsx`      | Metrics data context           |
| `SystemDataContext.tsx`   | System-wide data context       |
| `ToastContext.tsx`        | Toast notification context     |
| `index.ts`                | Barrel export                  |

Each context has a co-located `.test.tsx` file.

### `/mocks/` - MSW Mock Server

Mock Service Worker handlers for testing:

| File          | Purpose                  |
| ------------- | ------------------------ |
| `handlers.ts` | MSW request handlers     |
| `server.ts`   | MSW server setup         |

### `/pages/` - Additional Page Components

Page components not in feature directories:

| File                             | Purpose                       |
| -------------------------------- | ----------------------------- |
| `DataManagementPage.tsx`         | Data management settings page |
| `GpuSettingsPage.tsx`            | GPU configuration settings    |
| `NotificationPreferencesPage.tsx`| Notification preferences      |
| `TrashPage.tsx`                  | Deleted items / trash page    |
| `ZonesPage.tsx`                  | Zones management page         |

Each page has a co-located `.test.tsx` file.

### `/schemas/` - Validation Schemas

Zod schemas for runtime validation:

| File          | Purpose                       |
| ------------- | ----------------------------- |
| `alert.ts`    | Alert data schemas            |
| `alertRule.ts`| Alert rule validation schemas |
| `camera.ts`   | Camera data schemas           |
| `index.ts`    | Barrel export                 |

### `/stores/` - State Stores

Zustand stores for global state management:

| File                        | Purpose                            |
| --------------------------- | ---------------------------------- |
| `dashboardConfig.ts`        | Dashboard configuration store      |
| `dashboard-config-store.ts` | Dashboard config store (alternate) |
| `middleware.ts`             | Zustand middleware utilities       |
| `prometheus-alert-store.ts` | Prometheus alert state             |
| `rate-limit-store.ts`       | Rate limiting state                |
| `realtime-metrics-store.ts` | Real-time metrics state            |
| `storage-status-store.ts`   | Storage status state               |
| `worker-status-store.ts`    | Worker status state                |

Each store has a co-located `.test.ts` file.

### `/theme/` - Theme Configuration

| File        | Purpose                                   |
| ----------- | ----------------------------------------- |
| `colors.ts` | Color palette and theme color definitions |
| `index.ts`  | Barrel export                             |

### `/hooks/` - Custom React Hooks

| Hook                        | Purpose                                             | Exported |
| --------------------------- | --------------------------------------------------- | -------- |
| `useWebSocket.ts`           | WebSocket connection management with auto-reconnect | Yes      |
| `useWebSocketStatus.ts`     | Enhanced WebSocket with channel status tracking     | Yes      |
| `useConnectionStatus.ts`    | Unified status for all WS channels (events/system)  | Yes      |
| `useEventStream.ts`         | Event stream subscription for `/ws/events`          | Yes      |
| `useSystemStatus.ts`        | System status monitoring via `/ws/system`           | Yes      |
| `useGpuHistory.ts`          | GPU metrics history with polling                    | Yes      |
| `useHealthStatus.ts`        | Health status polling                               | Yes      |
| `usePerformanceMetrics.ts`  | Performance metrics collection and tracking         | Yes      |
| `useAIMetrics.ts`           | AI performance metrics from multiple endpoints      | Yes      |
| `useDetectionEnrichment.ts` | Detection enrichment data fetching                  | Yes      |
| `useModelZooStatus.ts`      | Model Zoo status with VRAM stats                    | Yes      |
| `useSavedSearches.ts`       | Saved searches in localStorage                      | Yes      |
| `useStorageStats.ts`        | Storage/disk usage polling with cleanup preview     | No       |
| `useServiceStatus.ts`       | Service health status tracking                      | No       |
| `useSidebarContext.ts`      | Context hook for mobile sidebar state               | No       |
| `webSocketManager.ts`       | Singleton WebSocket connection manager              | No       |
| `index.ts`                  | Barrel export for exported hooks                    | N/A      |

Each hook has a co-located `.test.ts` file.

### `/services/` - API Client and Services

| File                       | Purpose                                          |
| -------------------------- | ------------------------------------------------ |
| `api.ts`                   | REST API client with typed fetch wrappers        |
| `auditApi.ts`              | AI pipeline audit API client                     |
| `promptManagementApi.ts`   | Prompt management API client                     |
| `abTestService.ts`         | A/B testing service                              |
| `queryClient.ts`           | React Query client configuration                 |
| `interceptors.ts`          | Request/response interceptors                    |
| `logger.ts`                | Client-side structured logging                   |
| `metricsParser.ts`         | Prometheus text format parser                    |
| `sentry.ts`                | Sentry error tracking integration                |
| `rum.ts`                   | Real User Monitoring (RUM) service               |

**Test Files:**

| File                          | Purpose                                      |
| ----------------------------- | -------------------------------------------- |
| `api.test.ts`                 | API client tests                             |
| `api.abort.test.ts`           | Request cancellation tests                   |
| `api.timeout.test.ts`         | Request timeout tests                        |
| `api.sentry.test.ts`          | Sentry integration tests                     |
| `api.missing-coverage.test.ts`| Coverage gap tests                           |
| `auditApi.test.ts`            | Audit API client tests                       |
| `promptManagementApi.test.ts` | Prompt management API tests                  |
| `abTestService.test.ts`       | A/B test service tests                       |
| `queryClient.test.ts`         | Query client tests                           |
| `interceptors.test.ts`        | Interceptor tests                            |
| `logger.test.ts`              | Logger tests                                 |
| `metricsParser.test.ts`       | Metrics parser tests                         |
| `sentry.test.ts`              | Sentry integration tests                     |
| `rum.test.ts`                 | RUM service tests                            |

The `api.ts` file re-exports all types from `types/generated/` for convenience.

### `/styles/` - Global Styles

- **`index.css`** - Global CSS with Tailwind directives
  - `@tailwind base` - Base styles reset
  - `@tailwind components` - Component classes
  - `@tailwind utilities` - Utility classes
  - Custom component classes (`.nvidia-card`, `.btn-primary`, etc.)
  - Custom utilities (`.glass`, `.text-gradient-nvidia`, `.glow-nvidia`)
  - Dark theme scrollbar styling
  - Selection color with NVIDIA green

### `/test/` - Test Setup

- **`setup.ts`** - Vitest test configuration
  - Extends expect with jest-dom matchers
  - Mocks ResizeObserver and IntersectionObserver for jsdom
  - Fixes HeadlessUI focus issues
  - Cleanup after each test

### `/types/` - TypeScript Types

- **`generated/`** - Auto-generated from backend OpenAPI
  - `api.ts` - Full OpenAPI types (DO NOT EDIT)
  - `index.ts` - Re-exports with convenient aliases
- **`performance.ts`** - Performance metrics type definitions
- **`enrichment.ts`** - Detection enrichment types (vehicle, pet, person, weather)

### `/utils/` - Utility Functions

| File           | Purpose                                                                      |
| -------------- | ---------------------------------------------------------------------------- |
| `index.ts`     | Barrel export for all utility modules                                        |
| `risk.ts`      | Risk level utilities (getRiskLevel, getRiskColor, getRiskLabel)              |
| `confidence.ts`| Detection confidence utilities (levels, colors, Tailwind classes, array ops) |
| `time.ts`      | Time formatting (formatDuration, getDurationLabel, isEventOngoing)           |
| `webcodecs.ts` | WebCodecs API feature detection and fallback helpers                         |

Each utility has a co-located `.test.ts` file.

### `/test-utils/` - Test Utilities

| File                     | Purpose                                                   |
| ------------------------ | --------------------------------------------------------- |
| `index.ts`               | Central export point for all test utilities               |
| `renderWithProviders.tsx`| Custom render function wrapping components with providers |
| `factories.ts`           | Test data factories for events, detections, cameras       |
| `test-utils.test.tsx`    | Tests for test utilities                                  |

Import test utilities from `../test-utils` in test files.

### `/__tests__/` - Additional Tests

- `api-contracts.test.ts` - API contract validation tests
- `lighthouserc.test.ts` - Lighthouse CI configuration tests
- `matchers.ts` - Custom test matchers
- `matchers.test.ts` - Tests for custom matchers
- `AGENTS.md` - Test directory documentation

## Application Routes

All routes use lazy loading for code splitting. Defined in `App.tsx`:

| Path          | Component              | Description                        |
| ------------- | ---------------------- | ---------------------------------- |
| `/`           | `DashboardPage`        | Main dashboard with live monitoring|
| `/timeline`   | `EventTimeline`        | Chronological event timeline       |
| `/analytics`  | `AnalyticsPage`        | Analytics and insights dashboard   |
| `/alerts`     | `AlertsPage`           | Alert management and history       |
| `/entities`   | `EntitiesPage`         | Entity tracking and management     |
| `/logs`       | `LogsPage`             | System logs via Grafana/Loki       |
| `/audit`      | `AuditLogPage`         | System audit log                   |
| `/ai`         | `AIPerformancePage`    | AI model performance monitoring    |
| `/ai-audit`   | `AIAuditPage`          | AI decision audit and analysis     |
| `/system`     | `SystemMonitoringPage` | System health and metrics          |
| `/settings`   | `SettingsPage`         | Application settings               |

### Lazy Loading Pattern

All page components use React's `lazy()` for code splitting:

```typescript
// Direct default export
const DashboardPage = lazy(() => import('./components/dashboard/DashboardPage'));

// Named export from barrel file (requires .then() transformation)
const AnalyticsPage = lazy(() =>
  import('./components/analytics').then((module) => ({ default: module.AnalyticsPage }))
);
```

Routes are wrapped with error handling and loading states:

```typescript
<ErrorBoundary>
  <Layout>
    <ChunkLoadErrorBoundary>
      <Suspense fallback={<RouteLoadingFallback />}>
        <PageTransition>
          <Routes>...</Routes>
        </PageTransition>
      </Suspense>
    </ChunkLoadErrorBoundary>
  </Layout>
</ErrorBoundary>
```

## Testing

All test files use naming convention: `*.test.ts` or `*.test.tsx`

### Test Coverage Thresholds

- Statements: 83%
- Branches: 77%
- Functions: 81%
- Lines: 84%

### Test Setup

- Environment: jsdom
- Setup file: `test/setup.ts`
- Provider: v8 coverage
- Pool: forks (single fork for memory optimization)

## Type Safety

TypeScript strict mode with:

- `strict: true`
- `noUnusedLocals: true`
- `noUnusedParameters: true`
- `noFallthroughCasesInSwitch: true`

## Styling Guidelines

### Tailwind Colors

| Color                     | Usage                        |
| ------------------------- | ---------------------------- |
| `bg-background`           | Page background (`#0E0E0E`)  |
| `bg-panel`                | Panel background (`#1A1A1A`) |
| `bg-card`                 | Card background (`#1E1E1E`)  |
| `bg-primary-500`          | Primary action (`#76B900`)   |
| `bg-risk-low/medium/high` | Risk level indicators        |
| `text-text-primary`       | Main text (`#FFFFFF`)        |
| `text-text-secondary`     | Secondary text (`#A0A0A0`)   |
| `text-text-muted`         | Muted text (`#707070`)       |

### Custom CSS Classes

| Class                                  | Purpose                |
| -------------------------------------- | ---------------------- |
| `.nvidia-card`                         | Standard card styling  |
| `.nvidia-card-hover`                   | Card with hover effect |
| `.nvidia-panel`                        | Panel styling          |
| `.btn-primary`                         | Primary button         |
| `.btn-secondary`                       | Secondary button       |
| `.btn-ghost`                           | Ghost button           |
| `.nvidia-input`                        | Input field styling    |
| `.risk-badge-low/medium/high`          | Risk badges            |
| `.status-online/offline/warning/error` | Status dots            |
| `.glass`                               | Glass morphism effect  |
| `.glow-nvidia`                         | NVIDIA green glow      |

## Common Imports

```typescript
// React
import { useState, useEffect, useCallback } from 'react';

// Routing
import { useNavigate, useParams, Link } from 'react-router-dom';

// API client and types
import { fetchCameras, fetchHealth } from '../services/api';
import type { Camera, Event, HealthResponse } from '../services/api';

// Hooks
import {
  useWebSocket,
  useEventStream,
  useSystemStatus,
  useConnectionStatus,
  useStorageStats,
} from '../hooks';

// Components
import { RiskBadge, ObjectTypeBadge, ConfidenceBadge } from '../components/common';

// Utilities
import { getRiskLevel, getRiskColor, getRiskLevelWithThresholds } from '../utils/risk';
import { getConfidenceLevel, formatConfidencePercent } from '../utils/confidence';
import { formatDuration, isEventOngoing } from '../utils/time';

// Icons
import { Activity, Camera, Settings, AlertTriangle } from 'lucide-react';

// Tremor (data visualization)
import { Card, Title, Text, DonutChart, BarChart } from '@tremor/react';

// Headless UI (accessible components)
import { Dialog, Transition, Tab } from '@headlessui/react';
```

## Best Practices

1. **Co-locate tests**: Every component/hook/utility must have a test file
2. **Use TypeScript**: No `any` types unless absolutely necessary
3. **Follow component structure**:
   - Props interface at top
   - Component function with typed props
   - Return JSX with Tailwind classes
   - Export default at bottom
4. **API calls**: Use functions from `services/api.ts`
5. **WebSocket**: Use hooks from `/hooks/` for connections
6. **Styling**: Prefer existing custom classes, use Tailwind utilities for one-offs
7. **Testing**: Test user-visible behavior, not implementation details
8. **File organization**: Components in feature directories, hooks in `/hooks/`

## Notes

- **Routing**: Uses react-router-dom v7
- **State Management**: React Query for server state, React hooks for local state
- **WebSocket channels**: `/ws/events` and `/ws/system`
- **Media URLs**: `/api/media/cameras/{cameraId}/{filename}`
- **Environment variables**: Use `import.meta.env.VITE_*`
- **Hot reload**: Vite HMR for instant updates
- **Error Tracking**: Sentry integration for production error monitoring
- **Performance**: Real User Monitoring (RUM) for performance tracking
