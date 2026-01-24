/**
 * GpuApplyButton - Save and apply GPU configuration button
 *
 * Provides a button to save and apply GPU configuration changes.
 * Shows a confirmation dialog before applying changes that will restart services.
 * Displays restart progress during the apply operation.
 *
 * @see NEM-3320 - Create GPU Settings UI component
 */

import { Card, Text } from '@tremor/react';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  CheckCircle,
  Loader2,
  PlayCircle,
  RefreshCw,
  Save,
  XCircle,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import Button from '../common/Button';

import type { GpuApplyResult, ServiceStatus } from '../../hooks/useGpuConfig';

/**
 * Props for GpuApplyButton component
 */
export interface GpuApplyButtonProps {
  /** Whether there are unsaved changes */
  hasChanges: boolean;
  /** Callback to save configuration (without restarting services) */
  onSave: () => Promise<void>;
  /** Callback to apply configuration (save + restart services) */
  onApply: () => Promise<GpuApplyResult>;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Whether the apply operation is in progress */
  isApplying?: boolean;
  /** Service statuses for showing restart progress */
  serviceStatuses?: ServiceStatus[];
  /** Last apply result for showing success/failure */
  lastApplyResult?: GpuApplyResult | null;
  /** Error message if operation failed */
  error?: string | null;
  /** Whether the buttons should be disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Confirmation dialog component
 */
function ConfirmationDialog({
  isOpen,
  onConfirm,
  onCancel,
  isLoading,
}: {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading: boolean;
}) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      data-testid="apply-confirmation-dialog"
    >
      <div className="mx-4 max-w-md rounded-lg border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-yellow-500/20">
            <AlertTriangle className="h-5 w-5 text-yellow-500" />
          </div>
          <div>
            <h3 className="font-semibold text-white">Restart Services?</h3>
            <Text className="text-sm text-gray-400">This action will restart AI services</Text>
          </div>
        </div>

        <p className="mb-6 text-sm text-gray-300">
          Applying GPU configuration changes will restart the affected AI services. This may cause
          brief interruption to detection and analysis capabilities. Are you sure you want to
          continue?
        </p>

        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            variant="primary"
            leftIcon={<PlayCircle className="h-4 w-4" />}
            onClick={onConfirm}
            isLoading={isLoading}
          >
            Apply Changes
          </Button>
        </div>
      </div>
    </div>
  );
}

/**
 * Service restart progress component
 */
function RestartProgress({ serviceStatuses }: { serviceStatuses: ServiceStatus[] }) {
  const restartingServices = serviceStatuses.filter((s) => s.restart_status);
  const healthyCount = serviceStatuses.filter((s) => s.health === 'healthy').length;
  const totalCount = serviceStatuses.length;

  if (restartingServices.length === 0 && healthyCount === totalCount) {
    return null;
  }

  return (
    <div className="mt-4 space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-400">Restart Progress</span>
        <span className="text-white">
          {healthyCount} / {totalCount} healthy
        </span>
      </div>
      <div className="space-y-1">
        {serviceStatuses.map((status) => (
          <div
            key={status.name}
            className="flex items-center justify-between rounded bg-gray-800 px-3 py-2 text-sm"
          >
            <span className="text-gray-300">{status.name}</span>
            <div className="flex items-center gap-2">
              {status.restart_status ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-yellow-500" />
                  <span className="text-yellow-500">{status.restart_status}</span>
                </>
              ) : status.health === 'healthy' ? (
                <>
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-green-500">Healthy</span>
                </>
              ) : status.health === 'unhealthy' ? (
                <>
                  <XCircle className="h-4 w-4 text-red-500" />
                  <span className="text-red-500">Unhealthy</span>
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4 text-gray-500" />
                  <span className="text-gray-500">{status.status}</span>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Apply result display component
 */
function ApplyResult({ result }: { result: GpuApplyResult }) {
  const hasFailures = result.failed.length > 0;

  return (
    <div
      className={clsx('mt-4 rounded-lg border p-4', {
        'border-green-500/30 bg-green-500/10': !hasFailures,
        'border-red-500/30 bg-red-500/10': hasFailures,
      })}
      data-testid="apply-result"
    >
      <div className="mb-2 flex items-center gap-2">
        {hasFailures ? (
          <>
            <XCircle className="h-5 w-5 text-red-500" />
            <span className="font-medium text-red-400">Apply completed with errors</span>
          </>
        ) : (
          <>
            <CheckCircle className="h-5 w-5 text-green-500" />
            <span className="font-medium text-green-400">Configuration applied successfully</span>
          </>
        )}
      </div>

      {result.restarted.length > 0 && (
        <div className="mb-2 text-sm">
          <span className="text-gray-400">Restarted: </span>
          <span className="text-white">{result.restarted.join(', ')}</span>
        </div>
      )}

      {result.failed.length > 0 && (
        <div className="mb-2 text-sm">
          <span className="text-gray-400">Failed: </span>
          <span className="text-red-400">{result.failed.join(', ')}</span>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="mt-2 space-y-1">
          {result.warnings.map((warning, idx) => (
            <div key={idx} className="flex items-start gap-2 text-sm text-yellow-400">
              <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * GpuApplyButton component for saving and applying GPU configuration
 */
export default function GpuApplyButton({
  hasChanges,
  onSave,
  onApply,
  isSaving = false,
  isApplying = false,
  serviceStatuses = [],
  lastApplyResult = null,
  error = null,
  disabled = false,
  className,
}: GpuApplyButtonProps) {
  const [showConfirmation, setShowConfirmation] = useState(false);

  const handleSave = useCallback(async () => {
    await onSave();
  }, [onSave]);

  const handleApplyClick = useCallback(() => {
    setShowConfirmation(true);
  }, []);

  const handleConfirmApply = useCallback(async () => {
    await onApply();
    setShowConfirmation(false);
  }, [onApply]);

  const handleCancelApply = useCallback(() => {
    setShowConfirmation(false);
  }, []);

  const isLoading = isSaving || isApplying;
  const showRestartProgress = isApplying && serviceStatuses.length > 0;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="gpu-apply-button-card"
    >
      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="secondary"
          leftIcon={<Save className="h-4 w-4" />}
          onClick={() => void handleSave()}
          isLoading={isSaving}
          disabled={disabled || !hasChanges || isLoading}
          data-testid="save-config-button"
        >
          Save Configuration
        </Button>

        <Button
          variant="primary"
          leftIcon={<PlayCircle className="h-4 w-4" />}
          onClick={handleApplyClick}
          isLoading={isApplying}
          disabled={disabled || isLoading}
          data-testid="apply-config-button"
        >
          Save & Apply
        </Button>

        {hasChanges && !isLoading && (
          <Text className="text-sm text-yellow-500">
            <AlertTriangle className="mr-1 inline-block h-4 w-4" />
            You have unsaved changes
          </Text>
        )}
      </div>

      {/* Helper Text */}
      <div className="mt-3 text-sm text-gray-400">
        <p>
          <strong className="text-gray-300">Save Configuration</strong> saves changes without
          restarting services.
        </p>
        <p>
          <strong className="text-gray-300">Save & Apply</strong> saves changes and restarts
          affected services.
        </p>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
          <XCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500" />
          <div>
            <span className="font-medium text-red-400">Error</span>
            <p className="mt-1 text-sm text-red-300">{error}</p>
          </div>
        </div>
      )}

      {/* Restart Progress */}
      {showRestartProgress && <RestartProgress serviceStatuses={serviceStatuses} />}

      {/* Apply Result */}
      {lastApplyResult && !isApplying && <ApplyResult result={lastApplyResult} />}

      {/* Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={showConfirmation}
        onConfirm={() => void handleConfirmApply()}
        onCancel={handleCancelApply}
        isLoading={isApplying}
      />
    </Card>
  );
}
