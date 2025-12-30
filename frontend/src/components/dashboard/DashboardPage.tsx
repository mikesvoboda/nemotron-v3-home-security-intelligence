import { useEffect, useState, useMemo } from 'react';

import ActivityFeed, { type ActivityEvent } from './ActivityFeed';
import CameraGrid, { type CameraStatus } from './CameraGrid';
import GpuStats from './GpuStats';
import RiskGauge from './RiskGauge';
import StatsRow from './StatsRow';
import { useEventStream, type SecurityEvent } from '../../hooks/useEventStream';
import { useSystemStatus } from '../../hooks/useSystemStatus';
import {
  fetchCameras,
  fetchGPUStats,
  fetchEvents,
  fetchEventStats,
  getCameraSnapshotUrl,
  type Camera,
  type GPUStats,
  type Event,
  type EventStatsResponse,
} from '../../services/api';

/**
 * Main Dashboard Page Component
 *
 * Assembles Phase 6 components into a cohesive dashboard layout:
 * - Top row: RiskGauge (left), GpuStats (right)
 * - Middle: CameraGrid (full width)
 * - Bottom: ActivityFeed (full width)
 *
 * Features:
 * - Real-time updates via WebSocket
 * - Loading skeletons while data loads
 * - Error boundaries for failed components
 * - NVIDIA dark theme (bg-[#121212])
 */
export default function DashboardPage() {
  // State for REST API data
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [gpuStats, setGpuStats] = useState<GPUStats | null>(null);
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

        // Fetch cameras, GPU stats, events, and event stats in parallel
        const [camerasData, gpuData, eventsData, statsData] = await Promise.all([
          fetchCameras(),
          fetchGPUStats(),
          fetchEvents({ limit: 50 }),
          fetchEventStats({ start_date: startDate }),
        ]);

        setCameras(camerasData);
        setGpuStats(gpuData);
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

  // Poll GPU stats periodically (every 5 seconds)
  useEffect(() => {
    const interval = setInterval(() => {
      void (async () => {
        try {
          const gpuData = await fetchGPUStats();
          setGpuStats(gpuData);
        } catch (err) {
          console.error('Failed to update GPU stats:', err);
        }
      })();
    }, 5000);

    return () => clearInterval(interval);
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
  const systemHealth = systemStatus?.health ?? 'unknown';

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

  // Create a map from camera_id to camera name for quick lookups
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    cameras.forEach((camera) => {
      map.set(camera.id, camera.name);
    });
    return map;
  }, [cameras]);

  // Convert merged events to ActivityEvent[] for ActivityFeed
  // Resolve camera_name from cameras list or fall back to 'Unknown Camera'
  const activityEvents: ActivityEvent[] = mergedEvents.map((event) => ({
    id: String(event.id),
    timestamp: event.timestamp ?? event.started_at ?? new Date().toISOString(),
    camera_name: event.camera_name ?? cameraNameMap.get(event.camera_id) ?? 'Unknown Camera',
    risk_score: event.risk_score,
    summary: event.summary,
  }));

  // Error state
  if (error && !loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#121212] p-8">
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
      <div className="min-h-screen bg-[#121212] p-8">
        <div className="mx-auto max-w-[1920px]">
          {/* Header skeleton */}
          <div className="mb-8">
            <div className="h-10 w-64 animate-pulse rounded-lg bg-gray-800"></div>
          </div>

          {/* Top row skeleton */}
          <div className="mb-8 grid gap-6 lg:grid-cols-2">
            <div className="h-64 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="h-64 animate-pulse rounded-lg bg-gray-800"></div>
          </div>

          {/* Camera grid skeleton */}
          <div className="mb-8">
            <div className="mb-4 h-8 w-48 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 4 }, (_, i) => (
                <div key={i} className="h-48 animate-pulse rounded-lg bg-gray-800"></div>
              ))}
            </div>
          </div>

          {/* Activity feed skeleton */}
          <div className="mb-4 h-8 w-48 animate-pulse rounded-lg bg-gray-800"></div>
          <div className="h-96 animate-pulse rounded-lg bg-gray-800"></div>
        </div>
      </div>
    );
  }

  // Main dashboard
  return (
    <div className="min-h-screen bg-[#121212] p-8">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white">Security Dashboard</h1>
          <p className="mt-2 text-sm text-gray-400">
            Real-time AI-powered home security monitoring
            {!eventsConnected && !systemConnected && (
              <span className="ml-2 text-yellow-500">(Disconnected)</span>
            )}
          </p>
        </div>

        {/* Stats Row */}
        <div className="mb-8">
          <StatsRow
            activeCameras={activeCamerasCount}
            eventsToday={eventsToday}
            currentRiskScore={currentRiskScore}
            systemStatus={systemHealth}
          />
        </div>

        {/* Top Row: RiskGauge + GpuStats */}
        <div className="mb-8 grid gap-6 lg:grid-cols-2">
          {/* Risk Gauge */}
          <div className="rounded-lg border border-gray-800 bg-[#1A1A1A] shadow-lg">
            <div className="border-b border-gray-800 px-6 py-4">
              <h2 className="text-xl font-semibold text-white">Current Risk Level</h2>
            </div>
            <div className="flex items-center justify-center py-8">
              <RiskGauge
                value={currentRiskScore}
                history={riskHistory.length > 0 ? riskHistory : undefined}
                size="lg"
                showLabel={true}
              />
            </div>
          </div>

          {/* GPU Stats */}
          <GpuStats
            gpuName={gpuStats?.gpu_name ?? null}
            utilization={gpuStats?.utilization ?? null}
            memoryUsed={gpuStats?.memory_used ?? null}
            memoryTotal={gpuStats?.memory_total ?? null}
            temperature={gpuStats?.temperature ?? null}
            powerUsage={gpuStats?.power_usage ?? null}
            inferenceFps={gpuStats?.inference_fps ?? null}
          />
        </div>

        {/* Camera Grid */}
        <div className="mb-8">
          <h2 className="mb-4 text-2xl font-semibold text-white">Camera Status</h2>
          <CameraGrid cameras={cameraStatuses} />
        </div>

        {/* Activity Feed */}
        <div className="mb-8">
          <h2 className="mb-4 text-2xl font-semibold text-white">Live Activity</h2>
          <ActivityFeed
            events={activityEvents}
            maxItems={10}
            autoScroll={true}
            className="h-[600px]"
          />
        </div>
      </div>
    </div>
  );
}
