# Frontend Components Inventory

## Executive Summary

- **Total Components:** 358 in `/frontend/src/components/`
- **Total Pages:** 7 in `/frontend/src/pages/`
- **Total TSX Files:** 365
- **Components with Props Interfaces:** 304

## Component Directory Structure

### Major Categories

| Category  | Count | Purpose                                                 |
| --------- | ----- | ------------------------------------------------------- |
| common    | 40+   | Reusable UI (badges, buttons, modals, error boundaries) |
| events    | 32    | Event listing, display, detail, enrichment              |
| settings  | 35+   | Configuration panels and settings pages                 |
| dashboard | 20+   | Main dashboard and monitoring                           |
| zones     | 20+   | Zone management and visualization                       |
| ai        | 24    | AI performance, audit, model management                 |
| analytics | 16    | Analytics dashboards and charts                         |
| alerts    | 11    | Alert management and filtering                          |
| system    | 16    | System monitoring and health                            |
| jobs      | 16    | Background job management                               |
| entities  | 12    | Entity tracking and management                          |
| detection | 7     | Detection visualization                                 |
| audit     | 10    | Audit logging and review                                |

## Common Components (`/components/common/`)

### Badges & Indicators

| Component              | Purpose                             |
| ---------------------- | ----------------------------------- |
| RiskBadge              | Risk level with color-coded display |
| ConfidenceBadge        | Detection confidence scores         |
| ObjectTypeBadge        | Object classification               |
| AlertBadge             | Alert count indicators              |
| WebSocketStatus        | Connection status                   |
| ServiceStatusIndicator | Service health                      |
| WorkerStatusIndicator  | Worker process status               |

### Error Boundaries & Fallbacks

| Component              | Purpose                     |
| ---------------------- | --------------------------- |
| ErrorBoundary          | Generic error isolation     |
| ChunkLoadErrorBoundary | Lazy-load failures          |
| FeatureErrorBoundary   | Feature-specific errors     |
| ActionErrorBoundary    | React 19 form action errors |
| ApiErrorBoundary       | API error handling          |
| SafeErrorMessage       | Safe error display          |

### Loading & Skeleton States

| Component            | Purpose                 |
| -------------------- | ----------------------- |
| LoadingSpinner       | Animated loading        |
| Skeleton             | Placeholder during load |
| RouteLoadingFallback | Route loading state     |
| EventCardSkeleton    | Event card placeholder  |
| CameraCardSkeleton   | Camera card placeholder |
| StatsCardSkeleton    | Stats card placeholder  |
| ChartSkeleton        | Chart placeholder       |
| EntityCardSkeleton   | Entity card placeholder |
| TableRowSkeleton     | Table row placeholder   |

### Modals & Overlays

| Component          | Purpose                 |
| ------------------ | ----------------------- |
| AnimatedModal      | Modal with animations   |
| ResponsiveModal    | Responsive modal        |
| AlertDrawer        | Alert side drawer       |
| BottomSheet        | Mobile bottom sheet     |
| Lightbox           | Image viewer            |
| CommandPalette     | Command palette (Cmd+K) |
| ShortcutsHelpModal | Keyboard shortcuts      |

### User Experience

| Component              | Purpose                |
| ---------------------- | ---------------------- |
| ProductTour            | First-time onboarding  |
| ToastProvider          | Global notifications   |
| PageTransition         | Page animations        |
| AnimatedList           | List item animations   |
| PullToRefresh          | Mobile pull-to-refresh |
| ConnectionStatusBanner | Network status         |
| OfflineIndicator       | Offline mode           |
| OfflineFallback        | Offline fallback UI    |

## Dashboard Components (`/components/dashboard/`)

| Component            | Purpose                    |
| -------------------- | -------------------------- |
| DashboardPage        | Main dashboard entry point |
| CameraGrid           | Multi-camera display       |
| ActivityFeed         | Real-time event stream     |
| GpuStats             | GPU utilization metrics    |
| StatsRow             | Key statistics             |
| PipelineQueues       | Queue visualization        |
| PipelineTelemetry    | Pipeline performance       |
| SummaryCards         | Summary statistics         |
| DashboardLayout      | Customizable layout        |
| DashboardConfigModal | Widget configuration       |

## Event Components (`/components/events/`)

32 components for event management:

| Component              | Purpose                |
| ---------------------- | ---------------------- |
| EventCard              | Individual event card  |
| EventTimeline          | Chronological list     |
| EventDetailModal       | Full event details     |
| EventListView          | List view mode         |
| MobileEventCard        | Mobile-optimized card  |
| EventClusterCard       | Grouped events         |
| DeletedEventCard       | Deleted event display  |
| EventFilters           | Filter controls        |
| FilterChips            | Filter chip display    |
| EventSearch            | Search functionality   |
| ViewToggle             | View mode switching    |
| ThumbnailStrip         | Thumbnail gallery      |
| TimelineScrubber       | Timeline scrubbing     |
| ExportPanel            | Event export           |
| FeedbackForm           | User feedback          |
| EnrichmentPanel        | Detection enrichment   |
| EntityTrackingPanel    | Entity tracking        |
| ReidMatchesPanel       | Re-ID results          |
| MatchedEntitiesSection | Matched entities       |
| LiveActivitySection    | Real-time activity     |
| EventVideoPlayer       | Video playback         |
| TimeGroupedEvents      | Time-grouped view      |
| ConfidenceIndicators   | Confidence display     |
| EnrichmentBadges       | Enrichment status      |
| DetectionFeedback      | Detection corrections  |
| EntityThreatCards      | Entity threat display  |
| RiskFactorsList        | Risk breakdown         |
| RiskFactorsBreakdown   | Risk analysis          |
| RiskFlagsPanel         | Risk flags             |
| RecommendedActionCard  | Action recommendations |
| EventStatsPanel        | Event statistics       |
| DateRangePickerModal   | Date range selection   |

## Analytics Components (`/components/analytics/`)

| Component                 | Purpose                   |
| ------------------------- | ------------------------- |
| AnalyticsPage             | Main analytics dashboard  |
| ActivityHeatmap           | Activity visualization    |
| CameraUptimeCard          | Uptime metrics            |
| ClassFrequencyChart       | Detection distribution    |
| DateRangeDropdown         | Date range picker         |
| CustomDateRangePicker     | Custom date selection     |
| PipelineLatencyPanel      | Pipeline performance      |
| SceneChangePanel          | Scene change detection    |
| AnomalyConfigPanel        | Anomaly configuration     |
| DetectionTrendsCard       | Detection trends          |
| ObjectDistributionCard    | Object type distribution  |
| RiskHistoryCard           | Risk level trends         |
| RiskScoreDistributionCard | Risk distribution         |
| CameraAnalyticsDetail     | Camera-specific analytics |
| CameraAnalyticsSelector   | Camera selection          |
| CameraBaselinePanel       | Baseline activity         |
| ChartTooltip              | Custom chart tooltip      |

## AI Components (`/components/ai/` + `/components/ai-audit/`)

### Main Pages

| Component         | Purpose                  |
| ----------------- | ------------------------ |
| AIPerformancePage | AI model monitoring      |
| AIAuditPage       | Decision audit interface |
| AIServicesPage    | Service management       |

### Model Monitoring

| Component              | Purpose                  |
| ---------------------- | ------------------------ |
| ModelStatusCards       | Health and status        |
| ModelZooSection        | Model overview with VRAM |
| ModelLeaderboard       | Performance ranking      |
| ModelContributionChart | Contribution analysis    |

### Performance Metrics

| Component               | Purpose                |
| ----------------------- | ---------------------- |
| LatencyPanel            | Inference latency      |
| PipelineHealthPanel     | Pipeline health        |
| QualityScoreTrends      | Quality trend charts   |
| InsightsCharts          | Metrics visualizations |
| AIPerformanceSummaryRow | Summary row            |

### Prompt Engineering

| Component             | Purpose                |
| --------------------- | ---------------------- |
| PromptPlayground      | Prompt testing         |
| PromptABTest          | A/B testing            |
| ABTestStats           | Test statistics        |
| SuggestionDiffView    | Diff visualization     |
| SuggestionExplanation | Suggestion explanation |
| PromptVersionHistory  | Version tracking       |

## Alert Components (`/components/alerts/`)

| Component           | Purpose                 |
| ------------------- | ----------------------- |
| AlertsPage          | Main alerts page        |
| AlertCard           | Alert display card      |
| AlertFilters        | Filter controls         |
| AlertActions        | Action buttons          |
| AlertForm           | Alert creation/editing  |
| AlertRuleForm       | Rule configuration      |
| AlertCameraGroup    | Camera grouping         |
| BulkActionBar       | Bulk operations         |
| RiskThresholdSlider | Threshold configuration |
| ThresholdPreview    | Preview changes         |

## Zone Components (`/components/zones/`)

| Component             | Purpose              |
| --------------------- | -------------------- |
| ZoneEditor            | Zone drawing/editing |
| ZoneCanvas            | Canvas visualization |
| ZoneForm              | Configuration form   |
| ZoneList              | Zone listing         |
| ZoneEditorSidebar     | Editor controls      |
| CameraZoneOverlay     | Zone overlay         |
| ZoneActivityHeatmap   | Activity heatmap     |
| ZoneAlertFeed         | Alert feed           |
| ZoneAnomalyAlert      | Anomaly alerts       |
| ZoneAnomalyFeed       | Anomaly feed         |
| ZoneCrossingFeed      | Crossing events      |
| ZoneOwnershipPanel    | Ownership management |
| ZonePresenceIndicator | Presence status      |
| ZoneStatusCard        | Status display       |
| ZoneTimelineScrubber  | Timeline control     |
| ZoneTrustMatrix       | Access matrix        |

## Settings Components (`/components/settings/`)

### Main Pages

| Component             | Purpose                  |
| --------------------- | ------------------------ |
| SettingsPage          | Settings hub             |
| CamerasSettings       | Camera configuration     |
| AIModelsSettings      | Model management         |
| ProcessingSettings    | Batch processing         |
| NotificationSettings  | Notification preferences |
| StorageDashboard      | Storage management       |
| AlertRulesSettings    | Alert rules              |
| AdminSettings         | Admin panel              |
| AmbientStatusSettings | Ambient awareness        |
| HouseholdSettings     | Household members        |
| PropertyManagement    | Property settings        |

### Configuration Panels

| Component               | Purpose                |
| ----------------------- | ---------------------- |
| ModelManagementPanel    | Model management       |
| PromptManagementPanel   | Prompt management      |
| AreaCameraLinking       | Area to camera mapping |
| CalibrationPanel        | Camera calibration     |
| CleanupPreviewPanel     | Cleanup preview        |
| GpuApplyButton          | GPU apply              |
| GpuAssignmentTable      | GPU assignment         |
| GpuDeviceCard           | GPU device display     |
| GpuStrategySelector     | Assignment strategy    |
| RiskSensitivitySettings | Risk configuration     |
| SeverityThresholds      | Severity thresholds    |
| VRAMUsageCard           | VRAM display           |

## Page Components (`/frontend/src/pages/`)

| Page                        | Purpose                  |
| --------------------------- | ------------------------ |
| DataManagementPage          | Data retention           |
| GpuSettingsPage             | GPU configuration        |
| NotificationPreferencesPage | Notification preferences |
| ScheduledReportsPage        | Scheduled reports        |
| TrashPage                   | Deleted items            |
| WebhooksPage                | Webhook management       |
| ZonesPage                   | Zone intelligence        |

## Component Props Patterns

### Common Patterns

```typescript
// Basic component props
interface ComponentProps {
  children?: React.ReactNode;
  className?: string;
}

// Data display components
interface DataProps<T> {
  data: Array<T>;
  isLoading?: boolean;
  error?: Error | null;
  onRefresh?: () => void;
}

// Modal/Dialog props
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
}

// Callback-based props
interface CallbackProps<T> {
  onChange?: (value: T) => void;
  onDelete?: (id: string) => void;
  onSelect?: (item: T) => void;
}
```

## Hook Integration

Components use custom hooks from `/frontend/src/hooks/`:

| Hook                 | Usage                |
| -------------------- | -------------------- |
| useEventStream       | Real-time events     |
| useSystemStatus      | System monitoring    |
| useWebSocket         | WebSocket connection |
| useAIMetrics         | AI performance data  |
| useCamerasQuery      | Camera data          |
| useZonesQuery        | Zone data            |
| useDateRangeState    | Date filtering       |
| useRecentEventsQuery | Recent events        |
| useSceneChangeEvents | Scene changes        |
| useSummaries         | Summary statistics   |
