/**
 * GpuAssignmentTable - Table for managing GPU assignments to AI services
 *
 * Displays a table of AI services with GPU assignment dropdowns.
 * Columns include: Service name, Current GPU, VRAM Required, Status.
 * Allows manual GPU assignment when strategy is set to 'manual'.
 *
 * @see NEM-3320 - Create GPU Settings UI component
 */

import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, AlertTriangle, RotateCcw } from 'lucide-react';
import { useState, useCallback } from 'react';

import type { GpuDevice, GpuAssignment, ServiceHealthStatus } from '../../hooks/useGpuConfig';

/**
 * Service VRAM requirements (in GB) - default values
 * These can be overridden via vram_budget_override in GpuAssignment
 */
const DEFAULT_VRAM_REQUIREMENTS: Record<string, number> = {
  'ai-llm': 8.0,
  'ai-yolo26': 0.1, // ~100MB for YOLO26m TensorRT
  'ai-enrichment': 3.5,
  'ai-florence': 4.0,
  'ai-clip': 2.0,
};

/**
 * Props for GpuAssignmentTable component
 */
export interface GpuAssignmentTableProps {
  /** Current GPU assignments */
  assignments: GpuAssignment[];
  /** Available GPU devices */
  gpus: GpuDevice[];
  /** Service health status information */
  serviceStatuses: ServiceHealthStatus[];
  /** Current assignment strategy */
  strategy: string;
  /** Callback when an assignment is changed */
  onAssignmentChange: (service: string, gpuIndex: number | null) => void;
  /** Callback when VRAM budget override is changed */
  onVramOverrideChange?: (service: string, vramOverride: number | null) => void;
  /** Whether the table is in loading state */
  isLoading?: boolean;
  /** Whether changes are pending (not yet saved) */
  hasPendingChanges?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get status badge color based on service health
 */
function getStatusColor(health: string): 'green' | 'yellow' | 'red' | 'gray' {
  switch (health.toLowerCase()) {
    case 'healthy':
      return 'green';
    case 'unhealthy':
      return 'red';
    case 'starting':
    case 'restarting':
      return 'yellow';
    default:
      return 'gray';
  }
}

/**
 * Get status label from health value
 */
function getStatusLabel(health: string, restartStatus: string | null): string {
  if (restartStatus) {
    return restartStatus;
  }
  switch (health.toLowerCase()) {
    case 'healthy':
      return 'Healthy';
    case 'unhealthy':
      return 'Unhealthy';
    case 'starting':
      return 'Starting';
    case 'unknown':
    default:
      return 'Unknown';
  }
}

/**
 * Format VRAM requirement in GB
 */
function formatVram(gb: number): string {
  return `${gb.toFixed(1)} GB`;
}

/**
 * Get VRAM requirement for a service
 */
function getVramRequirement(assignment: GpuAssignment): number {
  if (assignment.vram_budget_override !== null && assignment.vram_budget_override !== undefined) {
    return assignment.vram_budget_override;
  }
  return DEFAULT_VRAM_REQUIREMENTS[assignment.service] ?? 2.0;
}

/**
 * Check if assignment exceeds GPU VRAM
 */
function isOverVram(assignment: GpuAssignment, gpus: GpuDevice[]): boolean {
  if (assignment.gpu_index === null) return false;
  const gpu = gpus.find((g) => g.index === assignment.gpu_index);
  if (!gpu) return false;
  const vramRequired = getVramRequirement(assignment) * 1024; // Convert to MB
  const available = gpu.vram_total_mb - gpu.vram_used_mb;
  return vramRequired > available;
}

/**
 * Loading skeleton row
 */
function LoadingRow() {
  return (
    <tr className="animate-pulse">
      <td className="px-4 py-3">
        <div className="h-4 w-24 rounded bg-gray-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-8 w-32 rounded bg-gray-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-4 w-16 rounded bg-gray-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-5 w-20 rounded bg-gray-700" />
      </td>
    </tr>
  );
}

/**
 * Props for VramOverrideInput component
 */
interface VramOverrideInputProps {
  service: string;
  currentValue: number;
  hasOverride: boolean;
  defaultValue: number;
  onChange: (value: number | null) => void;
  disabled?: boolean;
}

/**
 * VRAM budget override input with reset button
 */
function VramOverrideInput({
  service,
  currentValue,
  hasOverride,
  defaultValue,
  onChange,
  disabled = false,
}: VramOverrideInputProps) {
  const [localValue, setLocalValue] = useState(currentValue.toString());
  const [isEditing, setIsEditing] = useState(false);

  const handleBlur = useCallback(() => {
    setIsEditing(false);
    const numValue = parseFloat(localValue);
    if (isNaN(numValue) || numValue <= 0) {
      // Reset to current value if invalid
      setLocalValue(currentValue.toString());
      return;
    }
    // Only call onChange if value actually changed
    if (numValue !== currentValue) {
      onChange(numValue);
    }
  }, [localValue, currentValue, onChange]);

  const handleReset = useCallback(() => {
    onChange(null);
    setLocalValue(defaultValue.toString());
  }, [onChange, defaultValue]);

  // Update local value when prop changes
  if (!isEditing && localValue !== currentValue.toString()) {
    setLocalValue(currentValue.toString());
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        value={localValue}
        onChange={(e) => {
          setIsEditing(true);
          setLocalValue(e.target.value);
        }}
        onBlur={handleBlur}
        disabled={disabled}
        step="0.1"
        min="0.1"
        className={clsx(
          'w-20 rounded-lg border bg-gray-800 px-2 py-1 text-sm text-white',
          'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
          {
            'border-gray-700': !hasOverride,
            'border-[#76B900]': hasOverride,
            'cursor-not-allowed opacity-60': disabled,
          }
        )}
        data-testid={`vram-override-${service}`}
        aria-label={`VRAM budget override for ${service}`}
      />
      <span className="text-xs text-gray-400">GB</span>
      {hasOverride && !disabled && (
        <button
          type="button"
          onClick={handleReset}
          className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white"
          title="Reset to default"
          data-testid={`vram-reset-${service}`}
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

/**
 * GpuAssignmentTable component for managing service-to-GPU assignments
 */
export default function GpuAssignmentTable({
  assignments,
  gpus,
  serviceStatuses,
  strategy,
  onAssignmentChange,
  onVramOverrideChange,
  isLoading = false,
  hasPendingChanges = false,
  className,
}: GpuAssignmentTableProps) {
  const isManual = strategy === 'manual';

  // Create a map of service name to status
  const statusMap = new Map(serviceStatuses.map((s) => [s.name, s]));

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="gpu-assignment-table"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#76B900]/20">
            <Cpu className="h-5 w-5 text-[#76B900]" />
          </div>
          <div>
            <Title className="text-white">Service Assignments</Title>
            <Text className="mt-1 text-sm text-gray-400">
              {isManual
                ? 'Assign GPUs to each AI service manually'
                : 'GPU assignments are managed by the selected strategy'}
            </Text>
          </div>
        </div>
        {hasPendingChanges && (
          <Badge color="yellow" size="sm">
            Unsaved Changes
          </Badge>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full" data-testid="assignment-table">
          <thead>
            <tr className="border-b border-gray-700 text-left text-sm text-gray-400">
              <th className="px-4 py-3 font-medium">Service</th>
              <th className="px-4 py-3 font-medium">Current GPU</th>
              <th className="px-4 py-3 font-medium">VRAM Required</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {isLoading ? (
              <>
                <LoadingRow />
                <LoadingRow />
                <LoadingRow />
              </>
            ) : (
              assignments.map((assignment) => {
                const status = statusMap.get(assignment.service);
                const vramRequired = getVramRequirement(assignment);
                const overVram = isOverVram(assignment, gpus);
                const currentGpu = gpus.find((g) => g.index === assignment.gpu_index);

                return (
                  <tr
                    key={assignment.service}
                    className="hover:bg-gray-800/50"
                    data-testid={`assignment-row-${assignment.service}`}
                  >
                    {/* Service Name */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{assignment.service}</span>
                      </div>
                    </td>

                    {/* GPU Assignment Dropdown */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <select
                          value={assignment.gpu_index ?? 'auto'}
                          onChange={(e) => {
                            const value = e.target.value;
                            onAssignmentChange(
                              assignment.service,
                              value === 'auto' ? null : parseInt(value, 10)
                            );
                          }}
                          disabled={!isManual}
                          className={clsx(
                            'rounded-lg border bg-gray-800 px-3 py-1.5 text-sm text-white',
                            'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
                            {
                              'border-gray-700': !overVram,
                              'border-orange-500': overVram,
                              'cursor-not-allowed opacity-60': !isManual,
                            }
                          )}
                          data-testid={`gpu-select-${assignment.service}`}
                          aria-label={`GPU assignment for ${assignment.service}`}
                        >
                          <option value="auto">Auto</option>
                          {gpus.map((gpu) => (
                            <option key={gpu.index} value={gpu.index}>
                              GPU {gpu.index}: {gpu.name}
                            </option>
                          ))}
                        </select>
                        {overVram && (
                          <span title="VRAM requirement exceeds available memory">
                            <AlertTriangle className="h-4 w-4 text-orange-500" />
                          </span>
                        )}
                      </div>
                      {currentGpu && (
                        <Text className="mt-1 text-xs text-gray-500">
                          {formatVram(currentGpu.vram_total_mb / 1024)} total
                        </Text>
                      )}
                    </td>

                    {/* VRAM Required */}
                    <td className="px-4 py-3">
                      {isManual && onVramOverrideChange ? (
                        <VramOverrideInput
                          service={assignment.service}
                          currentValue={vramRequired}
                          hasOverride={
                            assignment.vram_budget_override !== null &&
                            assignment.vram_budget_override !== undefined
                          }
                          defaultValue={DEFAULT_VRAM_REQUIREMENTS[assignment.service] ?? 2.0}
                          onChange={(value) => onVramOverrideChange(assignment.service, value)}
                        />
                      ) : (
                        <span
                          className={clsx('text-sm', {
                            'text-white': !overVram,
                            'text-orange-400': overVram,
                          })}
                        >
                          {formatVram(vramRequired)}
                        </span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3">
                      {status ? (
                        <Badge
                          color={getStatusColor(status.health)}
                          size="sm"
                          data-testid={`status-badge-${assignment.service}`}
                        >
                          {getStatusLabel(status.health, status.restart_status)}
                        </Badge>
                      ) : (
                        <Badge
                          color="gray"
                          size="sm"
                          data-testid={`status-badge-${assignment.service}`}
                        >
                          Unknown
                        </Badge>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Empty State */}
      {!isLoading && assignments.length === 0 && (
        <div className="py-8 text-center">
          <Text className="text-gray-400">No services configured</Text>
        </div>
      )}

      {/* Footer Note */}
      {!isManual && (
        <div className="mt-4 rounded-lg bg-gray-800/50 px-4 py-3">
          <Text className="text-sm text-gray-400">
            <span className="font-medium text-gray-300">Note:</span> GPU assignments are managed
            automatically based on the selected strategy. Switch to{' '}
            <span className="text-[#76B900]">Manual</span> mode to customize assignments.
          </Text>
        </div>
      )}
    </Card>
  );
}
