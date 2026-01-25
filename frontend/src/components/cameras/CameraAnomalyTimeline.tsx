/**
 * CameraAnomalyTimeline - Display anomaly events for a camera (NEM-3577)
 *
 * Shows a timeline of anomaly events detected against the camera's established
 * baseline activity patterns. Each anomaly displays:
 * - Timestamp and detection class
 * - Anomaly score with severity indicator
 * - Expected vs observed frequency comparison
 * - Human-readable explanation
 *
 * Severity colors based on anomaly score:
 * - Red (critical): >= 0.9 - Highly anomalous
 * - Orange (high): 0.75-0.89 - Significant deviation
 * - Yellow (medium): 0.5-0.74 - Moderate anomaly
 * - Blue (low): < 0.5 - Minor deviation
 */

import { Card, Title, Text } from '@tremor/react';
import { AlertTriangle, Clock, TrendingUp, Loader2, AlertCircle } from 'lucide-react';
import { useMemo } from 'react';

import {
  useCameraAnomaliesQuery,
  type UseCameraAnomaliesQueryOptions,
} from '../../hooks/useCameraAnomaliesQuery';

import type { CameraAnomalyEvent } from '../../services/api';

// ============================================================================
// Types
// ============================================================================

interface CameraAnomalyTimelineProps {
  /** Camera ID to fetch anomalies for */
  cameraId: string;
  /** Camera name for display */
  cameraName?: string;
  /** Number of days to look back (default: 7) */
  days?: number;
  /** Whether to show the card header (default: true) */
  showHeader?: boolean;
  /** Optional className for additional styling */
  className?: string;
}

/**
 * Severity level based on anomaly score.
 */
type AnomalySeverity = 'critical' | 'high' | 'medium' | 'low';

// ============================================================================
// Constants
// ============================================================================

/**
 * Color mapping based on anomaly severity.
 */
const SEVERITY_COLORS: Record<AnomalySeverity, { bg: string; text: string; border: string }> = {
  critical: {
    bg: 'bg-red-500/10',
    text: 'text-red-400',
    border: 'border-red-500/30',
  },
  high: {
    bg: 'bg-orange-500/10',
    text: 'text-orange-400',
    border: 'border-orange-500/30',
  },
  medium: {
    bg: 'bg-yellow-500/10',
    text: 'text-yellow-400',
    border: 'border-yellow-500/30',
  },
  low: {
    bg: 'bg-blue-500/10',
    text: 'text-blue-400',
    border: 'border-blue-500/30',
  },
};

const SEVERITY_LABELS: Record<AnomalySeverity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Determine the severity level based on anomaly score.
 *
 * @param score - Anomaly score (0.0-1.0)
 * @returns Severity level
 */
function getAnomalySeverity(score: number): AnomalySeverity {
  if (score >= 0.9) return 'critical';
  if (score >= 0.75) return 'high';
  if (score >= 0.5) return 'medium';
  return 'low';
}

/**
 * Format a timestamp for display.
 *
 * @param timestamp - ISO 8601 timestamp string
 * @returns Formatted date/time string
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Format frequency value for display.
 *
 * @param frequency - Frequency value
 * @returns Formatted string
 */
function formatFrequency(frequency: number): string {
  return frequency.toFixed(1);
}

// ============================================================================
// Sub-Components
// ============================================================================

interface AnomalyItemProps {
  anomaly: CameraAnomalyEvent;
  index: number;
}

/**
 * Individual anomaly item in the timeline.
 */
function AnomalyItem({ anomaly, index }: AnomalyItemProps) {
  const severity = getAnomalySeverity(anomaly.anomaly_score);
  const colors = SEVERITY_COLORS[severity];

  return (
    <div
      data-testid={`anomaly-item-${index}`}
      data-anomaly-severity={severity}
      className={`rounded-lg border p-4 transition-colors hover:brightness-110 ${colors.bg} ${colors.border}`}
    >
      {/* Header: timestamp and severity badge */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Clock className="h-4 w-4" />
          <span data-testid="anomaly-timestamp">{formatTimestamp(anomaly.timestamp)}</span>
        </div>
        <span
          data-testid="anomaly-severity-badge"
          className={`rounded px-2 py-0.5 text-xs font-medium ${colors.bg} ${colors.text}`}
        >
          {SEVERITY_LABELS[severity]} ({(anomaly.anomaly_score * 100).toFixed(0)}%)
        </span>
      </div>

      {/* Detection class */}
      <div className="mb-2 flex items-center gap-2">
        <AlertTriangle className={`h-4 w-4 ${colors.text}`} />
        <span data-testid="anomaly-class" className="font-medium capitalize text-white">
          {anomaly.detection_class}
        </span>
      </div>

      {/* Reason */}
      <p data-testid="anomaly-reason" className="mb-3 text-sm text-gray-300">
        {anomaly.reason}
      </p>

      {/* Frequency comparison */}
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <div className="flex items-center gap-1">
          <TrendingUp className="h-3 w-3" />
          <span>Expected: {formatFrequency(anomaly.expected_frequency)}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className={colors.text}>Observed: {formatFrequency(anomaly.observed_frequency)}</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * CameraAnomalyTimeline displays a list of anomaly events for a camera.
 *
 * Fetches anomaly data using the useCameraAnomaliesQuery hook and displays
 * each anomaly with severity indicators, timestamps, and explanations.
 *
 * @param props - Component props
 * @returns React element
 */
export default function CameraAnomalyTimeline({
  cameraId,
  cameraName,
  days = 7,
  showHeader = true,
  className = '',
}: CameraAnomalyTimelineProps) {
  const queryOptions: UseCameraAnomaliesQueryOptions = useMemo(
    () => ({ days }),
    [days]
  );

  const { anomalies, isLoading, error, count, periodDays } = useCameraAnomaliesQuery(
    cameraId,
    queryOptions
  );

  // Sort anomalies by timestamp (most recent first)
  const sortedAnomalies = useMemo(() => {
    return [...anomalies].sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }, [anomalies]);

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="camera-anomaly-timeline-loading" className={className}>
        {showHeader && <Title>Baseline Anomalies</Title>}
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card data-testid="camera-anomaly-timeline-error" className={className}>
        {showHeader && <Title>Baseline Anomalies</Title>}
        <div className="flex h-48 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load anomaly data</Text>
          <Text className="text-xs text-gray-500">{error.message}</Text>
        </div>
      </Card>
    );
  }

  // Empty state
  if (anomalies.length === 0) {
    return (
      <Card data-testid="camera-anomaly-timeline-empty" className={className}>
        {showHeader && (
          <div className="mb-4 flex items-center justify-between">
            <Title>Baseline Anomalies</Title>
            <Text className="text-gray-400">Last {periodDays} days</Text>
          </div>
        )}
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>No anomalies detected</Text>
          <Text className="text-xs">
            {cameraName ? `${cameraName} is operating normally` : 'Camera operating normally'}
          </Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="camera-anomaly-timeline" className={className}>
      {showHeader && (
        <div className="mb-4 flex items-center justify-between">
          <div>
            <Title>Baseline Anomalies</Title>
            {cameraName && <Text className="text-gray-400">{cameraName}</Text>}
          </div>
          <div className="text-right">
            <Text className="font-medium text-white">{count} anomalies</Text>
            <Text className="text-xs text-gray-400">Last {periodDays} days</Text>
          </div>
        </div>
      )}

      {/* Anomaly list */}
      <div className="space-y-3" data-testid="anomaly-list">
        {sortedAnomalies.map((anomaly, index) => (
          <AnomalyItem key={`${anomaly.timestamp}-${index}`} anomaly={anomaly} index={index} />
        ))}
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 border-t border-gray-800 pt-4 text-xs text-gray-400">
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-red-500" />
          <span>Critical (90%+)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-orange-500" />
          <span>High (75-89%)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-yellow-500" />
          <span>Medium (50-74%)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-blue-500" />
          <span>Low (&lt;50%)</span>
        </div>
      </div>
    </Card>
  );
}
