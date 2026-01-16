import {
  Activity,
  AlertTriangle,
  Calendar,
  Camera,
  CheckCircle,
  HelpCircle,
  Shield,
  XCircle,
} from 'lucide-react';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

import { getRiskColor, getRiskLabel, getRiskLevel } from '../../utils/risk';

/**
 * Generates an SVG path for a sparkline chart
 * @param data - Array of data points (0-100)
 * @param width - Width of the SVG viewBox
 * @param height - Height of the SVG viewBox
 * @param fillPath - Whether to generate a filled area path (true) or line path (false)
 * @returns SVG path string
 */
function generateSparklinePath(
  data: number[],
  width: number,
  height: number,
  fillPath: boolean
): string {
  /* c8 ignore next */ if (data.length === 0) return '';

  const maxValue = Math.max(...data, 100); // Ensure scale includes 100
  const minValue = Math.min(...data, 0); // Ensure scale includes 0
  const range = maxValue - minValue || 1; // Avoid division by zero
  const padding = 2; // Padding from edges
  const availableHeight = height - padding * 2;

  // Calculate points using numeric coordinates within viewBox
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1 || 1)) * width; // Numeric x within viewBox width
    const normalizedValue = (value - minValue) / range;
    const y = height - padding - normalizedValue * availableHeight; // Invert Y axis
    return { x, y };
  });

  /* c8 ignore next */ if (points.length === 0) return '';

  // Build path with numeric coordinates
  let path = `M ${points[0].x} ${points[0].y}`;

  // Add line segments
  for (let i = 1; i < points.length; i++) {
    path += ` L ${points[i].x} ${points[i].y}`;
  }

  // For filled area, close the path
  if (fillPath) {
    path += ` L ${points[points.length - 1].x} ${height}`;
    path += ` L ${points[0].x} ${height}`;
    path += ' Z';
  }

  return path;
}

export interface StatsRowProps {
  /** Number of active cameras */
  activeCameras: number;
  /** Total number of events today */
  eventsToday: number;
  /** Current risk score (0-100) */
  currentRiskScore: number;
  /** System health status */
  systemStatus: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  /** Optional array of historical risk values for sparkline display */
  riskHistory?: number[];
  /** Additional CSS classes */
  className?: string;
}

/**
 * StatsRow displays key metrics in the dashboard header area.
 *
 * Shows:
 * - Active cameras count
 * - Events today count
 * - Current risk level (color-coded) with optional sparkline
 * - System status indicator
 *
 * Features NVIDIA dark theme with color-coded indicators.
 */
export default function StatsRow({
  activeCameras,
  eventsToday,
  currentRiskScore,
  systemStatus,
  riskHistory,
  className = '',
}: StatsRowProps) {
  const navigate = useNavigate();

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

  // Get status icon for accessibility (not color-only)
  const StatusIcon = useMemo(() => {
    switch (systemStatus) {
      case 'healthy':
        return CheckCircle;
      case 'degraded':
        return AlertTriangle;
      case 'unhealthy':
        return XCircle;
      default:
        return HelpCircle;
    }
  }, [systemStatus]);

  // Get status icon color
  const statusIconColor = useMemo(() => {
    switch (systemStatus) {
      case 'healthy':
        return 'text-green-500';
      case 'degraded':
        return 'text-yellow-500';
      case 'unhealthy':
        return 'text-red-500';
      default:
        return 'text-gray-500';
    }
  }, [systemStatus]);

  // Check if we should show the sparkline
  const showSparkline = (riskHistory?.length ?? 0) > 1;

  return (
    <div
      className={`grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 ${className}`}
      role="region"
      aria-label="Dashboard statistics"
    >
      {/* Active Cameras */}
      <button
        type="button"
        onClick={() => {
          void navigate('/settings');
        }}
        className="flex cursor-pointer items-center gap-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4 text-left shadow-sm transition-all duration-200 hover:border-[#76B900]/50 hover:bg-[#1A1A1A]/90 focus:outline-none focus:ring-2 focus:ring-[#76B900]/50"
        data-testid="cameras-card"
        aria-label={`Active cameras: ${activeCameras}. Click to view camera settings.`}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[#76B900]/10">
          <Camera className="h-6 w-6 text-[#76B900]" aria-hidden="true" />
        </div>
        <div className="flex flex-col">
          <div className="text-2xl font-bold text-white" data-testid="active-cameras-count">
            {activeCameras}
          </div>
          <div className="text-sm text-text-secondary">Active Cameras</div>
        </div>
      </button>

      {/* Events Today */}
      <button
        type="button"
        onClick={() => {
          void navigate('/timeline');
        }}
        className="flex cursor-pointer items-center gap-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4 text-left shadow-sm transition-all duration-200 hover:border-blue-500/50 hover:bg-[#1A1A1A]/90 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        data-testid="events-card"
        aria-label={`Events today: ${eventsToday}. Click to view event timeline.`}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10">
          <Calendar className="h-6 w-6 text-blue-500" aria-hidden="true" />
        </div>
        <div className="flex flex-col">
          <div className="text-2xl font-bold text-white" data-testid="events-today-count">
            {eventsToday}
          </div>
          <div className="text-sm text-text-secondary">Events Today</div>
        </div>
      </button>

      {/* Current Risk Level with Sparkline */}
      <button
        type="button"
        onClick={() => {
          void navigate('/alerts');
        }}
        className="flex cursor-pointer items-center gap-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4 text-left shadow-sm transition-all duration-200 hover:border-gray-600 hover:bg-[#1A1A1A]/90 focus:outline-none focus:ring-2 focus:ring-gray-500/50"
        data-testid="risk-card"
        aria-label={`Current risk: ${riskLabel} (${currentRiskScore}). Click to view alerts.`}
      >
        <div
          className="flex h-12 w-12 items-center justify-center rounded-lg"
          style={{ backgroundColor: `${riskColor}20` }}
        >
          <Shield className="h-6 w-6" style={{ color: riskColor }} aria-hidden="true" />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2">
            <div className="text-2xl font-bold text-white" data-testid="risk-score">
              {currentRiskScore}
            </div>
            {/* Sparkline for risk history */}
            {showSparkline && (
              <svg
                width="60"
                height="24"
                viewBox="0 0 60 24"
                preserveAspectRatio="none"
                className="flex-shrink-0"
                aria-hidden="true"
                data-testid="risk-sparkline"
              >
                {/* Background area */}
                <path
                  d={generateSparklinePath(riskHistory ?? [], 60, 24, true)}
                  fill={`${riskColor}20`}
                  stroke="none"
                />
                {/* Line */}
                <path
                  d={generateSparklinePath(riskHistory ?? [], 60, 24, false)}
                  fill="none"
                  stroke={riskColor}
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>
          <div className="text-sm" style={{ color: riskColor }} data-testid="risk-label">
            {riskLabel}
          </div>
        </div>
      </button>

      {/* System Status */}
      <button
        type="button"
        onClick={() => {
          void navigate('/system');
        }}
        className="flex cursor-pointer items-center gap-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4 text-left shadow-sm transition-all duration-200 hover:border-gray-600 hover:bg-[#1A1A1A]/90 focus:outline-none focus:ring-2 focus:ring-gray-500/50"
        data-testid="system-card"
        aria-label={`System status: ${statusLabel}. Click to view system monitoring.`}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-gray-800">
          <Activity className="h-6 w-6 text-white" aria-hidden="true" />
        </div>
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            {/* Status icon for accessibility (not color-only) */}
            <StatusIcon
              className={`h-5 w-5 ${statusIconColor}`}
              aria-hidden="true"
              data-testid="status-icon"
            />
            <div
              className={`h-2 w-2 rounded-full ${statusColor} ${systemStatus === 'healthy' ? 'animate-pulse' : ''}`}
              data-testid="status-indicator"
              aria-hidden="true"
            />
            <div className="text-2xl font-bold text-white" data-testid="system-status-label">
              {statusLabel}
            </div>
            <span className="sr-only">System status: {statusLabel}</span>
          </div>
          <div className="text-sm text-text-secondary">System Status</div>
        </div>
      </button>
    </div>
  );
}
