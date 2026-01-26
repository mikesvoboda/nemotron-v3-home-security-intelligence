/**
 * WebhookHealthCard - Dashboard card showing webhook health summary
 *
 * Displays overall webhook health metrics including:
 * - Total, enabled, healthy, and unhealthy webhook counts
 * - 24-hour delivery statistics
 * - Average response time
 *
 * @module components/webhooks/WebhookHealthCard
 * @see NEM-3624 - Webhook Management Feature
 */

import { Activity, AlertTriangle, CheckCircle2, Clock, Send, Wifi, XCircle } from 'lucide-react';

import type { WebhookHealthSummary } from '../../types/webhook';

export interface WebhookHealthCardProps {
  /** Health summary data */
  health: WebhookHealthSummary | undefined;
  /** Whether the data is loading */
  isLoading?: boolean;
  /** Whether the data is refetching */
  isRefetching?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Stat item component for displaying a single metric
 */
function StatItem({
  icon: Icon,
  label,
  value,
  subValue,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  subValue?: string;
  color: 'green' | 'yellow' | 'red' | 'blue' | 'gray';
}) {
  const colorClasses = {
    green: 'text-green-400 bg-green-500/10',
    yellow: 'text-yellow-400 bg-yellow-500/10',
    red: 'text-red-400 bg-red-500/10',
    blue: 'text-blue-400 bg-blue-500/10',
    gray: 'text-gray-400 bg-gray-500/10',
  };

  return (
    <div className="flex items-center gap-3">
      <div className={`rounded-lg p-2 ${colorClasses[color]}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-sm text-gray-400">{label}</p>
        <p className="text-lg font-semibold text-white">{value}</p>
        {subValue && <p className="text-xs text-gray-500">{subValue}</p>}
      </div>
    </div>
  );
}

/**
 * Loading skeleton for the health card
 */
function HealthCardSkeleton() {
  return (
    <div className="animate-pulse rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
      <div className="mb-4 h-6 w-32 rounded bg-gray-700" />
      <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-gray-700" />
            <div>
              <div className="mb-1 h-4 w-16 rounded bg-gray-700" />
              <div className="h-6 w-12 rounded bg-gray-700" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * WebhookHealthCard component displays overall webhook health metrics
 */
export default function WebhookHealthCard({
  health,
  isLoading = false,
  isRefetching = false,
  className = '',
}: WebhookHealthCardProps) {
  if (isLoading) {
    return <HealthCardSkeleton />;
  }

  // Calculate success rate for 24h
  const deliverySuccessRate =
    health && health.total_deliveries_24h > 0
      ? Math.round((health.successful_deliveries_24h / health.total_deliveries_24h) * 100)
      : null;

  // Format average response time
  const avgResponseTime =
    health?.average_response_time_ms !== null && health?.average_response_time_ms !== undefined
      ? `${Math.round(health.average_response_time_ms)}ms`
      : 'N/A';

  return (
    <div
      className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-6 ${className}`}
      data-testid="webhook-health-card"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
          <Activity className="h-5 w-5 text-[#76B900]" />
          Webhook Health
        </h2>
        {isRefetching && (
          <span className="text-xs text-gray-500">Refreshing...</span>
        )}
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-6 md:grid-cols-4 lg:grid-cols-6">
        {/* Total Webhooks */}
        <StatItem
          icon={Wifi}
          label="Total"
          value={health?.total_webhooks ?? 0}
          subValue={`${health?.enabled_webhooks ?? 0} enabled`}
          color="blue"
        />

        {/* Healthy Webhooks */}
        <StatItem
          icon={CheckCircle2}
          label="Healthy"
          value={health?.healthy_webhooks ?? 0}
          subValue=">90% success rate"
          color="green"
        />

        {/* Unhealthy Webhooks */}
        <StatItem
          icon={XCircle}
          label="Unhealthy"
          value={health?.unhealthy_webhooks ?? 0}
          subValue="<50% success rate"
          color={health && health.unhealthy_webhooks > 0 ? 'red' : 'gray'}
        />

        {/* 24h Deliveries */}
        <StatItem
          icon={Send}
          label="24h Deliveries"
          value={health?.total_deliveries_24h ?? 0}
          subValue={
            deliverySuccessRate !== null
              ? `${deliverySuccessRate}% success`
              : 'No deliveries'
          }
          color={
            deliverySuccessRate === null
              ? 'gray'
              : deliverySuccessRate >= 90
                ? 'green'
                : deliverySuccessRate >= 50
                  ? 'yellow'
                  : 'red'
          }
        />

        {/* Failed 24h */}
        <StatItem
          icon={AlertTriangle}
          label="Failed (24h)"
          value={health?.failed_deliveries_24h ?? 0}
          color={health && health.failed_deliveries_24h > 0 ? 'yellow' : 'gray'}
        />

        {/* Avg Response Time */}
        <StatItem
          icon={Clock}
          label="Avg Response"
          value={avgResponseTime}
          color="blue"
        />
      </div>
    </div>
  );
}
