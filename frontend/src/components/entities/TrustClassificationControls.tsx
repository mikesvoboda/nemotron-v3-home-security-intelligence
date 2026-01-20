import { clsx } from 'clsx';
import {
  AlertCircle,
  Check,
  HelpCircle,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  X,
} from 'lucide-react';
import { memo, useState } from 'react';

import type { TrustStatus } from '../../services/api';

// Re-export TrustStatus for consumers who import from this module
export type { TrustStatus };

export interface TrustClassificationControlsProps {
  /** Current trust status of the entity */
  currentStatus: TrustStatus;
  /** Entity ID for API calls */
  entityId: string;
  /** Callback when trust status is successfully updated */
  onStatusChange: (entityId: string, newStatus: TrustStatus) => Promise<void>;
  /** Optional callback when status change fails */
  onError?: (error: Error) => void;
  /** Whether the component is in a loading state */
  isLoading?: boolean;
  /** Whether to show the status badge only (no action buttons) */
  readOnly?: boolean;
  /** Size variant for the component */
  size?: 'sm' | 'md' | 'lg';
  /** Additional CSS classes */
  className?: string;
}

/**
 * Trust status configuration for styling and labels
 */
const trustStatusConfig: Record<
  TrustStatus,
  {
    label: string;
    description: string;
    icon: typeof ShieldCheck;
    badgeClasses: string;
    buttonClasses: string;
  }
> = {
  trusted: {
    label: 'Trusted',
    description: 'This entity is a known trusted individual',
    icon: ShieldCheck,
    badgeClasses: 'bg-green-500/10 text-green-400 border-green-500/30',
    buttonClasses: 'bg-green-600/20 text-green-400 hover:bg-green-600/30 border-green-500/30',
  },
  untrusted: {
    label: 'Untrusted',
    description: 'This entity is flagged as suspicious',
    icon: ShieldAlert,
    badgeClasses: 'bg-red-500/10 text-red-400 border-red-500/30',
    buttonClasses: 'bg-red-600/20 text-red-400 hover:bg-red-600/30 border-red-500/30',
  },
  unclassified: {
    label: 'Unknown',
    description: 'This entity has not been classified',
    icon: ShieldQuestion,
    badgeClasses: 'bg-gray-500/10 text-gray-400 border-gray-500/30',
    buttonClasses: 'bg-gray-600/20 text-gray-400 hover:bg-gray-600/30 border-gray-500/30',
  },
};

/**
 * Get size classes for the component
 */
const getSizeClasses = (size: 'sm' | 'md' | 'lg') => {
  switch (size) {
    case 'sm':
      return {
        badge: 'text-xs px-2 py-0.5',
        button: 'text-xs px-2 py-1',
        icon: 'h-3 w-3',
        buttonIcon: 'h-3 w-3',
      };
    case 'lg':
      return {
        badge: 'text-base px-4 py-2',
        button: 'text-sm px-4 py-2',
        icon: 'h-5 w-5',
        buttonIcon: 'h-4 w-4',
      };
    default:
      return {
        badge: 'text-sm px-3 py-1',
        button: 'text-sm px-3 py-1.5',
        icon: 'h-4 w-4',
        buttonIcon: 'h-3.5 w-3.5',
      };
  }
};

/**
 * TrustClassificationControls component displays current trust status
 * and provides controls for changing entity trust classification.
 *
 * Features:
 * - Visual status badge with appropriate coloring (green=trusted, red=untrusted, gray=unknown)
 * - Action buttons to change trust status
 * - Confirmation dialog before changing status
 * - Loading states during API calls
 * - Error handling with optional callback
 */
const TrustClassificationControls = memo(function TrustClassificationControls({
  currentStatus,
  entityId,
  onStatusChange,
  onError,
  isLoading = false,
  readOnly = false,
  size = 'md',
  className,
}: TrustClassificationControlsProps) {
  // State for confirmation dialog
  const [pendingStatus, setPendingStatus] = useState<TrustStatus | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const config = trustStatusConfig[currentStatus];
  const sizeClasses = getSizeClasses(size);
  const Icon = config.icon;

  // Handle status change with confirmation
  const handleStatusClick = (newStatus: TrustStatus) => {
    if (newStatus === currentStatus) return;
    setPendingStatus(newStatus);
    setError(null);
  };

  // Confirm and execute status change
  const handleConfirm = async () => {
    if (!pendingStatus) return;

    setIsUpdating(true);
    setError(null);

    try {
      await onStatusChange(entityId, pendingStatus);
      setPendingStatus(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update trust status';
      setError(errorMessage);
      if (onError && err instanceof Error) {
        onError(err);
      }
    } finally {
      setIsUpdating(false);
    }
  };

  // Cancel confirmation
  const handleCancel = () => {
    setPendingStatus(null);
    setError(null);
  };

  const isDisabled = isLoading || isUpdating;

  return (
    <div
      className={clsx('flex flex-col gap-3', className)}
      data-testid="trust-classification-controls"
    >
      {/* Current Status Badge */}
      <div className="flex items-center gap-2">
        <span
          className={clsx(
            'inline-flex items-center gap-1.5 rounded-full border font-medium',
            sizeClasses.badge,
            config.badgeClasses
          )}
          role="status"
          aria-label={`Trust status: ${config.label}`}
          data-testid="trust-status-badge"
        >
          <Icon className={sizeClasses.icon} aria-hidden="true" />
          {config.label}
        </span>
        {!readOnly && (
          <button
            type="button"
            className="text-gray-500 transition-colors hover:text-gray-300"
            aria-label="Trust status help"
            title={config.description}
          >
            <HelpCircle className={sizeClasses.icon} />
          </button>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div
          className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
          role="alert"
          data-testid="trust-error-message"
        >
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Confirmation Dialog */}
      {pendingStatus && (
        <div
          className="flex items-center gap-2 rounded-lg border border-gray-700 bg-[#1F1F1F] px-3 py-2"
          data-testid="trust-confirmation-dialog"
        >
          <span className="text-sm text-gray-300">
            Change status to{' '}
            <span
              className={clsx(
                'font-semibold',
                pendingStatus === 'trusted' && 'text-green-400',
                pendingStatus === 'untrusted' && 'text-red-400',
                pendingStatus === 'unclassified' && 'text-gray-400'
              )}
            >
              {trustStatusConfig[pendingStatus].label}
            </span>
            ?
          </span>
          <button
            type="button"
            onClick={() => void handleConfirm()}
            disabled={isUpdating}
            className={clsx(
              'flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors',
              pendingStatus === 'trusted' && 'bg-green-600 text-white hover:bg-green-700',
              pendingStatus === 'untrusted' && 'bg-red-600 text-white hover:bg-red-700',
              pendingStatus === 'unclassified' && 'bg-gray-600 text-white hover:bg-gray-700',
              isUpdating && 'cursor-not-allowed opacity-50'
            )}
            aria-label="Confirm status change"
            data-testid="trust-confirm-button"
          >
            <Check className="h-3 w-3" />
            {isUpdating ? 'Updating...' : 'Confirm'}
          </button>
          <button
            type="button"
            onClick={handleCancel}
            disabled={isUpdating}
            className="flex items-center gap-1 rounded-md bg-gray-700 px-2 py-1 text-xs font-medium text-gray-300 transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Cancel status change"
            data-testid="trust-cancel-button"
          >
            <X className="h-3 w-3" />
            Cancel
          </button>
        </div>
      )}

      {/* Action Buttons (when not in confirmation mode and not read-only) */}
      {!readOnly && !pendingStatus && (
        <div className="flex flex-wrap gap-2" data-testid="trust-action-buttons">
          {(['trusted', 'untrusted', 'unclassified'] as TrustStatus[]).map((status) => {
            const statusConfig = trustStatusConfig[status];
            const StatusIcon = statusConfig.icon;
            const isCurrentStatus = status === currentStatus;

            return (
              <button
                key={status}
                type="button"
                onClick={() => handleStatusClick(status)}
                disabled={isDisabled || isCurrentStatus}
                className={clsx(
                  'flex items-center gap-1.5 rounded-md border font-medium transition-colors',
                  sizeClasses.button,
                  isCurrentStatus
                    ? 'cursor-default border-[#76B900] bg-[#76B900]/10 text-[#76B900]'
                    : statusConfig.buttonClasses,
                  isDisabled && !isCurrentStatus && 'cursor-not-allowed opacity-50'
                )}
                aria-label={`Set trust status to ${statusConfig.label}`}
                aria-pressed={isCurrentStatus}
                data-testid={`trust-button-${status}`}
              >
                <StatusIcon className={sizeClasses.buttonIcon} aria-hidden="true" />
                {statusConfig.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Loading Indicator */}
      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-400" data-testid="trust-loading">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-600 border-t-[#76B900]" />
          <span>Loading trust status...</span>
        </div>
      )}
    </div>
  );
});

export default TrustClassificationControls;
