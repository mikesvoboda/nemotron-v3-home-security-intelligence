/**
 * GpuBatchActions - Batch operation buttons for GPU assignments
 *
 * Provides quick actions for managing GPU assignments in bulk:
 * - Assign All: Move all services to a selected GPU
 * - Reset to Defaults: Clear all custom assignments (reset to GPU 0)
 * - Auto-Balance: Distribute services evenly using the balanced strategy
 *
 * @see NEM-4943 - GPU Batch Operations
 */

import { Card, Title, Text } from '@tremor/react';
import { clsx } from 'clsx';
import { Cpu, RotateCcw, Scale, Wand2 } from 'lucide-react';
import { useCallback, useState } from 'react';

import Button from '../common/Button';

import type { GpuDevice, GpuAssignment } from '../../hooks/useGpuConfig';

/**
 * Props for GpuBatchActions component
 */
export interface GpuBatchActionsProps {
  /** Available GPU devices */
  gpus: GpuDevice[];
  /** Current assignments */
  assignments: GpuAssignment[];
  /** Whether the component is in a loading/disabled state */
  disabled?: boolean;
  /** Callback when "Assign All" is triggered */
  onAssignAll: (gpuIndex: number) => void;
  /** Callback when "Reset to Defaults" is triggered */
  onResetDefaults: () => void;
  /** Callback when "Auto-Balance" is triggered */
  onAutoBalance: () => void;
  /** Whether auto-balance is in progress */
  isAutoBalancing?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Assign All dialog component
 */
function AssignAllDialog({
  isOpen,
  gpus,
  onConfirm,
  onCancel,
}: {
  isOpen: boolean;
  gpus: GpuDevice[];
  onConfirm: (gpuIndex: number) => void;
  onCancel: () => void;
}) {
  const [selectedGpu, setSelectedGpu] = useState<number>(gpus[0]?.index ?? 0);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      data-testid="assign-all-dialog"
    >
      <div className="mx-4 max-w-md rounded-lg border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#76B900]/20">
            <Cpu className="h-5 w-5 text-[#76B900]" />
          </div>
          <div>
            <h3 className="font-semibold text-white">Assign All Services</h3>
            <Text className="text-sm text-gray-400">Move all services to a single GPU</Text>
          </div>
        </div>

        <div className="mb-6">
          <label htmlFor="gpu-select" className="mb-2 block text-sm font-medium text-gray-300">
            Select Target GPU
          </label>
          <select
            id="gpu-select"
            value={selectedGpu}
            onChange={(e) => setSelectedGpu(parseInt(e.target.value, 10))}
            className={clsx(
              'w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white',
              'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]'
            )}
            data-testid="assign-all-gpu-select"
          >
            {gpus.map((gpu) => (
              <option key={gpu.index} value={gpu.index}>
                GPU {gpu.index}: {gpu.name} ({(gpu.vram_total_mb / 1024).toFixed(1)} GB)
              </option>
            ))}
          </select>
        </div>

        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="primary"
            leftIcon={<Cpu className="h-4 w-4" />}
            onClick={() => onConfirm(selectedGpu)}
            data-testid="assign-all-confirm-button"
          >
            Assign All
          </Button>
        </div>
      </div>
    </div>
  );
}

/**
 * Reset confirmation dialog component
 */
function ResetConfirmDialog({
  isOpen,
  onConfirm,
  onCancel,
}: {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      data-testid="reset-confirm-dialog"
    >
      <div className="mx-4 max-w-md rounded-lg border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-yellow-500/20">
            <RotateCcw className="h-5 w-5 text-yellow-500" />
          </div>
          <div>
            <h3 className="font-semibold text-white">Reset to Defaults?</h3>
            <Text className="text-sm text-gray-400">This will clear all custom assignments</Text>
          </div>
        </div>

        <p className="mb-6 text-sm text-gray-300">
          All services will be assigned to GPU 0 and any VRAM budget overrides will be cleared.
          This action cannot be undone.
        </p>

        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="danger"
            leftIcon={<RotateCcw className="h-4 w-4" />}
            onClick={onConfirm}
            data-testid="reset-confirm-button"
          >
            Reset All
          </Button>
        </div>
      </div>
    </div>
  );
}

/**
 * GpuBatchActions component for bulk GPU assignment operations
 */
export default function GpuBatchActions({
  gpus,
  assignments,
  disabled = false,
  onAssignAll,
  onResetDefaults,
  onAutoBalance,
  isAutoBalancing = false,
  className,
}: GpuBatchActionsProps) {
  const [showAssignAllDialog, setShowAssignAllDialog] = useState(false);
  const [showResetDialog, setShowResetDialog] = useState(false);

  const handleAssignAllClick = useCallback(() => {
    setShowAssignAllDialog(true);
  }, []);

  const handleAssignAllConfirm = useCallback(
    (gpuIndex: number) => {
      onAssignAll(gpuIndex);
      setShowAssignAllDialog(false);
    },
    [onAssignAll]
  );

  const handleResetClick = useCallback(() => {
    setShowResetDialog(true);
  }, []);

  const handleResetConfirm = useCallback(() => {
    onResetDefaults();
    setShowResetDialog(false);
  }, [onResetDefaults]);

  const handleAutoBalance = useCallback(() => {
    onAutoBalance();
  }, [onAutoBalance]);

  // Check if reset would make a difference (all on GPU 0 with no overrides)
  const isAlreadyDefault = assignments.every(
    (a) => a.gpu_index === 0 && (a.vram_budget_override === null || a.vram_budget_override === undefined)
  );

  // Check if we have multiple GPUs for auto-balance to be useful
  const hasMultipleGpus = gpus.length > 1;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="gpu-batch-actions"
    >
      {/* Header */}
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/20">
          <Wand2 className="h-5 w-5 text-purple-400" />
        </div>
        <div>
          <Title className="text-white">Quick Actions</Title>
          <Text className="mt-1 text-sm text-gray-400">
            Batch operations for GPU assignments
          </Text>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3">
        {/* Assign All */}
        <Button
          variant="outline"
          size="sm"
          leftIcon={<Cpu className="h-4 w-4" />}
          onClick={handleAssignAllClick}
          disabled={disabled || gpus.length === 0}
          data-testid="assign-all-button"
        >
          Assign All to GPU
        </Button>

        {/* Reset to Defaults */}
        <Button
          variant="outline"
          size="sm"
          leftIcon={<RotateCcw className="h-4 w-4" />}
          onClick={handleResetClick}
          disabled={disabled || isAlreadyDefault}
          data-testid="reset-defaults-button"
        >
          Reset to Defaults
        </Button>

        {/* Auto-Balance */}
        <Button
          variant="outline"
          size="sm"
          leftIcon={<Scale className="h-4 w-4" />}
          onClick={handleAutoBalance}
          disabled={disabled || !hasMultipleGpus}
          isLoading={isAutoBalancing}
          data-testid="auto-balance-button"
        >
          Auto-Balance
        </Button>
      </div>

      {/* Helper Text */}
      <div className="mt-4 space-y-1 text-xs text-gray-500">
        <p>
          <strong className="text-gray-400">Assign All:</strong> Move all services to a single GPU.
        </p>
        <p>
          <strong className="text-gray-400">Reset:</strong> Assign all services to GPU 0 and clear overrides.
        </p>
        <p>
          <strong className="text-gray-400">Auto-Balance:</strong> Distribute services evenly across GPUs.
        </p>
      </div>

      {/* Dialogs */}
      <AssignAllDialog
        isOpen={showAssignAllDialog}
        gpus={gpus}
        onConfirm={handleAssignAllConfirm}
        onCancel={() => setShowAssignAllDialog(false)}
      />

      <ResetConfirmDialog
        isOpen={showResetDialog}
        onConfirm={handleResetConfirm}
        onCancel={() => setShowResetDialog(false)}
      />
    </Card>
  );
}
