/**
 * CameraBaselinePanel - Display camera activity baseline data
 *
 * This component integrates the ActivityHeatmap with the camera baseline API,
 * showing weekly activity patterns, learning progress, and current deviation status.
 *
 * @module components/analytics/CameraBaselinePanel
 * @see NEM-3576 - Camera Baseline Activity API Integration
 */

import { clsx } from 'clsx';
import { AlertCircle, TrendingDown, TrendingUp, Activity, Calendar } from 'lucide-react';

import ActivityHeatmap from './ActivityHeatmap';
import {
  useCameraBaselineQuery,
  useCameraActivityBaselineQuery,
} from '../../hooks/useCameraBaselineQuery';

import type { DeviationInterpretation } from '../../services/api';

export interface CameraBaselinePanelProps {
  /** Camera ID to fetch baseline data for */
  cameraId: string;
  /** Camera name for display */
  cameraName: string;
}

/**
 * Format deviation interpretation for display.
 */
function formatInterpretation(interpretation: DeviationInterpretation): string {
  const labels: Record<DeviationInterpretation, string> = {
    far_below_normal: 'Far Below Normal',
    below_normal: 'Below Normal',
    normal: 'Normal',
    slightly_above_normal: 'Slightly Above Normal',
    above_normal: 'Above Normal',
    far_above_normal: 'Far Above Normal',
  };
  return labels[interpretation];
}

/**
 * Get color class for deviation interpretation.
 */
function getDeviationColor(interpretation: DeviationInterpretation): string {
  switch (interpretation) {
    case 'far_below_normal':
    case 'below_normal':
      return 'text-blue-400';
    case 'normal':
      return 'text-green-400';
    case 'slightly_above_normal':
      return 'text-yellow-400';
    case 'above_normal':
      return 'text-orange-400';
    case 'far_above_normal':
      return 'text-red-400';
    default:
      return 'text-gray-400';
  }
}

/**
 * Get icon for deviation direction.
 */
function getDeviationIcon(interpretation: DeviationInterpretation) {
  switch (interpretation) {
    case 'far_below_normal':
    case 'below_normal':
      return <TrendingDown className="h-4 w-4" />;
    case 'normal':
      return <Activity className="h-4 w-4" />;
    case 'slightly_above_normal':
    case 'above_normal':
    case 'far_above_normal':
      return <TrendingUp className="h-4 w-4" />;
    default:
      return <Activity className="h-4 w-4" />;
  }
}

/**
 * Format date for display.
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * CameraBaselinePanel displays comprehensive baseline activity data for a camera.
 *
 * Features:
 * - Activity heatmap showing weekly patterns
 * - Learning progress indicator
 * - Current deviation status with interpretation
 * - Contributing factors for anomalies
 */
export default function CameraBaselinePanel({
  cameraId,
  cameraName,
}: CameraBaselinePanelProps) {
  // Fetch baseline summary and activity data
  const {
    data: baselineData,
    isLoading: isLoadingBaseline,
    error: baselineError,
    hasBaseline,
  } = useCameraBaselineQuery(cameraId);

  const {
    entries,
    learningComplete,
    minSamplesRequired,
    isLoading: isLoadingActivity,
    error: activityError,
  } = useCameraActivityBaselineQuery(cameraId);

  const isLoading = isLoadingBaseline || isLoadingActivity;
  const error = baselineError || activityError;

  // Loading state
  if (isLoading) {
    return (
      <div
        className="flex h-64 items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F] p-4"
        data-testid="camera-baseline-panel"
      >
        <div className="flex flex-col items-center gap-2">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-600 border-t-[#76B900]" />
          <span className="text-sm text-gray-400">Loading baseline data...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className="rounded-lg border border-red-500/20 bg-red-500/10 p-4"
        data-testid="camera-baseline-panel"
      >
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <div>
            <h3 className="font-semibold text-red-500">Error loading baseline</h3>
            <p className="mt-1 text-sm text-red-400">{error.message}</p>
          </div>
        </div>
      </div>
    );
  }

  // Empty state - no baseline data
  if (!hasBaseline || entries.length === 0) {
    return (
      <div
        className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6"
        data-testid="camera-baseline-panel"
      >
        <div className="flex items-center gap-2 mb-4">
          <Activity className="h-5 w-5 text-[#76B900]" />
          <h3 className="text-lg font-semibold text-white">{cameraName}</h3>
        </div>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <Calendar className="h-12 w-12 text-gray-600 mb-4" />
          <h4 className="text-lg font-medium text-gray-300">No Baseline Data Yet</h4>
          <p className="mt-2 max-w-sm text-sm text-gray-500">
            Baseline data will be collected automatically as the camera captures activity.
            Check back after a few days of operation.
          </p>
        </div>
      </div>
    );
  }

  const deviation = baselineData?.current_deviation;

  return (
    <div
      className="space-y-4"
      data-testid="camera-baseline-panel"
    >
      {/* Header with camera name and stats */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-[#76B900]" />
          <h3 className="text-lg font-semibold text-white">{cameraName}</h3>
        </div>
        {baselineData && (
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <span>
              <span className="font-medium text-white">{baselineData.data_points}</span> data points
            </span>
            {baselineData.baseline_established && (
              <span>
                Since <span className="text-white">{formatDate(baselineData.baseline_established)}</span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Current deviation status */}
      {deviation && (
        <div
          className="rounded-lg border border-gray-800 bg-[#1A1A1A] p-4"
          data-testid="deviation-status"
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className={clsx('flex items-center gap-2', getDeviationColor(deviation.interpretation))}>
                {getDeviationIcon(deviation.interpretation)}
                <span className="font-medium">
                  {formatInterpretation(deviation.interpretation)}
                </span>
              </div>
              <span className="text-sm text-gray-500">
                Score: <span className="font-mono text-gray-300">{deviation.score.toFixed(1)}</span>
              </span>
            </div>
          </div>

          {deviation.contributing_factors.length > 0 && (
            <div className="mt-3 border-t border-gray-800 pt-3">
              <span className="text-xs uppercase tracking-wider text-gray-500">Contributing Factors</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {deviation.contributing_factors.map((factor) => (
                  <span
                    key={factor}
                    className="rounded bg-gray-800 px-2 py-1 text-xs text-gray-300"
                  >
                    {factor}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Activity heatmap */}
      <ActivityHeatmap
        entries={entries}
        learningComplete={learningComplete}
        minSamplesRequired={minSamplesRequired}
      />
    </div>
  );
}
