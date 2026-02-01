/**
 * AnomalyInvestigationModal - Modal for investigating zone anomalies (NEM-4714)
 *
 * Displays detailed context for a zone anomaly including:
 * - Anomaly type and severity with appropriate styling
 * - Zone name and timestamp
 * - Expected vs Actual value comparison
 * - AI-generated explanation
 * - List of associated detections with thumbnails
 * - Navigation to detection timeline
 * - Acknowledge functionality
 *
 * Part of Phase 3B: Anomaly Investigation Features.
 *
 * @module components/zones/AnomalyInvestigationModal
 */

import { clsx } from 'clsx';
import { format } from 'date-fns';
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  Check,
  Clock,
  Image as ImageIcon,
  Info,
  MapPin,
  Search,
  X,
} from 'lucide-react';
import { memo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAnomalyContext } from '../../hooks/useAnomalyContext';
import AnimatedModal from '../common/AnimatedModal';
import Button from '../common/Button';

import type { AssociatedDetection } from '../../hooks/useAnomalyContext';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the AnomalyInvestigationModal component.
 */
export interface AnomalyInvestigationModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Anomaly ID to investigate */
  anomalyId: string | null;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Severity badge with appropriate colors and icon.
 */
function SeverityBadge({ severity }: { severity: string }) {
  const config: Record<string, { color: string; bg: string; icon: typeof Info }> = {
    info: { color: 'text-blue-400', bg: 'bg-blue-500/20', icon: Info },
    warning: { color: 'text-yellow-400', bg: 'bg-yellow-500/20', icon: AlertTriangle },
    critical: { color: 'text-red-400', bg: 'bg-red-500/20', icon: AlertOctagon },
  };

  const { color, bg, icon: Icon } = config[severity] || config.info;

  return (
    <span
      className={clsx('inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium', bg, color)}
      data-testid="severity-badge"
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {severity.charAt(0).toUpperCase() + severity.slice(1)}
    </span>
  );
}

/**
 * Visual comparison of expected vs actual values.
 */
function ValueComparison({
  expected,
  actual,
}: {
  expected: number | null;
  actual: number | null;
}) {
  if (expected === null && actual === null) {
    return null;
  }

  // Calculate the difference for visual emphasis
  const difference = expected !== null && actual !== null ? actual - expected : null;
  const isHigher = difference !== null && difference > 0;

  return (
    <div
      className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
      data-testid="value-comparison"
    >
      <h4 className="mb-3 text-sm font-medium text-gray-300">Value Comparison</h4>
      <div className="flex items-center justify-around gap-4">
        {/* Expected value */}
        <div className="text-center">
          <span className="block text-xs text-gray-500">Expected</span>
          <span className="mt-1 block text-2xl font-semibold text-gray-300" data-testid="expected-value">
            {expected !== null ? expected.toFixed(1) : '-'}
          </span>
        </div>

        {/* Arrow indicator */}
        <div className="flex flex-col items-center">
          <ArrowRight
            className={clsx(
              'h-6 w-6',
              isHigher ? 'text-red-400' : 'text-green-400'
            )}
            aria-hidden="true"
          />
          {difference !== null && (
            <span
              className={clsx(
                'mt-1 text-xs font-medium',
                isHigher ? 'text-red-400' : 'text-green-400'
              )}
              data-testid="difference-value"
            >
              {isHigher ? '+' : ''}{difference.toFixed(1)}
            </span>
          )}
        </div>

        {/* Actual value */}
        <div className="text-center">
          <span className="block text-xs text-gray-500">Actual</span>
          <span
            className={clsx(
              'mt-1 block text-2xl font-semibold',
              isHigher ? 'text-red-400' : 'text-green-400'
            )}
            data-testid="actual-value"
          >
            {actual !== null ? actual.toFixed(1) : '-'}
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * Individual detection card with thumbnail and details.
 */
function DetectionCard({
  detection,
  onViewInTimeline,
}: {
  detection: AssociatedDetection;
  onViewInTimeline: (detectionId: string) => void;
}) {
  const handleViewClick = useCallback(() => {
    onViewInTimeline(detection.id);
  }, [detection.id, onViewInTimeline]);

  return (
    <div
      className="flex items-start gap-3 rounded-lg border border-gray-700 bg-gray-800/50 p-3"
      data-testid="detection-card"
    >
      {/* Thumbnail */}
      <div className="h-16 w-16 shrink-0 overflow-hidden rounded bg-gray-700">
        {detection.thumbnail_url ? (
          <img
            src={detection.thumbnail_url}
            alt={`Detection of ${detection.object_class}`}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ImageIcon className="h-6 w-6 text-gray-500" aria-hidden="true" />
          </div>
        )}
      </div>

      {/* Details */}
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between">
          <div>
            <span className="font-medium capitalize text-white">
              {detection.object_class}
            </span>
            <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
              <span>Confidence: {(detection.confidence * 100).toFixed(0)}%</span>
              {detection.risk_score !== null && (
                <span
                  className={clsx(
                    'rounded px-1.5 py-0.5',
                    detection.risk_score >= 70
                      ? 'bg-red-500/20 text-red-400'
                      : detection.risk_score >= 40
                        ? 'bg-yellow-500/20 text-yellow-400'
                        : 'bg-green-500/20 text-green-400'
                  )}
                >
                  Risk: {detection.risk_score}
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={handleViewClick}
            className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white"
            title="View in Timeline"
            aria-label="View detection in timeline"
            data-testid="view-in-timeline-button"
          >
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
        <span className="mt-1 block text-xs text-gray-500">
          {format(new Date(detection.timestamp), 'PPp')}
        </span>
      </div>
    </div>
  );
}

/**
 * Loading skeleton for the modal content.
 */
function LoadingState() {
  return (
    <div className="space-y-4 p-6" data-testid="investigation-loading">
      <div className="h-8 w-3/4 animate-pulse rounded bg-gray-700" />
      <div className="h-4 w-1/2 animate-pulse rounded bg-gray-700" />
      <div className="h-24 animate-pulse rounded bg-gray-700" />
      <div className="h-24 animate-pulse rounded bg-gray-700" />
    </div>
  );
}

/**
 * Error state for failed data fetch.
 */
function ErrorState({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div
      className="flex flex-col items-center justify-center p-8 text-center"
      data-testid="investigation-error"
    >
      <AlertTriangle className="h-8 w-8 text-red-400" aria-hidden="true" />
      <h3 className="mt-3 font-medium text-red-400">Failed to load anomaly details</h3>
      <p className="mt-1 text-sm text-gray-400">{error.message}</p>
      <Button
        variant="outline-primary"
        size="sm"
        onClick={onRetry}
        className="mt-4"
      >
        Try Again
      </Button>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * AnomalyInvestigationModal displays detailed context for investigating an anomaly.
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <AnomalyInvestigationModal
 *   isOpen={isModalOpen}
 *   onClose={() => setIsModalOpen(false)}
 *   anomalyId={selectedAnomalyId}
 * />
 * ```
 */
function AnomalyInvestigationModalComponent({
  isOpen,
  onClose,
  anomalyId,
}: AnomalyInvestigationModalProps) {
  const navigate = useNavigate();

  // Fetch anomaly context
  const {
    data: context,
    isLoading,
    error,
    isError,
    refetch,
    acknowledgeAnomaly,
    isAcknowledging,
  } = useAnomalyContext(anomalyId, { enabled: isOpen && !!anomalyId });

  // Handle view in timeline
  const handleViewInTimeline = useCallback(
    (detectionId: string) => {
      onClose();
      void navigate(`/events?detection=${detectionId}`);
    },
    [navigate, onClose]
  );

  // Handle acknowledge
  const handleAcknowledge = useCallback(() => {
    acknowledgeAnomaly();
  }, [acknowledgeAnomaly]);

  // Handle retry
  const handleRetry = useCallback(() => {
    void refetch();
  }, [refetch]);

  return (
    <AnimatedModal
      isOpen={isOpen}
      onClose={onClose}
      variant="scale"
      size="lg"
      aria-labelledby="investigation-modal-title"
      modalName="anomaly-investigation"
    >
      <div data-testid="anomaly-investigation-modal">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-gray-700 p-6">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/20 p-2">
              <Search className="h-5 w-5 text-primary" aria-hidden="true" />
            </div>
            <div>
              <h2
                id="investigation-modal-title"
                className="text-lg font-semibold text-white"
              >
                Anomaly Investigation
              </h2>
              {context && (
                <div className="mt-1 flex items-center gap-2">
                  <SeverityBadge severity={context.severity} />
                  <span className="text-sm capitalize text-gray-400">
                    {context.anomaly_type.replace(/_/g, ' ')}
                  </span>
                </div>
              )}
            </div>
          </div>
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

        {/* Content */}
        {isLoading ? (
          <LoadingState />
        ) : isError && error ? (
          <ErrorState error={error} onRetry={handleRetry} />
        ) : context ? (
          <div className="max-h-[60vh] overflow-y-auto p-6">
            {/* Zone and timestamp info */}
            <div className="mb-4 flex flex-wrap items-center gap-4 text-sm">
              <div className="flex items-center gap-1.5 text-gray-400">
                <MapPin className="h-4 w-4" aria-hidden="true" />
                <span data-testid="zone-name">{context.zone_name}</span>
              </div>
              <div className="flex items-center gap-1.5 text-gray-400">
                <Clock className="h-4 w-4" aria-hidden="true" />
                <span data-testid="timestamp">
                  {format(new Date(context.timestamp), 'PPp')}
                </span>
              </div>
            </div>

            {/* Value comparison */}
            <ValueComparison
              expected={context.expected_value}
              actual={context.actual_value}
            />

            {/* Explanation */}
            {context.explanation && (
              <div className="mt-4 rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                <h4 className="mb-2 text-sm font-medium text-gray-300">
                  AI Analysis
                </h4>
                <p className="text-sm text-gray-400" data-testid="explanation">
                  {context.explanation}
                </p>
              </div>
            )}

            {/* Associated detections */}
            {context.detections.length > 0 && (
              <div className="mt-4">
                <h4 className="mb-3 text-sm font-medium text-gray-300">
                  Associated Detections ({context.detections.length})
                </h4>
                <div className="space-y-2" data-testid="detections-list">
                  {context.detections.map((detection) => (
                    <DetectionCard
                      key={detection.id}
                      detection={detection}
                      onViewInTimeline={handleViewInTimeline}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* No detections message */}
            {context.detections.length === 0 && (
              <div className="mt-4 rounded-lg border border-gray-700 bg-gray-800/50 p-4 text-center">
                <p className="text-sm text-gray-400">
                  No associated detections found for this anomaly.
                </p>
              </div>
            )}
          </div>
        ) : null}

        {/* Footer */}
        {context && (
          <div className="flex items-center justify-between border-t border-gray-700 p-4">
            <div>
              {context.acknowledged && (
                <span
                  className="text-sm text-green-400"
                  data-testid="acknowledged-status"
                >
                  Acknowledged
                  {context.acknowledged_at && (
                    <span className="text-gray-500">
                      {' '}
                      on {format(new Date(context.acknowledged_at), 'PP')}
                    </span>
                  )}
                </span>
              )}
            </div>
            <div className="flex gap-3">
              <Button variant="ghost" onClick={onClose} data-testid="close-action-button">
                Close
              </Button>
              {!context.acknowledged && (
                <Button
                  variant="primary"
                  onClick={handleAcknowledge}
                  disabled={isAcknowledging}
                  leftIcon={<Check className="h-4 w-4" />}
                  data-testid="acknowledge-button"
                >
                  {isAcknowledging ? 'Acknowledging...' : 'Acknowledge'}
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </AnimatedModal>
  );
}

/**
 * Memoized AnomalyInvestigationModal for performance.
 */
export const AnomalyInvestigationModal = memo(AnomalyInvestigationModalComponent);

export default AnomalyInvestigationModal;
