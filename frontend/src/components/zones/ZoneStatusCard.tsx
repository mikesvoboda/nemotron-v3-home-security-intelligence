/**
 * ZoneStatusCard - Zone intelligence status display (NEM-3188, NEM-3200)
 *
 * Displays a summary of zone intelligence data including:
 * - Activity level and trend
 * - Current presence status
 * - Recent anomaly alerts
 * - Zone health indicators
 *
 * Part of Phase 5.1: Enhanced Zone Editor Integration.
 *
 * @module components/zones/ZoneStatusCard
 */

import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  Shield,
  TrendingDown,
  TrendingUp,
  Users,
  Loader2,
} from 'lucide-react';
import { useMemo } from 'react';

import { useZoneAnomalies } from '../../hooks/useZoneAnomalies';
import { useZonePresence } from '../../hooks/useZonePresence';
import { AnomalySeverity } from '../../types/zoneAnomaly';

// ============================================================================
// Types
// ============================================================================

/**
 * Activity level categories.
 */
export type ActivityLevel = 'low' | 'normal' | 'high' | 'critical';

/**
 * Zone status summary data.
 */
export interface ZoneStatus {
  /** Current activity level */
  activityLevel: ActivityLevel;
  /** Activity trend direction */
  activityTrend: 'up' | 'down' | 'stable';
  /** Number of detections in last hour */
  detectionsLastHour: number;
  /** Number of unacknowledged anomalies */
  unacknowledgedAnomalies: number;
  /** Highest severity anomaly */
  highestSeverity: AnomalySeverity | null;
  /** Number of people currently present */
  presentCount: number;
  /** Zone health score (0-100) */
  healthScore: number;
}

/**
 * Props for the ZoneStatusCard component.
 */
export interface ZoneStatusCardProps {
  /** Zone ID to display status for */
  zoneId: string;
  /** Zone name for display */
  zoneName?: string;
  /** Whether to show compact mode */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Optional click handler for the card */
  onClick?: () => void;
}

// ============================================================================
// Constants
// ============================================================================

const ACTIVITY_LEVEL_CONFIG: Record<
  ActivityLevel,
  { label: string; color: 'gray' | 'green' | 'yellow' | 'red'; icon: typeof Activity }
> = {
  low: { label: 'Low Activity', color: 'gray', icon: Activity },
  normal: { label: 'Normal', color: 'green', icon: Activity },
  high: { label: 'High Activity', color: 'yellow', icon: Activity },
  critical: { label: 'Critical', color: 'red', icon: AlertTriangle },
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Calculate activity level from detection count and anomaly count.
 */
function calculateActivityLevel(anomalyCount: number, hasCritical: boolean): ActivityLevel {
  if (hasCritical || anomalyCount >= 5) return 'critical';
  if (anomalyCount >= 3) return 'high';
  if (anomalyCount >= 1) return 'normal';
  return 'low';
}

/**
 * Calculate health score based on activity and anomaly data.
 */
function calculateHealthScore(
  anomalyCount: number,
  criticalCount: number,
  warningCount: number
): number {
  // Start with 100, deduct for issues
  let score = 100;
  score -= criticalCount * 20;
  score -= warningCount * 10;
  score -= anomalyCount * 2;
  return Math.max(0, Math.min(100, score));
}

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Loading skeleton for the status card.
 */
function StatusCardSkeleton({ compact }: { compact?: boolean }) {
  return (
    <div className={clsx('space-y-3', compact && 'space-y-2')}>
      <div className="flex items-center justify-between">
        <div className="h-5 w-32 animate-pulse rounded bg-gray-700" />
        <div className="h-5 w-16 animate-pulse rounded bg-gray-700" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2 rounded-lg bg-gray-800/50 p-2">
            <div className="h-8 w-8 animate-pulse rounded-full bg-gray-700" />
            <div className="space-y-1">
              <div className="h-3 w-12 animate-pulse rounded bg-gray-700" />
              <div className="h-4 w-8 animate-pulse rounded bg-gray-700" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Status metric item.
 */
interface StatusMetricProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color?: string;
  compact?: boolean;
}

function StatusMetric({ icon, label, value, color, compact }: StatusMetricProps) {
  return (
    <div
      className={clsx(
        'flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 transition-colors hover:border-gray-600',
        compact ? 'p-2' : 'p-3'
      )}
    >
      <div
        className={clsx(
          'flex items-center justify-center rounded-full',
          color || 'text-gray-400',
          compact ? 'h-7 w-7' : 'h-9 w-9'
        )}
      >
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <Text className={clsx('truncate text-gray-400', compact && 'text-xs')}>{label}</Text>
        <Text className={clsx('font-medium text-white', compact && 'text-sm')}>{value}</Text>
      </div>
    </div>
  );
}

/**
 * Activity trend indicator.
 */
function TrendIndicator({
  trend,
  compact,
}: {
  trend: 'up' | 'down' | 'stable';
  compact?: boolean;
}) {
  const iconClass = compact ? 'h-3 w-3' : 'h-4 w-4';

  if (trend === 'up') {
    return (
      <div className="flex items-center gap-1 text-yellow-400">
        <TrendingUp className={iconClass} />
        <span className={clsx('font-medium', compact && 'text-xs')}>Rising</span>
      </div>
    );
  }

  if (trend === 'down') {
    return (
      <div className="flex items-center gap-1 text-green-400">
        <TrendingDown className={iconClass} />
        <span className={clsx('font-medium', compact && 'text-xs')}>Falling</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 text-gray-400">
      <Activity className={iconClass} />
      <span className={clsx('font-medium', compact && 'text-xs')}>Stable</span>
    </div>
  );
}

/**
 * Health score indicator.
 */
function HealthIndicator({ score, compact }: { score: number; compact?: boolean }) {
  const color = score >= 80 ? 'text-green-400' : score >= 50 ? 'text-yellow-400' : 'text-red-400';
  const bgColor =
    score >= 80 ? 'bg-green-500/20' : score >= 50 ? 'bg-yellow-500/20' : 'bg-red-500/20';

  return (
    <div
      className={clsx(
        'flex items-center gap-2 rounded-lg border border-gray-700',
        bgColor,
        compact ? 'px-2 py-1' : 'px-3 py-2'
      )}
    >
      {score >= 80 ? (
        <CheckCircle className={clsx(color, compact ? 'h-4 w-4' : 'h-5 w-5')} />
      ) : (
        <AlertTriangle className={clsx(color, compact ? 'h-4 w-4' : 'h-5 w-5')} />
      )}
      <div>
        <Text className={clsx('font-medium', color, compact && 'text-sm')}>{score}%</Text>
        <Text className={clsx('text-gray-400', compact ? 'text-xs' : 'text-sm')}>Health</Text>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneStatusCard component.
 *
 * Displays a summary of zone intelligence including activity levels,
 * presence information, and anomaly alerts.
 *
 * @param props - Component props
 * @returns Rendered component
 */
export default function ZoneStatusCard({
  zoneId,
  zoneName,
  compact = false,
  className,
  onClick,
}: ZoneStatusCardProps) {
  // Fetch zone data
  const { presentCount, isLoading: presenceLoading } = useZonePresence(zoneId);
  const {
    anomalies,
    totalCount: anomalyCount,
    isLoading: anomaliesLoading,
  } = useZoneAnomalies({
    zoneId,
    unacknowledgedOnly: true,
    limit: 10,
  });

  // Calculate derived status
  const status = useMemo<ZoneStatus>(() => {
    const criticalAnomalies = anomalies.filter((a) => a.severity === AnomalySeverity.CRITICAL);
    const warningAnomalies = anomalies.filter((a) => a.severity === AnomalySeverity.WARNING);
    const hasCritical = criticalAnomalies.length > 0;

    const highestSeverity = hasCritical
      ? AnomalySeverity.CRITICAL
      : warningAnomalies.length > 0
        ? AnomalySeverity.WARNING
        : anomalies.length > 0
          ? AnomalySeverity.INFO
          : null;

    return {
      activityLevel: calculateActivityLevel(anomalyCount, hasCritical),
      activityTrend: anomalyCount > 3 ? 'up' : anomalyCount === 0 ? 'down' : 'stable',
      detectionsLastHour: 0, // TODO: Hook up to detection API
      unacknowledgedAnomalies: anomalyCount,
      highestSeverity,
      presentCount,
      healthScore: calculateHealthScore(
        anomalyCount,
        criticalAnomalies.length,
        warningAnomalies.length
      ),
    };
  }, [anomalies, anomalyCount, presentCount]);

  const isLoading = presenceLoading || anomaliesLoading;
  const activityConfig = ACTIVITY_LEVEL_CONFIG[status.activityLevel];

  return (
    <Card
      className={clsx(
        'border-gray-800 bg-[#1A1A1A] shadow-lg transition-colors',
        onClick && 'cursor-pointer hover:border-gray-700',
        className
      )}
      onClick={onClick}
      data-testid="zone-status-card"
    >
      {/* Header */}
      <div className={clsx('flex items-center justify-between', compact ? 'mb-3' : 'mb-4')}>
        <div className="flex items-center gap-2">
          <Shield className={clsx('text-[#76B900]', compact ? 'h-4 w-4' : 'h-5 w-5')} />
          <Title className={clsx('text-white', compact && 'text-sm')}>
            {zoneName || 'Zone Status'}
          </Title>
        </div>
        <Badge
          color={activityConfig.color}
          size={compact ? 'xs' : 'sm'}
          data-testid="activity-badge"
        >
          {activityConfig.label}
        </Badge>
      </div>

      {isLoading ? (
        <StatusCardSkeleton compact={compact} />
      ) : (
        <div className={clsx('space-y-3', compact && 'space-y-2')}>
          {/* Activity trend and health */}
          <div className="flex items-center justify-between">
            <TrendIndicator trend={status.activityTrend} compact={compact} />
            <HealthIndicator score={status.healthScore} compact={compact} />
          </div>

          {/* Metrics grid */}
          <div className={clsx('grid gap-2', compact ? 'grid-cols-2' : 'grid-cols-2')}>
            <StatusMetric
              icon={<Users className={clsx(compact ? 'h-4 w-4' : 'h-5 w-5')} />}
              label="Present"
              value={status.presentCount}
              color="text-blue-400"
              compact={compact}
            />
            <StatusMetric
              icon={<AlertTriangle className={clsx(compact ? 'h-4 w-4' : 'h-5 w-5')} />}
              label="Alerts"
              value={status.unacknowledgedAnomalies}
              color={status.unacknowledgedAnomalies > 0 ? 'text-yellow-400' : 'text-gray-400'}
              compact={compact}
            />
            <StatusMetric
              icon={<Clock className={clsx(compact ? 'h-4 w-4' : 'h-5 w-5')} />}
              label="Last Hour"
              value={status.detectionsLastHour}
              color="text-gray-400"
              compact={compact}
            />
            <StatusMetric
              icon={<Activity className={clsx(compact ? 'h-4 w-4' : 'h-5 w-5')} />}
              label="Severity"
              value={status.highestSeverity || 'None'}
              color={
                status.highestSeverity === AnomalySeverity.CRITICAL
                  ? 'text-red-400'
                  : status.highestSeverity === AnomalySeverity.WARNING
                    ? 'text-yellow-400'
                    : 'text-gray-400'
              }
              compact={compact}
            />
          </div>

          {/* Recent anomalies summary */}
          {status.unacknowledgedAnomalies > 0 && !compact && (
            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-yellow-400" />
                <Text className="text-sm text-yellow-400">
                  {status.unacknowledgedAnomalies} unacknowledged{' '}
                  {status.unacknowledgedAnomalies === 1 ? 'alert' : 'alerts'}
                </Text>
              </div>
              {anomalies.length > 0 && (
                <Text className="mt-1 truncate text-xs text-gray-400">
                  Latest: {anomalies[0].title}
                </Text>
              )}
            </div>
          )}
        </div>
      )}

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/50">
          <Loader2 className="h-6 w-6 animate-spin text-[#76B900]" />
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// Exports
// ============================================================================

export { StatusCardSkeleton, StatusMetric, TrendIndicator, HealthIndicator };
