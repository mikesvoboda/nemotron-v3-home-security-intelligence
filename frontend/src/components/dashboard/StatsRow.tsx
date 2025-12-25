import { Activity, Calendar, Camera, Shield } from 'lucide-react';
import { useMemo } from 'react';

import { getRiskColor, getRiskLabel, getRiskLevel } from '../../utils/risk';

export interface StatsRowProps {
  /** Number of active cameras */
  activeCameras: number;
  /** Total number of events today */
  eventsToday: number;
  /** Current risk score (0-100) */
  currentRiskScore: number;
  /** System health status */
  systemStatus: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  /** Additional CSS classes */
  className?: string;
}

/**
 * StatsRow displays key metrics in the dashboard header area.
 *
 * Shows:
 * - Active cameras count
 * - Events today count
 * - Current risk level (color-coded)
 * - System status indicator
 *
 * Features NVIDIA dark theme with color-coded indicators.
 */
export default function StatsRow({
  activeCameras,
  eventsToday,
  currentRiskScore,
  systemStatus,
  className = '',
}: StatsRowProps) {
  // Get risk level and color
  const riskLevel = getRiskLevel(currentRiskScore);
  const riskColor = getRiskColor(riskLevel);
  const riskLabel = getRiskLabel(riskLevel);

  // Get system status color
  const statusColor = useMemo(() => {
    switch (systemStatus) {
      case 'healthy':
        return 'bg-green-500';
      case 'degraded':
        return 'bg-yellow-500';
      case 'unhealthy':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  }, [systemStatus]);

  const statusLabel = useMemo(() => {
    switch (systemStatus) {
      case 'healthy':
        return 'Online';
      case 'degraded':
        return 'Degraded';
      case 'unhealthy':
        return 'Offline';
      default:
        return 'Unknown';
    }
  }, [systemStatus]);

  return (
    <div
      className={`grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 ${className}`}
      role="region"
      aria-label="Dashboard statistics"
    >
      {/* Active Cameras */}
      <div className="flex items-center gap-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4 shadow-sm">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[#76B900]/10">
          <Camera className="h-6 w-6 text-[#76B900]" aria-hidden="true" />
        </div>
        <div className="flex flex-col">
          <div className="text-2xl font-bold text-white" data-testid="active-cameras-count">
            {activeCameras}
          </div>
          <div className="text-sm text-gray-400">Active Cameras</div>
        </div>
      </div>

      {/* Events Today */}
      <div className="flex items-center gap-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4 shadow-sm">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10">
          <Calendar className="h-6 w-6 text-blue-500" aria-hidden="true" />
        </div>
        <div className="flex flex-col">
          <div className="text-2xl font-bold text-white" data-testid="events-today-count">
            {eventsToday}
          </div>
          <div className="text-sm text-gray-400">Events Today</div>
        </div>
      </div>

      {/* Current Risk Level */}
      <div className="flex items-center gap-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4 shadow-sm">
        <div
          className="flex h-12 w-12 items-center justify-center rounded-lg"
          style={{ backgroundColor: `${riskColor}20` }}
        >
          <Shield className="h-6 w-6" style={{ color: riskColor }} aria-hidden="true" />
        </div>
        <div className="flex flex-col">
          <div className="text-2xl font-bold text-white" data-testid="risk-score">
            {currentRiskScore}
          </div>
          <div className="text-sm" style={{ color: riskColor }} data-testid="risk-label">
            {riskLabel}
          </div>
        </div>
      </div>

      {/* System Status */}
      <div className="flex items-center gap-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4 shadow-sm">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-gray-800">
          <Activity className="h-6 w-6 text-white" aria-hidden="true" />
        </div>
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <div
              className={`h-2 w-2 rounded-full ${statusColor} ${systemStatus === 'healthy' ? 'animate-pulse' : ''}`}
              data-testid="status-indicator"
              aria-label={`System status: ${statusLabel}`}
            />
            <div className="text-2xl font-bold text-white" data-testid="system-status-label">
              {statusLabel}
            </div>
          </div>
          <div className="text-sm text-gray-400">System Status</div>
        </div>
      </div>
    </div>
  );
}
