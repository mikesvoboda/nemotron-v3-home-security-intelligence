import { AlertTriangle } from 'lucide-react';
import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import ActivityFeed, { type ActivityEvent } from './ActivityFeed';
import CameraGrid, { type CameraStatus } from './CameraGrid';
import DashboardLayout from './DashboardLayout';
import GpuStats from './GpuStats';
import PipelineQueues from './PipelineQueues';
import PipelineTelemetry from './PipelineTelemetry';
import StatsRow from './StatsRow';
import { SummaryCards } from './SummaryCards';
import { useAIMetrics } from '../../hooks/useAIMetrics';
import { useDateRangeState } from '../../hooks/useDateRangeState';
import { useEventStream, type SecurityEvent } from '../../hooks/useEventStream';
import { useRecentEventsQuery } from '../../hooks/useRecentEventsQuery';
import { useSummaries } from '../../hooks/useSummaries';
import { useSystemStatus } from '../../hooks/useSystemStatus';
import { useThrottledValue } from '../../hooks/useThrottledValue';
import {
  fetchCameras,
  fetchEventStats,
  getCameraSnapshotUrl,
  type Camera,
  type EventStatsResponse,
} from '../../services/api';
import AIPerformanceSummaryRow from '../ai-performance/AIPerformanceSummaryRow';
import {
  CameraCardSkeleton,
  FeatureErrorBoundary,
  SafeErrorMessage,
  StatsCardSkeleton,
  Skeleton,
} from '../common';

/**
 * Throttle interval for WebSocket data updates (in milliseconds).
 * This reduces unnecessary re-renders in StatsRow while keeping
 * the UI responsive. 500ms provides a good balance between
 * responsiveness and performance.
 */
const WEBSOCKET_THROTTLE_INTERVAL = 500;

/**
 * Main Dashboard Page Component
 *
 * Assembles Phase 6 components into a cohesive dashboard layout:
 * - Top row: StatsRow with risk sparkline
 * - Bottom: CameraGrid (full width)
 *
 * Now with customizable widget layout via DashboardLayout.
 * GPU Statistics and Pipeline Telemetry can be enabled via the Configure button.
 *
 * Features:
 * - Real-time updates via WebSocket
 * - Loading skeletons while data loads
 * - Error boundaries for failed components
 * - NVIDIA dark theme (bg-[#121212])
 * - Customizable widget visibility and order
 */
export default function DashboardPage() {
  // Navigation hook for camera card clicks
  const navigate = useNavigate();

  // Date range state for event stats filtering (defaults to 'today')
  // URL persistence allows shareable dashboard links with date filter
  const { apiParams: dateRangeParams } = useDateRangeState({
    defaultPreset: 'today',
    persistToUrl: true,
  });

  // State for REST API data
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [eventStats, setEventStats] = useState<EventStatsResponse | null>(null);
  const [camerasLoading, setCamerasLoading] = useState(true);
  const [camerasError, setCamerasError] = useState<string | null>(null);

  // Use React Query hook for recent events (server-side limiting)
  // This replaces the previous fetchEvents({ limit: 50 }) + client-side slicing
  const {
    events: initialEvents,
    isLoading: eventsLoading,
    error: eventsError,
  } = useRecentEventsQuery({
    limit: 50, // Fetch 50 events for merging with WebSocket events
    staleTime: 30000, // 30 seconds
  });

  // WebSocket hooks for real-time data
  const { events: wsEvents, isConnected: eventsConnected } = useEventStream();
  const { status: systemStatus, isConnected: systemConnected } = useSystemStatus();

  // Fetch summaries for dashboard cards (hourly and daily summaries)
  const {
    hourly: hourlySummary,
    daily: dailySummary,
    isLoading: summariesLoading,
    error: summariesError,
    refetch: refetchSummaries,
  } = useSummaries();

  // Fetch AI metrics for the AI Performance Summary Row
  const { data: aiMetrics } = useAIMetrics({
    pollingInterval: 5000, // Refresh every 5 seconds
    enablePolling: true,
  });

  // Throttle WebSocket data to reduce StatsRow re-renders
  // This batches rapid updates within WEBSOCKET_THROTTLE_INTERVAL (500ms)
  const throttledWsEvents = useThrottledValue(wsEvents, {
    interval: WEBSOCKET_THROTTLE_INTERVAL,
  });
  const throttledSystemStatus = useThrottledValue(systemStatus, {
    interval: WEBSOCKET_THROTTLE_INTERVAL,
  });

  // Fetch cameras and event stats (events now handled by useRecentEventsQuery)
  // Re-fetches when date range changes (from useDateRangeState)
  useEffect(() => {
    async function loadInitialData() {
      setCamerasLoading(true);
      setCamerasError(null);

      try {
        // Use date range from useDateRangeState hook (YYYY-MM-DD format)
        // Convert to ISO string format for API compatibility
        const startDate = dateRangeParams.start_date
          ? new Date(dateRangeParams.start_date + 'T00:00:00').toISOString()
          : undefined;

        // Fetch cameras and event stats in parallel
        const [camerasData, statsData] = await Promise.all([
          fetchCameras(),
          fetchEventStats({ start_date: startDate }),
        ]);

        setCameras(camerasData);
        setEventStats(statsData);
      } catch (err) {
        console.error('Failed to load initial data:', err);
        setCamerasError(err instanceof Error ? err.message : 'Failed to load dashboard data');
      } finally {
        setCamerasLoading(false);
      }
    }

    void loadInitialData();
  }, [dateRangeParams.start_date]);

  // Combined loading and error states
  // Show loading only if no errors have occurred yet
  // Once an error occurs, we should stop loading and show the error state
  const hasError = camerasError !== null || eventsError !== null;
  const loading = !hasError && (camerasLoading || eventsLoading);
  const error = camerasError || (eventsError ? eventsError.message : null);

  // Merge throttled WebSocket events with initial events, avoiding duplicates
  // WebSocket events take precedence (they're newer)
  // Using throttledWsEvents to reduce StatsRow re-renders
  const mergedEvents: SecurityEvent[] = useMemo(() => {
    // Create a Set of WebSocket event IDs for deduplication
    const wsEventIds = new Set(throttledWsEvents.map((e) => String(e.id)));

    // Convert initial events to SecurityEvent format, excluding any that are also in wsEvents
    const initialSecurityEvents: SecurityEvent[] = initialEvents
      .filter((event) => !wsEventIds.has(String(event.id)))
      .map((event) => ({
        id: event.id,
        camera_id: event.camera_id,
        risk_score: event.risk_score ?? 0,
        risk_level: (event.risk_level as SecurityEvent['risk_level']) ?? 'low',
        summary: event.summary ?? '',
        started_at: event.started_at,
      }));

    // Combine: WebSocket events first (newest), then initial events
    return [...throttledWsEvents, ...initialSecurityEvents];
  }, [throttledWsEvents, initialEvents]);

  // Calculate current risk score from latest merged event
  const currentRiskScore = mergedEvents.length > 0 ? mergedEvents[0].risk_score : 0;

  // Calculate risk history from recent merged events (last 10)
  const riskHistory = mergedEvents
    .slice(0, 10)
    .reverse()
    .map((event) => event.risk_score);

  // Calculate active cameras count
  const activeCamerasCount = cameras.filter((camera) => camera.status === 'online').length;

  // Calculate events today count from stats API (accurate) plus any new WebSocket events
  // eventStats.total_events gives us the count at page load, then we add new WS events from today
  // Using throttledWsEvents to reduce StatsRow re-renders
  const eventsToday = useMemo(() => {
    // Start with stats from API (events today at time of page load)
    const statsCount = eventStats?.total_events ?? 0;

    // Count WebSocket events that are from today and not in initial events
    // (to avoid double-counting events that were already in the stats)
    const initialEventIds = new Set(initialEvents.map((e) => String(e.id)));
    const today = new Date();
    const newWsEventsToday = throttledWsEvents.filter((event) => {
      // Skip if this event was in initial load (already counted in stats)
      if (initialEventIds.has(String(event.id))) return false;

      const eventTimestamp = event.timestamp ?? event.started_at;
      if (!eventTimestamp) return false;
      const eventDate = new Date(eventTimestamp);
      return (
        eventDate.getDate() === today.getDate() &&
        eventDate.getMonth() === today.getMonth() &&
        eventDate.getFullYear() === today.getFullYear()
      );
    }).length;

    return statsCount + newWsEventsToday;
  }, [eventStats, throttledWsEvents, initialEvents]);

  // Determine system health status
  // Default to 'healthy' during initial load (before WebSocket connects)
  // This prevents "Unknown" flashing on mobile where WS connection may be slower
  // Using throttledSystemStatus to reduce StatsRow re-renders
  const systemHealth = throttledSystemStatus?.health ?? 'healthy';

  // Convert Camera[] to CameraStatus[] for CameraGrid
  const cameraStatuses: CameraStatus[] = cameras.map((camera) => ({
    id: camera.id,
    name: camera.name,
    status:
      camera.status === 'online' || camera.status === 'offline' || camera.status === 'error'
        ? camera.status
        : 'unknown',
    thumbnail_url: getCameraSnapshotUrl(camera.id),
    last_seen_at: camera.last_seen_at ?? undefined,
  }));

  // Convert merged events to ActivityEvent format for ActivityFeed
  const activityEvents: ActivityEvent[] = mergedEvents.map((event) => {
    const timestamp = event.timestamp ?? event.started_at;
    return {
      id: String(event.id),
      timestamp: timestamp || new Date().toISOString(), // Fallback to current time if both are undefined
      camera_name: cameras.find((c) => c.id === event.camera_id)?.name ?? event.camera_id,
      risk_score: event.risk_score,
      summary: event.summary,
      thumbnail_url: getCameraSnapshotUrl(event.camera_id),
    };
  });

  // Handle camera card click - navigate to timeline with camera filter
  const handleCameraClick = useCallback(
    (cameraId: string) => {
      void navigate(`/timeline?camera=${cameraId}`);
    },
    [navigate]
  );

  // Handle activity event click - navigate to timeline with event ID to open modal
  const handleEventClick = useCallback(
    (eventId: string) => {
      void navigate(`/timeline?event=${eventId}`);
    },
    [navigate]
  );

  // Render loading skeleton
  const renderLoadingSkeleton = useCallback(
    () => (
      <>
        {/* Header skeleton */}
        <div className="mb-6 md:mb-8">
          <Skeleton variant="text" width={256} height={40} className="mb-2" />
          <Skeleton variant="text" width={320} height={20} />
        </div>

        {/* Stats Row skeleton */}
        <div className="mb-6 md:mb-8">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <StatsCardSkeleton key={i} />
            ))}
          </div>
        </div>

        {/* 2-Column Layout skeleton */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr,1fr] xl:grid-cols-[2.5fr,1fr]">
          {/* Camera grid skeleton */}
          <div>
            <Skeleton variant="text" width={192} height={32} className="mb-4" />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => (
                <CameraCardSkeleton key={i} />
              ))}
            </div>
          </div>

          {/* Activity feed skeleton */}
          <div>
            <Skeleton variant="text" width={192} height={32} className="mb-4" />
            <Skeleton variant="rectangular" width="100%" height={600} className="rounded-lg" />
          </div>
        </div>
      </>
    ),
    []
  );

  // Error state
  if (error && !loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#121212] p-4 md:p-8">
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-6 text-center">
          <h2 className="mb-2 text-xl font-bold text-red-500">Error Loading Dashboard</h2>
          <SafeErrorMessage message={error} size="sm" color="gray" />
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded-md bg-red-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-800"
          >
            Reload Page
          </button>
        </div>
      </div>
    );
  }

  // Loading state with skeleton loaders (legacy wrapper for test compatibility)
  // Include the page heading for accessibility and test compatibility (NEM-XXXX)
  if (loading) {
    return (
      <div data-testid="dashboard-container" className="min-h-screen bg-[#121212] p-4 md:p-8">
        <div className="mx-auto max-w-[1920px]">
          {/* Page heading - always visible for accessibility */}
          {/* Use explicit colors to ensure WCAG AA contrast during loading state */}
          <div className="mb-6 md:mb-8">
            <h1 className="text-4xl font-bold tracking-tight text-white">Security Dashboard</h1>
            <p className="mt-1 text-sm leading-normal text-gray-400 sm:mt-2">
              Real-time AI-powered home security monitoring
            </p>
          </div>
          {renderLoadingSkeleton()}
        </div>
      </div>
    );
  }

  // Disconnected indicator for header
  const disconnectedIndicator =
    !eventsConnected && !systemConnected ? (
      <span className="ml-2 text-yellow-500">(Disconnected)</span>
    ) : null;

  // Main dashboard with customizable layout
  return (
    <div data-testid="dashboard-container">
      <DashboardLayout
        isLoading={loading}
        renderLoadingSkeleton={renderLoadingSkeleton}
        widgetProps={{
          statsRow: {
            activeCameras: activeCamerasCount,
            eventsToday: eventsToday,
            currentRiskScore: currentRiskScore,
            systemStatus: systemHealth,
            riskHistory: riskHistory.length > 0 ? riskHistory : undefined,
          },
          aiSummaryRow: {
            rtdetr: aiMetrics.rtdetr,
            nemotron: aiMetrics.nemotron,
            detectionLatency: aiMetrics.detectionLatency,
            analysisLatency: aiMetrics.analysisLatency,
            detectionQueueDepth: aiMetrics.detectionQueueDepth,
            analysisQueueDepth: aiMetrics.analysisQueueDepth,
            totalDetections: aiMetrics.totalDetections,
            totalEvents: aiMetrics.totalEvents,
            totalErrors: Object.values(aiMetrics.pipelineErrors).reduce((sum, count) => sum + count, 0),
            throughputPerMinute: aiMetrics.eventsPerMinute,
          },
          cameraGrid: {
            cameras: cameraStatuses,
            onCameraClick: handleCameraClick,
          },
          activityFeed: {
            events: activityEvents,
            maxItems: 10,
            onEventClick: handleEventClick,
            className: 'h-[600px] lg:h-[700px]',
          },
          gpuStats: {
            gpuName: 'NVIDIA RTX A5500', // GPU name from system config
            utilization: throttledSystemStatus?.gpu_utilization ?? null,
            memoryUsed: throttledSystemStatus?.gpu_memory_used ?? null,
            memoryTotal: throttledSystemStatus?.gpu_memory_total ?? null,
            temperature: throttledSystemStatus?.gpu_temperature ?? null,
            powerUsage: null, // Power not available in current WebSocket data
            inferenceFps: throttledSystemStatus?.inference_fps ?? null,
          },
          pipelineTelemetry: {
            pollingInterval: 5000,
            queueWarningThreshold: 10,
            latencyWarningThreshold: 10000,
          },
          pipelineQueues: {
            detectionQueue: 0, // Would come from telemetry API
            analysisQueue: 0, // Would come from telemetry API
            warningThreshold: 10,
          },
        }}
        renderStatsRow={(props) => (
          <>
            {disconnectedIndicator && (
              <div className="mb-2 text-sm text-yellow-500">{disconnectedIndicator}</div>
            )}
            <StatsRow {...props} />
          </>
        )}
        renderAISummaryRow={(props) => <AIPerformanceSummaryRow {...props} />}
        renderCameraGrid={(props) =>
          props ? <CameraGrid cameras={props.cameras} onCameraClick={props.onCameraClick} /> : null
        }
        renderActivityFeed={(props) =>
          props ? (
            <>
              {/* Summary Cards - hourly and daily event summaries */}
              <div className="mb-6">
                <SummaryCards
                  hourly={hourlySummary}
                  daily={dailySummary}
                  isLoading={summariesLoading}
                  error={summariesError}
                  onRetry={() => void refetchSummaries()}
                />
              </div>
              <ActivityFeed
                events={props.events}
                maxItems={props.maxItems}
                onEventClick={props.onEventClick}
                className={props.className}
              />
            </>
          ) : null
        }
        renderGpuStats={(props) =>
          props ? (
            <GpuStats
              gpuName={props.gpuName}
              utilization={props.utilization}
              memoryUsed={props.memoryUsed}
              memoryTotal={props.memoryTotal}
              temperature={props.temperature}
              powerUsage={props.powerUsage}
              inferenceFps={props.inferenceFps}
            />
          ) : null
        }
        renderPipelineTelemetry={(props) =>
          props ? (
            <PipelineTelemetry
              pollingInterval={props.pollingInterval}
              queueWarningThreshold={props.queueWarningThreshold}
              latencyWarningThreshold={props.latencyWarningThreshold}
            />
          ) : null
        }
        renderPipelineQueues={(props) =>
          props ? (
            <PipelineQueues
              detectionQueue={props.detectionQueue}
              analysisQueue={props.analysisQueue}
              warningThreshold={props.warningThreshold}
              className={props.className}
            />
          ) : null
        }
      />
    </div>
  );
}

/**
 * DashboardPage with FeatureErrorBoundary wrapper.
 *
 * Wraps the DashboardPage component in a FeatureErrorBoundary to prevent
 * errors in the Dashboard from crashing the entire application.
 * The navigation should remain functional even if the dashboard content errors.
 */
function DashboardPageWithErrorBoundary() {
  return (
    <FeatureErrorBoundary
      feature="Dashboard"
      fallback={
        <div className="flex min-h-screen flex-col items-center justify-center bg-[#121212] p-8">
          <AlertTriangle className="mb-4 h-12 w-12 text-red-400" />
          <h3 className="mb-2 text-lg font-semibold text-red-400">Dashboard Unavailable</h3>
          <p className="max-w-md text-center text-sm text-gray-400">
            Unable to load the security dashboard. Please refresh the page or try again later.
            You can still navigate to other sections using the sidebar.
          </p>
        </div>
      }
    >
      <DashboardPage />
    </FeatureErrorBoundary>
  );
}

export { DashboardPageWithErrorBoundary };
