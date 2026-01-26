/**
 * BatchStatusMonitor - Real-time batch aggregator status monitoring component
 *
 * Displays real-time batch processing status:
 * - Active batch count
 * - Average batch age
 * - Total detection count
 * - Health indicators (green/yellow/red)
 *
 * Collapsible section that pauses polling when collapsed.
 *
 * @see NEM-3872 - Batch Status Monitoring
 */

import { Disclosure } from '@headlessui/react';
import { Text } from '@tremor/react';
import { clsx } from 'clsx';
import { ChevronDown, Activity, AlertCircle, Loader2 } from 'lucide-react';
import { useState } from 'react';

import { useBatchAggregatorStatus, type HealthIndicator } from '../../hooks/useBatchAggregatorStatus';

export interface BatchStatusMonitorProps {
  /** Optional className for styling */
  className?: string;
}

/**
 * Get the CSS class for the health indicator
 */
function getHealthIndicatorClass(health: HealthIndicator): string {
  switch (health) {
    case 'green':
      return 'bg-green-500';
    case 'yellow':
      return 'bg-yellow-500';
    case 'red':
      return 'bg-red-500';
    default:
      return 'bg-gray-500';
  }
}

/**
 * Get the health description text
 */
function getHealthDescription(health: HealthIndicator): string {
  switch (health) {
    case 'green':
      return 'Healthy - batches processing normally';
    case 'yellow':
      return 'Warning - batches approaching timeout';
    case 'red':
      return 'Critical - batches near or at timeout';
    default:
      return 'Unknown status';
  }
}

/**
 * Internal panel content component
 */
function BatchStatusPanelContent({
  isLoading,
  error,
  activeBatchCount,
  averageBatchAge,
  totalDetectionCount,
  batchWindowSeconds,
  healthIndicator,
}: {
  isLoading: boolean;
  error: string | null;
  activeBatchCount: number;
  averageBatchAge: number;
  totalDetectionCount: number;
  batchWindowSeconds: number;
  healthIndicator: HealthIndicator;
}) {
  if (isLoading) {
    return (
      <div data-testid="batch-status-loading" className="flex items-center justify-center py-4">
        <Loader2 className="h-6 w-6 animate-spin text-[#76B900]" />
        <Text className="ml-2 text-gray-400">Loading batch status...</Text>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
        <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
        <Text className="text-red-400">{error}</Text>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {/* Active Batches */}
        <div className="rounded-lg bg-[#1A1A1A] p-3">
          <Text className="text-xs text-gray-500">Active Batches</Text>
          <Text className="mt-1 text-xl font-semibold text-white">{activeBatchCount}</Text>
        </div>

        {/* Average Age */}
        <div className="rounded-lg bg-[#1A1A1A] p-3">
          <Text className="text-xs text-gray-500">Avg Age</Text>
          <Text className="mt-1 text-xl font-semibold text-white">{Math.round(averageBatchAge)}s</Text>
        </div>

        {/* Detections */}
        <div className="rounded-lg bg-[#1A1A1A] p-3">
          <Text className="text-xs text-gray-500">Detections</Text>
          <Text className="mt-1 text-xl font-semibold text-white">{totalDetectionCount}</Text>
        </div>

        {/* Window */}
        <div className="rounded-lg bg-[#1A1A1A] p-3">
          <Text className="text-xs text-gray-500">Window</Text>
          <Text className="mt-1 text-xl font-semibold text-white">{batchWindowSeconds}s</Text>
        </div>
      </div>

      {/* Health status bar */}
      <div className="rounded-lg bg-[#1A1A1A] p-3">
        <div className="flex items-center justify-between">
          <Text className="text-xs text-gray-500">Health Status</Text>
          <div className="flex items-center gap-2">
            <div className={clsx('h-3 w-3 rounded-full', getHealthIndicatorClass(healthIndicator))} />
            <Text className="text-sm text-gray-300">{getHealthDescription(healthIndicator)}</Text>
          </div>
        </div>

        {/* Progress bar showing batch age vs window */}
        {batchWindowSeconds > 0 && (
          <div className="mt-2">
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-700">
              <div
                className={clsx('h-full transition-all duration-300', getHealthIndicatorClass(healthIndicator))}
                style={{
                  width: `${Math.min(100, (averageBatchAge / batchWindowSeconds) * 100)}%`,
                }}
              />
            </div>
            <div className="mt-1 flex justify-between text-xs text-gray-500">
              <span>0s</span>
              <span>{batchWindowSeconds}s</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * BatchStatusMonitor component
 *
 * A collapsible panel showing real-time batch aggregator status.
 * Pauses polling when collapsed to reduce API load.
 */
export default function BatchStatusMonitor({ className }: BatchStatusMonitorProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Use the hook with enabled based on open state
  const {
    isLoading,
    error,
    activeBatchCount,
    averageBatchAge,
    totalDetectionCount,
    batchWindowSeconds,
    healthIndicator,
  } = useBatchAggregatorStatus({ enabled: isOpen, pollingInterval: 5000 });

  return (
    <Disclosure as="div" data-testid="batch-status-monitor" className={clsx('rounded-lg border border-gray-700 bg-[#121212]', className)}>
      {({ open }) => (
        <>
          <Disclosure.Button
            className="flex w-full items-center justify-between p-4 text-left focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]"
            onClick={() => setIsOpen(!open)}
          >
            <div className="flex items-center gap-3">
              <Activity className="h-5 w-5 text-[#76B900]" />
              <Text className="font-medium text-white">Batch Status</Text>

              {/* Health indicator dot */}
              <div
                data-testid="batch-health-indicator"
                className={clsx('h-2 w-2 rounded-full', getHealthIndicatorClass(healthIndicator))}
                title={getHealthDescription(healthIndicator)}
              />
            </div>

            <div className="flex items-center gap-3">
              {/* Summary when collapsed */}
              <Text className="text-sm text-gray-400">{activeBatchCount} active</Text>

              <ChevronDown
                className={clsx('h-5 w-5 text-gray-400 transition-transform duration-200', open && 'rotate-180')}
              />
            </div>
          </Disclosure.Button>

          {/* Expandable content */}
          <Disclosure.Panel className="border-t border-gray-700 p-4">
            <BatchStatusPanelContent
              isLoading={isLoading}
              error={error}
              activeBatchCount={activeBatchCount}
              averageBatchAge={averageBatchAge}
              totalDetectionCount={totalDetectionCount}
              batchWindowSeconds={batchWindowSeconds}
              healthIndicator={healthIndicator}
            />
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
