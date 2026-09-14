/**
 * VRAMUsageCard - Displays GPU VRAM usage visualization
 *
 * Shows VRAM budget, used, available with a progress bar.
 * Color-coded by usage level:
 * - Green (0-50%): Low usage
 * - Yellow (50-80%): Moderate usage
 * - Orange (80-90%): High usage
 * - Red (90%+): Critical usage
 *
 * @see NEM-3179 - Add AI model management UI
 */

import { Card, Title, Text, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import { MemoryStick } from 'lucide-react';

/**
 * Props for VRAMUsageCard component
 */
export interface VRAMUsageCardProps {
  /** Total VRAM budget in MB */
  budgetMb: number;
  /** Currently used VRAM in MB */
  usedMb: number;
  /** Available VRAM in MB */
  availableMb: number;
  /** Usage percentage (0-100) */
  usagePercent: number;
  /** Whether the card is in loading state */
  isLoading?: boolean;
  /** Compact display mode */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get status level based on usage percentage
 */
function getUsageStatus(percent: number): 'low' | 'moderate' | 'high' | 'critical' {
  if (percent >= 90) return 'critical';
  if (percent >= 80) return 'high';
  if (percent >= 50) return 'moderate';
  return 'low';
}

/**
 * Get Tremor color based on usage status
 */
function getProgressColor(
  status: 'low' | 'moderate' | 'high' | 'critical'
): 'emerald' | 'yellow' | 'orange' | 'red' {
  switch (status) {
    case 'low':
      return 'emerald';
    case 'moderate':
      return 'yellow';
    case 'high':
      return 'orange';
    case 'critical':
      return 'red';
  }
}

/**
 * Format memory value (show GB for large values, MB otherwise)
 */
function formatMemory(mb: number): string {
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(1)} GB`;
  }
  return `${mb} MB`;
}

/**
 * Loading skeleton for the card
 */
function LoadingSkeleton() {
  return (
    <div data-testid="vram-loading-skeleton" className="animate-pulse space-y-4">
      <div className="h-4 w-32 rounded bg-gray-700" />
      <div className="h-2 w-full rounded bg-gray-700" />
      <div className="flex justify-between">
        <div className="h-3 w-20 rounded bg-gray-700" />
        <div className="h-3 w-20 rounded bg-gray-700" />
        <div className="h-3 w-20 rounded bg-gray-700" />
      </div>
    </div>
  );
}

/**
 * VRAMUsageCard component displays GPU VRAM usage with visualization
 */
export default function VRAMUsageCard({
  budgetMb,
  usedMb,
  availableMb,
  usagePercent,
  isLoading = false,
  compact = false,
  className,
}: VRAMUsageCardProps) {
  const status = getUsageStatus(usagePercent);
  const progressColor = getProgressColor(status);
  const formattedPercent = usagePercent.toFixed(1);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="vram-usage-card"
      data-compact={compact ? 'true' : 'false'}
    >
      {isLoading ? (
        <LoadingSkeleton />
      ) : (
        <>
          {/* Header */}
          <div className="mb-4 flex items-center justify-between">
            <Title className="flex items-center gap-2 text-white">
              <MemoryStick className="h-5 w-5 text-[#76B900]" />
              VRAM Usage
            </Title>
            <div
              data-testid="usage-indicator"
              data-status={status}
              className={clsx(
                'flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium',
                {
                  'bg-emerald-500/20 text-emerald-400': status === 'low',
                  'bg-yellow-500/20 text-yellow-400': status === 'moderate',
                  'bg-orange-500/20 text-orange-400': status === 'high',
                  'bg-red-500/20 text-red-400': status === 'critical',
                }
              )}
            >
              {formattedPercent}%
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mb-4">
            <ProgressBar
              value={usagePercent}
              color={progressColor}
              className="h-2"
              role="progressbar"
              aria-valuenow={parseFloat(formattedPercent)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`VRAM usage: ${formattedPercent}% of ${formatMemory(budgetMb)}`}
            />
          </div>

          {/* Stats Row */}
          {!compact && (
            <div className="grid grid-cols-3 gap-4">
              {/* Used */}
              <div className="text-center">
                <Text className="text-xs text-gray-500">Used</Text>
                <Text className="text-sm font-semibold text-white">{formatMemory(usedMb)}</Text>
              </div>

              {/* Budget */}
              <div className="border-x border-gray-700 text-center">
                <Text className="text-xs text-gray-500">Budget</Text>
                <Text className="text-sm font-semibold text-white">{formatMemory(budgetMb)}</Text>
              </div>

              {/* Available */}
              <div className="text-center">
                <Text className="text-xs text-gray-500">Available</Text>
                <Text className="text-sm font-semibold text-[#76B900]">
                  {formatMemory(availableMb)}
                </Text>
              </div>
            </div>
          )}

          {compact && (
            <div className="flex items-center justify-between text-sm">
              <Text className="text-gray-400">
                {formatMemory(usedMb)} / {formatMemory(budgetMb)}
              </Text>
              <Text className="text-[#76B900]">{formatMemory(availableMb)} free</Text>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
