import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import { useEventStream, type SecurityEvent } from '../../hooks/useEventStream';
import { useSystemStatus } from '../../hooks/useSystemStatus';
import { useThrottledValue } from '../../hooks/useThrottledValue';
import {
  fetchCameras,
  fetchEvents,
  fetchEventStats,
  getCameraSnapshotUrl,
  type Camera,
  type Event,
  type EventStatsResponse,
} from '../../services/api';
import { CameraCardSkeleton, StatsCardSkeleton, Skeleton } from '../common';
import ActivityFeed, { type ActivityEvent } from './ActivityFeed';
import CameraGrid, { type CameraStatus } from './CameraGrid';
import StatsRow from './StatsRow';

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
 * Note: GPU Statistics and Pipeline Telemetry are available on the System page
 * which provides better context with RT-DETRv2/Nemotron model cards and pipeline metrics.
 * Live Activity feed is available on the Timeline page.
 *
 * Features:
 * - Real-time updates via WebSocket
 * - Loading skeletons while data loads
 * - Error boundaries for failed components
 * - NVIDIA dark theme (bg-[#121212])
 */
export default function DashboardPage() {
// Navigation hook for camera card clicks
  const navigate = useNavigate();

  // State for REST API data
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [initialEvents, setInitialEvents] = useState<Event[]>([]);
  const [eventStats, setEventStats] = useState<EventStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // WebSocket hooks for real-time data
  const { events: wsEvents, isConnected: eventsConnected } = useEventStream();
  const { status: systemStatus, isConnected: systemConnected } = useSystemStatus();

  // Throttle WebSocket data to reduce StatsRow re-renders
  // This batches rapid updates within WEBSOCKET_THROTTLE_INTERVAL (500ms)
  const throttledWsEvents = useThrottledValue(wsEvents, {
    interval: WEBSOCKET_THROTTLE_INTERVAL,
  });
  const throttledSystemStatus = useThrottledValue(systemStatus, {
    interval: WEBSOCKET_THROTTLE_INTERVAL,
  });

  // Fetch initial data including events and stats
  useEffect(() => {
    async function loadInitialData() {
      setLoading(true);
      setError(null);

      try {
        // Calculate today's date range for stats
        const today = new Date();
        const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate());
        const startDate = startOfDay.toISOString();

        // Fetch cameras, events, and event stats in parallel
        const [camerasData, eventsData, statsData] = await Promise.all([
          fetchCameras(),
          fetchEvents({ limit: 50 }),
          fetchEventStats({ start_date: startDate }),
        ]);

        setCameras(camerasData);
        setInitialEvents(eventsData.events);
        setEventStats(statsData);
      } catch (err) {
        console.error('Failed to load initial data:', err);
        setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    }

    void loadInitialData();
  }, []);

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

  // Error state
  if (error && !loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#121212] p-4 md:p-8">
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-6 text-center">
          <h2 className="mb-2 text-xl font-bold text-red-500">Error Loading Dashboard</h2>
          <p className="text-sm text-gray-300">{error}</p>
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

  // Loading state with skeleton loaders
  if (loading) {
    return (
      <div data-testid="dashboard-container" className="min-h-screen bg-[#121212] p-4 md:p-8">
        <div className="mx-auto max-w-[1920px]">
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
        </div>
      </div>
    );
  }

  // Main dashboard
  return (
    <div data-testid="dashboard-container" className="min-h-screen bg-[#121212] p-4 md:p-8">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-6 md:mb-8">
          <h1 className="text-page-title">Security Dashboard</h1>
          <p className="text-body-sm mt-1 sm:mt-2">
            Real-time AI-powered home security monitoring
            {!eventsConnected && !systemConnected && (
              <span className="ml-2 text-yellow-500">(Disconnected)</span>
            )}
          </p>
        </div>

        {/* Stats Row with integrated risk sparkline */}
        <div className="mb-6 md:mb-8">
          <StatsRow
            activeCameras={activeCamerasCount}
            eventsToday={eventsToday}
            currentRiskScore={currentRiskScore}
            systemStatus={systemHealth}
            riskHistory={riskHistory.length > 0 ? riskHistory : undefined}
          />
        </div>

        {/* 2-Column Layout: Camera Grid + Activity Feed */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr,1fr] xl:grid-cols-[2.5fr,1fr]">
          {/* Left Column: Camera Grid */}
          <div>
            <h2 className="text-section-title mb-3 md:mb-4">Camera Status</h2>
            <CameraGrid cameras={cameraStatuses} onCameraClick={handleCameraClick} />
          </div>

          {/* Right Column: Live Activity Feed */}
          <div>
            <h2 className="text-section-title mb-3 md:mb-4">Live Activity</h2>
            <ActivityFeed
              events={activityEvents}
              maxItems={10}
              onEventClick={handleEventClick}
              className="h-[600px] lg:h-[700px]"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
