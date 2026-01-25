/**
 * ConflictResolutionModal - Modal for handling optimistic locking conflicts
 *
 * Displays when a concurrent modification conflict (HTTP 409) occurs,
 * giving users options to retry, cancel, or refresh the data.
 *
 * @see NEM-3626
 */

import { AlertTriangle, RefreshCw, X } from 'lucide-react';
import { memo } from 'react';

import AnimatedModal from './AnimatedModal';
import Button from './Button';

// ============================================================================
// Types
// ============================================================================

/**
 * Resource types that can have conflicts
 */
export type ConflictResourceType = 'alert' | 'event' | 'camera' | 'rule' | 'settings';

/**
 * Actions that can trigger conflicts
 */
export type ConflictAction = 'acknowledge' | 'dismiss' | 'update' | 'delete' | 'create';

/**
 * Props for the ConflictResolutionModal component
 */
export interface ConflictResolutionModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close (cancel action) */
  onClose: () => void;
  /** Callback to retry the operation */
  onRetry: () => void;
  /** Optional callback to refresh data before retrying */
  onRefresh?: () => void;
  /** Error message to display */
  errorMessage: string;
  /** Type of resource that has the conflict */
  resourceType: ConflictResourceType;
  /** The action that was being attempted */
  action: ConflictAction;
  /** Whether a retry operation is in progress */
  isLoading?: boolean;
  /** Number of retries already attempted */
  retryCount?: number;
  /** Maximum allowed retries */
  maxRetries?: number;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get human-readable action text
 */
function getActionText(action: ConflictAction): string {
  switch (action) {
    case 'acknowledge':
      return 'acknowledge';
    case 'dismiss':
      return 'dismiss';
    case 'update':
      return 'update';
    case 'delete':
      return 'delete';
    case 'create':
      return 'create';
    default:
      return 'modify';
  }
}

/**
 * Get human-readable resource text
 */
function getResourceText(resourceType: ConflictResourceType): string {
  switch (resourceType) {
    case 'alert':
      return 'alert';
    case 'event':
      return 'event';
    case 'camera':
      return 'camera';
    case 'rule':
      return 'rule';
    case 'settings':
      return 'settings';
    default:
      return 'resource';
  }
}

// ============================================================================
// Component
// ============================================================================

/**
 * Modal for resolving optimistic locking conflicts.
 *
 * Shows when a user's action fails due to concurrent modification,
 * providing options to retry (with latest data) or cancel.
 *
 * @example
 * ```tsx
 * <ConflictResolutionModal
 *   isOpen={hasConflict}
 *   onClose={clearConflict}
 *   onRetry={handleRetry}
 *   onRefresh={refetchAlert}
 *   errorMessage={conflictError?.message}
 *   resourceType="alert"
 *   action="acknowledge"
 *   isLoading={isRetrying}
 *   retryCount={retryCount}
 *   maxRetries={3}
 * />
 * ```
 */
const ConflictResolutionModal = memo(function ConflictResolutionModal({
  isOpen,
  onClose,
  onRetry,
  onRefresh,
  errorMessage,
  resourceType,
  action,
  isLoading = false,
  retryCount = 0,
  maxRetries = 3,
}: ConflictResolutionModalProps) {
  const actionText = getActionText(action);
  const resourceText = getResourceText(resourceType);
  const retriesRemaining = maxRetries - retryCount;

  return (
    <AnimatedModal
      isOpen={isOpen}
      onClose={onClose}
      variant="scale"
      size="sm"
      closeOnBackdropClick={!isLoading}
      closeOnEscape={!isLoading}
      aria-labelledby="conflict-modal-title"
      aria-describedby="conflict-modal-description"
      modalName="conflict-resolution"
    >
      <div className="p-6">
        {/* Header with warning icon */}
        <div className="flex items-start gap-4">
          <div
            className="flex-shrink-0 rounded-full bg-amber-500/20 p-3"
            data-testid="conflict-icon"
          >
            <AlertTriangle className="h-6 w-6 text-amber-500" aria-hidden="true" />
          </div>
          <div className="flex-1">
            <h2
              id="conflict-modal-title"
              className="text-lg font-semibold text-white"
            >
              Update Conflict
            </h2>
            <p
              id="conflict-modal-description"
              className="mt-1 text-sm text-gray-400"
            >
              The {resourceText} was modified while you were trying to {actionText} it.
            </p>
          </div>
        </div>

        {/* Error message */}
        <div className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/10 p-3">
          <p className="text-sm text-amber-200">
            {errorMessage}
          </p>
        </div>

        {/* Retry count info */}
        {retryCount > 0 && (
          <div className="mt-3">
            <p className="text-xs text-gray-500">
              {retriesRemaining > 0 ? (
                <>
                  Retry attempt {retryCount} of {maxRetries}.{' '}
                  {retriesRemaining === 1 ? (
                    <span className="text-amber-500">This is your final attempt.</span>
                  ) : (
                    <span>{retriesRemaining} remaining.</span>
                  )}
                </>
              ) : (
                <span className="text-red-400">Maximum retries reached.</span>
              )}
            </p>
          </div>
        )}

        {/* Action buttons */}
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          {/* Cancel button */}
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={isLoading}
            className="w-full sm:w-auto"
          >
            <X className="mr-2 h-4 w-4" />
            Cancel
          </Button>

          {/* Refresh button (optional) */}
          {onRefresh && (
            <Button
              variant="secondary"
              onClick={onRefresh}
              disabled={isLoading}
              className="w-full sm:w-auto"
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          )}

          {/* Retry button */}
          <Button
            variant="primary"
            onClick={onRetry}
            disabled={isLoading || retriesRemaining <= 0}
            className="w-full sm:w-auto"
          >
            {isLoading ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Retrying...
              </>
            ) : (
              <>
                <RefreshCw className="mr-2 h-4 w-4" />
                Retry
              </>
            )}
          </Button>
        </div>

        {/* Helper text */}
        <p className="mt-4 text-center text-xs text-gray-500">
          Click Retry to attempt the {actionText} action again with the latest data.
        </p>
      </div>
    </AnimatedModal>
  );
});

export default ConflictResolutionModal;
