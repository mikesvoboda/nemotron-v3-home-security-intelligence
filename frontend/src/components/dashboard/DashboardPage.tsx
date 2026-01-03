import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import CameraGrid, { type CameraStatus } from './CameraGrid';
import RiskGauge from './RiskGauge';
import StatsRow from './StatsRow';
import { useEventStream, type SecurityEvent } from '../../hooks/useEventStream';
import { useSystemStatus } from '../../hooks/useSystemStatus';
import {
  fetchCameras,
  fetchEvents,
  fetchEventStats,
  getCameraSnapshotUrl,
  type Camera,
  type Event,
  type EventStatsResponse,
} from '../../services/api';

/**
 * Main Dashboard Page Component
 *
 * Assembles Phase 6 components into a cohesive dashboard layout:
 * - Top row: RiskGauge (full width)
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

  // Merge WebSocket events with initial events, avoiding duplicates
  // WebSocket events take precedence (they're newer)
  const mergedEvents: SecurityEvent[] = useMemo(() => {
    // Create a Set of WebSocket event IDs for deduplication
    const wsEventIds = new Set(wsEvents.map((e) => String(e.id)));

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
    return [...wsEvents, ...initialSecurityEvents];
  }, [wsEvents, initialEvents]);

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
  const eventsToday = useMemo(() => {
    // Start with stats from API (events today at time of page load)
    const statsCount = eventStats?.total_events ?? 0;

    // Count WebSocket events that are from today and not in initial events
    // (to avoid double-counting events that were already in the stats)
    const initialEventIds = new Set(initialEvents.map((e) => String(e.id)));
    const today = new Date();
    const newWsEventsToday = wsEvents.filter((event) => {
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
  }, [eventStats, wsEvents, initialEvents]);

  // Determine system health status
  // Default to 'healthy' during initial load (before WebSocket connects)
  // This prevents "Unknown" flashing on mobile where WS connection may be slower
  const systemHealth = systemStatus?.health ?? 'healthy';

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

// Handle camera card click - navigate to timeline with camera filter
  const handleCameraClick = useCallback(
    (cameraId: string) => {
      void navigate(`/timeline?camera=${cameraId}`);
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
            className="mt-4 rounded-md bg-red-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600"
          >
            Reload Page
          </button>
        </div>
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-[#121212] p-4 md:p-8">
        <div className="mx-auto max-w-[1920px]">
          {/* Header skeleton */}
          <div className="mb-6 md:mb-8">
            <div className="h-8 w-48 animate-pulse rounded-lg bg-gray-800 md:h-10 md:w-64"></div>
          </div>

          {/* Risk Gauge skeleton */}
          <div className="mb-6 md:mb-8">
            <div className="h-48 animate-pulse rounded-lg bg-gray-800 md:h-64"></div>
          </div>

          {/* Camera grid skeleton */}
          <div className="mb-6 md:mb-8">
            <div className="mb-4 h-6 w-32 animate-pulse rounded-lg bg-gray-800 md:h-8 md:w-48"></div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 4 }, (_, i) => (
                <div key={i} className="h-40 animate-pulse rounded-lg bg-gray-800 md:h-48"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Main dashboard
  return (
    <div className="min-h-screen bg-[#121212] p-4 md:p-8">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-6 md:mb-8">
          <h1 className="text-2xl font-bold text-white sm:text-3xl md:text-4xl">Security Dashboard</h1>
          <p className="mt-1 text-xs text-gray-400 sm:mt-2 sm:text-sm">
            Real-time AI-powered home security monitoring
            {!eventsConnected && !systemConnected && (
              <span className="ml-2 text-yellow-500">(Disconnected)</span>
            )}
          </p>
        </div>

        {/* Stats Row */}
        <div className="mb-6 md:mb-8">
          <StatsRow
            activeCameras={activeCamerasCount}
            eventsToday={eventsToday}
            currentRiskScore={currentRiskScore}
            systemStatus={systemHealth}
          />
        </div>

        {/* Risk Gauge - full width */}
        <div className="mb-6 md:mb-8">
          <div className="rounded-lg border border-gray-800 bg-[#1A1A1A] shadow-lg">
            <div className="border-b border-gray-800 px-4 py-3 md:px-6 md:py-4">
              <h2 className="text-lg font-semibold text-white md:text-xl">Current Risk Level</h2>
            </div>
            <div className="flex items-center justify-center py-6 md:py-8">
              <RiskGauge
                value={currentRiskScore}
                history={riskHistory.length > 0 ? riskHistory : undefined}
                size="lg"
                showLabel={true}
              />
            </div>
          </div>
        </div>

        {/* Camera Grid */}
        <div className="mb-6 md:mb-8">
          <h2 className="mb-3 text-xl font-semibold text-white md:mb-4 md:text-2xl">Camera Status</h2>
          <CameraGrid cameras={cameraStatuses} onCameraClick={handleCameraClick} />
        </div>
      </div>
    </div>
  );
}
