/**
 * ConfidenceMetricsCard - Display detection confidence metrics
 *
 * NEM-3662: Visualizes detection confidence metrics that are available from
 * the fetchDetectionStats API but were not previously displayed in the
 * native analytics view.
 */

import { Card, Title, Text, ProgressBar } from '@tremor/react';
import { AlertCircle, Gauge, Loader2 } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import { fetchDetectionStats, type DetectionStatsResponse } from '../../services/api';

interface ConfidenceMetricsCardProps {
  /** Optional camera ID to filter stats */
  cameraId?: string;
  /** Refresh interval in milliseconds (0 to disable) */
  refreshInterval?: number;
}

type ConfidenceLevel = 'high' | 'medium' | 'low';

interface ConfidenceLevelInfo {
  label: string;
  color: 'emerald' | 'amber' | 'red';
  textColor: string;
}

const CONFIDENCE_LEVELS: Record<ConfidenceLevel, ConfidenceLevelInfo> = {
  high: {
    label: 'High Confidence',
    color: 'emerald',
    textColor: 'text-emerald-400',
  },
  medium: {
    label: 'Medium Confidence',
    color: 'amber',
    textColor: 'text-amber-400',
  },
  low: {
    label: 'Low Confidence',
    color: 'red',
    textColor: 'text-red-400',
  },
};

function getConfidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= 0.85) return 'high';
  if (confidence >= 0.7) return 'medium';
  return 'low';
}

function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(num: number): string {
  return num.toLocaleString();
}

export default function ConfidenceMetricsCard({
  cameraId,
  refreshInterval = 0,
}: ConfidenceMetricsCardProps) {
  const [stats, setStats] = useState<DetectionStatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const data = await fetchDetectionStats(cameraId ? { camera_id: cameraId } : undefined);
      setStats(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch detection stats'));
    } finally {
      setIsLoading(false);
    }
  }, [cameraId]);

  useEffect(() => {
    void fetchStats();

    if (refreshInterval > 0) {
      const intervalId = setInterval(() => {
        void fetchStats();
      }, refreshInterval);

      return () => clearInterval(intervalId);
    }
  }, [fetchStats, refreshInterval]);

  if (isLoading) {
    return (
      <Card data-testid="confidence-metrics-loading">
        <Title>Confidence Metrics</Title>
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card data-testid="confidence-metrics-error">
        <Title>Confidence Metrics</Title>
        <div className="flex h-64 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load confidence metrics</Text>
        </div>
      </Card>
    );
  }

  if (!stats || stats.total_detections === 0 || stats.average_confidence === null) {
    return (
      <Card data-testid="confidence-metrics-empty">
        <Title>Confidence Metrics</Title>
        <div className="flex h-64 flex-col items-center justify-center text-gray-400">
          <Gauge className="mb-2 h-8 w-8" />
          <Text>No detection data available</Text>
          <Text className="mt-1 text-sm">
            Confidence metrics will appear as objects are detected
          </Text>
        </div>
      </Card>
    );
  }

  const confidenceLevel = getConfidenceLevel(stats.average_confidence);
  const levelInfo = CONFIDENCE_LEVELS[confidenceLevel];
  const confidencePercent = stats.average_confidence * 100;

  // Get top 3 detection classes
  const topClasses = Object.entries(stats.detections_by_class)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3);

  return (
    <Card data-testid="confidence-metrics-card">
      <div className="mb-4 flex items-center gap-3">
        <Gauge className="h-5 w-5 text-[#76B900]" />
        <Title>Confidence Metrics</Title>
      </div>

      {/* Main confidence display */}
      <div className="mb-6 rounded-lg bg-gray-800/50 p-4">
        <div className="mb-2 flex items-baseline justify-between">
          <Text className="text-sm text-gray-400">Average Confidence</Text>
          <span className={`text-sm font-medium ${levelInfo.textColor}`} data-testid="confidence-level-label">
            {levelInfo.label}
          </span>
        </div>
        <p className="mb-3 text-4xl font-bold text-white" data-testid="confidence-value">
          {formatPercentage(stats.average_confidence)}
        </p>
        <ProgressBar
          value={confidencePercent}
          color={levelInfo.color}
          className="h-2"
          data-testid="confidence-progress-bar"
        />
      </div>

      {/* Detection stats */}
      <div className="mb-4">
        <div className="flex items-center justify-between">
          <Text className="text-sm text-gray-400">Total Detections</Text>
          <p className="text-lg font-semibold text-white" data-testid="confidence-total-detections">
            {formatNumber(stats.total_detections)}
          </p>
        </div>
      </div>

      {/* Top detection classes */}
      {topClasses.length > 0 && (
        <div>
          <Text className="mb-2 text-sm text-gray-400">Top Detection Classes</Text>
          <div className="space-y-2">
            {topClasses.map(([className, count]) => {
              const percentage = (count / stats.total_detections) * 100;
              return (
                <div key={className} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full bg-[#76B900]" />
                    <Text className="text-sm capitalize text-gray-300">{className}</Text>
                  </div>
                  <div className="flex items-center gap-2">
                    <Text className="text-sm text-gray-400">{formatNumber(count)}</Text>
                    <Text className="text-xs text-gray-500">({percentage.toFixed(1)}%)</Text>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}
