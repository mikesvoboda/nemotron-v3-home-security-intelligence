/**
 * LoiteringConfigModal - Modal for configuring loitering threshold (NEM-4714)
 *
 * Provides a modal dialog for configuring loitering detection settings
 * for a polygon zone including:
 * - Threshold slider (1-60 minutes)
 * - Alert enable/disable toggle
 * - Save and cancel actions
 *
 * Part of Phase 2C: Loitering Configuration Modal.
 *
 * @module components/zones/LoiteringConfigModal
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import { AlertTriangle, Clock, X } from 'lucide-react';
import { memo, useCallback, useEffect, useState } from 'react';

import AnimatedModal from '../common/AnimatedModal';
import Button from '../common/Button';

// ============================================================================
// Types
// ============================================================================

/**
 * Loitering configuration data from the API.
 */
export interface LoiteringConfig {
  /** Zone ID */
  zone_id: number;
  /** Zone name */
  zone_name: string;
  /** Loitering threshold in seconds */
  threshold_seconds: number;
  /** Whether alerts are enabled */
  alert_enabled: boolean;
}

/**
 * Props for the LoiteringConfigModal component.
 */
export interface LoiteringConfigModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Zone ID to configure */
  zoneId: number;
  /** Zone name for display */
  zoneName: string;
}

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = '/api/analytics-zones';

/**
 * Fetch loitering configuration for a zone.
 */
async function fetchLoiteringConfig(zoneId: number): Promise<LoiteringConfig> {
  const response = await fetch(`${API_BASE}/polygon-zones/${zoneId}/loitering-config`);
  if (!response.ok) {
    throw new Error(`Failed to fetch loitering config: ${response.statusText}`);
  }
  return response.json() as Promise<LoiteringConfig>;
}

/**
 * Update loitering configuration for a zone.
 */
async function updateLoiteringConfig(
  zoneId: number,
  config: { threshold_seconds: number; alert_enabled: boolean }
): Promise<LoiteringConfig> {
  const response = await fetch(`${API_BASE}/polygon-zones/${zoneId}/loitering-config`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    throw new Error(`Failed to update loitering config: ${response.statusText}`);
  }
  return response.json() as Promise<LoiteringConfig>;
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * LoiteringConfigModal provides configuration UI for zone loitering settings.
 *
 * Allows users to adjust the loitering threshold (in minutes) and
 * enable/disable alert notifications for when entities exceed the threshold.
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <LoiteringConfigModal
 *   isOpen={isModalOpen}
 *   onClose={() => setIsModalOpen(false)}
 *   zoneId={123}
 *   zoneName="Front Yard"
 * />
 * ```
 */
function LoiteringConfigModalComponent({
  isOpen,
  onClose,
  zoneId,
  zoneName,
}: LoiteringConfigModalProps) {
  const queryClient = useQueryClient();

  // Local form state
  const [thresholdMinutes, setThresholdMinutes] = useState(5);
  const [alertEnabled, setAlertEnabled] = useState(true);

  // Fetch current config when modal opens
  const {
    data: config,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['loitering-config', zoneId],
    queryFn: () => fetchLoiteringConfig(zoneId),
    enabled: isOpen,
  });

  // Update local state when config loads
  useEffect(() => {
    if (config) {
      setThresholdMinutes(Math.round(config.threshold_seconds / 60));
      setAlertEnabled(config.alert_enabled);
    }
  }, [config]);

  // Mutation for saving config
  const mutation = useMutation({
    mutationFn: (data: { threshold_seconds: number; alert_enabled: boolean }) =>
      updateLoiteringConfig(zoneId, data),
    onSuccess: () => {
      // Invalidate related queries
      void queryClient.invalidateQueries({ queryKey: ['loitering-config', zoneId] });
      void queryClient.invalidateQueries({ queryKey: ['dwell-time', 'statistics', zoneId] });
      onClose();
    },
  });

  // Handle save button click
  const handleSave = useCallback(() => {
    mutation.mutate({
      threshold_seconds: thresholdMinutes * 60,
      alert_enabled: alertEnabled,
    });
  }, [mutation, thresholdMinutes, alertEnabled]);

  // Handle threshold slider change
  const handleThresholdChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setThresholdMinutes(Number(e.target.value));
  }, []);

  // Handle alert toggle
  const handleAlertToggle = useCallback(() => {
    setAlertEnabled((prev) => !prev);
  }, []);

  return (
    <AnimatedModal
      isOpen={isOpen}
      onClose={onClose}
      variant="scale"
      size="sm"
      aria-labelledby="loitering-config-title"
      modalName="loitering-config"
    >
      <div className="p-6" data-testid="loitering-config-modal">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h2
            id="loitering-config-title"
            className="flex items-center gap-2 text-lg font-semibold text-white"
          >
            <Clock className="h-5 w-5 text-primary" aria-hidden="true" />
            Loitering Configuration
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white"
            aria-label="Close modal"
            data-testid="close-button"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Zone name */}
        <p className="mb-4 text-sm text-gray-400">
          Configure loitering detection for{' '}
          <span className="text-white" data-testid="zone-name">
            {zoneName}
          </span>
        </p>

        {/* Content */}
        {isLoading ? (
          <div className="flex h-32 items-center justify-center" data-testid="loading-state">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : error ? (
          <div
            className="flex h-32 items-center justify-center text-red-400"
            data-testid="error-state"
          >
            <p className="text-sm">Failed to load configuration</p>
          </div>
        ) : (
          <div className="space-y-4" data-testid="config-form">
            {/* Threshold slider */}
            <div>
              <label
                htmlFor="threshold-slider"
                className="mb-2 block text-sm font-medium text-gray-200"
              >
                Loitering Threshold
              </label>
              <div className="flex items-center gap-4">
                <input
                  id="threshold-slider"
                  type="range"
                  min={1}
                  max={60}
                  value={thresholdMinutes}
                  onChange={handleThresholdChange}
                  className="h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-gray-700 accent-primary"
                  data-testid="threshold-slider"
                />
                <span
                  className="w-16 text-right font-mono text-white"
                  data-testid="threshold-value"
                >
                  {thresholdMinutes} min
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-500">
                Alert when someone stays longer than this
              </p>
            </div>

            {/* Alert toggle */}
            <div className="flex items-center justify-between rounded-lg bg-gray-700/50 px-4 py-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-yellow-400" aria-hidden="true" />
                <span className="text-sm text-gray-200">Enable Alerts</span>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={alertEnabled}
                onClick={handleAlertToggle}
                className={clsx(
                  'relative h-6 w-11 rounded-full transition-colors',
                  alertEnabled ? 'bg-primary' : 'bg-gray-600'
                )}
                data-testid="alert-toggle"
              >
                <span
                  className={clsx(
                    'absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform',
                    alertEnabled ? 'left-5' : 'left-0.5'
                  )}
                />
              </button>
            </div>

            {/* Mutation error message */}
            {mutation.isError && (
              <p className="text-sm text-red-400" data-testid="mutation-error">
                Failed to save configuration. Please try again.
              </p>
            )}

            {/* Action buttons */}
            <div className="flex justify-end gap-3 pt-4">
              <Button variant="ghost" onClick={onClose} data-testid="cancel-button">
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleSave}
                disabled={mutation.isPending}
                data-testid="save-button"
              >
                {mutation.isPending ? 'Saving...' : 'Save'}
              </Button>
            </div>
          </div>
        )}
      </div>
    </AnimatedModal>
  );
}

/**
 * Memoized LoiteringConfigModal for performance.
 */
export const LoiteringConfigModal = memo(LoiteringConfigModalComponent);

export default LoiteringConfigModal;
