/**
 * GpuDeviceCard - Displays information about a single GPU device
 *
 * Shows GPU name, index, VRAM usage bar visualization, and assigned services.
 * Color-coded by VRAM usage level:
 * - Green (0-50%): Low usage
 * - Yellow (50-80%): Moderate usage
 * - Orange (80-90%): High usage
 * - Red (90%+): Critical usage
 *
 * @see NEM-3320 - Create GPU Settings UI component
 */

import { Card, Title, Text, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, Layers } from 'lucide-react';

import type { GpuDevice, GpuAssignment } from '../../hooks/useGpuConfig';

/**
 * Props for GpuDeviceCard component
 */
export interface GpuDeviceCardProps {
  /** GPU device information */
  gpu: GpuDevice;
  /** Services assigned to this GPU */
  assignedServices: GpuAssignment[];
  /** Whether the card is in loading state */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get usage status based on VRAM usage percentage
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
    <div data-testid="gpu-card-loading-skeleton" className="animate-pulse space-y-4">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-gray-700" />
        <div className="space-y-2">
          <div className="h-4 w-32 rounded bg-gray-700" />
          <div className="h-3 w-20 rounded bg-gray-700" />
        </div>
      </div>
      <div className="h-2 w-full rounded bg-gray-700" />
      <div className="flex justify-between">
        <div className="h-3 w-16 rounded bg-gray-700" />
        <div className="h-3 w-16 rounded bg-gray-700" />
      </div>
    </div>
  );
}

/**
 * GpuDeviceCard component displays information about a single GPU
 */
export default function GpuDeviceCard({
  gpu,
  assignedServices,
  isLoading = false,
  className,
}: GpuDeviceCardProps) {
  const usagePercent =
    gpu.vram_total_mb > 0 ? (gpu.vram_used_mb / gpu.vram_total_mb) * 100 : 0;
  const status = getUsageStatus(usagePercent);
  const progressColor = getProgressColor(status);
  const availableMb = gpu.vram_total_mb - gpu.vram_used_mb;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid={`gpu-device-card-${gpu.index}`}
    >
      {isLoading ? (
        <LoadingSkeleton />
      ) : (
        <>
          {/* Header */}
          <div className="mb-4 flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#76B900]/20">
                <Cpu className="h-5 w-5 text-[#76B900]" />
              </div>
              <div>
                <Title className="text-white">{gpu.name}</Title>
                <Text className="text-sm text-gray-400">GPU {gpu.index}</Text>
              </div>
            </div>
            <div
              data-testid={`gpu-usage-indicator-${gpu.index}`}
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
              {usagePercent.toFixed(1)}%
            </div>
          </div>

          {/* VRAM Progress Bar */}
          <div className="mb-4">
            <div className="mb-1 flex items-center justify-between text-sm">
              <Text className="text-gray-400">VRAM Usage</Text>
              <Text className="font-medium text-white">
                {formatMemory(gpu.vram_used_mb)} / {formatMemory(gpu.vram_total_mb)}
              </Text>
            </div>
            <ProgressBar
              value={usagePercent}
              color={progressColor}
              className="h-2"
              aria-label={`VRAM usage: ${usagePercent.toFixed(1)}%`}
            />
            <div className="mt-1 flex justify-between text-xs">
              <Text className="text-gray-500">Used: {formatMemory(gpu.vram_used_mb)}</Text>
              <Text className="text-[#76B900]">Available: {formatMemory(availableMb)}</Text>
            </div>
          </div>

          {/* Compute Capability */}
          <div className="mb-4 rounded-lg bg-gray-800/50 px-3 py-2">
            <Text className="text-xs text-gray-500">Compute Capability</Text>
            <Text className="font-mono text-sm text-white">{gpu.compute_capability}</Text>
          </div>

          {/* Assigned Services */}
          <div>
            <div className="mb-2 flex items-center gap-2">
              <Layers className="h-4 w-4 text-gray-400" />
              <Text className="text-sm font-medium text-gray-300">Assigned Services</Text>
            </div>
            {assignedServices.length === 0 ? (
              <Text className="text-sm italic text-gray-500">No services assigned</Text>
            ) : (
              <div className="flex flex-wrap gap-2">
                {assignedServices.map((assignment) => (
                  <span
                    key={assignment.service}
                    className="rounded-full bg-[#76B900]/20 px-3 py-1 text-xs font-medium text-[#76B900]"
                  >
                    {assignment.service}
                  </span>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </Card>
  );
}
