import { useEffect, useState } from 'react';

import ActivityFeed, { type ActivityEvent } from './ActivityFeed';
import CameraGrid, { type CameraStatus } from './CameraGrid';
import GpuStats from './GpuStats';
import RiskGauge from './RiskGauge';
import StatsRow from './StatsRow';
import { useEventStream } from '../../hooks/useEventStream';
import { useSystemStatus } from '../../hooks/useSystemStatus';
import { fetchCameras, fetchGPUStats, type Camera, type GPUStats } from '../../services/api';

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // WebSocket hooks for real-time data
  const { events, isConnected: eventsConnected } = useEventStream();
  const { status: systemStatus, isConnected: systemConnected } = useSystemStatus();

  // Fetch initial data
  useEffect(() => {
    async function loadInitialData() {
      setLoading(true);
      setError(null);

      try {
        // Fetch cameras and GPU stats in parallel
        const [camerasData, gpuData] = await Promise.all([
          fetchCameras(),
          fetchGPUStats(),
        ]);

        setCameras(camerasData);
        setGpuStats(gpuData);
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

  // Calculate current risk score from system status or latest event
  const currentRiskScore = events.length > 0 ? events[0].risk_score : 0;

  // Calculate risk history from recent events (last 10)
  const riskHistory = events.slice(0, 10).reverse().map((event) => event.risk_score);

  // Calculate active cameras count
  const activeCamerasCount = cameras.filter((camera) => camera.status === 'active').length;

  // Calculate events today count
  const eventsToday = events.filter((event) => {
    const eventDate = new Date(event.timestamp);
    const today = new Date();
    return (
      eventDate.getDate() === today.getDate() &&
      eventDate.getMonth() === today.getMonth() &&
      eventDate.getFullYear() === today.getFullYear()
    );
  }).length;

  // Determine system health status
  const systemHealth = systemStatus?.health ?? 'unknown';

  // Convert Camera[] to CameraStatus[] for CameraGrid
  const cameraStatuses: CameraStatus[] = cameras.map((camera) => ({
    id: camera.id,
    name: camera.name,
    status: camera.status === 'active' ? 'online' : camera.status === 'inactive' ? 'offline' : 'unknown',
    last_seen_at: camera.last_seen_at ?? undefined,
  }));

  // Convert SecurityEvent[] to ActivityEvent[] for ActivityFeed
  const activityEvents: ActivityEvent[] = events.map((event) => ({
    id: event.id,
    timestamp: event.timestamp,
    camera_name: event.camera_name,
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
            utilization={gpuStats?.utilization ?? null}
            memoryUsed={gpuStats?.memory_used ?? null}
            memoryTotal={gpuStats?.memory_total ?? null}
            temperature={gpuStats?.temperature ?? null}
            inferenceFps={gpuStats?.inference_fps ?? null}
          />
        </div>

        {/* Camera Grid */}
        <div className="mb-8">
          <h2 className="mb-4 text-2xl font-semibold text-white">Camera Status</h2>
          <CameraGrid
            cameras={cameraStatuses}
          />
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
